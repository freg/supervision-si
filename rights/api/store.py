"""
rights-api -- livraison #283, demandé explicitement : "une gestion de
droit incluant la visibilité en listing doit être mise en place" +
"un nouveau groupe admin_hub donnera les tous les droits à ses
membres et notamment celui de gérer les droits" + "la gestion des
droits devient une tuile et impacte toutes les api".

Service CENTRAL d'autorisation -- ne stocke JAMAIS de secret, jamais
le contenu d'un fichier, uniquement des RÉFÉRENCES (type de
ressource + identifiant) et des OCTROIS (quel groupe Keycloak peut
faire quelle action sur quelle ressource).

`admin_hub` (groupe Keycloak, voir keycloak/realm-template.json) a
TOUS les droits par construction -- jamais stocké comme une ligne de
permission parmi d'autres (fragile, oubliable), un COURT-CIRCUIT
explicite dans has_permission() : si ce groupe est présent dans les
groupes de l'appelant, la réponse est TOUJOURS "oui", pour TOUTE
ressource et TOUTE action, y compris gérer les droits eux-mêmes
(l'un contient l'autre par nature -- gérer les droits est déjà une
action sur la ressource "rights", inutile de le déclarer séparément).

Portée de CETTE livraison (#283) : la fondation (schéma, vérification
de droit, gestion des octrois) + le PREMIER consommateur concret
(inventaire de fichiers, voir file_inventory.py) -- brancher
progressivement les ~40 autres API du projet sur ce service reste un
chantier À POURSUIVRE, jamais fait d'un coup (risque réel de
régression si bâclé sur autant de services en une seule fois, jamais
testé un par un dans ce cas).
"""
import sqlite3
import time

# Actions reconnues -- volontairement UNE liste OUVERTE (pas un enum
# strict en base), chaque futur consommateur (une API existante qui
# se branche sur ce service) peut définir ses propres actions
# (ex. "delete", "export"...) sans migration de schéma. "view" et
# "manage" sont les deux universelles utilisées par ce service
# lui-même (listing = view, octroyer/révoquer = manage).

SCHEMA = """
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_type TEXT NOT NULL,
    identifier TEXT NOT NULL,
    label TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(resource_type, identifier)
);
CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(resource_type);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_type TEXT NOT NULL,
    -- NULL = tous les identifiants de ce type (octroi "large"),
    -- une valeur précise = seulement CETTE ressource.
    resource_id TEXT,
    group_name TEXT NOT NULL,
    action TEXT NOT NULL,
    granted_by TEXT,
    granted_at TEXT NOT NULL,
    UNIQUE(resource_type, resource_id, group_name, action)
);
CREATE INDEX IF NOT EXISTS idx_permissions_lookup ON permissions(resource_type, group_name, action);

-- #559 : sujets à accès RESTREINT. Par défaut le hub est ouvert : toute
-- personne connectée voit toutes les tuiles disponibles (comportement
-- historique). Un sujet inscrit ici (group:<nom> ou user:<login>) ne voit
-- que ce que la matrice lui accorde. Une personne est restreinte si son
-- login l'est, ou si TOUS ses groupes le sont (un groupe ouvert suffit à
-- ouvrir). admin_hub et administrateurs ne sont jamais restreints.
CREATE TABLE IF NOT EXISTS restricted_subjects (
    subject TEXT PRIMARY KEY, set_by TEXT, set_at TEXT NOT NULL
);

-- #559 : catalogue des ressources du hub (tuiles, actions) publié par le
-- hub lui-même ; `actions` = liste JSON, `theme` = thématique d'affichage.
CREATE TABLE IF NOT EXISTS catalog (
    resource_type TEXT NOT NULL, identifier TEXT NOT NULL, label TEXT, theme TEXT, actions TEXT, position INTEGER,
    PRIMARY KEY (resource_type, identifier)
);
"""

ADMIN_GROUP = "admin_hub"
OPEN_GROUPS = ("admin_hub", "administrateurs")  # jamais restreints


def subjects_of(groups, user=None):
    """Sujets porteurs de droits : les groupes tels quels (compatibilité)
    et le login sous la forme user:<login> (#559)."""
    out = [g for g in (groups or []) if g]
    if user:
        out.append("user:%s" % user)
    return out


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def has_permission(db_path, groups, resource_type, resource_id, action, user=None):
    """LE cœur du service -- vérifie si l'un des groupes fournis a le
    droit `action` sur la ressource (resource_type, resource_id).

    `groups` : liste des groupes Keycloak de l'appelant (déjà extraits
    du jeton par l'appelant -- ce service ne décode JAMAIS de jeton
    lui-même, ne fait AUCUNE hypothèse sur le mécanisme d'authentification
    de qui l'appelle, reste un simple vérificateur d'autorisation à
    partir d'une liste de groupes déjà établie).

    Court-circuit admin_hub -- TOUJOURS vrai, avant toute requête SQL,
    jamais contournable par une ligne de permission manquante ou mal
    octroyée.

    Ordre de recherche : octroi PRÉCIS (ce resource_id exact) d'abord,
    puis octroi LARGE (resource_id NULL, tout le type) -- un octroi
    précis qui REFUSERAIT n'existe pas dans ce modèle (pas de refus
    explicite, seulement des octrois -- l'absence d'octroi = refus par
    défaut, jamais l'inverse)."""
    if ADMIN_GROUP in groups:
        return True
    groups = subjects_of(groups, user)
    if not groups:
        return False

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        placeholders = ",".join("?" * len(groups))
        cur.execute(
            f"""SELECT 1 FROM permissions
                WHERE resource_type = ? AND action = ?
                AND (resource_id = ? OR resource_id IS NULL)
                AND group_name IN ({placeholders})
                LIMIT 1""",
            [resource_type, action, resource_id, *groups],
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def filter_visible(db_path, groups, resource_type, items, action="view", id_key="identifier", user=None):
    """Filtre une liste d'items selon la visibilité -- livraison
    #283, "une gestion de droit incluant la visibilité en listing" :
    ne garde que ceux pour lesquels l'appelant a le droit `action`.
    Admin_hub voit tout (court-circuit unique, une seule requête pour
    charger tous les octrois LARGES d'un coup plutôt qu'une requête
    SQL par item -- volume potentiellement élevé pour un inventaire
    de fichiers, jamais du N+1 ici)."""
    if ADMIN_GROUP in groups:
        return list(items)
    groups = subjects_of(groups, user)
    if not groups:
        return []

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        placeholders = ",".join("?" * len(groups))
        cur.execute(
            f"""SELECT resource_id FROM permissions
                WHERE resource_type = ? AND action = ? AND group_name IN ({placeholders})""",
            [resource_type, action, *groups],
        )
        rows = cur.fetchall()
        wide_access = any(r["resource_id"] is None for r in rows)
        if wide_access:
            return list(items)
        allowed_ids = {r["resource_id"] for r in rows}
        return [item for item in items if item.get(id_key) in allowed_ids]
    finally:
        conn.close()


def grant_permission(db_path, resource_type, resource_id, group_name, action, granted_by):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT OR IGNORE INTO permissions (resource_type, resource_id, group_name, action, granted_by, granted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [resource_type, resource_id, group_name, action, granted_by, now_iso()],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def revoke_permission(db_path, permission_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM permissions WHERE id = ?", [permission_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_permissions(db_path, resource_type=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if resource_type:
            cur.execute("SELECT * FROM permissions WHERE resource_type = ? ORDER BY resource_type, group_name", [resource_type])
        else:
            cur.execute("SELECT * FROM permissions ORDER BY resource_type, group_name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_resource_types(db_path):
    """Types de ressources DÉJÀ enregistrés (via upsert_resource) --
    pour peupler un sélecteur côté interface sans deviner une liste
    figée à l'avance."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT resource_type FROM resources ORDER BY resource_type")
        return [r["resource_type"] for r in cur.fetchall()]
    finally:
        conn.close()


def upsert_resource(db_path, resource_type, identifier, label=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO resources (resource_type, identifier, label, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(resource_type, identifier) DO UPDATE SET label = excluded.label""",
            [resource_type, identifier, label, now_iso()],
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ #559
def restricted_subjects(db_path):
    conn = get_connection(db_path)
    try:
        return [r["subject"] for r in conn.execute("SELECT subject FROM restricted_subjects ORDER BY subject")]
    finally:
        conn.close()


def set_restricted(db_path, subject, restricted, set_by=None):
    subject = (subject or "").strip()
    if not subject or subject in OPEN_GROUPS or subject in ("group:admin_hub", "group:administrateurs"):
        return False
    conn = get_connection(db_path)
    try:
        if restricted:
            conn.execute("INSERT OR REPLACE INTO restricted_subjects (subject, set_by, set_at) VALUES (?, ?, ?)", [subject, set_by, now_iso()])
        else:
            conn.execute("DELETE FROM restricted_subjects WHERE subject = ?", [subject])
        conn.commit()
        return True
    finally:
        conn.close()


def is_restricted(db_path, groups, user=None):
    """Restreint si le login l'est, ou si la personne a des groupes et que
    TOUS sont restreints. Jamais pour admin_hub / administrateurs."""
    groups = [g for g in (groups or []) if g]
    if any(g in OPEN_GROUPS for g in groups):
        return False
    restricted = set(restricted_subjects(db_path))
    if user and ("user:%s" % user) in restricted:
        return True
    return bool(groups) and all(("group:%s" % g) in restricted or g in restricted for g in groups)


def visible_ids(db_path, groups, resource_type, ids, user=None, action="view"):
    """Identifiants visibles : tout si la personne n'est pas restreinte,
    sinon ceux accordés (par groupe ou par login) -- fondement de
    l'application réelle des droits sur les tuiles du hub."""
    if not is_restricted(db_path, groups, user):
        return list(ids)
    items = [{"identifier": i} for i in ids]
    return [i["identifier"] for i in filter_visible(db_path, groups, resource_type, items, action=action, user=user)]


def set_catalog(db_path, resource_type, items):
    """Remplace le catalogue d'un type : [{identifier, label, theme, actions[]}]."""
    import json
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM catalog WHERE resource_type = ?", [resource_type])
        for i, it in enumerate(items or []):
            if not it.get("identifier"):
                continue
            conn.execute("INSERT INTO catalog (resource_type, identifier, label, theme, actions, position) VALUES (?, ?, ?, ?, ?, ?)",
                         [resource_type, it["identifier"], it.get("label"), it.get("theme"), json.dumps(it.get("actions") or ["view"]), i])
        conn.commit()
    finally:
        conn.close()


def get_catalog(db_path, resource_type):
    import json
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM catalog WHERE resource_type = ? ORDER BY position", [resource_type]).fetchall()
        return [{"identifier": r["identifier"], "label": r["label"], "theme": r["theme"], "actions": json.loads(r["actions"] or '["view"]')} for r in rows]
    finally:
        conn.close()


def set_grant(db_path, resource_type, resource_id, subject, action, allowed, granted_by=None):
    """Octroi idempotent (allowed=True) ou révocation (False) d'une case de la matrice."""
    if allowed:
        grant_permission(db_path, resource_type, resource_id, subject, action, granted_by)
        return True
    conn = get_connection(db_path)
    try:
        if resource_id is None:
            conn.execute("DELETE FROM permissions WHERE resource_type = ? AND resource_id IS NULL AND group_name = ? AND action = ?", [resource_type, subject, action])
        else:
            conn.execute("DELETE FROM permissions WHERE resource_type = ? AND resource_id = ? AND group_name = ? AND action = ?", [resource_type, resource_id, subject, action])
        conn.commit()
        return True
    finally:
        conn.close()
