# -*- coding: utf-8 -*-
"""#653 : plans de reprise / d'exploitation PVE (PRA) -- un plan = une suite ordonnée d'étapes {agent_id, vmid, kind, action,
params}, chaque étape = une commande `vm_action` adressée à l'agent de l'hyperviseur (migrate, backup, move_disk, clone,
replicate, start, shutdown…). Exécution séquentielle par le central : la commande est mise en file, le central attend
l'acquittement de l'agent (délai par étape), s'arrête à la première erreur sauf `continue_on_error`. Mode « simuler » :
validation de chaque étape et liste des commandes qui seraient envoyées, sans rien envoyer. Un seul worker gunicorn :
le fil d'exécution vit dans le processus (motif #522/#586)."""
import json, time, threading
import store

ACTIONS = ("migrate", "backup", "move_disk", "clone", "replicate", "unreplicate", "start", "shutdown", "stop", "reboot", "snapshot", "rollback")
REQUIRED = {"migrate": ("target",), "backup": ("storage",), "move_disk": ("disk", "storage"), "clone": ("newid",), "replicate": ("target",), "snapshot": ("snapname",), "rollback": ("snapname",)}
STEP_TIMEOUT = 3600
_runs = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS pra_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT DEFAULT 'pra', notes TEXT DEFAULT '',
    steps TEXT NOT NULL DEFAULT '[]', continue_on_error INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS pra_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
    started_at TEXT, finished_at TEXT DEFAULT '', by_user TEXT DEFAULT '', steps TEXT NOT NULL DEFAULT '[]');
"""

def init(db_path):
    conn = store._connect(db_path)
    try: conn.executescript(SCHEMA); conn.commit()
    finally: conn.close()

def validate_steps(steps):
    """-> (étapes normalisées, erreur) ; chaque étape : agent_id, vmid > 0, kind qemu|lxc, action connue, paramètres requis présents."""
    if not isinstance(steps, list) or not steps: return None, "au moins une étape"
    out = []
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict): return None, "étape %d : objet attendu" % i
        try: vmid = int(s.get("vmid"))
        except (TypeError, ValueError): return None, "étape %d : vmid entier requis" % i
        a = str(s.get("action") or "").lower(); kind = str(s.get("kind") or "qemu").lower()
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
