"""
Persistance des règles de tri IMAP (livraison #190, précision
apportée par la personne sur le sens de "filtres" -- volet 2/4,
BACKLOG.md #4 : "c'est aussi l'idée de trier et poser des étiquettes,
déplacer vers des dossiers, déclencher des actions"). PREMIÈRE base
de données de ce module -- `imap-client` était SANS ÉTAT jusqu'ici
(#179/#189), chaque requête ouvrant une connexion IMAP neuve --
les RÈGLES, elles, doivent PERSISTER entre deux appels (rien dans le
protocole IMAP lui-même pour les stocker, contrairement à un vrai
serveur Sieve -- pas ce qui est visé ici, voir docstring d'app.py).

Une règle = un ENSEMBLE DE CRITÈRES (tous optionnels, combinés en
ET) + un ENSEMBLE D'ACTIONS (toutes optionnelles, appliquées dans
l'ordre : étiquette/lu D'ABORD, déplacement EN DERNIER -- un message
déplacé change d'UID, plus aucune action n'aurait de sens dessus
après ça). `watch_folder` : UN SEUL dossier par règle, jamais une
liste -- une règle qui devrait surveiller plusieurs dossiers, c'est
PLUSIEURS règles, plus simple à raisonner et à afficher.
"""
import sqlite3
import time


SCHEMA = """
CREATE TABLE IF NOT EXISTS imap_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    watch_folder TEXT NOT NULL DEFAULT 'INBOX',
    match_subject TEXT,
    match_from TEXT,
    match_unseen_only INTEGER NOT NULL DEFAULT 0,
    action_move_to TEXT,
    action_add_label TEXT,
    action_mark_seen INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
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


def row_to_rule(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "watch_folder": row["watch_folder"],
        "match_subject": row["match_subject"],
        "match_from": row["match_from"],
        "match_unseen_only": bool(row["match_unseen_only"]),
        "action_move_to": row["action_move_to"],
        "action_add_label": row["action_add_label"],
        "action_mark_seen": bool(row["action_mark_seen"]),
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_rules(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM imap_rules ORDER BY id")
        return [row_to_rule(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_rule(db_path, rule_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM imap_rules WHERE id = ?", [rule_id])
        row = cur.fetchone()
        return row_to_rule(row) if row else None
    finally:
        conn.close()


def create_rule(db_path, name, watch_folder, match_subject=None, match_from=None,
                 match_unseen_only=False, action_move_to=None, action_add_label=None,
                 action_mark_seen=False):
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO imap_rules
               (name, watch_folder, match_subject, match_from, match_unseen_only,
                action_move_to, action_add_label, action_mark_seen, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            [name, watch_folder, match_subject, match_from, int(match_unseen_only),
             action_move_to, action_add_label, int(action_mark_seen), now, now],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_rule(db_path, rule_id, patch):
    """Mise à jour PARTIELLE -- seuls les champs présents dans
    `patch` changent (même motif que cyber_risks/prefs-api, #187) --
    l'usage principal attendu est de juste basculer `enabled`."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM imap_rules WHERE id = ?", [rule_id])
        row = cur.fetchone()
        if row is None:
            return None
        current = row_to_rule(row)
        merged = {**current, **patch}
        cur.execute(
            """UPDATE imap_rules SET name = ?, watch_folder = ?, match_subject = ?,
               match_from = ?, match_unseen_only = ?, action_move_to = ?, action_add_label = ?,
               action_mark_seen = ?, enabled = ?, updated_at = ? WHERE id = ?""",
            [merged["name"], merged["watch_folder"], merged["match_subject"], merged["match_from"],
             int(merged["match_unseen_only"]), merged["action_move_to"], merged["action_add_label"],
             int(merged["action_mark_seen"]), int(merged["enabled"]), now_iso(), rule_id],
        )
        conn.commit()
        cur.execute("SELECT * FROM imap_rules WHERE id = ?", [rule_id])
        return row_to_rule(cur.fetchone())
    finally:
        conn.close()


def delete_rule(db_path, rule_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM imap_rules WHERE id = ?", [rule_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
