"""
Persistance des liaisons POLYMORPHES uniquement (livraison #158) --
les tables `documents`/`document_versions` de la fondation homemade
de #157 ont disparu, REMPLACÉES par de vrais appels à l'API REST de
Mayan EDMS (voir mayan_client.py) après adoption explicite ("allons-y
pour Mayan EDMS"). Mayan n'a pas d'équivalent direct à "lier un
document à N'IMPORTE QUEL type d'entité externe" -- ged-api continue
donc de gérer CETTE table lui-même, en référençant les IDs de
documents MAYAN (`document_id` ci-dessous = id Mayan, pas un id
local comme en #157).

Même motif SQLite que dba-api/prefs-api/schema-analyzer
(DB_PATH/get_connection/ensure_schema/now_iso).
"""
import sqlite3
import time

SCHEMA = """
-- Liaison POLYMORPHE -- `linked_type` : chaîne libre ("ticket" pour
-- l'instant, potentiellement d'autres types plus tard), `linked_id` :
-- identifiant de l'entité liée DANS SON PROPRE SYSTÈME (ex. l'id
-- d'un ticket dans tickets-api). `document_id` : id du document DANS
-- MAYAN (pas un id local) -- jamais une clé étrangère SQL réelle
-- vers un AUTRE service (couplage FAIBLE, même raisonnement que
-- schema-analyzer vers dba-api : juste un identifiant).
CREATE TABLE IF NOT EXISTS document_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    linked_type TEXT NOT NULL,
    linked_id TEXT NOT NULL,
    linked_by TEXT,
    linked_at TEXT NOT NULL,
    UNIQUE(document_id, linked_type, linked_id)
);
"""


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


def create_link(db_path, document_id, linked_type, linked_id, linked_by=None):
    """Renvoie (id, error) -- error non-None si cette liaison EXACTE
    existe déjà (contrainte UNIQUE) -- jamais un doublon silencieux
    ni une exception sqlite3 brute."""
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO document_links (document_id, linked_type, linked_id, linked_by, linked_at) VALUES (?, ?, ?, ?, ?)",
            [document_id, linked_type, str(linked_id), linked_by, now],
        )
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "ce document est déjà lié à cette entité"
    finally:
        conn.close()


def list_links(db_path, document_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM document_links WHERE document_id = ? ORDER BY linked_at", [document_id])
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_linked_document_ids(db_path, linked_type, linked_id):
    """Renvoie la liste des `document_id` Mayan liés à cette entité
    précise -- ged-api interroge ENSUITE Mayan pour chacun (cette
    table ne connaît RIEN du contenu/label des documents eux-mêmes,
    volontairement -- Mayan reste la seule source de vérité pour
    ça)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT document_id FROM document_links WHERE linked_type = ? AND linked_id = ?",
            [linked_type, str(linked_id)],
        )
        return [r["document_id"] for r in cur.fetchall()]
    finally:
        conn.close()


def delete_link(db_path, link_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM document_links WHERE id = ?", [link_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_links_for_document(db_path, document_id):
    """Supprime TOUTES les liaisons d'un document -- appelée quand le
    document lui-même est supprimé (côté Mayan) pour ne jamais garder
    de liaisons orphelines pointant vers un document qui n'existe
    plus."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM document_links WHERE document_id = ?", [document_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
