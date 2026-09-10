"""Sondes distribuées côté CENTRAL (livraison #406, items 45/47/48) --
flotte (sondes et collecteurs, secrets, tâches) et mesures remontées.

Module séparé de store.py, volontairement : store.py porte les volets
"actifs" exécutés PAR le conteneur central (smokeping, nmap, iperf3...),
celui-ci porte ce qui est exécuté AILLEURS (Raspberry Pi sur le site) et
seulement collecté ici. Même base SQLite, même motif (`CREATE TABLE IF
NOT EXISTS` ré-exécuté au démarrage, `PRAGMA foreign_keys = ON`).

Secrets : un secret par appareil, généré ici (`secrets.token_urlsafe`),
stocké EN CLAIR -- il doit l'être, la vérification HMAC exige le secret
lui-même (pas de hachage possible, contrairement à un mot de passe). Même
niveau de confiance que les autres API de module (LAN + passerelle) ;
les routes de lecture ne le renvoient JAMAIS sauf `provision` et la
flotte signée d'un collecteur, qui en ont besoin par construction.
"""
import json
import secrets as _secrets
import sqlite3
import time

ROLES = ("probe", "collector")

SCHEMA = """
CREATE TABLE IF NOT EXISTS probe_agents (
    agent_id TEXT PRIMARY KEY,
    site TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('probe', 'collector')),
    label TEXT,
    secret TEXT NOT NULL,
    tasks TEXT NOT NULL DEFAULT '[]',
    tasks_version TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT,
    last_seen_via TEXT,
    last_ip TEXT
);
CREATE INDEX IF NOT EXISTS idx_probe_agents_site ON probe_agents(site);

CREATE TABLE IF NOT EXISTS agent_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    site TEXT,
    task TEXT NOT NULL,
    at TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 1,
    data TEXT,
    error TEXT,
    received_at TEXT NOT NULL,
    via TEXT,
    UNIQUE(agent_id, task, at)
);
CREATE INDEX IF NOT EXISTS idx_agent_measurements_agent_task ON agent_measurements(agent_id, task, at);
CREATE INDEX IF NOT EXISTS idx_agent_measurements_site_at ON agent_measurements(site, at);
"""

AGENT_ID_MAX = 64


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def valid_agent_id(agent_id):
    """Identifiant = segment d'URL et nom de fichier : lettres, chiffres,
    tiret, point, souligné, 64 max -- jamais interpolé en SQL de toute
    façon (toujours lié), mais il finit dans des chemins et des noms
    d'hôte, donc restreint."""
    if not isinstance(agent_id, str) or not 1 <= len(agent_id) <= AGENT_ID_MAX:
        return False
    return all(c.isalnum() or c in "-._" for c in agent_id) and agent_id[0].isalnum()


def _row_public(r):
    d = dict(r)
    d.pop("secret", None)
    d["tasks"] = json.loads(d.get("tasks") or "[]")
    d["active"] = bool(d.get("active"))
    return d


def _bump_version():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + _secrets.token_hex(2)


# ------------------------------------------------------------------
# Flotte
# ------------------------------------------------------------------

def create_agent(db_path, agent_id, site, role, label=None, tasks=None):
    """Crée l'appareil et renvoie son enregistrement AVEC le secret -- la
    seule fois où il est renvoyé par une route de création."""
    if not valid_agent_id(agent_id):
        raise ValueError("agent_id invalide (lettres, chiffres, - . _ ; 64 max)")
    if role not in ROLES:
        raise ValueError("role doit être 'probe' ou 'collector'")
    if not isinstance(site, str) or not site.strip():
        raise ValueError("site requis")
    tasks = tasks if isinstance(tasks, list) else []
    secret = _secrets.token_urlsafe(32)
    now = now_iso()
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO probe_agents(agent_id, site, role, label, secret, tasks, tasks_version, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (agent_id, site.strip(), role, (label or "").strip() or None, secret, json.dumps(tasks, ensure_ascii=False),
             _bump_version(), now, now))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("agent_id déjà utilisé : %s" % agent_id)
    finally:
        conn.close()
    out = get_agent(db_path, agent_id)
    out["secret"] = secret
    return out


def get_agent(db_path, agent_id, with_secret=False):
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT * FROM probe_agents WHERE agent_id = ?", (agent_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    d = _row_public(r)
    if with_secret:
        d["secret"] = r["secret"]
    return d


def get_secret(db_path, agent_id):
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT secret, role, site, active FROM probe_agents WHERE agent_id = ?", (agent_id,)).fetchone()
    finally:
        conn.close()
    if r is None or not r["active"]:
        return None
    return {"secret": r["secret"], "role": r["role"], "site": r["site"]}


def list_agents(db_path, site=None, role=None):
    conn = _connect(db_path)
    try:
        sql = "SELECT * FROM probe_agents WHERE 1=1"
        params = []
        if site:
            sql += " AND site = ?"; params.append(site)
        if role:
            sql += " AND role = ?"; params.append(role)
        sql += " ORDER BY site, role, agent_id"
        return [_row_public(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def update_agent(db_path, agent_id, label=None, active=None, tasks=None, site=None):
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT * FROM probe_agents WHERE agent_id = ?", (agent_id,)).fetchone()
        if r is None:
            return None
        fields, params = [], []
        if label is not None:
            fields.append("label = ?"); params.append(label.strip() or None)
        if active is not None:
            fields.append("active = ?"); params.append(1 if active else 0)
        if site is not None and site.strip():
            fields.append("site = ?"); params.append(site.strip())
        if tasks is not None:
            if not isinstance(tasks, list):
                raise ValueError("tasks doit être une liste")
            fields.append("tasks = ?"); params.append(json.dumps(tasks, ensure_ascii=False))
            fields.append("tasks_version = ?"); params.append(_bump_version())
        if not fields:
            return _row_public(r)
        fields.append("updated_at = ?"); params.append(now_iso())
        params.append(agent_id)
        conn.execute("UPDATE probe_agents SET %s WHERE agent_id = ?" % ", ".join(fields), params)
        conn.commit()
    finally:
        conn.close()
    return get_agent(db_path, agent_id)


def rotate_secret(db_path, agent_id):
    secret = _secrets.token_urlsafe(32)
    conn = _connect(db_path)
    try:
        cur = conn.execute("UPDATE probe_agents SET secret = ?, updated_at = ? WHERE agent_id = ?", (secret, now_iso(), agent_id))
        conn.commit()
        if cur.rowcount == 0:
            return None
    finally:
        conn.close()
    out = get_agent(db_path, agent_id)
    out["secret"] = secret
    return out


def delete_agent(db_path, agent_id, purge_measurements=False):
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM probe_agents WHERE agent_id = ?", (agent_id,))
        if purge_measurements:
            conn.execute("DELETE FROM agent_measurements WHERE agent_id = ?", (agent_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def fleet_for_site(db_path, site):
    """Ce qu'un COLLECTEUR du site reçoit : les sondes actives du site avec
    leurs secrets et leurs tâches (il doit vérifier leurs signatures et
    leur servir leurs tâches). Jamais les autres collecteurs, jamais les
    autres sites. `version` = la plus récente des versions de tâches +
    le nombre de sondes, pour que le collecteur détecte un changement."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT agent_id, secret, tasks, tasks_version, updated_at FROM probe_agents "
            "WHERE site = ? AND role = 'probe' AND active = 1 ORDER BY agent_id", (site,)).fetchall()
    finally:
        conn.close()
    agents = {}
    latest = ""
    for r in rows:
        agents[r["agent_id"]] = {"secret": r["secret"], "tasks": json.loads(r["tasks"] or "[]"), "tasks_version": r["tasks_version"]}
        latest = max(latest, r["updated_at"] or "")
    return {"site": site, "agents": agents, "version": "%s-%d" % (latest or "0", len(agents))}


def touch_agent(conn, agent_id, via, ip):
    conn.execute("UPDATE probe_agents SET last_seen_at = ?, last_seen_via = ?, last_ip = ? WHERE agent_id = ?",
                 (now_iso(), via, ip, agent_id))


# ------------------------------------------------------------------
# Mesures
# ------------------------------------------------------------------

def ingest_measurements(db_path, measurements, via, ip=None, only_agent=None, site=None):
    """Insère un lot ; renvoie (acceptées, doublons, rejetées[]). Une
    mesure dont l'agent est inconnu ou inactif est rejetée -- jamais une
    ligne orpheline. `only_agent` : une SONDE qui parle directement au
    central ne peut écrire que pour elle-même."""
    conn = _connect(db_path)
    accepted, duplicates, rejected = 0, 0, []
    known = {}
    try:
        for i, m in enumerate(measurements):
            if not isinstance(m, dict) or not isinstance(m.get("task"), str) or not isinstance(m.get("at"), str) \
                    or not m["task"] or not m["at"]:
                rejected.append({"index": i, "error": "forme invalide (task/at)"})
                continue
            agent_id = m.get("agent_id") if only_agent is None else only_agent
            if not isinstance(agent_id, str):
                rejected.append({"index": i, "error": "agent_id manquant"})
                continue
            if agent_id not in known:
                r = conn.execute("SELECT site, active FROM probe_agents WHERE agent_id = ?", (agent_id,)).fetchone()
                known[agent_id] = (r["site"] if r and r["active"] else None)
            agent_site = known[agent_id]
            if agent_site is None:
                rejected.append({"index": i, "error": "sonde inconnue ou inactive : %s" % agent_id})
                continue
            if site is not None and agent_site != site:
                rejected.append({"index": i, "error": "sonde %s hors du site du collecteur" % agent_id})
                continue
            data = m.get("data")
            try:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO agent_measurements(agent_id, site, task, at, ok, data, error, received_at, via) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (agent_id, agent_site, m["task"], m["at"], 1 if m.get("ok", True) else 0,
                     json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else None,
                     (m.get("error") or None), now_iso(), via))
            except sqlite3.DatabaseError as exc:
                rejected.append({"index": i, "error": str(exc)[:120]})
                continue
            if cur.rowcount:
                accepted += 1
            else:
                duplicates += 1
        for agent_id, agent_site in known.items():
            if agent_site is not None:
                touch_agent(conn, agent_id, via, ip)
        conn.commit()
    finally:
        conn.close()
    return accepted, duplicates, rejected


def list_measurements(db_path, agent_id, task=None, limit=200, since=None):
    conn = _connect(db_path)
    try:
        sql = "SELECT agent_id, task, at, ok, data, error, received_at, via FROM agent_measurements WHERE agent_id = ?"
        params = [agent_id]
        if task:
            sql += " AND task = ?"; params.append(task)
        if since:
            sql += " AND at >= ?"; params.append(since)
        sql += " ORDER BY at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 5000)))
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_measurement(r) for r in rows]


def _measurement(r):
    return {"agent_id": r["agent_id"], "task": r["task"], "at": r["at"], "ok": bool(r["ok"]),
            "data": json.loads(r["data"]) if r["data"] else None, "error": r["error"],
            "received_at": r["received_at"], "via": r["via"]}


def latest_per_agent_task(db_path, site=None):
    """Dernière mesure de chaque (sonde, tâche) -- ce que l'onglet du hub
    affiche en tableau. Une seule requête, jamais N+1."""
    conn = _connect(db_path)
    try:
        sql = ("SELECT m.agent_id, m.task, m.at, m.ok, m.data, m.error, m.received_at, m.via "
               "FROM agent_measurements m JOIN (SELECT agent_id, task, MAX(at) AS at FROM agent_measurements "
               "%s GROUP BY agent_id, task) x ON x.agent_id = m.agent_id AND x.task = m.task AND x.at = m.at")
        params = []
        if site:
            sql = sql % "WHERE site = ?"; params.append(site)
        else:
            sql = sql % ""
        rows = conn.execute(sql + " ORDER BY m.agent_id, m.task", params).fetchall()
    finally:
        conn.close()
    return [_measurement(r) for r in rows]


def prune_measurements(db_path, keep_days=90):
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - keep_days * 86400))
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM agent_measurements WHERE at < ?", (cutoff,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
