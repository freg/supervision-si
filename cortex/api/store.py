# -*- coding: utf-8 -*-
"""Persistance de Cortex (livraison #462) -- SQLite : entités fusionnées,
relations, événements normalisés avec cycle de vie (open / acked /
closed, compteur de répétition), incidents (état, accusé, hypothèses),
retours humains par principe (l'évaluation des partis pris), journal des
collectes (transparence : qui a répondu, combien, en combien de temps).
"""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    key TEXT PRIMARY KEY, kind TEXT, name TEXT, ip TEXT, mac TEXT, site TEXT,
    origins_json TEXT, hints_json TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relations (
    a TEXT NOT NULL, b TEXT NOT NULL, kind TEXT NOT NULL, weight REAL, principle TEXT, evidence TEXT, source TEXT,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY (a, b, kind, source)
);
CREATE TABLE IF NOT EXISTS events (
    fingerprint TEXT PRIMARY KEY, source TEXT, kind TEXT, severity TEXT, entity TEXT, site TEXT, message TEXT, raw_ref TEXT,
    at TEXT, first_at TEXT, last_at TEXT, count INTEGER DEFAULT 1, state TEXT DEFAULT 'open',
    acked_by TEXT, acked_at TEXT, closed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_state ON events(state, last_at);
CREATE TABLE IF NOT EXISTS incidents (
    key TEXT PRIMARY KEY, severity TEXT, state TEXT DEFAULT 'open', opened_at TEXT, last_at TEXT, closed_at TEXT,
    root TEXT, title TEXT, confidence REAL, weak INTEGER, entities_json TEXT, events_json TEXT, hypotheses_json TEXT, sources_json TEXT,
    acked_by TEXT, acked_at TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, principle TEXT NOT NULL, verdict TEXT NOT NULL,
    incident_key TEXT, claim TEXT, by_user TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, duration_ms INTEGER, sources_json TEXT, counts_json TEXT
);
"""


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect(db_path):
    c = sqlite3.connect(db_path, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def ensure_schema(db_path):
    c = connect(db_path)
    try:
        c.executescript(SCHEMA)
        c.commit()
    finally:
        c.close()


def _row(r, json_fields=()):
    d = dict(r)
    for f in json_fields:
        if f in d:
            try:
                d[f[:-5]] = json.loads(d.pop(f) or "null")
            except ValueError:
                d[f[:-5]] = None
    return d


# ---------------------------------------------------------------- entités / relations
def upsert_entities(db_path, entities):
    now = now_iso()
    c = connect(db_path)
    try:
        for e in entities:
            c.execute("""INSERT INTO entities (key, kind, name, ip, mac, site, origins_json, hints_json, first_seen, last_seen)
                         VALUES (?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(key) DO UPDATE SET kind=excluded.kind, name=COALESCE(excluded.name, entities.name),
                           ip=COALESCE(excluded.ip, entities.ip), mac=COALESCE(excluded.mac, entities.mac), site=COALESCE(excluded.site, entities.site),
                           origins_json=excluded.origins_json, hints_json=excluded.hints_json, last_seen=excluded.last_seen""",
                      (e["key"], e.get("kind"), e.get("name"), e.get("ip"), e.get("mac"), e.get("site"),
                       json.dumps(e.get("origins") or []), json.dumps(e.get("hints") or []), now, now))
        c.commit()
    finally:
        c.close()


def upsert_relations(db_path, relations):
    now = now_iso()
    c = connect(db_path)
    try:
        for r in relations:
            c.execute("""INSERT INTO relations (a, b, kind, weight, principle, evidence, source, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(a, b, kind, source) DO UPDATE SET weight=excluded.weight, evidence=excluded.evidence, last_seen=excluded.last_seen""",
                      (r["a"], r["b"], r["kind"], r.get("weight"), r.get("principle"), r.get("evidence"), r.get("source"), now, now))
        c.commit()
    finally:
        c.close()


def list_entities(db_path, q=None, limit=500):
    c = connect(db_path)
    try:
        if q:
            like = "%%%s%%" % q
            rows = c.execute("SELECT * FROM entities WHERE key LIKE ? OR name LIKE ? OR ip LIKE ? OR site LIKE ? ORDER BY last_seen DESC LIMIT ?", (like, like, like, like, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM entities ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
        return [_row(r, ("origins_json", "hints_json")) for r in rows]
    finally:
        c.close()


def get_entity(db_path, key):
    c = connect(db_path)
    try:
        r = c.execute("SELECT * FROM entities WHERE key=?", (key,)).fetchone()
        return _row(r, ("origins_json", "hints_json")) if r else None
    finally:
        c.close()


def list_relations(db_path, entity=None, fresh_hours=None):
    c = connect(db_path)
    try:
        if entity:
            rows = c.execute("SELECT * FROM relations WHERE a=? OR b=? ORDER BY weight DESC", (entity, entity)).fetchall()
        else:
            rows = c.execute("SELECT * FROM relations").fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


# ---------------------------------------------------------------- événements
def upsert_events(db_path, events):
    """Un événement déjà connu (empreinte) est rafraîchi (last_at, count) ;
    un événement fermé qui revient est rouvert. -> (nouveaux, rafraîchis)"""
    now = now_iso()
    new, refreshed = 0, 0
    c = connect(db_path)
    try:
        for e in events:
            at = e.get("at") or now
            r = c.execute("SELECT state, count FROM events WHERE fingerprint=?", (e["fingerprint"],)).fetchone()
            if r is None:
                c.execute("INSERT INTO events (fingerprint, source, kind, severity, entity, site, message, raw_ref, at, first_at, last_at, count, state) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,'open')",
                          (e["fingerprint"], e.get("source"), e.get("kind"), e.get("severity"), e.get("entity"), e.get("site"), e.get("message"), e.get("raw_ref"), at, at, at))
                new += 1
            else:
                state = "open" if r["state"] == "closed" else r["state"]
                c.execute("UPDATE events SET last_at=?, count=count+1, message=?, severity=?, state=?, closed_at=NULL WHERE fingerprint=?",
                          (max(at, r["state"] and at), e.get("message"), e.get("severity"), state, e["fingerprint"]))
                refreshed += 1
        c.commit()
    finally:
        c.close()
    return new, refreshed


def close_missing_events(db_path, seen_fingerprints, sources):
    """Un événement ouvert d'une source collectée avec succès qui n'est plus
    remonté est FERMÉ (la source ne le voit plus) -- sauf ceux à identifiant
    source unique (raw_ref d'événement historique), qui ne se ferment que par accusé."""
    now = now_iso()
    c = connect(db_path)
    try:
        rows = c.execute("SELECT fingerprint, source, raw_ref FROM events WHERE state IN ('open','acked')").fetchall()
        closed = 0
        for r in rows:
            if r["source"] in sources and r["fingerprint"] not in seen_fingerprints and ":event:" not in (r["raw_ref"] or ""):
                c.execute("UPDATE events SET state='closed', closed_at=? WHERE fingerprint=?", (now, r["fingerprint"]))
                closed += 1
        c.commit()
        return closed
    finally:
        c.close()


def list_events(db_path, state=None, severity=None, since=None, entity=None, limit=300):
    c = connect(db_path)
    try:
        q, args = "SELECT * FROM events WHERE 1=1", []
        if state and state != "all":
            q += " AND state=?"; args.append(state)
        if severity:
            q += " AND severity=?"; args.append(severity)
        if since:
            q += " AND last_at>=?"; args.append(since)
        if entity:
            q += " AND entity=?"; args.append(entity)
        q += " ORDER BY last_at DESC LIMIT ?"; args.append(limit)
        return [dict(r) for r in c.execute(q, args).fetchall()]
    finally:
        c.close()


def set_event_state(db_path, fingerprint, state, by=None):
    now = now_iso()
    c = connect(db_path)
    try:
        if state == "acked":
            n = c.execute("UPDATE events SET state='acked', acked_by=?, acked_at=? WHERE fingerprint=? AND state='open'", (by, now, fingerprint)).rowcount
        elif state == "closed":
            n = c.execute("UPDATE events SET state='closed', closed_at=? WHERE fingerprint=? AND state!='closed'", (now, fingerprint)).rowcount
        else:
            n = 0
        c.commit()
        return n > 0
    finally:
        c.close()


# ---------------------------------------------------------------- incidents
def sync_incidents(db_path, computed):
    """Aligne la table sur les incidents recalculés : un incident dont la clé
    existe garde son état (acked) et son accusé ; un incident absent du
    calcul (tous ses événements fermés) est fermé ; un nouveau est ouvert."""
    now = now_iso()
    keys = {i["key"] for i in computed}
    c = connect(db_path)
    try:
        existing = {r["key"]: dict(r) for r in c.execute("SELECT key, state, acked_by, acked_at FROM incidents").fetchall()}
        for i in computed:
            ex = existing.get(i["key"])
            state = ex["state"] if ex and ex["state"] == "acked" else "open"
            c.execute("""INSERT INTO incidents (key, severity, state, opened_at, last_at, closed_at, root, title, confidence, weak, entities_json, events_json, hypotheses_json, sources_json, acked_by, acked_at)
                         VALUES (?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(key) DO UPDATE SET severity=excluded.severity, state=?, last_at=excluded.last_at, closed_at=NULL, root=excluded.root, title=excluded.title,
                           confidence=excluded.confidence, weak=excluded.weak, entities_json=excluded.entities_json, events_json=excluded.events_json, hypotheses_json=excluded.hypotheses_json, sources_json=excluded.sources_json""",
                      (i["key"], i["severity"], state, i["opened_at"] or now, i["last_at"] or now, i["root"], i["title"], i["confidence"], 1 if i.get("weak") else 0,
                       json.dumps(i["entities"]), json.dumps(i["events"]), json.dumps(i["hypotheses"], ensure_ascii=False), json.dumps(i.get("sources") or []),
                       ex["acked_by"] if ex else None, ex["acked_at"] if ex else None, state))
        for k, ex in existing.items():
            if k not in keys and ex["state"] != "closed":
                c.execute("UPDATE incidents SET state='closed', closed_at=? WHERE key=?", (now, k))
        c.commit()
    finally:
        c.close()


def list_incidents(db_path, state="open", limit=200):
    c = connect(db_path)
    try:
        if state == "all":
            rows = c.execute("SELECT * FROM incidents ORDER BY (state='closed'), CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, last_at DESC LIMIT ?", (limit,)).fetchall()
        elif state == "open":
            rows = c.execute("SELECT * FROM incidents WHERE state IN ('open','acked') ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, last_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM incidents WHERE state=? ORDER BY last_at DESC LIMIT ?", (state, limit)).fetchall()
        return [_row(r, ("entities_json", "events_json", "hypotheses_json", "sources_json")) for r in rows]
    finally:
        c.close()


def get_incident(db_path, key):
    c = connect(db_path)
    try:
        r = c.execute("SELECT * FROM incidents WHERE key=?", (key,)).fetchone()
        return _row(r, ("entities_json", "events_json", "hypotheses_json", "sources_json")) if r else None
    finally:
        c.close()


def set_incident_state(db_path, key, state, by=None):
    now = now_iso()
    c = connect(db_path)
    try:
        if state == "acked":
            n = c.execute("UPDATE incidents SET state='acked', acked_by=?, acked_at=? WHERE key=? AND state='open'", (by, now, key)).rowcount
            fps = json.loads((c.execute("SELECT events_json FROM incidents WHERE key=?", (key,)).fetchone() or {"events_json": "[]"})["events_json"])
            for fp in fps:
                c.execute("UPDATE events SET state='acked', acked_by=?, acked_at=? WHERE fingerprint=? AND state='open'", (by, now, fp))
        elif state == "closed":
            n = c.execute("UPDATE incidents SET state='closed', closed_at=? WHERE key=? AND state!='closed'", (now, key)).rowcount
            fps = json.loads((c.execute("SELECT events_json FROM incidents WHERE key=?", (key,)).fetchone() or {"events_json": "[]"})["events_json"])
            for fp in fps:
                c.execute("UPDATE events SET state='closed', closed_at=? WHERE fingerprint=? AND state!='closed'", (now, fp))
        else:
            n = 0
        c.commit()
        return n > 0
    finally:
        c.close()


# ---------------------------------------------------------------- retours et journal
def add_feedback(db_path, principle, verdict, incident_key=None, claim=None, by=None, note=None):
    c = connect(db_path)
    try:
        c.execute("INSERT INTO feedback (at, principle, verdict, incident_key, claim, by_user, note) VALUES (?,?,?,?,?,?,?)",
                  (now_iso(), principle, verdict, incident_key, claim, by, note))
        c.commit()
    finally:
        c.close()


def feedback_counts(db_path):
    """{principe: {confirmed, rejected, applied}} -- applied = nombre
    d'hypothèses émises portant ce principe dans les incidents connus."""
    c = connect(db_path)
    try:
        out = {}
        for r in c.execute("SELECT principle, verdict, COUNT(*) n FROM feedback GROUP BY principle, verdict").fetchall():
            out.setdefault(r["principle"], {"confirmed": 0, "rejected": 0, "applied": 0})
            if r["verdict"] in ("confirmed", "rejected"):
                out[r["principle"]][r["verdict"]] += r["n"]
        for r in c.execute("SELECT hypotheses_json FROM incidents").fetchall():
            try:
                for h in json.loads(r["hypotheses_json"] or "[]"):
                    out.setdefault(h.get("principle"), {"confirmed": 0, "rejected": 0, "applied": 0})["applied"] += 1
            except ValueError:
                pass
        return out
    finally:
        c.close()


def list_feedback(db_path, limit=100):
    c = connect(db_path)
    try:
        return [dict(r) for r in c.execute("SELECT * FROM feedback ORDER BY at DESC LIMIT ?", (limit,)).fetchall()]
    finally:
        c.close()


def add_run(db_path, duration_ms, sources, counts):
    c = connect(db_path)
    try:
        c.execute("INSERT INTO runs (at, duration_ms, sources_json, counts_json) VALUES (?,?,?,?)", (now_iso(), duration_ms, json.dumps(sources, ensure_ascii=False), json.dumps(counts)))
        c.execute("DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT 200)")
        c.commit()
    finally:
        c.close()


def list_runs(db_path, limit=20):
    c = connect(db_path)
    try:
        return [_row(r, ("sources_json", "counts_json")) for r in c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    finally:
        c.close()


def purge(db_path, days=30):
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400))
    c = connect(db_path)
    try:
        c.execute("DELETE FROM events WHERE state='closed' AND closed_at < ?", (cutoff,))
        c.execute("DELETE FROM incidents WHERE state='closed' AND closed_at < ?", (cutoff,))
        c.execute("DELETE FROM relations WHERE last_seen < ?", (cutoff,))
        c.commit()
    finally:
        c.close()
