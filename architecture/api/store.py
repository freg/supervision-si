"""
Registre d'équipements et topologie réseau DÉCLARÉE (livraison #253,
nouveau chantier -- vue/outil de parcours de l'architecture réseau,
demandé explicitement : "quand un équipement remonte dans la
supervision zenoss [ou lors d'un dysfonctionnement]... identifier les
interfaces en amont, en aval et les accès... les lieux
d'intervention... les documentations liées aux contrats, aux
spécifications techniques et aux paramètres spécifiques".

**Ce que ce module NE DUPLIQUE PAS** -- croisé À LA LECTURE plutôt que
recopié, pour ne jamais avoir deux sources de vérité qui divergent :
- Localisation physique -- déjà dans `zenoss-api`
  (`/location_tree`, colonnes `Location`/`Systems`, #??). Croisement
  LIVE différé à une prochaine tranche (structure en ARBRE côté
  Zenoss, pas de recherche directe "localisation de CET équipement" --
  nécessiterait de parcourir/mettre en cache tout l'arbre, hors de
  portée de cette première tranche).
- Accès de gestion (SSH) -- déjà dans `ssh-tunnels-api`
  (`ssh_connections`, `ssh_host`/`ssh_user`/`ssh_port`). Croisé EN
  DIRECT par correspondance d'adresse IP (voir `app.py` --
  `GET /connections` renvoie une liste PLATE, contrairement à Zenoss,
  filtrable simplement).
- Documents liés (contrats, spécifications, paramètres) -- réutilise
  le mécanisme de liaison POLYMORPHE déjà existant côté GED
  (`document_links`, `linked_type`/`linked_id`, #158) --
  `linked_type="equipment"` ici, jamais une nouvelle table de liaison
  dupliquée.

**Ce que ce module APPORTE, la pièce manquante** -- la TOPOLOGIE
amont/aval elle-même : `network-agent` (#250) enregistre déjà des
échanges entre appareils, mais ce sont des paires "qui a PARLÉ à
qui" observées sur le trafic RÉEL -- ça ne dit JAMAIS quelle
interface est "en amont" ou "en aval" d'une autre dans une hiérarchie
réseau. Cette hiérarchie est une connaissance MÉTIER (comment le
réseau est réellement câblé/configuré), pas quelque chose de fiable
à déduire automatiquement du trafic observé -- saisie ici
explicitement, par la personne qui la connaît.
"""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS arch_equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ip_address TEXT,
    mac_address TEXT,
    equipment_type TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_arch_equipment_ip ON arch_equipment(ip_address);

-- Interface d'un équipement -- un port physique ou logique
-- (ex. "Gi0/1", "eth0", "Port 3 - baie A"). Le NIVEAU de détail
-- reste libre -- une interface "générique" par équipement est
-- acceptable si le détail précis n'est pas connu, jamais un champ
-- obligatoire trop exigeant qui bloquerait la saisie.
CREATE TABLE IF NOT EXISTS arch_interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES arch_equipment(id),
    label TEXT NOT NULL,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_arch_interfaces_equipment ON arch_interfaces(equipment_id);

-- Lien topologique DÉCLARÉ entre deux interfaces -- DIRECTIONNEL,
-- `upstream_interface_id` est EN AMONT de `downstream_interface_id`
-- (la hiérarchie/le flux descend de l'amont vers l'aval). Reflète
-- une connaissance MÉTIER saisie par la personne, jamais déduite
-- automatiquement (voir docstring du module).
CREATE TABLE IF NOT EXISTS arch_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upstream_interface_id INTEGER NOT NULL REFERENCES arch_interfaces(id),
    downstream_interface_id INTEGER NOT NULL REFERENCES arch_interfaces(id),
    notes TEXT,
    UNIQUE(upstream_interface_id, downstream_interface_id)
);
CREATE INDEX IF NOT EXISTS idx_arch_links_up ON arch_links(upstream_interface_id);
CREATE INDEX IF NOT EXISTS idx_arch_links_down ON arch_links(downstream_interface_id);
"""


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


# --- Équipements -----------------------------------------------------

def create_equipment(db_path, name, ip_address=None, mac_address=None, equipment_type=None, notes=None):
    conn = get_connection(db_path)
    try:
        now = now_iso()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO arch_equipment (name, ip_address, mac_address, equipment_type, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [name.strip(), ip_address, mac_address, equipment_type, notes, now, now],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def import_from_network_agent(db_path, devices):
    """Import/synchronisation IDEMPOTENTE depuis les appareils déjà
    découverts par `network-agent` (livraison #263, "reste à faire"
    signalé dès #253 -- "actuellement, un équipement se crée
    entièrement à la main ici, aucun pré-remplissage depuis ces
    sources"). Matché PAR ADRESSE MAC, jamais de doublon sur des
    imports répétés.

    Un équipement DÉJÀ PRÉSENT (même MAC) voit SEULEMENT son IP mise
    à jour si elle a changé (plausible via DHCP) -- son NOM, TYPE et
    NOTES restent INTACTS, potentiellement personnalisés par la
    personne après import, JAMAIS écrasés par un import répété. Un
    NOUVEL équipement est créé avec le nom d'hôte comme nom (ou
    l'adresse MAC si aucun nom d'hôte connu), et une note signalant
    son origine.

    `devices` -- la liste telle que renvoyée par `GET /devices` de
    network-agent-api (voir architecture-api/app.py pour l'appel
    réel). Renvoie {"created", "updated", "skipped"}."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        created, updated, skipped = 0, 0, 0
        now = now_iso()
        for device in devices:
            mac = (device.get("mac_address") or "").strip().lower()
            if not mac:
                skipped += 1  # jamais rencontré en pratique (network-agent exige toujours une MAC), défensif malgré tout
                continue
            cur.execute("SELECT id, ip_address FROM arch_equipment WHERE lower(mac_address) = ?", [mac])
            row = cur.fetchone()
            new_ip = device.get("ip_address")
            if row:
                if new_ip and new_ip != row["ip_address"]:
                    cur.execute("UPDATE arch_equipment SET ip_address = ?, updated_at = ? WHERE id = ?", [new_ip, now, row["id"]])
                    updated += 1
            else:
                name = device.get("hostname") or mac
                cur.execute(
                    """INSERT INTO arch_equipment (name, ip_address, mac_address, equipment_type, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [name, new_ip, mac, None, "Importé automatiquement depuis Exploration réseau", now, now],
                )
                created += 1
        conn.commit()
        return {"created": created, "updated": updated, "skipped": skipped}
    finally:
        conn.close()


def list_equipment(db_path, search=None):
    """`search` (optionnel) -- filtre PAR SOUS-CHAÎNE sur le nom OU
    l'IP, insensible à la casse -- retrouver un équipement dans un
    registre qui grandit sans devoir connaître son id exact."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if search:
            like = f"%{search.lower()}%"
            cur.execute(
                "SELECT * FROM arch_equipment WHERE lower(name) LIKE ? OR lower(ip_address) LIKE ? ORDER BY name",
                [like, like],
            )
        else:
            cur.execute("SELECT * FROM arch_equipment ORDER BY name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_equipment(db_path, equipment_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM arch_equipment WHERE id = ?", [equipment_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_equipment(db_path, equipment_id, **fields):
    """`fields` -- seulement les colonnes reconnues sont appliquées
    (name/ip_address/mac_address/equipment_type/notes), jamais un nom
    de colonne arbitraire interpolé dans le SQL."""
    allowed = {"name", "ip_address", "mac_address", "equipment_type", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return 0
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        cur.execute(
            f"UPDATE arch_equipment SET {set_clause}, updated_at = ? WHERE id = ?",
            [*updates.values(), now_iso(), equipment_id],
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_equipment(db_path, equipment_id):
    """Supprime l'équipement ET ses interfaces (les liens topologiques
    référençant ces interfaces deviendraient orphelins sinon --
    supprimés en cascade explicitement, SQLite n'appliquant pas de
    CASCADE automatique par défaut)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM arch_interfaces WHERE equipment_id = ?", [equipment_id])
        interface_ids = [row["id"] for row in cur.fetchall()]
        for iface_id in interface_ids:
            cur.execute("DELETE FROM arch_links WHERE upstream_interface_id = ? OR downstream_interface_id = ?", [iface_id, iface_id])
        cur.execute("DELETE FROM arch_interfaces WHERE equipment_id = ?", [equipment_id])
        cur.execute("DELETE FROM arch_equipment WHERE id = ?", [equipment_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# --- Interfaces --------------------------------------------------------

def create_interface(db_path, equipment_id, label, notes=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO arch_interfaces (equipment_id, label, notes) VALUES (?, ?, ?)",
            [equipment_id, label.strip(), notes],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_interfaces(db_path, equipment_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM arch_interfaces WHERE equipment_id = ? ORDER BY label", [equipment_id])
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_interface(db_path, interface_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM arch_links WHERE upstream_interface_id = ? OR downstream_interface_id = ?", [interface_id, interface_id])
        cur.execute("DELETE FROM arch_interfaces WHERE id = ?", [interface_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# --- Liens topologiques ------------------------------------------------

def create_link(db_path, upstream_interface_id, downstream_interface_id, notes=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO arch_links (upstream_interface_id, downstream_interface_id, notes) VALUES (?, ?, ?)",
            [upstream_interface_id, downstream_interface_id, notes],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_link(db_path, link_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM arch_links WHERE id = ?", [link_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_neighbors(db_path, equipment_id):
    """Voisins topologiques DIRECTS d'un équipement (livraison #253,
    le cœur de la demande -- "interfaces en amont, en aval") --
    renvoie {"upstream": [...], "downstream": [...]}, chaque entrée
    portant l'interface locale concernée, l'interface distante, ET
    l'équipement distant (jointure complète -- la personne veut
    naviguer directement vers l'équipement voisin, pas seulement
    voir un id d'interface isolé)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, label FROM arch_interfaces WHERE equipment_id = ?", [equipment_id])
        local_interfaces = {row["id"]: row["label"] for row in cur.fetchall()}
        if not local_interfaces:
            return {"upstream": [], "downstream": []}

        upstream, downstream = [], []
        for iface_id, iface_label in local_interfaces.items():
            # Voisins EN AMONT de CETTE interface locale (elle est le "downstream" du lien)
            cur.execute(
                """SELECT l.id AS link_id, l.notes, ai.id AS remote_interface_id, ai.label AS remote_interface_label,
                          ae.id AS remote_equipment_id, ae.name AS remote_equipment_name, ae.ip_address AS remote_equipment_ip
                   FROM arch_links l
                   JOIN arch_interfaces ai ON ai.id = l.upstream_interface_id
                   JOIN arch_equipment ae ON ae.id = ai.equipment_id
                   WHERE l.downstream_interface_id = ?""",
                [iface_id],
            )
            for row in cur.fetchall():
                upstream.append({"local_interface_id": iface_id, "local_interface_label": iface_label, **dict(row)})

            # Voisins EN AVAL de CETTE interface locale (elle est le "upstream" du lien)
            cur.execute(
                """SELECT l.id AS link_id, l.notes, ai.id AS remote_interface_id, ai.label AS remote_interface_label,
                          ae.id AS remote_equipment_id, ae.name AS remote_equipment_name, ae.ip_address AS remote_equipment_ip
                   FROM arch_links l
                   JOIN arch_interfaces ai ON ai.id = l.downstream_interface_id
                   JOIN arch_equipment ae ON ae.id = ai.equipment_id
                   WHERE l.upstream_interface_id = ?""",
                [iface_id],
            )
            for row in cur.fetchall():
                downstream.append({"local_interface_id": iface_id, "local_interface_label": iface_label, **dict(row)})

        return {"upstream": upstream, "downstream": downstream}
    finally:
        conn.close()
