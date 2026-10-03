# -*- coding: utf-8 -*-
"""#653 : plans de reprise / d'exploitation PVE (PRA) -- un plan = une suite ordonnée d'étapes {agent_id, vmid, kind, action,
params}, chaque étape = une commande `vm_action` adressée à l'agent de l'hyperviseur (migrate, backup, move_disk, clone,
replicate, start, shutdown…). Exécution séquentielle par le central : la commande est mise en file, le central attend
l'acquittement de l'agent (délai par étape), s'arrête à la première erreur sauf `continue_on_error`. Mode « simuler » :
validation de chaque étape et liste des commandes qui seraient envoyées, sans rien envoyer. Un seul worker gunicorn :
le fil d'exécution vit dans le processus (motif #522/#586)."""
import json, time, threading
import store

ACTIONS = ("migrate", "backup", "move_disk", "clone", "replicate", "unreplicate", "start", "shutdown", "stop", "reboot", "snapshot", "rollback", "role_switch",
           # #658 (item 112) : migration vers la virtualisation -- create / import_disk / set / destroy (vm_action sur le nœud), image_host
           # (image à chaud du serveur source), host_shutdown (power_action sur le serveur source), checkpoint (étape de transition :
           # le plan attend « Reprendre » ou « Abandonner » depuis le hub)
           "create", "import_disk", "set", "destroy", "image_host", "host_shutdown", "checkpoint")
REQUIRED = {"migrate": ("target",), "backup": ("storage",), "move_disk": ("disk", "storage"), "clone": ("newid",), "replicate": ("target",), "snapshot": ("snapname",), "rollback": ("snapname",),
            "create": ("name",), "import_disk": ("source", "storage"), "set": ("options",), "destroy": ("confirm",), "image_host": ("target",)}
HOST_ACTIONS = ("image_host", "host_shutdown")          # adressées à l'agent du serveur source (pas de vmid)
CENTRAL_ACTIONS = ("role_switch", "checkpoint")          # exécutées par le central
STEP_TIMEOUT = 3600
IMAGE_TIMEOUT = 12 * 3600       # image à chaud + transfert au central
CHECKPOINT_TIMEOUT = 7 * 86400  # une transition attend l'opérateur (au plus une semaine)
IMAGES_DIR = ""                 # fixé par app.py (SI_AGENT_IMAGES_DIR)
_runs, _resume, _abort = {}, {}, {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS pra_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT DEFAULT 'pra', notes TEXT DEFAULT '',
    steps TEXT NOT NULL DEFAULT '[]', continue_on_error INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS pra_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
    started_at TEXT, finished_at TEXT DEFAULT '', by_user TEXT DEFAULT '', steps TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS pra_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, service_url TEXT DEFAULT '', candidates TEXT NOT NULL DEFAULT '[]',
    mechanism TEXT NOT NULL DEFAULT '{}', active INTEGER DEFAULT 0, last_switch_at TEXT DEFAULT '', last_check TEXT DEFAULT '{}', notes TEXT DEFAULT '', created_at TEXT, updated_at TEXT);
"""
MIGRATIONS = (("pra_plans", "trigger_agent_id", "TEXT DEFAULT ''"), ("pra_plans", "trigger_mode", "TEXT DEFAULT 'notify'"), ("pra_plans", "trigger_cooldown_s", "INTEGER DEFAULT 3600"),
              ("pra_plans", "rollback_steps", "TEXT DEFAULT '[]'"), ("pra_plans", "auto_rollback", "INTEGER DEFAULT 0"), ("pra_runs", "parent_run_id", "INTEGER DEFAULT 0"))
ROLE_MECHANISMS = ("manual", "mikrotik_nat", "dns", "keepalived")
MIKROTIK_API_URL = __import__("os").environ.get("MIKROTIK_API_URL", "").rstrip("/")
DNS_API_URL = __import__("os").environ.get("DNS_API_URL", "").rstrip("/")        # #656 : bascule par enregistrement DNS (dns-api, fallback intranet inclus)
VRRP_WAIT_S = 120

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
        try: vmid = int(s.get("vmid")) if a not in CENTRAL_ACTIONS + HOST_ACTIONS else 0
        except (TypeError, ValueError): return None, "étape %d : vmid entier requis" % i
        if a == "role_switch":                      # #654 : bascule de rôle (celui qui répond) -- exécutée par le central, pas par un agent
            try: role_id, to = int(s.get("role_id")), int(s.get("to"))
            except (TypeError, ValueError): return None, "étape %d : role_id et to (indice du candidat) requis" % i
            out.append(dict(agent_id="central", vmid=0, kind="qemu", action="role_switch", params=dict(role_id=role_id, to=to), label=str(s.get("label") or "")[:120], wait_s=int(s.get("wait_s") or 0)))
            continue
        if a == "checkpoint":                       # #658 : étape de transition -- le plan s'arrête et attend l'opérateur
            if not str(s.get("label") or "").strip(): return None, "étape %d : checkpoint sans consigne (label)" % i
            out.append(dict(agent_id="central", vmid=0, kind="qemu", action="checkpoint", params=dict(timeout_s=int(s.get("timeout_s") or 0)), label=str(s.get("label") or "")[:300], wait_s=0))
            continue
        if a in HOST_ACTIONS:                       # #658 : commande au serveur source (image à chaud, arrêt)
            if not s.get("agent_id"): return None, "étape %d : agent_id (serveur source) requis" % i
            params = dict(s.get("params") or {})
            for k in REQUIRED.get(a, ()):
                if params.get(k) in (None, ""): return None, "étape %d (%s) : paramètre %s requis" % (i, a, k)
            out.append(dict(agent_id=str(s["agent_id"]), vmid=0, kind="host", action=a, params=params, label=str(s.get("label") or "")[:200], wait_s=int(s.get("wait_s") or 0)))
            continue
        if not s.get("agent_id"): return None, "étape %d : agent_id (hyperviseur) requis" % i
        if a not in ACTIONS: return None, "étape %d : action inconnue (%s)" % (i, ", ".join(ACTIONS))
        if kind not in ("qemu", "lxc"): return None, "étape %d : kind qemu ou lxc" % i
        params = {k: v for k, v in dict(s.get("params") or {}).items() if v is not None}
        for k in REQUIRED.get(a, ()):
            if params.get(k) in (None, ""): return None, "étape %d (%s) : paramètre %s requis" % (i, a, k)
        if a == "destroy" and str(params.get("confirm")) != str(vmid): return None, "étape %d (destroy) : confirm doit répéter le vmid" % i
        out.append(dict(agent_id=str(s["agent_id"]), vmid=vmid, kind=kind, action=a, params=params, label=str(s.get("label") or "")[:200], wait_s=int(s.get("wait_s") or 0)))
    return out, None

def command_params(step):
    if step["action"] == "host_shutdown": return dict(step["params"], action="shutdown")
    if step["action"] == "image_host": return dict(step["params"], transfer=True)
    return dict(step["params"], vmid=step["vmid"], action=step["action"], kind=step["kind"])

def command_type(step):
    return {"host_shutdown": "power_action", "image_host": "image_host"}.get(step["action"], "vm_action")

def simulate(db_path, plan):
    """Ce qui serait envoyé, agent par agent, avec l'état de présence de chaque agent."""
    conn = store._connect(db_path)
    try: agents = {r["agent_id"]: dict(r) for r in conn.execute("SELECT agent_id, hostname, last_seen_at FROM agents")}
    finally: conn.close()
    res = []
    for i, st in enumerate(plan["steps"], 1):
        if st["action"] == "checkpoint":
            res.append(dict(index=i, label=st["label"], agent_id="central", agent_known=True, command="checkpoint", params={}, ok=True, error=None, hostname="opérateur")); continue
        if st["action"] == "role_switch":
            role = get_role(db_path, st["params"]["role_id"]); cand = (role or {}).get("candidates", [])
            ok = bool(role) and 0 <= st["params"]["to"] < len(cand)
            res.append(dict(index=i, label=st["label"], agent_id="central", agent_known=True, command="role_switch", params=st["params"], ok=ok,
                            error=None if ok else ("rôle inconnu" if not role else "candidat inconnu"), hostname=(role or {}).get("name")))
            continue
        a = agents.get(st["agent_id"])
        res.append(dict(index=i, label=st["label"], agent_id=st["agent_id"], agent_known=bool(a), hostname=(a or {}).get("hostname"), last_seen=(a or {}).get("last_seen_at"),
                        command=command_type(st), params=command_params(st), ok=bool(a), error=None if a else "agent inconnu du central"))
    return res

def _save_run(db_path, rid, status, steps, finished=False):
    conn = store._connect(db_path)
    try:
        conn.execute("UPDATE pra_runs SET status = ?, steps = ?, finished_at = ? WHERE id = ?", (status, json.dumps(steps, ensure_ascii=False), store.now_iso() if finished else "", rid)); conn.commit()
    finally: conn.close()

SLEEP = time.sleep


def execute(db_path, plan, rid, continue_on_error, sleep=None):
    """Fil d'exécution : une commande à la fois, acquittement attendu (statut done/failed), arrêt à la première erreur."""
    try:
        return _execute(db_path, plan, rid, continue_on_error, sleep or SLEEP)
    except Exception as e:          # jamais un fil mort en silence : l'exécution est marquée en échec avec la cause
        _save_run(db_path, rid, "failed", [dict(index=0, status="failed", result={"error": "%s : %s" % (type(e).__name__, e)})], finished=True)
        return "failed"


def _execute(db_path, plan, rid, continue_on_error, sleep):
    steps = [dict(index=i, label=st["label"], agent_id=st["agent_id"], params=command_params(st), status="pending", command_id=None, result=None) for i, st in enumerate(plan["steps"], 1)]
    status = "running"; ctx = {}
    for st, src in zip(steps, plan["steps"]):
        if _abort.get(rid):
            st["status"] = "aborted"; st["result"] = {"error": "abandonné depuis le hub"}; status = "failed"; break
        if src["action"] == "checkpoint":          # #658 : transition -- attendre Reprendre / Abandonner
            st["status"] = "waiting"; _save_run(db_path, rid, "paused", steps)
            ev = _resume.setdefault(rid, threading.Event()); ev.clear()
            ok = ev.wait(min(int(src["params"].get("timeout_s") or 0) or CHECKPOINT_TIMEOUT, CHECKPOINT_TIMEOUT))
            if _abort.get(rid): st["status"] = "aborted"; st["result"] = {"error": "abandonné à la transition"}; status = "failed"; break
            if not ok: st["status"] = "timeout"; st["result"] = {"error": "transition sans réponse dans le délai"}; status = "failed"; break
            st["status"] = "done"; st["result"] = {"resumed_at": store.now_iso()}; _save_run(db_path, rid, "running", steps); continue
        if src["action"] == "role_switch":
            r = switch_role(db_path, src["params"]["role_id"], src["params"]["to"], by_user="plan %s" % plan.get("name", ""))
            st["status"] = "done" if r.get("ok") else "failed"; st["result"] = r; status = "failed" if not r.get("ok") else status
            _save_run(db_path, rid, status, steps)
            if not r.get("ok") and not continue_on_error: break
            continue
        if st["params"].get("source") == "{{image}}":
            if not ctx.get("image"): st["status"] = "failed"; st["result"] = {"error": "aucune image reçue par une étape image_host précédente"}; status = "failed"; break
            st["params"] = dict(st["params"], source=ctx["image"])
        baseline = _last_event_id(db_path)
        created = store.create_command(db_path, st["agent_id"], command_type(src), st["params"])
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
        if st["status"] == "done" and src["action"] == "image_host":      # l'image part en tâche de fond : attendre sa réception par le central
            _save_run(db_path, rid, status, steps)
            img = _wait_image(db_path, st["agent_id"], baseline, sleep)
            if img.get("ok"): ctx["image"] = "central:%s/%s" % (st["agent_id"], img["name"]); st["result"] = dict(st["result"] or {}, image=img)
            else: st["status"] = "failed"; st["result"] = dict(st["result"] or {}, error=img.get("error")); status = "failed"
        _save_run(db_path, rid, status, steps)
        if st["status"] != "done" and not continue_on_error: break
        if src.get("wait_s"): sleep(min(int(src["wait_s"]), 600))
    if status == "running": status = "done"
    _save_run(db_path, rid, status, steps, finished=True)
    _resume.pop(rid, None); _abort.pop(rid, None)
    if status == "failed" and plan.get("auto_rollback") and plan.get("rollback_steps") and plan.get("_mode", "execute") != "rollback":
        start_rollback(db_path, plan, rid, "retour automatique (échec de l'exécution n°%s)" % rid)
    return status


def _last_event_id(db_path):
    conn = store._connect(db_path)
    try: r = conn.execute("SELECT MAX(id) AS m FROM events").fetchone(); return int(r["m"] or 0)
    finally: conn.close()


def _wait_image(db_path, agent_id, baseline, sleep):
    """Après image_host : attend l'événement image-received (image complète sur le central) ou image-failed / image-upload-failed."""
    t0 = time.time()
    while time.time() - t0 < IMAGE_TIMEOUT:
        conn = store._connect(db_path)
        try: rows = conn.execute("SELECT kind, message, details FROM events WHERE id > ? AND agent_id = ? AND kind IN ('image-received','image-failed','image-upload-failed') ORDER BY id", (baseline, agent_id)).fetchall()
        finally: conn.close()
        for r in rows:
            det = json.loads(r["details"] or "{}") if isinstance(r["details"], str) else (r["details"] or {})
            if r["kind"] == "image-received": return {"ok": True, "name": str(det.get("path") or "").replace("\\", "/").split("/")[-1], "path": det.get("path"), "sha256": det.get("sha256")}
            return {"ok": False, "error": r["message"]}
        sleep(5)
    return {"ok": False, "error": "image non reçue dans le délai (%d h)" % (IMAGE_TIMEOUT // 3600)}


def resume_run(db_path, rid):
    """#658 : « Reprendre » à une transition."""
    ev = _resume.get(rid)
    if not ev: return {"ok": False, "error": "exécution n°%s pas en attente dans ce processus (redémarrage du central ? relancer le plan)" % rid}
    ev.set(); return {"ok": True}


def abort_run(db_path, rid, rollback=False, by_user=""):
    """#658 : « Abandonner » (à une transition ou entre deux étapes), avec retour en arrière si demandé."""
    _abort[rid] = True
    ev = _resume.get(rid)
    if ev: ev.set()
    t = _runs.get(rid)
    if t and t.is_alive(): t.join(10)
    out = {"ok": True, "aborted": rid}
    if rollback:
        conn = store._connect(db_path)
        try:
            run = conn.execute("SELECT plan_id FROM pra_runs WHERE id = ?", (rid,)).fetchone()
            row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (run["plan_id"],)).fetchone() if run else None
        finally: conn.close()
        if not row: return {"ok": False, "error": "plan inconnu"}
        out["rollback_run_id"] = start_rollback(db_path, plan_public(row), rid, by_user or "abandon")
    return out


def start_rollback(db_path, plan, parent_rid, by_user, background=True):
    """Exécution des rollback_steps du plan (mode rollback, liée à l'exécution d'origine)."""
    rb = plan.get("rollback_steps") or []
    if not rb: return None
    sub = dict(plan, steps=rb, _mode="rollback", auto_rollback=False)
    conn = store._connect(db_path)
    try:
        cur = conn.execute("INSERT INTO pra_runs (plan_id, mode, status, started_at, by_user, parent_run_id) VALUES (?,?,?,?,?,?)", (plan["id"], "rollback", "running", store.now_iso(), by_user, parent_rid)); rid = cur.lastrowid; conn.commit()
    finally: conn.close()
    t = threading.Thread(target=execute, args=(db_path, sub, rid, True), daemon=True); _runs[rid] = t
    if background: t.start()
    else: t.run()
    return rid

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
    d = dict(r); d["steps"] = json.loads(d.get("steps") or "[]"); d["continue_on_error"] = bool(d.get("continue_on_error"))
    d["rollback_steps"] = json.loads(d.get("rollback_steps") or "[]"); d["auto_rollback"] = bool(d.get("auto_rollback")); return d

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
    if mech["kind"] == "dns" and not (mech.get("zone") and mech.get("record")): return None, "mechanism dns : zone et record (nom relatif, ex. www) requis"
    if mech["kind"] == "keepalived":
        if not mech.get("instance"): return None, "mechanism keepalived : instance VRRP requise"
        if not all(c.get("agent_id") for c in out): return None, "mechanism keepalived : chaque candidat porte l'agent_id de son hôte"
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
    cand = role["candidates"][int(to)]; mech = dict(role["mechanism"], _db_path=db_path, _candidates=role["candidates"]); applied = {"kind": mech.get("kind")}
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
    if mech.get("kind") == "dns":
        if not DNS_API_URL: raise RuntimeError("DNS_API_URL non configurée sur si-agent-api")
        import urllib.request
        body = json.dumps({"name": mech["record"], "type": mech.get("type") or "A", "value": cand["address"].split(":")[0], "ttl": int(mech.get("ttl") or 60), "by_user": "bascule de rôle"}).encode()
        req = urllib.request.Request("%s/zones/%s/records" % (DNS_API_URL, mech["zone"]), data=body, headers={"Content-Type": "application/json"}, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=30) as r: data = json.loads(r.read().decode() or "{}"); code = r.status
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode() or "{}"); code = e.code
        if code >= 500 or data.get("error"): raise RuntimeError(data.get("error") or ("statut " + str(data.get("status"))))
        return {"zone": mech["zone"], "record": mech["record"], "value": cand["address"].split(":")[0], "status": data.get("status"), "providers": (data.get("change") or {}).get("results")}
    if mech.get("kind") == "keepalived":
        return _apply_keepalived(mech, cand)
    if mech.get("kind") == "mikrotik_nat":
        if not MIKROTIK_API_URL: raise RuntimeError("MIKROTIK_API_URL non configurée sur si-agent-api")
        import urllib.request
        body = json.dumps({"to-addresses": cand["address"].split(":")[0]}).encode()
        req = urllib.request.Request("%s/mikrotik/routers/%s/nat/%s" % (MIKROTIK_API_URL, mech["router"], mech["rule_id"]), data=body, headers={"Content-Type": "application/json"}, method="PATCH")
        with urllib.request.urlopen(req, timeout=15) as r: data = json.loads(r.read().decode() or "{}")
        if data.get("error"): raise RuntimeError(data["error"])
        return {"router": mech["router"], "rule_id": mech["rule_id"], "to_addresses": cand["address"].split(":")[0]}
    raise RuntimeError("mécanisme inconnu")


def _apply_keepalived(mech, cand, candidates=None, sleep=time.sleep):
    """Priorité haute (200) sur l'agent du candidat choisi, basse (100) sur les autres candidats du rôle ; acquittements attendus."""
    db_path = mech.get("_db_path"); others = [c for c in (candidates or mech.get("_candidates") or []) if c.get("agent_id") and c["agent_id"] != cand.get("agent_id")]
    if not cand.get("agent_id"): raise RuntimeError("candidat sans agent_id")
    sent = []
    for c, prio in [(cand, int(mech.get("high") or 200))] + [(o, int(mech.get("low") or 100)) for o in others]:
        created = store.create_command(db_path, c["agent_id"], "vrrp_set", {"instance": mech["instance"], "priority": prio})
        cid = created["id"] if isinstance(created, dict) else created
        if not cid: raise RuntimeError("agent %s inconnu" % c["agent_id"])
        sent.append((c["agent_id"], cid, prio))
    results = {}; t0 = time.time()
    while time.time() - t0 < VRRP_WAIT_S and len(results) < len(sent):
        for agent_id, cid, prio in sent:
            if agent_id in results: continue
            cmd = store.get_command(db_path, cid)
            if cmd and cmd.get("status") in ("done", "failed"): results[agent_id] = {"ok": cmd["status"] == "done", "priority": prio, "error": (cmd.get("result") or {}).get("error")}
        if len(results) < len(sent): sleep(1)
    missing = [a for a, _, _ in sent if a not in results]
    if missing: raise RuntimeError("pas d'acquittement de : " + ", ".join(missing))
    if not results[cand["agent_id"]]["ok"]: raise RuntimeError("candidat choisi : " + str(results[cand["agent_id"]]["error"]))
    return {"instance": mech["instance"], "priorities": results}
