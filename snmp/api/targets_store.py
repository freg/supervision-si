"""
Stockage des cibles SNMP (livraison #213, backlog item 13, volet 2 --
"gestion des paramètres d'accès sécurisés"). Une cible = un
hôte+port+communauté NOMMÉ et réutilisable -- évite de ressaisir la
communauté à chaque interrogation (`POST /query`/`POST
/walk-interfaces` acceptent toujours `host`+`community` en direct,
sans cible enregistrée, pour un usage ponctuel -- voir app.py).

Communauté chiffrée via `credential_crypto.py` (enveloppe
`secret_crypto.py`, #202-206) -- jamais stockée en clair.
"""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS snmp_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 161,
    community_encrypted TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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


def create_target(db_path, label, host, port, community_encrypted, created_by=None):
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO snmp_targets (label, host, port, community_encrypted, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [label, host, port, community_encrypted, created_by, now, now],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_targets(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM snmp_targets ORDER BY label")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_target(db_path, target_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM snmp_targets WHERE id = ?", [target_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_target(db_path, target_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM snmp_targets WHERE id = ?", [target_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
