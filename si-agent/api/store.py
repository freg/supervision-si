"""si-agent-api -- stockage du central des agents hôtes (livraison #421,
backlog 63). Même motif que netprobe/api/agents_store.py : SQLite,
`CREATE TABLE IF NOT EXISTS` ré-exécuté au démarrage, un secret par agent
généré ici et stocké en clair (la vérification HMAC exige le secret
lui-même), jamais renvoyé par les lectures sauf `install` (qui sert à
l'écrire sur l'hôte).

Quatre familles :
  - agents : flotte (identité, site, secret, réglages poussés : intervalle
    et seuils de risques), dernier contact ;
  - measurements : tout ce que les agents remontent (host, risks,
    inventory, plugin:<id>), dédupliqué sur (agent, tâche, instant) ;
  - plugins : CATALOGUE central de sondes (manifeste + corps du script) ;
    agent_plugins : affectation d'un plugin à un agent (activé ou non) ;
  - commands : ordres du tableau de bord vers un agent, acquittés par lui.

Version de configuration d'un agent = empreinte déterministe de ses
réglages + plugins affectés (id, version, activation, sha256) : l'agent
ne réapplique la configuration que si l'empreinte change.
"""
import calendar
import hashlib
import json
import secrets as _secrets
import sqlite3
import time

import si_agent_plugins as plugin_lib

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    site TEXT NOT NULL,
    label TEXT,
    secret TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    host_interval_seconds INTEGER NOT NULL DEFAULT 60,
    risk_thresholds TEXT NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT,
    last_ip TEXT,
    last_config_version TEXT,
    hostname TEXT,
    os TEXT,
    agent_version TEXT
);
CREATE INDEX IF NOT EXISTS idx_agents_site ON agents(site);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    task TEXT NOT NULL,
    at TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 1,
    data TEXT,
    error TEXT,
    received_at TEXT NOT NULL,
    UNIQUE(agent_id, task, at)
);
CREATE INDEX IF NOT EXISTS idx_measurements_agent_task ON measurements(agent_id, task, at);

CREATE TABLE IF NOT EXISTS plugins (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    runner TEXT NOT NULL,
    entry TEXT NOT NULL,
    interval_seconds INTEGER NOT NULL DEFAULT 3600,
    timeout_seconds INTEGER NOT NULL DEFAULT 60,
    args TEXT NOT NULL DEFAULT '[]',
    description TEXT,
    body TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_plugins (
    agent_id TEXT NOT NULL,
    plugin_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (agent_id, plugin_id)
);

CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    type TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    acked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_commands_agent_status ON commands(agent_id, status);
"""

AGENT_ID_MAX = 64
COMMAND_TYPES = ("collect_now", "run_plugin", "enable_plugin", "disable_plugin", "remove_plugin", "flush")
TASKS_KEPT_LATEST = ("host", "risks", "inventory")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _connect(db_path):
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


def valid_agent_id(agent_id):
    if not isinstance(agent_id, str) or not 1 <= len(agent_id) <= AGENT_ID_MAX:
        return False
    return all(c.isalnum() or c in "-._" for c in agent_id) and agent_id[0].isalnum()


def _agent_public(r):
    d = dict(r)
    d.pop("secret", None)
    d["active"] = bool(d.get("active"))
    d["risk_thresholds"] = json.loads(d.get("risk_thresholds") or "{}")
    return d


# ------------------------------------------------------------------
# Flotte
# ------------------------------------------------------------------

def create_agent(db_path, agent_id, site, label=None, host_interval_seconds=None, risk_thresholds=None, notes=None):
    """Renvoie l'enregistrement AVEC le secret -- la seule fois (avec
    install/rotate-secret) où il sort de la base."""
    if not valid_agent_id(agent_id):
        raise ValueError("agent_id invalide (lettres, chiffres, - . _ ; 64 max)")
    if not isinstance(site, str) or not site.strip():
        raise ValueError("site requis")
    interval = _interval(host_interval_seconds, 60)
    thresholds = _thresholds(risk_thresholds)
    secret = _secrets.token_urlsafe(32)
    now = now_iso()
    conn = _connect(db_path)
    try:
        try:
            conn.execute(
                "INSERT INTO agents (agent_id, site, label, secret, host_interval_seconds, risk_thresholds, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (agent_id, site.strip(), label, secret, interval, json.dumps(thresholds), notes, now, now))
        except sqlite3.IntegrityError:
            raise ValueError("agent %s déjà déclaré" % agent_id)
        conn.commit()
        r = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    finally:
        conn.close()
    d = _agent_public(r)
    d["secret"] = secret
    return d


def _interval(value, default):
    if value is None or value == "":
        return default
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError("host_interval_seconds : entier attendu")
    if v < 10:
        raise ValueError("host_interval_seconds : 10 s minimum")
    return v


def _thresholds(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("risk_thresholds : objet attendu")
    out = {}
    for k, v in value.items():
        if v is None or v == "":
            continue
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            raise ValueError("risk_thresholds.%s : nombre attendu" % k)
    return out


def list_agents(db_path, site=None):
    conn = _connect(db_path)
    try:
        if site:
            rows = conn.execute("SELECT * FROM agents WHERE site = ? ORDER BY site, agent_id", (site,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM agents ORDER BY site, agent_id").fetchall()
        return [_agent_public(r) for r in rows]
    finally:
        conn.close()


def get_agent(db_path, agent_id, with_secret=False):
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    d = _agent_public(r)
    if with_secret:
        d["secret"] = r["secret"]
    return d


def get_secret(db_path, agent_id):
    """Secret d'un agent ACTIF (authentification) ; None sinon."""
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT secret, site, active FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    finally:
        conn.close()
    if r is None or not r["active"]:
        return None
    return {"secret": r["secret"], "site": r["site"]}


def update_agent(db_path, agent_id, label=None, active=None, site=None, host_interval_seconds=None, risk_thresholds=None, notes=None):
    sets, params = [], []
    if label is not None:
        sets.append("label = ?"); params.append(label)
    if active is not None:
        sets.append("active = ?"); params.append(1 if active else 0)
    if site is not None:
        if not isinstance(site, str) or not site.strip():
            raise ValueError("site requis")
        sets.append("site = ?"); params.append(site.strip())
    if host_interval_seconds is not None:
        sets.append("host_interval_seconds = ?"); params.append(_interval(host_interval_seconds, 60))
    if risk_thresholds is not None:
        sets.append("risk_thresholds = ?"); params.append(json.dumps(_thresholds(risk_thresholds)))
    if notes is not None:
        sets.append("notes = ?"); params.append(notes)
    if not sets:
        return get_agent(db_path, agent_id)
    sets.append("updated_at = ?"); params.append(now_iso())
    params.append(agent_id)
    conn = _connect(db_path)
    try:
        cur = conn.execute("UPDATE agents SET %s WHERE agent_id = ?" % ", ".join(sets), params)
        conn.commit()
        if cur.rowcount == 0:
            return None
    finally:
        conn.close()
    return get_agent(db_path, agent_id)


def rotate_secret(db_path, agent_id):
    secret = _secrets.token_urlsafe(32)
    conn = _connect(db_path)
    try:
        cur = conn.execute("UPDATE agents SET secret = ?, updated_at = ? WHERE agent_id = ?", (secret, now_iso(), agent_id))
        conn.commit()
        if cur.rowcount == 0:
            return None
    finally:
        conn.close()
    d = get_agent(db_path, agent_id)
    d["secret"] = secret
    return d


def delete_agent(db_path, agent_id, purge_measurements=False):
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM agent_plugins WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM commands WHERE agent_id = ?", (agent_id,))
        if purge_measurements:
            conn.execute("DELETE FROM measurements WHERE agent_id = ?", (agent_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def touch_agent(conn, agent_id, ip=None, config_version=None):
    sets = ["last_seen_at = ?"]
    params = [now_iso()]
    if ip:
        sets.append("last_ip = ?"); params.append(ip)
    if config_version is not None:
        sets.append("last_config_version = ?"); params.append(config_version)
    params.append(agent_id)
    conn.execute("UPDATE agents SET %s WHERE agent_id = ?" % ", ".join(sets), params)


# ------------------------------------------------------------------
# Catalogue de plugins et affectations
# ------------------------------------------------------------------

def _plugin_public(r, with_body=False):
    d = dict(r)
    d["args"] = json.loads(d.get("args") or "[]")
    if not with_body:
        d.pop("body", None)
    return d


def upsert_plugin(db_path, manifest, body):
    """Crée ou remplace un plugin du catalogue. Le manifeste est validé
    par la MÊME fonction que l'agent (copie de si_agent/plugins.py) --
    ce qui est refusé ici l'aurait été là-bas."""
    if not isinstance(body, str) or not body.strip():
        raise ValueError("corps du script vide")
    m = dict(manifest or {})
    m.setdefault("version", "1")
    m["version"] = str(m["version"])
    ok, why = plugin_lib.validate_manifest(m)
    if not ok:
        raise ValueError(why)
    digest = plugin_lib.sha256_text(body)
    now = now_iso()
    conn = _connect(db_path)
    try:
        exists = conn.execute("SELECT created_at FROM plugins WHERE id = ?", (m["id"],)).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO plugins (id, version, runner, entry, interval_seconds, timeout_seconds, args, description, body, sha256, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (m["id"], m["version"], m["runner"], m["entry"], int(m.get("interval_seconds", 3600)), int(m.get("timeout_seconds") or 60),
             json.dumps(m.get("args") or []), m.get("description"), body, digest, exists["created_at"] if exists else now, now))
        conn.commit()
        r = conn.execute("SELECT * FROM plugins WHERE id = ?", (m["id"],)).fetchone()
    finally:
        conn.close()
    return _plugin_public(r)


def list_plugins(db_path):
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM plugins ORDER BY id").fetchall()
        counts = {r["plugin_id"]: r["n"] for r in conn.execute(
            "SELECT plugin_id, COUNT(*) AS n FROM agent_plugins GROUP BY plugin_id").fetchall()}
    finally:
        conn.close()
    out = []
    for r in rows:
        d = _plugin_public(r)
        d["assigned_agents"] = counts.get(d["id"], 0)
        out.append(d)
    return out


def get_plugin(db_path, plugin_id, with_body=False):
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT * FROM plugins WHERE id = ?", (plugin_id,)).fetchone()
    finally:
        conn.close()
    return _plugin_public(r, with_body) if r else None


def delete_plugin(db_path, plugin_id):
    """Retire du catalogue ET des affectations -- les agents concernés
    reçoivent `remove_plugins` à leur prochaine configuration."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
        conn.execute("DELETE FROM agent_plugins WHERE plugin_id = ?", (plugin_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def assign_plugin(db_path, agent_id, plugin_id, enabled=True):
    conn = _connect(db_path)
    try:
        if conn.execute("SELECT 1 FROM agents WHERE agent_id = ?", (agent_id,)).fetchone() is None:
            return None
        if conn.execute("SELECT 1 FROM plugins WHERE id = ?", (plugin_id,)).fetchone() is None:
            raise ValueError("plugin %s absent du catalogue" % plugin_id)
        conn.execute("INSERT OR REPLACE INTO agent_plugins (agent_id, plugin_id, enabled, assigned_at) VALUES (?, ?, ?, ?)",
                     (agent_id, plugin_id, 1 if enabled else 0, now_iso()))
        conn.commit()
    finally:
        conn.close()
    return agent_plugins(db_path, agent_id)


def unassign_plugin(db_path, agent_id, plugin_id):
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM agent_plugins WHERE agent_id = ? AND plugin_id = ?", (agent_id, plugin_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def agent_plugins(db_path, agent_id):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT p.id, p.version, p.runner, p.description, p.interval_seconds, p.sha256, ap.enabled, ap.assigned_at "
            "FROM agent_plugins ap JOIN plugins p ON p.id = ap.plugin_id WHERE ap.agent_id = ? ORDER BY p.id", (agent_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r, enabled=bool(r["enabled"])) for r in rows]


# ------------------------------------------------------------------
# Configuration poussée à l'agent (route signée)
# ------------------------------------------------------------------

def config_for_agent(db_path, agent_id):
    """Ce que l'agent reçoit sur GET /api/v1/agents/<id>/config : réglages,
    plugins affectés (manifeste SIGNÉ avec le secret de l'agent + corps),
    plugins d'origine centrale à retirer = ceux qu'il a déclarés dans son
    dernier inventaire et qui ne lui sont plus affectés."""
    conn = _connect(db_path)
    try:
        a = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        if a is None:
            return None
        rows = conn.execute(
            "SELECT p.*, ap.enabled AS assigned_enabled FROM agent_plugins ap JOIN plugins p ON p.id = ap.plugin_id "
            "WHERE ap.agent_id = ? ORDER BY p.id", (agent_id,)).fetchall()
        inv = conn.execute("SELECT data FROM measurements WHERE agent_id = ? AND task = 'inventory' ORDER BY at DESC LIMIT 1",
                           (agent_id,)).fetchone()
    finally:
        conn.close()
    assigned = []
    fingerprint = [str(a["host_interval_seconds"]), a["risk_thresholds"] or "{}"]
    for r in rows:
        manifest = {"id": r["id"], "version": r["version"], "runner": r["runner"], "entry": r["entry"],
                    "interval_seconds": r["interval_seconds"], "timeout_seconds": r["timeout_seconds"],
                    "args": json.loads(r["args"] or "[]"), "enabled": bool(r["assigned_enabled"]),
                    "description": r["description"], "sha256": r["sha256"],
                    "signature": plugin_lib.plugin_signature(a["secret"], r["id"], r["version"], r["sha256"])}
        assigned.append({"manifest": manifest, "body": r["body"]})
        fingerprint.append("%s@%s:%s:%d" % (r["id"], r["version"], r["sha256"][:12], 1 if r["assigned_enabled"] else 0))
    assigned_ids = {p["manifest"]["id"] for p in assigned}
    remove = []
    if inv and inv["data"]:
        try:
            for p in (json.loads(inv["data"]).get("plugins") or []):
                if p.get("source") == "central" and p.get("id") not in assigned_ids:
                    remove.append(p["id"])
        except ValueError:
            pass
    fingerprint.append("rm:" + ",".join(sorted(remove)))
    version = hashlib.sha256("\n".join(fingerprint).encode("utf-8")).hexdigest()[:16]
    return {"version": version, "host_interval_seconds": a["host_interval_seconds"],
            "risk_thresholds": json.loads(a["risk_thresholds"] or "{}"), "plugins": assigned, "remove_plugins": remove}


# ------------------------------------------------------------------
# Commandes
# ------------------------------------------------------------------

def create_command(db_path, agent_id, ctype, params=None):
    if ctype not in COMMAND_TYPES:
        raise ValueError("type de commande inconnu (%s)" % ", ".join(COMMAND_TYPES))
    if ctype in ("run_plugin", "enable_plugin", "disable_plugin", "remove_plugin") and not (params or {}).get("id"):
        raise ValueError("params.id (identifiant du plugin) requis")
    cid = "c-" + _secrets.token_hex(6)
    conn = _connect(db_path)
    try:
        if conn.execute("SELECT 1 FROM agents WHERE agent_id = ?", (agent_id,)).fetchone() is None:
            return None
        conn.execute("INSERT INTO commands (id, agent_id, type, params, created_at) VALUES (?, ?, ?, ?, ?)",
                     (cid, agent_id, ctype, json.dumps(params or {}), now_iso()))
        conn.commit()
    finally:
        conn.close()
    return get_command(db_path, cid)


def _command_public(r):
    d = dict(r)
    d["params"] = json.loads(d.get("params") or "{}")
    d["result"] = json.loads(d["result"]) if d.get("result") else None
    return d


def get_command(db_path, cid):
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT * FROM commands WHERE id = ?", (cid,)).fetchone()
    finally:
        conn.close()
    return _command_public(r) if r else None


def list_commands(db_path, agent_id, status=None, limit=50):
    conn = _connect(db_path)
    try:
        if status:
            rows = conn.execute("SELECT * FROM commands WHERE agent_id = ? AND status = ? ORDER BY created_at DESC, id LIMIT ?",
                                (agent_id, status, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM commands WHERE agent_id = ? ORDER BY created_at DESC, id LIMIT ?",
                                (agent_id, limit)).fetchall()
    finally:
        conn.close()
    return [_command_public(r) for r in rows]


def pending_commands_for_agent(db_path, agent_id):
    """Forme attendue par l'agent : [{id, type, params}] dans l'ordre d'émission."""
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT id, type, params FROM commands WHERE agent_id = ? AND status = 'pending' ORDER BY created_at, id",
                            (agent_id,)).fetchall()
    finally:
        conn.close()
    return [{"id": r["id"], "type": r["type"], "params": json.loads(r["params"] or "{}")} for r in rows]


def ack_command(db_path, agent_id, cid, result):
    conn = _connect(db_path)
    try:
        cur = conn.execute("UPDATE commands SET status = ?, result = ?, acked_at = ? WHERE id = ? AND agent_id = ? AND status = 'pending'",
                           ("done" if (result or {}).get("ok") else "failed", json.dumps(result or {}), now_iso(), cid, agent_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ------------------------------------------------------------------
# Mesures
# ------------------------------------------------------------------

def ingest_measurements(db_path, agent_id, items, ip=None):
    """Insère les mesures d'UN agent (celui qui a signé) ; les mesures
    portant un autre agent_id sont rejetées. Renvoie (acceptées, doublons,
    rejets). Met à jour le dernier contact et, sur `host`/`inventory`, la
    fiche de l'agent (hôte, OS, version)."""
    accepted, duplicates, rejected = 0, 0, []
    now = now_iso()
    conn = _connect(db_path)
    try:
        for m in items:
            if not isinstance(m, dict) or not m.get("task") or not m.get("at"):
                rejected.append({"reason": "task/at manquant"})
                continue
            if m.get("agent_id") not in (None, agent_id):
                rejected.append({"reason": "agent_id %s ≠ signataire" % m.get("agent_id")})
                continue
            data = m.get("data")
            try:
                conn.execute("INSERT INTO measurements (agent_id, task, at, ok, data, error, received_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (agent_id, m["task"], m["at"], 1 if m.get("ok", True) else 0,
                              json.dumps(data, ensure_ascii=False) if data is not None else None, m.get("error"), now))
                accepted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
                continue
            if m["task"] == "host" and isinstance(data, dict):
                s = data.get("system") or {}
                conn.execute("UPDATE agents SET hostname = COALESCE(?, hostname), os = COALESCE(?, os) WHERE agent_id = ?",
                             (s.get("hostname"), s.get("os"), agent_id))
            elif m["task"] == "inventory" and isinstance(data, dict):
                conn.execute("UPDATE agents SET agent_version = COALESCE(?, agent_version) WHERE agent_id = ?",
                             (data.get("agent_version"), agent_id))
        touch_agent(conn, agent_id, ip)
        conn.commit()
    finally:
        conn.close()
    return accepted, duplicates, rejected


def _measurement_public(r):
    d = dict(r)
    d["ok"] = bool(d["ok"])
    d["data"] = json.loads(d["data"]) if d.get("data") else None
    return d


def list_measurements(db_path, agent_id, task=None, limit=200, since=None):
    q = "SELECT id, agent_id, task, at, ok, data, error, received_at FROM measurements WHERE agent_id = ?"
    params = [agent_id]
    if task:
        q += " AND task = ?"; params.append(task)
    if since:
        q += " AND at >= ?"; params.append(since)
    q += " ORDER BY at DESC LIMIT ?"; params.append(max(1, min(int(limit or 200), 5000)))
    conn = _connect(db_path)
    try:
        rows = conn.execute(q, params).fetchall()
    finally:
        conn.close()
    return [_measurement_public(r) for r in rows]


def latest_per_task(db_path, agent_id):
    """Dernière mesure de chaque tâche pour un agent : {task: mesure}."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT m.id, m.agent_id, m.task, m.at, m.ok, m.data, m.error, m.received_at FROM measurements m "
            "JOIN (SELECT task, MAX(at) AS at FROM measurements WHERE agent_id = ? GROUP BY task) l "
            "ON l.task = m.task AND l.at = m.at WHERE m.agent_id = ?", (agent_id, agent_id)).fetchall()
    finally:
        conn.close()
    return {r["task"]: _measurement_public(r) for r in rows}


def fleet(db_path, site=None, offline_after_seconds=300):
    """Flotte avec, pour chaque agent, la dernière mesure `host` (résumée),
    le dernier `risks` et l'état de contact -- ce que la tuile affiche."""
    agents = list_agents(db_path, site=site)
    now = time.time()
    out = []
    for a in agents:
        latest = latest_per_task(db_path, a["agent_id"])
        host = (latest.get("host") or {}).get("data") or {}
        risks_m = latest.get("risks") or {}
        summary = {
            "cpu_percent": (host.get("cpu") or {}).get("percent"),
            "load5": (host.get("cpu") or {}).get("load5"),
            "memory_percent": (host.get("memory") or {}).get("used_percent"),
            "disk_max_percent": max([d.get("used_percent") or 0 for d in host.get("disks") or []] or [None]) if host.get("disks") else None,
            "uptime_seconds": (host.get("system") or {}).get("uptime_seconds"),
            "partial": host.get("partial") or [],
            "host_at": (latest.get("host") or {}).get("at"),
        }
        a["summary"] = summary
        a["risks"] = (risks_m.get("data") or {}).get("summary") or {"state": "unknown", "counts": {}, "total": 0}
        a["risks_at"] = risks_m.get("at")
        a["online"] = _online(a.get("last_seen_at"), now, offline_after_seconds, a["host_interval_seconds"])
        a["pending_commands"] = len(pending_commands_for_agent(db_path, a["agent_id"]))
        a["plugins_assigned"] = len(agent_plugins(db_path, a["agent_id"]))
        out.append(a)
    return out


def _online(last_seen, now, offline_after, interval):
    if not last_seen:
        return "never"
    try:
        ts = calendar.timegm(time.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return "unknown"
    return "online" if now - ts <= max(offline_after, 3 * (interval or 60)) else "offline"


def fleet_risks(db_path, site=None):
    """Tous les constats courants de la flotte, à plat (tableau « risques »)."""
    out = []
    for a in list_agents(db_path, site=site):
        latest = latest_per_task(db_path, a["agent_id"])
        r = latest.get("risks")
        if not r or not r.get("data"):
            continue
        for item in r["data"].get("risks") or []:
            out.append(dict(item, agent_id=a["agent_id"], site=a["site"], hostname=a.get("hostname"), at=r["at"]))
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda x: (order.get(x.get("severity"), 3), x.get("agent_id"), x.get("id")))
    return out


def purge_measurements(db_path, retention_days):
    """Efface les mesures plus vieilles que la rétention, en gardant
    toujours la dernière de chaque (agent, tâche)."""
    if not retention_days or retention_days <= 0:
        return 0
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - retention_days * 86400))
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM measurements WHERE at < ? AND id NOT IN (SELECT MAX(id) FROM measurements GROUP BY agent_id, task)", (cutoff,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
