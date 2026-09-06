"""
Persistance des relations (livraison #152, backlog BACKLOG.md #5,
"éditeur de relations") -- SQLite locale à ce service, même motif que
dba-api/prefs-api (voir DB_PATH/get_connection/ensure_schema).

Jusqu'ici (#151), /analyze produisait des propositions FRAÎCHES à
chaque appel, jamais stockées. Ça ne permettait aucune VALIDATION
persistante (demandée explicitement : "proposition automatique et
validation manuelle") -- une proposition qu'on ne peut ni accepter ni
corriger ni rejeter durablement n'est qu'un diagnostic, pas un
éditeur. Cette table comble ça : chaque relation a un `status`
("proposed" | "confirmed" | "rejected") et une `source` ("auto" | "manual"),
modifiable via l'API (voir app.py).

Une relation reste rattachée à un (connection_id, database) précis --
jamais partagée entre connexions DBA différentes, même si deux vieilles
bases ont des noms de table identiques par coïncidence.
"""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER NOT NULL,
    database_name TEXT,
    from_table TEXT NOT NULL,
    from_column TEXT NOT NULL,
    to_table TEXT NOT NULL,
    to_column TEXT NOT NULL,
    -- "foreign_key" (référence classique 1 valeur -> 1 ligne) |
    -- "list" (colonne texte contenant plusieurs identifiants, voir
    -- list_detector.py -- ex. sites: "1,2,5").
    relation_type TEXT NOT NULL DEFAULT 'foreign_key',
    -- "proposed" (proposition automatique, pas encore tranchée) |
    -- "confirmed" (validée -- automatiquement ou manuellement) |
    -- "rejected" (proposition écartée -- gardée en base plutôt que
    -- supprimée, pour ne pas la reproposer indéfiniment à chaque
    -- réimport, voir import_proposals()).
    status TEXT NOT NULL DEFAULT 'proposed',
    -- "auto" (issue de detect_name_based_relations/list_detector) |
    -- "manual" (saisie directement par une personne).
    source TEXT NOT NULL DEFAULT 'auto',
    -- "haute" | "moyenne" | NULL (une relation manuelle n'a pas de
    -- confiance -- une personne qui la saisit EST la validation).
    confidence TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- Empêche un réimport de dupliquer une relation déjà connue pour
    -- ce même (connexion, base, colonnes) -- voir import_proposals().
    UNIQUE(connection_id, database_name, from_table, from_column, to_table, to_column)
);
"""

VALID_RELATION_TYPES = ("foreign_key", "list")
VALID_STATUSES = ("proposed", "confirmed", "rejected")


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


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def row_to_relation(row):
    return dict(row)


def list_relations(db_path, connection_id, database=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if database is not None:
            cur.execute(
                "SELECT * FROM relations WHERE connection_id = ? AND database_name = ? ORDER BY from_table, from_column",
                [connection_id, database],
            )
        else:
            cur.execute(
                "SELECT * FROM relations WHERE connection_id = ? ORDER BY from_table, from_column",
                [connection_id],
            )
        return [row_to_relation(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _normalize_database(database):
    """NULL en SQL n'est JAMAIS égal à un autre NULL -- la contrainte
    UNIQUE de la table `relations` (qui inclut database_name) ne
    bloquerait donc AUCUN doublon pour une connexion sans base précise
    (ex. SQLite côté DBA, où `database` vaut None) : chaque insertion
    NULL serait traitée comme distincte, cassant silencieusement la
    protection contre l'écrasement (bug réel trouvé après une question
    de la personne, jamais couvert par les tests initiaux de #152).
    Corrigé en normalisant None vers une chaîne vide AVANT stockage/
    comparaison -- une chaîne vide EST comparable pour l'unicité,
    contrairement à NULL."""
    return database if database is not None else ""


def create_relation(db_path, connection_id, database, from_table, from_column, to_table, to_column,
                     relation_type="foreign_key", status="confirmed", source="manual", confidence=None,
                     created_by=None):
    """Renvoie (id, error) -- error non-None si la relation existe déjà
    (contrainte UNIQUE), jamais une exception sqlite3.IntegrityError
    brute qui remonterait à l'appelant HTTP."""
    database = _normalize_database(database)
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO relations
               (connection_id, database_name, from_table, from_column, to_table, to_column,
                relation_type, status, source, confidence, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [connection_id, database, from_table, from_column, to_table, to_column,
             relation_type, status, source, confidence, created_by, now, now],
        )
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "cette relation existe déjà pour cette connexion/base"
    finally:
        conn.close()


def update_relation(db_path, relation_id, **fields):
    """`fields` : sous-ensemble de {from_table, from_column, to_table,
    to_column, relation_type, status, confidence}, valeurs déjà
    validées par l'appelant (voir app.py) -- ce module ne revalide pas
    les types/statuts, seulement l'existence de la ligne. Renvoie
    (True, None) si mise à jour, (False, "introuvable") si l'id
    n'existe pas, (False, "conflit") si le changement créerait un
    doublon (contrainte UNIQUE)."""
    if not fields:
        return True, None  # rien à faire, pas une erreur pour autant
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM relations WHERE id = ?", [relation_id])
        if cur.fetchone() is None:
            return False, "introuvable"
        set_clause = ", ".join(f"{col} = ?" for col in fields)
        values = list(fields.values()) + [now_iso(), relation_id]
        try:
            cur.execute(f"UPDATE relations SET {set_clause}, updated_at = ? WHERE id = ?", values)
            conn.commit()
            return True, None
        except sqlite3.IntegrityError:
            return False, "conflit -- une relation identique existe déjà"
    finally:
        conn.close()


def delete_relation(db_path, relation_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM relations WHERE id = ?", [relation_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def import_proposals(db_path, connection_id, database, proposals, created_by=None):
    """`proposals` : liste de dicts {from_table, from_column, to_table,
    to_column, relation_type, confidence} (voir app.py, construits à
    partir de relation_detector.py/list_detector.py). INSÈRE chaque
    proposition avec status="proposed", source="auto".

    Renvoie {"imported": [...], "skipped": [...]} -- `imported` :
    les relations NOUVELLEMENT créées (avec leur id). `skipped` : les
    candidats déjà connus pour ce (connexion, base), CHACUN avec
    l'id ET le statut ACTUEL de la relation existante
    (proposed/confirmed/rejected) -- rend la protection contre
    l'écrasement VISIBLE (demandé explicitement par la personne après
    la livraison initiale) plutôt qu'un simple delta de compteur à
    déduire soi-même. Une décision déjà prise (confirmée OU rejetée)
    n'est JAMAIS écrasée, quel que soit le statut -- seulement
    SIGNALÉE comme ignorée, avec la raison exacte."""
    database_norm = _normalize_database(database)
    now = now_iso()
    imported = []
    skipped = []
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        for p in proposals:
            cur.execute(
                """SELECT id, status FROM relations
                   WHERE connection_id = ? AND database_name = ?
                   AND from_table = ? AND from_column = ? AND to_table = ? AND to_column = ?""",
                [connection_id, database_norm, p["from_table"], p["from_column"], p["to_table"], p["to_column"]],
            )
            existing = cur.fetchone()
            if existing is not None:
                skipped.append({
                    "from_table": p["from_table"], "from_column": p["from_column"],
                    "to_table": p["to_table"], "to_column": p["to_column"],
                    "existing_id": existing["id"], "existing_status": existing["status"],
                })
                continue
            cur.execute(
                """INSERT INTO relations
                   (connection_id, database_name, from_table, from_column, to_table, to_column,
                    relation_type, status, source, confidence, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed', 'auto', ?, ?, ?, ?)""",
                [connection_id, database_norm, p["from_table"], p["from_column"], p["to_table"], p["to_column"],
                 p.get("relation_type", "foreign_key"), p.get("confidence"), created_by, now, now],
            )
            imported.append({
                "id": cur.lastrowid,
                "from_table": p["from_table"], "from_column": p["from_column"],
                "to_table": p["to_table"], "to_column": p["to_column"],
            })
        conn.commit()
    finally:
        conn.close()
    return {"imported": imported, "skipped": skipped}
