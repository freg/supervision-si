# -*- coding: utf-8 -*-
"""#653 : plans de reprise / d'exploitation PVE (PRA) -- un plan = une suite ordonnée d'étapes {agent_id, vmid, kind, action,
params}, chaque étape = une commande `vm_action` adressée à l'agent de l'hyperviseur (migrate, backup, move_disk, clone,
replicate, start, shutdown…). Exécution séquentielle par le central : la commande est mise en file, le central attend
l'acquittement de l'agent (délai par étape), s'arrête à la première erreur sauf `continue_on_error`. Mode « simuler » :
validation de chaque étape et liste des commandes qui seraient envoyées, sans rien envoyer. Un seul worker gunicorn :
le fil d'exécution vit dans le processus (motif #522/#586)."""
import json, time, threading
import store

ACTIONS = ("migrate", "backup", "move_disk", "clone", "replicate", "unreplicate", "start", "shutdown", "stop", "reboot", "snapshot", "rollback", "role_switch")
REQUIRED = {"migrate": ("target",), "backup": ("storage",), "move_disk": ("disk", "storage"), "clone": ("newid",), "replicate": ("target",), "snapshot": ("snapname",), "rollback": ("snapname",)}
STEP_TIMEOUT = 3600
_runs = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS pra_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT DEFAULT 'pra', notes TEXT DEFAULT '',
    steps TEXT NOT NULL DEFAULT '[]', continue_on_error INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS pra_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
    started_at TEXT, finished_at TEXT DEFAULT '', by_user TEXT DEFAULT '', steps TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS pra_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, service_url TEXT DEFAULT '', candidates TEXT NOT NULL DEFAULT '[]',
    mechanism TEXT NOT NULL DEFAULT '{}', active INTEGER DEFAULT 0, last_switch_at TEXT DEFAULT '', last_check TEXT DEFAULT '{}', notes TEXT DEFAULT '', created_at TEXT, updated_at TEXT);
"""
MIGRATIONS = (("pra_plans", "trigger_agent_id", "TEXT DEFAULT ''"), ("pra_plans", "trigger_mode", "TEXT DEFAULT 'notify'"), ("pra_plans", "trigger_cooldown_s", "INTEGER DEFAULT 3600"))
ROLE_MECHANISMS = ("manual", "mikrotik_nat")
MIKROTIK_API_URL = __import__("os").environ.get("MIKROTIK_API_URL", "").rstrip("/")

def init(db_path):
    conn = store._connect(db_path)
    try:
        conn.executescript(SCHEMA)
        for table, col, decl in MIGRATIONS:      # convention du projet : nouvelle colonne = ALTER TABLE toléré
            cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table).fetchall()]
            if col not in cols: conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, decl))
        conn.commit()
    finally: conn.close()

def validate_steps(steps):
    """-> (étapes normalisées, erreur) ; chaque étape : agent_id, vmid > 0, kind qemu|lxc, action connue, paramètres requis présents."""
    if not isinstance(steps, list) or not steps: return None, "au moins une étape"
    out = []
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict): return None, "étape %d : objet attendu" % i
        a = str(s.get("action") or "").lower(); kind = str(s.get("kind") or "qemu").lower()
        try: vmid = int(s.get("vmid")) if a != "role_switch" else 0
        except (TypeError, ValueError): return None, "étape %d : vmid entier requis" % i
        if a == "role_switch":                      # #654 : bascule de rôle (celui qui répond) -- exécutée par le central, pas par un agent
            try: role_id, to = int(s.get("role_id")), int(s.get("to"))
            except (TypeError, ValueError): return None, "étape %d : role_id et to (indice du candidat) requis" % i
            out.append(dict(agent_id="central", vmid=0, kind="qemu", action="role_switch", params=dict(role_id=role_id, to=to), label=str(s.get("label") or "")[:120], wait_s=int(s.get("wait_s") or 0)))
            continue
        if not s.get("agent_id"): return None, "étape %d : agent_id (hyperviseur) requis" % i
        if a not in ACTIONS: return None, "étape %d : action inconnue (%s)" % (i, ", ".join(ACTIONS))
        if kind not in ("qemu", "lxc"): return None, "étape %d : kind qemu ou lxc" % i
        params = dict(s.get("params") or {})
        for k in REQUIRED.get(a, ()):
            if params.get(k) in (None, ""): return None, "étape %d (%s) : paramètre %s requis" % (i, a, k)
        out.append(dict(agent_id=str(s["agent_id"]), vmid=vmid, kind=kind, action=a, params=params, label=str(s.get("label") or "")[:120], wait_s=int(s.get("wait_s") or 0)))
    return out, None

def command_params(step):
    return dict(step["params"], vmid=step["vmid"], action=step["action"], kind=step["kind"])

def simulate(db_path, plan):
    """Ce qui serait envoyé, agent par agent, avec l'état de présence de chaque agent."""
    conn = store._connect(db_path)
    try: agents = {r["agent_id"]: dict(r) for r in conn.execute("SELECT agent_id, hostname, last_seen_at FROM agents")}
    finally: conn.close()
    res = []
    for i, st in enumerate(plan["steps"], 1):
        if st["action"] == "role_switch":
            role = get_role(db_path, st["params"]["role_id"]); cand = (role or {}).get("candidates", [])
            ok = bool(role) and 0 <= st["params"]["to"] < len(cand)
            res.append(dict(index=i, label=st["label"], agent_id="central", agent_known=True, command="role_switch", params=st["params"], ok=ok,
                            error=None if ok else ("rôle inconnu" if not role else "candidat inconnu"), hostname=(role or {}).get("name")))
            continue
        a = agents.get(st["agent_id"])
        res.append(dict(index=i, label=st["label"], agent_id=st["agent_id"], agent_known=bool(a), hostname=(a or {}).get("hostname"), last_seen=(a or {}).get("last_seen_at"),
                        command="vm_action", params=command_params(st), ok=bool(a), error=None if a else "agent inconnu du central"))
    return res

def _save_run(db_path, rid, status, steps, finished=False):
    conn = store._connect(db_path)
    try:
        conn.execute("UPDATE pra_runs SET status = ?, steps = ?, finished_at = ? WHERE id = ?", (status, json.dumps(steps, ensure_ascii=False), store.now_iso() if finished else "", rid)); conn.commit()
    finally: conn.close()

def execute(db_path, plan, rid, continue_on_error, sleep=time.sleep):
    """Fil d'exécution : une commande à la fois, acquittement attendu (statut done/failed), arrêt à la première erreur."""
    try:
        return _execute(db_path, plan, rid, continue_on_error, sleep)
    except Exception as e:          # jamais un fil mort en silence : l'exécution est marquée en échec avec la cause
        _save_run(db_path, rid, "failed", [dict(index=0, status="failed", result={"error": "%s : %s" % (type(e).__name__, e)})], finished=True)
        return "failed"


def _execute(db_path, plan, rid, continue_on_error, sleep):
    steps = [dict(index=i, label=st["label"], agent_id=st["agent_id"], params=command_params(st), status="pending", command_id=None, result=None) for i, st in enumerate(plan["steps"], 1)]
    status = "running"
    for st, src in zip(steps, plan["steps"]):
        if src["action"] == "role_switch":
            r = switch_role(db_path, src["params"]["role_id"], src["params"]["to"], by_user="plan %s" % plan.get("name", ""))
            st["status"] = "done" if r.get("ok") else "failed"; st["result"] = r; status = "failed" if not r.get("ok") else status
            _save_run(db_path, rid, status, steps)
            if not r.get("ok") and not continue_on_error: break
            continue
        created = store.create_command(db_path, st["agent_id"], "vm_action", st["params"])
        cid = created["id"] if isinstance(created, dict) else created
        if not cid:
            st["status"] = "failed"; st["result"] = {"error": "agent inconnu"}; status = "failed"
            if not continue_on_error: break
            continue
        st["command_id"] = cid; st["status"] = "sent"; _save_run(db_path, rid, status, steps)
        t0 = time.time(); c = None
        while time.time() - t0 < STEP_TIMEOUT:
            c = store.get_command(db_path, cid)
            if c and c.get("status") in ("done", "failed"): break
            sleep(2)
        if not c or c.get("status") not in ("done", "failed"):
            st["status"] = "timeout"; st["result"] = {"error": "pas d'acquittement de l'agent dans le délai"}; status = "failed"
        else:
            st["status"] = "done" if c["status"] == "done" else "failed"; st["result"] = c.get("result"); status = "failed" if st["status"] == "failed" else status
        _save_run(db_path, rid, status, steps)
        if st["status"] != "done" and not continue_on_error: break
        if src.get("wait_s"): sleep(min(int(src["wait_s"]), 600))
    if status == "running": status = "done"
    _save_run(db_path, rid, status, steps, finished=True)
    return status

def start_run(db_path, plan, mode, by_user, background=True):
    conn = store._connect(db_path)
    try:
        cur = conn.execute("INSERT INTO pra_runs (plan_id, mode, status, started_at, by_user) VALUES (?,?,?,?,?)", (plan["id"], mode, "running", store.now_iso(), by_user)); rid = cur.lastrowid; conn.commit()
    finally: conn.close()
    if mode == "simulate":
        res = simulate(db_path, plan); _save_run(db_path, rid, "done" if all(r["ok"] for r in res) else "failed", res, finished=True); return rid
    t = threading.Thread(target=execute, args=(db_path, plan, rid, bool(plan.get("continue_on_error"))), daemon=True); _runs[rid] = t
    if background: t.start()
    else: t.run()
    return rid

def plan_public(r):
    d = dict(r); d["steps"] = json.loads(d.get("steps") or "[]"); d["continue_on_error"] = bool(d.get("continue_on_error")); return d

def run_public(r):
    d = dict(r); d["steps"] = json.loads(d.get("steps") or "[]"); return d


# ------------------------------------------------------------------ #654 : déclencheurs (agent hors ligne -> plan) et rôles (bascule)
def on_agent_offline(db_path, agent_id, emit, start=None):
    """Appelé par le chien de garde du central à la transition hors ligne d'un agent : les plans dont c'est le déclencheur
    sont proposés (événement `pra-suggested`, notifié) ou, si trigger_mode = auto et hors délai de garde, lancés."""
    start = start or (lambda plan: start_run(db_path, plan, "execute", "déclencheur : %s hors ligne" % agent_id))
    conn = store._connect(db_path)
    try:
        plans = [plan_public(r) for r in conn.execute("SELECT * FROM pra_plans WHERE trigger_agent_id = ?", (agent_id,))]
        last = {p["id"]: conn.execute("SELECT started_at FROM pra_runs WHERE plan_id = ? AND mode = 'execute' ORDER BY id DESC LIMIT 1", (p["id"],)).fetchone() for p in plans}
    finally: conn.close()
    fired = []
    for p in plans:
        recent = last[p["id"]] and (time.time() - _ts(last[p["id"]]["started_at"])) < int(p.get("trigger_cooldown_s") or 3600)
        if p.get("trigger_mode") == "auto" and not recent:
            rid = start(p); emit("pra-triggered", "critical", "agent %s hors ligne : plan « %s » LANCÉ automatiquement (exécution n°%s)" % (agent_id, p["name"], rid), agent_id, {"plan_id": p["id"], "run_id": rid}); fired.append((p["id"], "auto", rid))
        else:
            why = " (délai de garde : exécution récente)" if recent else ""
            emit("pra-suggested", "warning", "agent %s hors ligne : plan « %s » à lancer depuis la tuile Contrôle PVE%s" % (agent_id, p["name"], why), agent_id, {"plan_id": p["id"]}); fired.append((p["id"], "notify", None))
    return fired

def _ts(iso):
    try: return time.mktime(time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError: return 0

def role_public(r):
    d = dict(r); d["candidates"] = json.loads(d.get("candidates") or "[]"); d["mechanism"] = json.loads(d.get("mechanism") or "{}"); d["last_check"] = json.loads(d.get("last_check") or "{}"); return d

def get_role(db_path, rid):
    conn = store._connect(db_path)
    try: r = conn.execute("SELECT * FROM pra_roles WHERE id = ?", (rid,)).fetchone()
    finally: conn.close()
    return role_public(r) if r else None

def validate_role(body):
    name = (body.get("name") or "").strip()
    if not name: return None, "nom du rôle requis"
    cands = body.get("candidates") or []
    if not isinstance(cands, list) or not cands: return None, "au moins un candidat {label, address}"
    out = []
    for i, c in enumerate(cands, 1):
        if not isinstance(c, dict) or not (c.get("address") or "").strip(): return None, "candidat %d : address requise" % i
        out.append(dict(label=str(c.get("label") or c["address"])[:80], address=str(c["address"]).strip()[:120], agent_id=str(c.get("agent_id") or ""), vmid=c.get("vmid")))
    mech = body.get("mechanism") or {"kind": "manual"}
    if mech.get("kind") not in ROLE_MECHANISMS: return None, "mechanism.kind : %s" % " | ".join(ROLE_MECHANISMS)
    if mech["kind"] == "mikrotik_nat" and not (mech.get("router") and mech.get("rule_id")): return None, "mechanism mikrotik_nat : router et rule_id (ex. *1A) requis"
    return dict(name=name, service_url=str(body.get("service_url") or "").strip(), candidates=out, mechanism=mech, notes=str(body.get("notes") or "")), None

def check_role(role, http_get=None):
    """Vérifie que « celui qui répond » répond : GET service_url (5 s) ; sans URL, rien à vérifier."""
    if not role.get("service_url"): return {"checked": False}
    http_get = http_get or _http_get
    try:
        code, ms = http_get(role["service_url"]); return {"checked": True, "ok": 200 <= code < 400, "status": code, "ms": ms, "at": store.now_iso()}
    except Exception as e:
        return {"checked": True, "ok": False, "error": str(e)[:200], "at": store.now_iso()}

def _http_get(url):
    import urllib.request, ssl
    t0 = time.time(); r = urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=5, context=ssl._create_unverified_context()); return r.status, int((time.time() - t0) * 1000)

def switch_role(db_path, rid, to, by_user="", apply=None, http_get=None):
    """Bascule : applique le mécanisme (NAT MikroTik : to-addresses de la règle ; manuel : enregistrement seul), vérifie, journalise."""
    role = get_role(db_path, rid)
    if not role: return {"ok": False, "error": "rôle inconnu"}
    if not (0 <= int(to) < len(role["candidates"])): return {"ok": False, "error": "candidat inconnu"}
    cand = role["candidates"][int(to)]; mech = role["mechanism"]; applied = {"kind": mech.get("kind")}
    apply = apply or _apply_mechanism
    try: applied.update(apply(mech, cand))
    except Exception as e: return {"ok": False, "error": "mécanisme %s : %s" % (mech.get("kind"), str(e)[:200])}
    check = check_role(dict(role), http_get)
    conn = store._connect(db_path)
    try: conn.execute("UPDATE pra_roles SET active = ?, last_switch_at = ?, last_check = ?, updated_at = ? WHERE id = ?", (int(to), store.now_iso(), json.dumps(check), store.now_iso(), rid)); conn.commit()
    finally: conn.close()
    ok = not check.get("checked") or bool(check.get("ok"))
    return {"ok": ok, "role": role["name"], "to": cand, "applied": applied, "check": check, "by": by_user, "error": None if ok else "bascule appliquée mais le service ne répond pas"}

def _apply_mechanism(mech, cand):
    if mech.get("kind") == "manual": return {"note": "enregistrement seul : la redirection est faite à la main"}
    if mech.get("kind") == "mikrotik_nat":
        if not MIKROTIK_API_URL: raise RuntimeError("MIKROTIK_API_URL non configurée sur si-agent-api")
        import urllib.request
        body = json.dumps({"to-addresses": cand["address"].split(":")[0]}).encode()
        req = urllib.request.Request("%s/mikrotik/routers/%s/nat/%s" % (MIKROTIK_API_URL, mech["router"], mech["rule_id"]), data=body, headers={"Content-Type": "application/json"}, method="PATCH")
        with urllib.request.urlopen(req, timeout=15) as r: data = json.loads(r.read().decode() or "{}")
        if data.get("error"): raise RuntimeError(data["error"])
        return {"router": mech["router"], "rule_id": mech["rule_id"], "to_addresses": cand["address"].split(":")[0]}
    raise RuntimeError("mécanisme inconnu")
