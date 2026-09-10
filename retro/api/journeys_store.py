# -*- coding: utf-8 -*-
"""Stockage SQLite des parcours (#441) : applications (avec leur dernier
scan de code), parcours, événements bruts (dans l'ordre d'arrivée),
requêtes SQL collectées. `RETRO_DATA_DIR` (volume `/data`) ; retro-api
était sans état jusqu'ici (#243 : /scan répondait sans rien garder)."""
import json
import os
import secrets
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
  label TEXT PRIMARY KEY, base_url TEXT, dba_connection_id INTEGER, dba_database TEXT,
  scan_json TEXT, scanned_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journeys (
  id TEXT PRIMARY KEY, app TEXT NOT NULL, name TEXT, tester TEXT, status TEXT NOT NULL DEFAULT 'recording',
  started_at TEXT NOT NULL, ended_at TEXT, notes TEXT, events_count INTEGER NOT NULL DEFAULT 0,
  queries_collected_at TEXT, queries_count INTEGER NOT NULL DEFAULT 0, annotations_json TEXT);
CREATE TABLE IF NOT EXISTS events (
  journey_id TEXT NOT NULL, seq INTEGER NOT NULL, at TEXT, kind TEXT NOT NULL, data TEXT,
  PRIMARY KEY (journey_id, seq));
CREATE TABLE IF NOT EXISTS queries (
  id INTEGER PRIMARY KEY AUTOINCREMENT, journey_id TEXT NOT NULL, at TEXT, sql TEXT, user TEXT, thread_id TEXT);
CREATE INDEX IF NOT EXISTS ix_queries_journey ON queries (journey_id, at);
"""


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _connect(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# #443 : arbre de parcours (sous-parcours à partir d'une étape) et rejeux
MIGRATIONS = (
    ("journeys", "parent_id", "ALTER TABLE journeys ADD COLUMN parent_id TEXT"),
    ("journeys", "branch_step", "ALTER TABLE journeys ADD COLUMN branch_step INTEGER"),
    ("journeys", "kind", "ALTER TABLE journeys ADD COLUMN kind TEXT NOT NULL DEFAULT 'recorded'"),
    ("apps", "ui_spec_json", "ALTER TABLE apps ADD COLUMN ui_spec_json TEXT"),   # #444 : interface générée
)


def ensure_schema(path):
    conn = _connect(path)
    try:
        conn.executescript(SCHEMA)
        for table, col, ddl in MIGRATIONS:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
            if col not in cols:
                conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()


def _j(s, default=None):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


# ---- applications ---------------------------------------------------------------

def upsert_app(path, label, base_url=None, dba_connection_id=None, dba_database=None):
    conn = _connect(path)
    try:
        row = conn.execute("SELECT label FROM apps WHERE label = ?", (label,)).fetchone()
        if row:
            sets, params = [], []
            for col, val in (("base_url", base_url), ("dba_connection_id", dba_connection_id), ("dba_database", dba_database)):
                if val is not None:
                    sets.append("%s = ?" % col); params.append(val)
            if sets:
                conn.execute("UPDATE apps SET %s WHERE label = ?" % ", ".join(sets), params + [label])
        else:
            conn.execute("INSERT INTO apps (label, base_url, dba_connection_id, dba_database, created_at) VALUES (?, ?, ?, ?, ?)",
                         (label, base_url, dba_connection_id, dba_database, now_iso()))
        conn.commit()
    finally:
        conn.close()
    return get_app(path, label)


def save_scan(path, label, scan):
    conn = _connect(path)
    try:
        if conn.execute("SELECT 1 FROM apps WHERE label = ?", (label,)).fetchone() is None:
            conn.execute("INSERT INTO apps (label, created_at) VALUES (?, ?)", (label, now_iso()))
        conn.execute("UPDATE apps SET scan_json = ?, scanned_at = ? WHERE label = ?", (json.dumps(scan, ensure_ascii=False), now_iso(), label))
        conn.commit()
    finally:
        conn.close()


def save_ui_spec(path, label, spec):
    conn = _connect(path)
    try:
        n = conn.execute("UPDATE apps SET ui_spec_json = ? WHERE label = ?", (json.dumps(spec, ensure_ascii=False) if spec is not None else None, label)).rowcount
        conn.commit()
    finally:
        conn.close()
    return n > 0


def get_ui_spec(path, label):
    conn = _connect(path)
    try:
        r = conn.execute("SELECT ui_spec_json FROM apps WHERE label = ?", (label,)).fetchone()
    finally:
        conn.close()
    return _j(r["ui_spec_json"], None) if r else None


def get_app(path, label, with_scan=False):
    conn = _connect(path)
    try:
        r = conn.execute("SELECT * FROM apps WHERE label = ?", (label,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return _app_public(r, with_scan)


def _app_public(r, with_scan=False):
    scan = _j(r["scan_json"], None)
    out = {"label": r["label"], "base_url": r["base_url"], "dba_connection_id": r["dba_connection_id"], "dba_database": r["dba_database"],
           "scanned_at": r["scanned_at"], "has_scan": scan is not None, "created_at": r["created_at"],
           "has_ui_spec": bool(r["ui_spec_json"]) if "ui_spec_json" in r.keys() else False,
           "scan_summary": {"routes": len(scan.get("routes") or []), "join_candidates": len(scan.get("join_candidates") or []),
                            "files": scan.get("scanned_files"), "classes": len(scan.get("classes") or {})} if scan else None}
    if with_scan:
        out["scan"] = scan
    return out


def list_apps(path):
    conn = _connect(path)
    try:
        rows = conn.execute("SELECT * FROM apps ORDER BY label").fetchall()
        counts = {r["app"]: r["n"] for r in conn.execute("SELECT app, COUNT(*) AS n FROM journeys GROUP BY app")}
    finally:
        conn.close()
    out = []
    for r in rows:
        a = _app_public(r)
        a["journeys"] = counts.get(r["label"], 0)
        out.append(a)
    return out


def delete_app(path, label):
    conn = _connect(path)
    try:
        n = conn.execute("DELETE FROM apps WHERE label = ?", (label,)).rowcount
        conn.commit()
    finally:
        conn.close()
    return n > 0


# ---- parcours ------------------------------------------------------------------

def create_journey(path, app, name=None, tester=None, base_url=None, parent_id=None, branch_step=None, kind="recorded"):
    """`parent_id` + `branch_step` (#443) : sous-parcours qui part de l'étape
    `branch_step` du parcours parent ; `kind` : recorded | replay."""
    jid = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + secrets.token_hex(3)
    conn = _connect(path)
    try:
        if conn.execute("SELECT 1 FROM apps WHERE label = ?", (app,)).fetchone() is None:
            conn.execute("INSERT INTO apps (label, base_url, created_at) VALUES (?, ?, ?)", (app, base_url, now_iso()))
        if parent_id and conn.execute("SELECT 1 FROM journeys WHERE id = ?", (parent_id,)).fetchone() is None:
            return None
        conn.execute("INSERT INTO journeys (id, app, name, tester, started_at, parent_id, branch_step, kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (jid, app, name, tester, now_iso(), parent_id, branch_step, kind if kind in ("recorded", "replay") else "recorded"))
        conn.commit()
    finally:
        conn.close()
    return get_journey(path, jid)


def get_journey(path, jid):
    conn = _connect(path)
    try:
        r = conn.execute("SELECT * FROM journeys WHERE id = ?", (jid,)).fetchone()
    finally:
        conn.close()
    return _journey_public(r) if r else None


def _journey_public(r):
    keys = r.keys()
    return {"id": r["id"], "app": r["app"], "name": r["name"], "tester": r["tester"], "status": r["status"], "started_at": r["started_at"],
            "ended_at": r["ended_at"], "notes": r["notes"], "events_count": r["events_count"], "queries_collected_at": r["queries_collected_at"],
            "queries_count": r["queries_count"], "annotations": _j(r["annotations_json"], {}) or {},
            "parent_id": r["parent_id"] if "parent_id" in keys else None, "branch_step": r["branch_step"] if "branch_step" in keys else None,
            "kind": r["kind"] if "kind" in keys else "recorded"}


def list_journeys(path, app=None):
    conn = _connect(path)
    try:
        q, params = "SELECT * FROM journeys", []
        if app:
            q += " WHERE app = ?"; params.append(app)
        rows = conn.execute(q + " ORDER BY started_at DESC", params).fetchall()
    finally:
        conn.close()
    out = [_journey_public(r) for r in rows]
    children = {}
    for j in out:
        if j.get("parent_id"):
            children[j["parent_id"]] = children.get(j["parent_id"], 0) + 1
    for j in out:
        j["children"] = children.get(j["id"], 0)
    return out


def add_events(path, jid, events):
    """Ajoute des événements (liste de {seq?, at, kind, data}) ; `seq` est
    attribué à la suite s'il manque ; un `seq` déjà reçu est ignoré (le
    relais rejoue ses lots en cas de coupure)."""
    conn = _connect(path)
    try:
        r = conn.execute("SELECT status FROM journeys WHERE id = ?", (jid,)).fetchone()
        if r is None:
            return None, "parcours inconnu"
        if r["status"] != "recording":
            return None, "parcours terminé : événements refusés"
        last = conn.execute("SELECT COALESCE(MAX(seq), 0) AS m FROM events WHERE journey_id = ?", (jid,)).fetchone()["m"]
        added = 0
        for ev in events:
            if not isinstance(ev, dict) or not ev.get("kind"):
                continue
            seq = ev.get("seq")
            if seq is None:
                last += 1; seq = last
            try:
                conn.execute("INSERT INTO events (journey_id, seq, at, kind, data) VALUES (?, ?, ?, ?, ?)",
                             (jid, int(seq), ev.get("at"), str(ev["kind"])[:40], json.dumps(ev.get("data") or {}, ensure_ascii=False)))
                added += 1
                last = max(last, int(seq))
            except sqlite3.IntegrityError:
                continue
        conn.execute("UPDATE journeys SET events_count = (SELECT COUNT(*) FROM events WHERE journey_id = ?) WHERE id = ?", (jid, jid))
        conn.commit()
        total = conn.execute("SELECT events_count FROM journeys WHERE id = ?", (jid,)).fetchone()["events_count"]
    finally:
        conn.close()
    return {"added": added, "events_count": total}, None


def get_events(path, jid):
    conn = _connect(path)
    try:
        rows = conn.execute("SELECT seq, at, kind, data FROM events WHERE journey_id = ? ORDER BY seq", (jid,)).fetchall()
    finally:
        conn.close()
    return [{"seq": r["seq"], "at": r["at"], "kind": r["kind"], "data": _j(r["data"], {}) or {}} for r in rows]


def end_journey(path, jid, notes=None):
    conn = _connect(path)
    try:
        n = conn.execute("UPDATE journeys SET status = 'done', ended_at = COALESCE(ended_at, ?), notes = COALESCE(?, notes) WHERE id = ?",
                         (now_iso(), notes, jid)).rowcount
        conn.commit()
    finally:
        conn.close()
    return n > 0


def annotate(path, jid, step, text):
    conn = _connect(path)
    try:
        r = conn.execute("SELECT annotations_json FROM journeys WHERE id = ?", (jid,)).fetchone()
        if r is None:
            return None
        ann = _j(r["annotations_json"], {}) or {}
        if text:
            ann[str(step)] = text
        else:
            ann.pop(str(step), None)
        conn.execute("UPDATE journeys SET annotations_json = ? WHERE id = ?", (json.dumps(ann, ensure_ascii=False), jid))
        conn.commit()
    finally:
        conn.close()
    return ann


def delete_journey(path, jid):
    conn = _connect(path)
    try:
        n = conn.execute("DELETE FROM journeys WHERE id = ?", (jid,)).rowcount
        conn.execute("DELETE FROM events WHERE journey_id = ?", (jid,))
        conn.execute("DELETE FROM queries WHERE journey_id = ?", (jid,))
        conn.commit()
    finally:
        conn.close()
    return n > 0


# ---- requêtes SQL collectées -----------------------------------------------------------

def replace_queries(path, jid, queries):
    conn = _connect(path)
    try:
        conn.execute("DELETE FROM queries WHERE journey_id = ?", (jid,))
        conn.executemany("INSERT INTO queries (journey_id, at, sql, user, thread_id) VALUES (?, ?, ?, ?, ?)",
                         [(jid, q.get("at"), q.get("sql"), q.get("user"), q.get("thread_id")) for q in queries])
        conn.execute("UPDATE journeys SET queries_collected_at = ?, queries_count = ? WHERE id = ?", (now_iso(), len(queries), jid))
        conn.commit()
    finally:
        conn.close()
    return len(queries)


def get_queries(path, jid):
    conn = _connect(path)
    try:
        rows = conn.execute("SELECT at, sql, user, thread_id FROM queries WHERE journey_id = ? ORDER BY at, id", (jid,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
