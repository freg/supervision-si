# -*- coding: utf-8 -*-
"""Base SQLite de service-watch (#531) : entrées (déclarées ou importées du
DNS), passages (qualification + constats), références de contenu, canaris
et leurs passages, événements. Jamais de secret (les identifiants restent
dans credentials-api, désignés par leur nom)."""
import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    name TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'manual',   -- manual | dns | registry
    dns_type TEXT, target TEXT, hint TEXT,
    config TEXT NOT NULL DEFAULT '{}',        -- ports, url, expected, scenario, masks, max_ms, diff_threshold_pct, kind_override, enabled
    kind TEXT, state TEXT, last_at TEXT, last_change_at TEXT,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, gone_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, at TEXT NOT NULL,
    result TEXT NOT NULL, alerts TEXT NOT NULL, state TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_name ON runs(name, at);
CREATE TABLE IF NOT EXISTS content_refs (
    name TEXT PRIMARY KEY, at TEXT NOT NULL, fingerprint TEXT NOT NULL, text TEXT NOT NULL, validated_by TEXT
);
CREATE TABLE IF NOT EXISTS canaries (
    name TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT, last_at TEXT, enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS canary_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, at TEXT NOT NULL, result TEXT NOT NULL, alerts TEXT NOT NULL, state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, subject TEXT NOT NULL, kind TEXT NOT NULL,
    severity TEXT NOT NULL, message TEXT NOT NULL, notified TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_at ON events(at);
"""


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_entry(conn, name, source="manual", dns_type=None, target=None, hint=None, config=None):
    now = now_iso()
    row = conn.execute("SELECT name, config FROM entries WHERE name = ?", (name,)).fetchone()
    if row:
        cfg = json.loads(row["config"] or "{}")
        if config:
            cfg.update(config)
        conn.execute("UPDATE entries SET last_seen = ?, gone_at = NULL, dns_type = COALESCE(?, dns_type), target = COALESCE(?, target), hint = COALESCE(?, hint), config = ? WHERE name = ?",
                     (now, dns_type, target, hint, json.dumps(cfg, ensure_ascii=False), name))
        return False
    conn.execute("INSERT INTO entries (name, source, dns_type, target, hint, config, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                 (name, source, dns_type, target, hint, json.dumps(config or {}, ensure_ascii=False), now, now))
    return True


def mark_gone(conn, source, keep_names):
    """Entrées d'une source absentes du dernier import -> gone_at (jamais supprimées)."""
    now = now_iso()
    gone = []
    for r in conn.execute("SELECT name FROM entries WHERE source = ? AND gone_at IS NULL", (source,)).fetchall():
        if r["name"] not in keep_names:
            conn.execute("UPDATE entries SET gone_at = ? WHERE name = ?", (now, r["name"]))
            gone.append(r["name"])
    return gone


def list_entries(conn, include_gone=True):
    rows = conn.execute("SELECT * FROM entries ORDER BY name").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["config"] = json.loads(d["config"] or "{}")
        if not include_gone and d.get("gone_at"):
            continue
        out.append(d)
    return out


def get_entry(conn, name):
    r = conn.execute("SELECT * FROM entries WHERE name = ?", (name,)).fetchone()
    if not r:
        return None
    d = dict(r); d["config"] = json.loads(d["config"] or "{}")
    return d


def delete_entry(conn, name):
    conn.execute("DELETE FROM entries WHERE name = ?", (name,))
    conn.execute("DELETE FROM runs WHERE name = ?", (name,))
    conn.execute("DELETE FROM content_refs WHERE name = ?", (name,))


def last_run(conn, name):
    r = conn.execute("SELECT * FROM runs WHERE name = ? ORDER BY at DESC LIMIT 1", (name,)).fetchone()
    return _run(r) if r else None


def _run(r):
    d = dict(r); d["result"] = json.loads(d["result"]); d["alerts"] = json.loads(d["alerts"])
    return d


def add_run(conn, name, result, alerts, state, keep=500):
    at = now_iso()
    conn.execute("INSERT INTO runs (name, at, result, alerts, state) VALUES (?,?,?,?,?)",
                 (name, at, json.dumps(result, ensure_ascii=False), json.dumps(alerts, ensure_ascii=False), state))
    prev = conn.execute("SELECT state, kind FROM entries WHERE name = ?", (name,)).fetchone()
    changed = bool(prev) and (prev["state"] != state or prev["kind"] != result.get("kind"))
    conn.execute("UPDATE entries SET kind = ?, state = ?, last_at = ?, last_change_at = CASE WHEN ? THEN ? ELSE last_change_at END WHERE name = ?",
                 (result.get("kind"), state, at, 1 if changed else 0, at, name))
    conn.execute("DELETE FROM runs WHERE name = ? AND id NOT IN (SELECT id FROM runs WHERE name = ? ORDER BY at DESC LIMIT ?)", (name, name, keep))
    return at


def list_runs(conn, name, limit=50):
    return [_run(r) for r in conn.execute("SELECT * FROM runs WHERE name = ? ORDER BY at DESC LIMIT ?", (name, limit)).fetchall()]


def content_ref(conn, name):
    r = conn.execute("SELECT * FROM content_refs WHERE name = ?", (name,)).fetchone()
    return dict(r) if r else None


def set_content_ref(conn, name, fingerprint, text, validated_by=None):
    conn.execute("INSERT OR REPLACE INTO content_refs (name, at, fingerprint, text, validated_by) VALUES (?,?,?,?,?)",
                 (name, now_iso(), fingerprint, text[:100000], validated_by))


def upsert_canary(conn, name, config, enabled=True):
    row = conn.execute("SELECT name FROM canaries WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute("UPDATE canaries SET config = ?, enabled = ? WHERE name = ?", (json.dumps(config, ensure_ascii=False), 1 if enabled else 0, name))
    else:
        conn.execute("INSERT INTO canaries (name, config, enabled) VALUES (?,?,?)", (name, json.dumps(config, ensure_ascii=False), 1 if enabled else 0))


def list_canaries(conn):
    out = []
    for r in conn.execute("SELECT * FROM canaries ORDER BY name").fetchall():
        d = dict(r); d["config"] = json.loads(d["config"]); d["enabled"] = bool(d["enabled"])
        d["last"] = last_canary_run(conn, d["name"])
        out.append(d)
    return out


def delete_canary(conn, name):
    conn.execute("DELETE FROM canaries WHERE name = ?", (name,))
    conn.execute("DELETE FROM canary_runs WHERE name = ?", (name,))


def add_canary_run(conn, name, result, alerts, state, keep=300):
    at = now_iso()
    conn.execute("INSERT INTO canary_runs (name, at, result, alerts, state) VALUES (?,?,?,?,?)",
                 (name, at, json.dumps(result, ensure_ascii=False), json.dumps(alerts, ensure_ascii=False), state))
    conn.execute("UPDATE canaries SET state = ?, last_at = ? WHERE name = ?", (state, at, name))
    conn.execute("DELETE FROM canary_runs WHERE name = ? AND id NOT IN (SELECT id FROM canary_runs WHERE name = ? ORDER BY at DESC LIMIT ?)", (name, name, keep))
    return at


def last_canary_run(conn, name):
    r = conn.execute("SELECT * FROM canary_runs WHERE name = ? ORDER BY at DESC LIMIT 1", (name,)).fetchone()
    return _run(r) if r else None


def list_canary_runs(conn, name, limit=50):
    return [_run(r) for r in conn.execute("SELECT * FROM canary_runs WHERE name = ? ORDER BY at DESC LIMIT ?", (name, limit)).fetchall()]


def add_event(conn, subject, kind, severity, message, notified=None):
    conn.execute("INSERT INTO events (at, subject, kind, severity, message, notified) VALUES (?,?,?,?,?,?)",
                 (now_iso(), subject, kind, severity, message[:500], notified))
    conn.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY at DESC LIMIT 5000)")


def list_events(conn, limit=200):
    return [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY at DESC, id DESC LIMIT ?", (limit,)).fetchall()]


def alert_changes(prev_alerts, new_alerts):
    """Constats apparus / disparus entre deux passages (par code)."""
    before = {a["code"]: a for a in prev_alerts or [] if a.get("severity") in ("warning", "critical")}
    after = {a["code"]: a for a in new_alerts or [] if a.get("severity") in ("warning", "critical")}
    new = [a for c, a in after.items() if c not in before or before[c]["severity"] != a["severity"]]
    gone = [a for c, a in before.items() if c not in after]
    return new, gone
