# -*- coding: utf-8 -*-
"""Stockage SQLite des connecteurs IMAP (livraison #489).

Trois tables : les connecteurs (boîtes + cible), les messages pris en
charge (journal complet — « le tout avec log et base de données »),
les livraisons vers les API cibles (une par tentative, avec statut).

Mots de passe IMAP en base, chiffrés ? Non — en CLAIR, même posture
que le module UPS (identifiants des cartes réseau en base) : la base
est un fichier du serveur, protégée par le système de fichiers. Les
secrets d'INFRASTRUCTURE (aucun ici) restent dans .env."""
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS connectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 993,
    tls INTEGER NOT NULL DEFAULT 1,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    folder TEXT NOT NULL DEFAULT 'INBOX',
    target TEXT NOT NULL,
    interval_seconds INTEGER NOT NULL DEFAULT 300,
    mark_seen INTEGER NOT NULL DEFAULT 1,
    auto_ack INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 0,
    default_type_id INTEGER,
    default_level_id INTEGER,
    notes TEXT,
    last_poll_at TEXT, last_ok INTEGER, last_error TEXT, last_message_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_id INTEGER NOT NULL REFERENCES connectors(id),
    uid TEXT NOT NULL,
    message_id TEXT,
    from_addr TEXT,
    subject TEXT,
    date TEXT,
    fetched_at TEXT NOT NULL,
    parsed INTEGER NOT NULL DEFAULT 0,
    kind TEXT,
    summary TEXT,
    fields TEXT,
    ack_at TEXT,
    UNIQUE(connector_id, uid)
);
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    target TEXT NOT NULL,
    ok INTEGER NOT NULL,
    detail TEXT,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_connector ON messages(connector_id, fetched_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_message ON deliveries(message_id);
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path):
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        # Migration #490 : ack_at (accusé de lecture de la cloche SMS)
        # ajouté aux bases créées en #489 — ALTER TABLE si absent.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
        if "ack_at" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN ack_at TEXT")
        # Migration #492 : auto_ack (acquittement automatique des
        # alertes à la résolution, paramétrable par connecteur).
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(connectors)").fetchall()}
        if "auto_ack" not in cols:
            conn.execute("ALTER TABLE connectors ADD COLUMN auto_ack INTEGER NOT NULL DEFAULT 1")
        conn.commit()
    finally:
        conn.close()


def _public(row):
    d = dict(row)
    d.pop("password", None)  # jamais vers l'API
    for k in ("tls", "mark_seen", "auto_ack", "enabled", "last_ok"):
        if k in d and d[k] is not None:
            d[k] = bool(d[k])
    return d


# ---------------------------------------------------------------- connecteurs

def list_connectors(db_path):
    conn = connect(db_path)
    try:
        return [_public(r) for r in conn.execute("SELECT * FROM connectors ORDER BY name").fetchall()]
    finally:
        conn.close()


def get_connector(db_path, connector_id, with_secret=False):
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    d = dict(r) if with_secret else _public(r)
    return d


def upsert_connector(db_path, fields, connector_id=None):
    allowed = {"name", "host", "port", "tls", "username", "password", "folder", "target",
               "interval_seconds", "mark_seen", "auto_ack", "enabled", "default_type_id", "default_level_id", "notes"}
    data = {k: v for k, v in fields.items() if k in allowed}
    for k in ("tls", "mark_seen", "auto_ack", "enabled"):
        if k in data:
            data[k] = 1 if data[k] else 0
    conn = connect(db_path)
    try:
        if connector_id is None:
            if not data.get("name") or not data.get("host") or not data.get("username") or not data.get("target"):
                raise ValueError("name, host, username et target sont obligatoires")
            if "password" not in data:
                raise ValueError("password est obligatoire à la création")
            cols = ", ".join(data) + ", created_at"
            marks = ", ".join("?" for _ in data) + ", ?"
            cur = conn.execute("INSERT INTO connectors (%s) VALUES (%s)" % (cols, marks),
                               list(data.values()) + [now_iso()])
            conn.commit()
            return get_connector(db_path, cur.lastrowid)
        # mise à jour : password absent = inchangé (jamais écrasé par vide)
        data = {k: v for k, v in data.items() if not (k == "password" and not v)}
        if not data:
            return get_connector(db_path, connector_id)
        conn.execute("UPDATE connectors SET %s WHERE id = ?" % ", ".join("%s = ?" % k for k in data),
                     list(data.values()) + [connector_id])
        conn.commit()
        return get_connector(db_path, connector_id)
    finally:
        conn.close()


def delete_connector(db_path, connector_id):
    conn = connect(db_path)
    try:
        ids = [r["id"] for r in conn.execute("SELECT id FROM messages WHERE connector_id = ?", (connector_id,)).fetchall()]
        if ids:
            conn.execute("DELETE FROM deliveries WHERE message_id IN (%s)" % ",".join("?" * len(ids)), ids)
        conn.execute("DELETE FROM messages WHERE connector_id = ?", (connector_id,))
        cur = conn.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def report_poll(db_path, connector_id, ok, error=None, message_at=None):
    conn = connect(db_path)
    try:
        conn.execute("UPDATE connectors SET last_poll_at = ?, last_ok = ?, last_error = ?, last_message_at = COALESCE(?, last_message_at) WHERE id = ?",
                     (now_iso(), 1 if ok else 0, error, message_at, connector_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- messages

def record_message(db_path, connector_id, msg, parsed):
    """Journalise un message (dédupliqué connector+uid) + son
    interprétation. Retourne (id, nouveau?)."""
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO messages (connector_id, uid, message_id, from_addr, subject, date, fetched_at, parsed, kind, summary, fields) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (connector_id, msg.get("uid", ""), msg.get("message_id"), msg.get("from_addr"), msg.get("subject"),
             msg.get("date"), now_iso(), 1 if parsed.get("ok") else 0, parsed.get("kind"),
             parsed.get("summary"), json.dumps(parsed.get("fields") or {}, ensure_ascii=False)))
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid, True
        row = conn.execute("SELECT id FROM messages WHERE connector_id = ? AND uid = ?",
                           (connector_id, msg.get("uid", ""))).fetchone()
        return (row["id"] if row else None), False
    finally:
        conn.close()


def record_delivery(db_path, message_id, target, ok, detail=None):
    conn = connect(db_path)
    try:
        conn.execute("INSERT INTO deliveries (message_id, target, ok, detail, at) VALUES (?,?,?,?,?)",
                     (message_id, target, 1 if ok else 0, (detail or "")[:500], now_iso()))
        conn.commit()
    finally:
        conn.close()


def list_messages(db_path, connector_id=None, limit=100, only_errors=False):
    conn = connect(db_path)
    try:
        q = ("SELECT m.*, c.name AS connector_name, c.target AS target FROM messages m "
             "JOIN connectors c ON c.id = m.connector_id")
        cond, params = [], []
        if connector_id:
            cond.append("m.connector_id = ?"); params.append(connector_id)
        if only_errors:
            cond.append("(m.parsed = 0 OR EXISTS (SELECT 1 FROM deliveries d WHERE d.message_id = m.id AND d.ok = 0))")
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY m.id DESC LIMIT ?"; params.append(min(int(limit), 500))
        rows = conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["deliveries"] = [dict(x) for x in conn.execute(
                "SELECT target, ok, detail, at FROM deliveries WHERE message_id = ? ORDER BY id", (d["id"],)).fetchall()]
            d.pop("fields", None)
            out.append(d)
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------- notifications (#490)

def list_unread(db_path, targets=("sms",), limit=50):
    """Messages non accusés des connecteurs des cibles données (la
    cloche SMS du hub). Le plus récent d'abord ; les champs
    interprétés (expéditeur, texte) sont décodés pour l'affichage."""
    marks = ",".join("?" for _ in targets)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT m.id, m.from_addr, m.subject, m.date, m.fetched_at, m.kind, m.summary, m.fields, "
            "c.name AS connector_name, c.target AS target FROM messages m "
            "JOIN connectors c ON c.id = m.connector_id "
            "WHERE m.ack_at IS NULL AND c.target IN (%s) "
            "ORDER BY m.id DESC LIMIT ?" % marks,
            list(targets) + [min(int(limit), 200)]).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["fields"] = json.loads(d.get("fields") or "{}")
            except ValueError:
                d["fields"] = {}
            out.append(d)
        return out
    finally:
        conn.close()


def unread_count(db_path, targets=("sms",)):
    marks = ",".join("?" for _ in targets)
    conn = connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) n FROM messages m JOIN connectors c ON c.id = m.connector_id "
            "WHERE m.ack_at IS NULL AND c.target IN (%s)" % marks, list(targets)).fetchone()["n"]
    finally:
        conn.close()


def ack_messages(db_path, ids=None, targets=("sms",)):
    """Accuse réception (cloche du hub) : les ids donnés, ou TOUT le
    non lu des cibles si ids est None. Retourne le nombre accusé."""
    conn = connect(db_path)
    try:
        if ids is not None:
            if not ids:
                return 0
            marks = ",".join("?" for _ in ids)
            cur = conn.execute(
                "UPDATE messages SET ack_at = ? WHERE ack_at IS NULL AND id IN (%s)" % marks,
                [now_iso()] + [int(i) for i in ids])
        else:
            marks = ",".join("?" for _ in targets)
            cur = conn.execute(
                "UPDATE messages SET ack_at = ? WHERE ack_at IS NULL AND connector_id IN "
                "(SELECT id FROM connectors WHERE target IN (%s))" % marks,
                [now_iso()] + list(targets))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def ack_active_alerts_for_device(db_path, device):
    """Auto-acquittement (#492, paramétrable par connecteur via
    auto_ack) : une résolution Zenoss acquitte les alertes ACTIVES
    non lues du même équipement — la cloche reflète l'état courant,
    pas l'historique. json_extract (JSON1) : disponible partout où
    Python sqlite3 est compilé normalement."""
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE messages SET ack_at = ? WHERE ack_at IS NULL AND kind = 'zenoss-active' "
            "AND json_extract(fields, '$.device') = ?",
            (now_iso(), device))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ---------------------------------------------------------------- statistiques

def stats(db_path, days=30):
    """Par connecteur : volumes, taux d'échec, dernier relevé ; et la
    grille d'activité jour × connecteur pour la vue pixelgrid du hub."""
    conn = connect(db_path)
    try:
        connectors = [_public(r) for r in conn.execute("SELECT * FROM connectors ORDER BY name").fetchall()]
        per = {}
        for c in connectors:
            cid = c["id"]
            total = conn.execute("SELECT COUNT(*) n FROM messages WHERE connector_id = ?", (cid,)).fetchone()["n"]
            unparsed = conn.execute("SELECT COUNT(*) n FROM messages WHERE connector_id = ? AND parsed = 0", (cid,)).fetchone()["n"]
            failed = conn.execute(
                "SELECT COUNT(*) n FROM deliveries d JOIN messages m ON m.id = d.message_id WHERE m.connector_id = ? AND d.ok = 0", (cid,)).fetchone()["n"]
            sent = conn.execute(
                "SELECT COUNT(*) n FROM deliveries d JOIN messages m ON m.id = d.message_id WHERE m.connector_id = ? AND d.ok = 1", (cid,)).fetchone()["n"]
            per[cid] = {"messages": total, "non_interpretes": unparsed, "livraisons_ok": sent, "livraisons_ko": failed}
        grid = [dict(r) for r in conn.execute(
            "SELECT connector_id, substr(fetched_at, 1, 10) AS day, COUNT(*) AS n, "
            "SUM(CASE WHEN parsed = 0 THEN 1 ELSE 0 END) AS errors "
            "FROM messages WHERE fetched_at >= date('now', ?) GROUP BY connector_id, day",
            ("-%d days" % int(days),)).fetchall()]
        return {"connectors": connectors, "per_connector": per, "grid": grid}
    finally:
        conn.close()
