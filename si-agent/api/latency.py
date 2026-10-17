# -*- coding: utf-8 -*-
"""#775 : tuile « Latence des IP publiques » -- mesures régulières de toutes les IP publiques du SI, vues de plusieurs
points de mesure, avec un configurateur des accès.

- CIBLES : IP publique (+ ports, + noms servis en HTTPS), groupe, notes. La liste réelle est saisie ou importée dans le
  hub (jamais dans le dépôt).
- POINTS DE MESURE : `agent` (l'agent mesure lui-même), `direct` (un agent EXÉCUTANT ouvre `ssh login@hôte`, sudo
  facultatif) ou `indirect` (idem par un rebond `-J`). Le cas général : compte personnel (« francois ») + sudo, ou un
  agent déjà en place. Aucun mot de passe ni clé n'est stocké : seulement le chemin d'une clé sur l'exécutant.
- Toutes les `period_minutes` (15 par défaut), une commande `latency` par point (agent 0.5.73, si_agent/latctl.py) ;
  les résultats (ping, ouverture TCP, HTTPS par l'IP et par le nom : résolution, connexion, TLS, premier octet, total)
  sont gardés 31 jours. Chaque échec est classé avec sa cause et une solution (commande exacte et où la lancer).
Pur : validate_target, validate_point, command_params, diagnose, classify, summarize."""
import json
import re
import secrets
import time

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS lat_targets (id TEXT PRIMARY KEY, label TEXT, ip TEXT NOT NULL, ports TEXT NOT NULL DEFAULT '[]', "
    "names TEXT NOT NULL DEFAULT '[]', grp TEXT, enabled INTEGER NOT NULL DEFAULT 1, notes TEXT, updated_at TEXT, updated_by TEXT)",
    "CREATE TABLE IF NOT EXISTS lat_points (id TEXT PRIMARY KEY, label TEXT, mode TEXT NOT NULL, agent TEXT NOT NULL, login TEXT, host TEXT, "
    "port INTEGER, jump TEXT, sudo INTEGER NOT NULL DEFAULT 0, key TEXT, targets TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 1, "
    "notes TEXT, updated_at TEXT, updated_by TEXT)",
    "CREATE TABLE IF NOT EXISTS lat_settings (k TEXT PRIMARY KEY, v TEXT)",
    "CREATE TABLE IF NOT EXISTS lat_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, point_id TEXT NOT NULL, slot INTEGER NOT NULL, agent_id TEXT, "
    "command_id TEXT, status TEXT NOT NULL, error TEXT, queued_at REAL, finished_at REAL, UNIQUE (point_id, slot))",
    "CREATE TABLE IF NOT EXISTS lat_results (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, point_id TEXT NOT NULL, "
    "target_id TEXT NOT NULL, data TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_lat_results ON lat_results (target_id, point_id, ts)",
)
MODES = ("agent", "direct", "indirect")
DEFAULTS = {"period_minutes": 15, "default_login": "francois", "keep_days": 31}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")
LOGIN_RE = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")
JUMP_RE = re.compile(r"^([a-z_][a-z0-9_.-]{0,31}@)?[A-Za-z0-9][A-Za-z0-9.-]{0,252}(:[0-9]{1,5})?$")
KEY_RE = re.compile(r"^/[A-Za-z0-9._/@-]{1,200}$")
STALE_S = 900          # commande non prise en 15 min -> « agent silencieux »


def init(conn):
    for s in SCHEMA:
        conn.execute(s)


def _slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(s or "")).strip("-.")[:63]


# ---------------------------------------------------------------- validation (pur)

def validate_target(b):
    b = b or {}
    ip = str(b.get("ip") or "").strip()
    if not HOST_RE.match(ip) or ".." in ip:
        return None, "adresse IP (ou nom) invalide"
    tid = str(b.get("id") or _slug(b.get("label") or ip)).strip()
    if not ID_RE.match(tid):
        return None, "identifiant invalide"
    ports = b.get("ports") if b.get("ports") is not None else [443]
    if isinstance(ports, str):
        ports = [int(x) for x in re.split(r"[\s,;]+", ports) if x.strip().isdigit()]
    if not isinstance(ports, list) or len(ports) > 10 or not all(isinstance(x, int) and 0 < x < 65536 for x in ports):
        return None, "ports : jusqu'à 10 numéros"
    names = b.get("names") or []
    if isinstance(names, str):
        names = [x for x in re.split(r"[\s,;]+", names) if x]
    if not isinstance(names, list) or len(names) > 5 or not all(isinstance(n, str) and HOST_RE.match(n) and ".." not in n for n in names):
        return None, "noms : jusqu'à 5 noms d'hôte"
    return {"id": tid, "label": str(b.get("label") or tid)[:120], "ip": ip, "ports": sorted(set(ports)), "names": names,
            "grp": str(b.get("grp") or b.get("group") or "")[:60], "enabled": bool(b.get("enabled", True)), "notes": str(b.get("notes") or "")[:500]}, None


def validate_point(b, default_login="francois"):
    b = b or {}
    mode = str(b.get("mode") or "agent")
    if mode not in MODES:
        return None, "mode : agent, direct ou indirect"
    agent = str(b.get("agent") or "").strip()
    if not ID_RE.match(agent):
        return None, "agent requis (celui qui mesure, ou qui ouvre la connexion SSH)"
    p = {"mode": mode, "agent": agent, "login": None, "host": None, "port": None, "jump": None, "sudo": False, "key": None}
    if mode != "agent":
        p["login"] = str(b.get("login") or default_login).strip()
        p["host"] = str(b.get("host") or "").strip()
        if not LOGIN_RE.match(p["login"]):
            return None, "compte de connexion invalide"
        if not HOST_RE.match(p["host"]) or ".." in p["host"]:
            return None, "hôte de connexion invalide"
        try:
            p["port"] = int(b.get("port") or 22)
        except (TypeError, ValueError):
            return None, "port SSH invalide"
        if not 0 < p["port"] < 65536:
            return None, "port SSH invalide"
        p["jump"] = str(b.get("jump") or "").strip() or None
        if mode == "indirect" and not p["jump"]:
            return None, "rebond requis en mode indirect (utilisateur@hôte:port)"
        if p["jump"] and not JUMP_RE.match(p["jump"]):
            return None, "rebond invalide (utilisateur@hôte:port)"
        p["sudo"] = bool(b.get("sudo"))
        p["key"] = str(b.get("key") or "").strip() or None
        if p["key"] and (not KEY_RE.match(p["key"]) or ".." in p["key"]):
            return None, "clé : chemin absolu sur l'agent exécutant"
    pid = str(b.get("id") or _slug(b.get("label") or (p["host"] if mode != "agent" else agent))).strip()
    if not ID_RE.match(pid):
        return None, "identifiant invalide"
    tg = b.get("targets") or []
    if not isinstance(tg, list) or not all(isinstance(x, str) and ID_RE.match(x) for x in tg):
        return None, "targets : liste d'identifiants de cibles (vide = toutes)"
    p.update(id=pid, label=str(b.get("label") or pid)[:120], targets=tg, enabled=bool(b.get("enabled", True)), notes=str(b.get("notes") or "")[:500])
    return p, None


def command_params(point, targets):
    """Paramètres de la commande `latency` pour un point -> (params, nb de cibles)."""
    sel = [t for t in targets if t["enabled"] and (not point["targets"] or t["id"] in point["targets"])][:40]
    params = {"targets": [{"id": t["id"], "ip": t["ip"], "ports": t["ports"], "names": t["names"]} for t in sel]}
    if point["mode"] != "agent":
        params["via"] = {"login": point["login"], "host": point["host"], "port": point["port"] or 22, "jump": point["jump"] or "",
                         "sudo": bool(point["sudo"]), "key": point["key"] or ""}
    return params, len(sel)


# ---------------------------------------------------------------- lecture des mesures (pur)

def first_https(m):
    """Première mesure HTTPS (par l'IP, sinon par le nom) d'une cible -> (nom, dict)."""
    for name, h in sorted(((m or {}).get("https") or {}).items()):
        if (h or {}).get("ip"):
            return name, h["ip"]
    for name, h in sorted(((m or {}).get("https") or {}).items()):
        if (h or {}).get("name"):
            return name, h["name"]
    return None, None


def diagnose(m, ip):
    """Mesure d'une cible vue d'un point -> (niveau ok|warning|critical, [constats])."""
    out, lvl = [], "ok"

    def up(x):
        nonlocal lvl
        if x == "critical" or (x == "warning" and lvl == "ok"):
            lvl = x
    if not m:
        return "critical", ["aucune mesure"]
    loss, rtt = m.get("ping_loss"), m.get("ping_ms")
    if loss is not None and loss >= 100:
        out.append("ne répond pas au ping (filtré ou éteint)")
    elif loss:
        out.append("pertes de paquets : %g %%" % loss)
        up("warning" if loss < 20 else "critical")
    for port, ms in sorted((m.get("tcp") or {}).items(), key=lambda kv: int(kv[0])):
        if ms is None:
            out.append("port %s fermé ou filtré" % port)
            up("critical")
        elif ms > 1000:
            out.append("ouverture du port %s lente : %d ms" % (port, ms))
            up("warning")
    for name, h in sorted((m.get("https") or {}).items()):
        hi, hn, res = (h or {}).get("ip"), (h or {}).get("name"), (h or {}).get("resolved")
        if hi is not None and not hi.get("ok"):
            out.append("%s : HTTPS par l'IP en échec (code %s)" % (name, hi.get("code") or "aucune réponse"))
            up("critical")
        elif hi:
            base = max(rtt or 0, hi.get("connect_ms") or 0)
            if hi.get("tls_ms") and hi["tls_ms"] > max(300, 6 * base):
                out.append("%s : poignée TLS lente (%d ms pour un aller-retour de %d ms) -- équipement intermédiaire ou frontal chargé"
                           % (name, hi["tls_ms"], base))
                up("critical" if hi["tls_ms"] > 2000 else "warning")
            if hi.get("ttfb_ms") and hi["ttfb_ms"] > 1500:
                out.append("%s : réponse lente du serveur (premier octet en %d ms)" % (name, hi["ttfb_ms"]))
                up("warning")
        if res is not None and ip not in res:
            out.append("%s résout vers %s depuis ce point, pas vers %s" % (name, ", ".join(res) or "rien", ip))
            up("warning")
        if hi and hn and hi.get("ok") and hn.get("ok") and hn["total_ms"] > hi["total_ms"] + 500:
            out.append("%s : plus lent par le nom (%d ms) que par l'IP (%d ms) -- résolution ou autre chemin" % (name, hn["total_ms"], hi["total_ms"]))
            up("warning")
        if hn is not None and not hn.get("ok") and (hi or {}).get("ok"):
            out.append("%s : joignable par l'IP mais pas par le nom depuis ce point" % name)
            up("warning")
    return lvl, out


def key_metrics(m):
    """Valeurs résumées d'une mesure : ping, TLS, premier octet, total (ms)."""
    _n, h = first_https(m)
    return {"ping_ms": (m or {}).get("ping_ms"), "loss": (m or {}).get("ping_loss"), "tls_ms": (h or {}).get("tls_ms"),
            "ttfb_ms": (h or {}).get("ttfb_ms"), "total_ms": (h or {}).get("total_ms") if (h or {}).get("ok") else None}


def _pct(vals, p):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    return v[min(len(v) - 1, int(round(p / 100.0 * (len(v) - 1))))]


def summarize(rows):
    """[(ts, data)] d'un couple cible × point (ordre chronologique) -> {n, median et p95 de total et TLS, série}."""
    km = [(ts, key_metrics(d)) for ts, d in rows]
    tot = [k["total_ms"] for _t, k in km]
    tls = [k["tls_ms"] for _t, k in km]
    return {"n": len(km), "total_med": _pct(tot, 50), "total_p95": _pct(tot, 95), "tls_med": _pct(tls, 50), "tls_p95": _pct(tls, 95),
            "series": [dict(k, ts=t) for t, k in km][-200:]}


# ---------------------------------------------------------------- erreurs : cause et solution (pur)

def _pub_key_cmd(executor):
    return "ssh root@%s 'cat /root/.ssh/id_ed25519.pub 2>/dev/null || cat /root/.ssh/id_rsa.pub'" % executor


ERRORS = [
    ("agent-ancien", r"commande inconnue : latency", "Agent trop ancien",
     "L'agent qui doit mesurer ne connaît pas encore les mesures de latence (version antérieure à 0.5.73).",
     lambda p, ex: {"label": "Mettre l'agent à jour depuis la maison", "where": "maison (Linux)",
                    "command": "curl -fsSL https://raw.githubusercontent.com/freg/supervision-si/dev/deploy/migration/agent-ssh.sh -o /tmp/agent-ssh.sh && bash /tmp/agent-ssh.sh root@%s" % ex}),
    ("ssh-cle", r"Permission denied \(publickey", "Clé refusée par l'hôte de connexion",
     "L'agent exécutant se connecte par clé ; sa clé publique n'est pas dans ~/.ssh/authorized_keys du compte de connexion.",
     lambda p, ex: {"label": "Poser la clé de l'exécutant dans le compte %s (mot de passe demandé une fois)" % (p.get("login") or "?"), "where": "maison (Linux)",
                    "command": ("K=$(%s) && ssh -t %s%s@%s \"mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
                                "(grep -qxF \\\"$K\\\" ~/.ssh/authorized_keys || echo \\\"$K\\\" >> ~/.ssh/authorized_keys) && chmod 600 ~/.ssh/authorized_keys && echo cle posee\"")
                    % (_pub_key_cmd(ex), ("-J %s " % p["jump"]) if p.get("jump") else "", p.get("login") or "francois", p.get("host") or "?")}),
    ("sudo", r"sudo: (a password is required|a terminal is required|.*not in the sudoers)", "sudo demande un mot de passe",
     "Les mesures (ping, curl) n'ont pas besoin des droits root ; sudo sans mot de passe n'est pas configuré pour ce compte.",
     lambda p, ex: {"label": "Décocher « sudo » sur ce point de mesure (recommandé), puis « Mesurer maintenant »", "where": "hub"}),
    ("empreinte", r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED", "Empreinte de l'hôte changée",
     "L'hôte de connexion a été réinstallé ou son adresse a changé.",
     lambda p, ex: {"label": "Oublier l'ancienne empreinte sur l'exécutant", "where": ex,
                    "command": "ssh-keygen -R %s" % (p.get("host") or "?")}),
    ("dns", r"Could not resolve hostname|Name or service not known", "Nom de l'hôte de connexion introuvable",
     "L'exécutant ne résout pas le nom de l'hôte de connexion.",
     lambda p, ex: {"label": "Mettre l'adresse IP dans le point de mesure, ou vérifier la résolution", "where": ex,
                    "command": "getent hosts %s; cat /etc/resolv.conf" % (p.get("host") or "?")}),
    ("reseau", r"Connection (timed out|refused|reset)|No route to host|Network is unreachable|kex_exchange_identification",
     "Hôte de connexion injoignable en SSH", "Le port SSH ne répond pas depuis l'exécutant (pare-feu, port, rebond nécessaire ?).",
     lambda p, ex: {"label": "Tester la connexion depuis l'exécutant", "where": ex,
                    "command": "ssh -v -o BatchMode=yes -p %s %s%s@%s true 2>&1 | tail -5" % (p.get("port") or 22, ("-J %s " % p["jump"]) if p.get("jump") else "",
                                                                                       p.get("login") or "francois", p.get("host") or "?")}),
    ("outils", r"missing:(ping|curl|getent|timeout)", "Outil de mesure absent",
     "Le point de mesure n'a pas ping ou curl : ces mesures restent vides.",
     lambda p, ex: {"label": "Installer les outils sur le point de mesure", "where": p.get("host") or ex,
                    "command": "sudo apt-get install -y iputils-ping curl"}),
    ("silence", r"^SILENCE$", "L'agent n'a pas pris la mesure",
     "Commande en attente depuis plus de 15 minutes : agent arrêté ou hôte injoignable.",
     lambda p, ex: {"label": "Vérifier l'agent", "where": ex, "command": "systemctl status si-agent --no-pager | head -5"}),
    ("agent-inconnu", r"^AGENT INCONNU", "Agent inconnu du hub",
     "L'agent indiqué pour ce point n'est pas enrôlé (nom ou identifiant à corriger).",
     lambda p, ex: {"label": "Corriger l'agent du point de mesure (liste des agents dans le formulaire)", "where": "hub"}),
]


def classify(point, error, executor):
    e = str(error or "")
    for code, rx, title, why, sol in ERRORS:
        if re.search(rx, e, re.I | re.M):
            return {"code": code, "title": title, "detail": why, "error": e[-800:], "solution": sol(point or {}, executor)}
    return {"code": "inconnue", "title": "Mesure en échec", "detail": "Cause non reconnue : lire le message.", "error": e[-800:], "solution": None}


# ---------------------------------------------------------------- base

def _settings(conn):
    s = dict(DEFAULTS)
    for k, v in conn.execute("SELECT k, v FROM lat_settings"):
        try:
            s[k] = json.loads(v)
        except ValueError:
            pass
    return s


def set_settings(conn, b):
    init(conn)
    out = {}
    if "period_minutes" in (b or {}):
        try:
            v = int(b["period_minutes"])
        except (TypeError, ValueError):
            return None, "period_minutes : entier"
        if not 5 <= v <= 1440:
            return None, "période entre 5 et 1440 minutes"
        out["period_minutes"] = v
    if "default_login" in (b or {}):
        if not LOGIN_RE.match(str(b["default_login"])):
            return None, "compte par défaut invalide"
        out["default_login"] = str(b["default_login"])
    for k, v in out.items():
        conn.execute("INSERT INTO lat_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k, json.dumps(v)))
    return _settings(conn), None


def _row_target(r):
    return {"id": r[0], "label": r[1], "ip": r[2], "ports": json.loads(r[3] or "[]"), "names": json.loads(r[4] or "[]"), "grp": r[5] or "",
            "enabled": bool(r[6]), "notes": r[7] or "", "updated_at": r[8], "updated_by": r[9]}


def _row_point(r):
    return {"id": r[0], "label": r[1], "mode": r[2], "agent": r[3], "login": r[4], "host": r[5], "port": r[6], "jump": r[7], "sudo": bool(r[8]),
            "key": r[9], "targets": json.loads(r[10] or "[]"), "enabled": bool(r[11]), "notes": r[12] or "", "updated_at": r[13], "updated_by": r[14]}


def targets(conn):
    init(conn)
    return [_row_target(r) for r in conn.execute("SELECT id, label, ip, ports, names, grp, enabled, notes, updated_at, updated_by FROM lat_targets ORDER BY grp, label")]


def points(conn):
    init(conn)
    return [_row_point(r) for r in conn.execute("SELECT id, label, mode, agent, login, host, port, jump, sudo, key, targets, enabled, notes, updated_at, updated_by "
                                                "FROM lat_points ORDER BY label")]


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def save_target(conn, b, by):
    t, err = validate_target(b)
    if err:
        return None, err
    init(conn)
    conn.execute("INSERT INTO lat_targets (id, label, ip, ports, names, grp, enabled, notes, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?) "
                 "ON CONFLICT(id) DO UPDATE SET label=excluded.label, ip=excluded.ip, ports=excluded.ports, names=excluded.names, grp=excluded.grp, "
                 "enabled=excluded.enabled, notes=excluded.notes, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                 (t["id"], t["label"], t["ip"], json.dumps(t["ports"]), json.dumps(t["names"]), t["grp"], int(t["enabled"]), t["notes"], _now_iso(), by))
    return t, None


def save_point(conn, b, by):
    init(conn)
    p, err = validate_point(b, _settings(conn)["default_login"])
    if err:
        return None, err
    conn.execute("INSERT INTO lat_points (id, label, mode, agent, login, host, port, jump, sudo, key, targets, enabled, notes, updated_at, updated_by) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET label=excluded.label, mode=excluded.mode, agent=excluded.agent, "
                 "login=excluded.login, host=excluded.host, port=excluded.port, jump=excluded.jump, sudo=excluded.sudo, key=excluded.key, "
                 "targets=excluded.targets, enabled=excluded.enabled, notes=excluded.notes, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                 (p["id"], p["label"], p["mode"], p["agent"], p["login"], p["host"], p["port"], p["jump"], int(p["sudo"]), p["key"],
                  json.dumps(p["targets"]), int(p["enabled"]), p["notes"], _now_iso(), by))
    return p, None


def delete(conn, what, oid):
    init(conn)
    table = {"target": "lat_targets", "point": "lat_points"}[what]
    n = conn.execute("DELETE FROM %s WHERE id = ?" % table, (oid,)).rowcount
    if what == "target":
        conn.execute("DELETE FROM lat_results WHERE target_id = ?", (oid,))
    else:
        conn.execute("DELETE FROM lat_results WHERE point_id = ?", (oid,))
        conn.execute("DELETE FROM lat_runs WHERE point_id = ?", (oid,))
    return n > 0


def import_config(conn, b, by):
    """{targets: [...], points: [...], settings: {...}} -> (compte, erreurs). Ajoute ou remplace par identifiant."""
    errs, n = [], {"targets": 0, "points": 0}
    if isinstance((b or {}).get("settings"), dict):
        _s, e = set_settings(conn, b["settings"])
        if e:
            errs.append("réglages : %s" % e)
    for t in (b or {}).get("targets") or []:
        _t, e = save_target(conn, t, by)
        if e:
            errs.append("cible %s : %s" % ((t or {}).get("id") or (t or {}).get("ip"), e))
        else:
            n["targets"] += 1
    for p in (b or {}).get("points") or []:
        _p, e = save_point(conn, p, by)
        if e:
            errs.append("point %s : %s" % ((p or {}).get("id") or (p or {}).get("host"), e))
        else:
            n["points"] += 1
    return n, errs


def export_config(conn):
    strip = lambda d, ks: {k: v for k, v in d.items() if k not in ks}  # noqa: E731
    return {"settings": {k: v for k, v in _settings(conn).items() if k in ("period_minutes", "default_login")},
            "targets": [strip(t, ("updated_at", "updated_by")) for t in targets(conn)],
            "points": [strip(p, ("updated_at", "updated_by")) for p in points(conn)]}


def resolve_agent(conn, name):
    r = conn.execute("SELECT agent_id FROM agents WHERE agent_id = ? OR lower(hostname) = lower(?) OR lower(label) = lower(?) "
                     "OR lower(hostname) LIKE lower(?) || '.%' ORDER BY (agent_id = ?) DESC, last_seen_at DESC LIMIT 1",
                     (name, name, name, name, name)).fetchone()
    return r[0] if r else None


def _enqueue(conn, agent_id, params):
    cid = "c-" + secrets.token_hex(6)
    t = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%06dZ" % int((t % 1) * 1e6)
    conn.execute("INSERT INTO commands (id, agent_id, type, params, created_at) VALUES (?, ?, 'latency', ?, ?)",
                 (cid, agent_id, json.dumps(params, ensure_ascii=False), stamp))
    return cid


def launch(conn, point, tlist, slot, now):
    """Dépose la commande d'un point pour ce créneau (une seule fois : UNIQUE(point, slot)). -> run_id ou None."""
    if conn.execute("SELECT 1 FROM lat_runs WHERE point_id = ? AND slot = ?", (point["id"], slot)).fetchone():
        return None
    params, n = command_params(point, tlist)
    aid = resolve_agent(conn, point["agent"])
    if not n:
        return None
    if not aid:
        conn.execute("INSERT OR IGNORE INTO lat_runs (point_id, slot, status, error, queued_at, finished_at) VALUES (?, ?, 'failed', ?, ?, ?)",
                     (point["id"], slot, "AGENT INCONNU : %s" % point["agent"], now, now))
        return None
    cid = _enqueue(conn, aid, params)
    cur = conn.execute("INSERT OR IGNORE INTO lat_runs (point_id, slot, agent_id, command_id, status, queued_at) VALUES (?, ?, ?, ?, 'queued', ?)",
                       (point["id"], slot, aid, cid, now))
    return cur.lastrowid


def collect(conn, now):
    """Commandes acquittées -> résultats ; commandes jamais prises -> « silence ». -> nombre de mesures rangées."""
    n = 0
    rows = conn.execute("SELECT r.id, r.point_id, c.status, c.result, r.queued_at FROM lat_runs r LEFT JOIN commands c ON c.id = r.command_id "
                        "WHERE r.status = 'queued'").fetchall()
    for rid, pid, cst, res, queued in rows:
        if cst == "done":
            try:
                data = (json.loads(res or "{}") or {}).get("result") or {}
            except ValueError:
                data = {}
            miss = data.get("missing") or []
            for tid, m in (data.get("targets") or {}).items():
                conn.execute("INSERT INTO lat_results (ts, point_id, target_id, data) VALUES (?, ?, ?, ?)", (now, pid, tid, json.dumps(m)))
                n += 1
            conn.execute("UPDATE lat_runs SET status = 'done', finished_at = ?, error = ? WHERE id = ?",
                         (now, ("missing:" + ",missing:".join(miss)) if miss else None, rid))
        elif cst == "failed":
            try:
                err = str((json.loads(res or "{}") or {}).get("error") or "échec")
            except ValueError:
                err = "échec"
            conn.execute("UPDATE lat_runs SET status = 'failed', finished_at = ?, error = ? WHERE id = ?", (now, err, rid))
        elif queued and now - queued > STALE_S:
            conn.execute("UPDATE lat_runs SET status = 'failed', finished_at = ?, error = 'SILENCE' WHERE id = ?", (now, rid))
    return n


def tick(conn, now=None):
    """Appelé par le chien de garde (30 s) : range les résultats, dépose les mesures du créneau, purge."""
    init(conn)
    now = now or time.time()
    collect(conn, now)
    st = _settings(conn)
    period = max(300, int(st["period_minutes"]) * 60)
    slot = int(now // period)
    tl = targets(conn)
    launched = 0
    for p in points(conn):
        if p["enabled"] and launch(conn, p, tl, slot, now):
            launched += 1
    conn.execute("DELETE FROM lat_results WHERE ts < ?", (now - st["keep_days"] * 86400,))
    conn.execute("DELETE FROM lat_runs WHERE queued_at < ?", (now - 7 * 86400,))
    return launched


def run_now(conn, point_id=None, now=None):
    """« Mesurer maintenant » : créneau négatif unique (n'empêche pas la mesure régulière)."""
    init(conn)
    now = now or time.time()
    tl, n = targets(conn), 0
    for p in points(conn):
        if (point_id and p["id"] != point_id) or (not point_id and not p["enabled"]):
            continue
        if launch(conn, p, tl, -int(now * 1000) - n, now):
            n += 1
    return n


def history(conn, target_id, point_id, hours=24):
    since = time.time() - hours * 3600
    rows = [(r[0], json.loads(r[1])) for r in conn.execute("SELECT ts, data FROM lat_results WHERE target_id = ? AND point_id = ? AND ts >= ? ORDER BY ts",
                                                            (target_id, point_id, since))]
    return summarize(rows)


def view(conn, now=None):
    """Tableau de la tuile : cibles × points (dernière mesure, diagnostic, médiane / p95 sur 24 h), état des points, erreurs."""
    init(conn)
    now = now or time.time()
    collect(conn, now)
    tl, pl = targets(conn), points(conn)
    names = {r[0]: (r[1] or r[2] or r[0]) for r in conn.execute("SELECT agent_id, hostname, label FROM agents")}
    agents = [{"agent_id": r[0], "name": r[1] or r[0], "last_seen_at": r[2]} for r in conn.execute("SELECT agent_id, hostname, last_seen_at FROM agents ORDER BY hostname")]
    cells = {}
    since = now - 86400
    last = {}
    for ts, pid, tid, data in conn.execute("SELECT ts, point_id, target_id, data FROM lat_results WHERE ts >= ? ORDER BY ts", (since,)):
        last.setdefault((tid, pid), []).append((ts, json.loads(data)))
    ip_of = {t["id"]: t["ip"] for t in tl}
    for (tid, pid), rows in last.items():
        ts, m = rows[-1]
        lvl, notes = diagnose(m, ip_of.get(tid))
        s = summarize(rows)
        cells["%s|%s" % (tid, pid)] = {"at": ts, "level": lvl, "notes": notes, "metrics": key_metrics(m), "raw": m,
                                       "n24": s["n"], "total_med": s["total_med"], "total_p95": s["total_p95"], "tls_med": s["tls_med"]}
    states = []
    for p in pl:
        r = conn.execute("SELECT status, error, queued_at, finished_at, agent_id FROM lat_runs WHERE point_id = ? ORDER BY queued_at DESC LIMIT 1", (p["id"],)).fetchone()
        ok_r = conn.execute("SELECT finished_at FROM lat_runs WHERE point_id = ? AND status = 'done' ORDER BY finished_at DESC LIMIT 1", (p["id"],)).fetchone()
        ex = names.get(r[4]) if r and r[4] else p["agent"]
        st = {"id": p["id"], "status": r[0] if r else "jamais", "queued_at": r[2] if r else None, "finished_at": r[3] if r else None,
              "last_ok": ok_r[0] if ok_r else None, "executor": ex, "error": None}
        if r and r[1]:
            st["error"] = classify(p, r[1], ex)
            if r[0] == "done":
                st["error"]["warning_only"] = True
        states.append(st)
    return {"settings": _settings(conn), "targets": tl, "points": pl, "agents": agents, "cells": cells, "states": states, "now": now}
