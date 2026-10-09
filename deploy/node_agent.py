#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent de nœud du déploiement réparti (livraison #513) -- module indépendant
sur CHAQUE hôte, bibliothèque standard seulement (tourne sur l'hôte, pas dans
un conteneur : il pilote docker compose du dépôt local).

  node_agent.py serve                 API HTTP sur l'adresse VPN du nœud (port SI_NODE_PORT, jeton SI_NODE_TOKEN)
  node_agent.py apply [--build]       applique deploy/nodes.json ici : override, compose up des services
                                      de ce nœud + relais, arrêt de ce qui n'y est plus
  node_agent.py stop <cohorte>        arrête les services d'une cohorte (données conservées)
  node_agent.py export <cohorte> > f  archive tar.gz des données de la cohorte (bind mounts + volumes nommés)
  node_agent.py import <cohorte> < f  restaure une archive ici (mêmes chemins, volumes recréés)
  node_agent.py status                état local (JSON)
  node_agent.py update                #659 : git pull --ff-only puis apply --build ici
  node_agent.py update-all            #659 : même chose sur TOUS les autres nœuds de nodes.json (POST /update, jeton du .env)
  node_agent.py instance-deploy <nom> #732 (manager) : crée l'instance sur son nœud puis rafraîchit les passerelles
  node_agent.py instance-create <nom> | instance-gateway | instance-stop <nom>   étapes locales correspondantes

API (jeton dans l'en-tête X-SI-Node-Token, en clair MAIS uniquement sur le VPN WireGuard) :
  GET  /status                        nœud, cohortes, conteneurs, plan courant
  POST /apply    {"nodes": {...}, "build": false}   remplace deploy/nodes.json puis applique
  POST /stop     {"cohort": "tickets"}
  GET  /export/<cohorte>              flux tar.gz
  POST /import/<cohorte> {"from": "10.99.0.2"}      va chercher l'export sur le nœud source et le restaure
  POST /update   {"build": true}      #659 : git pull --ff-only (origin, branche courante) puis apply
  POST /instance {"registry", "name", "build"}   #732 : instance clonée ici (apply + clonage de la configuration)
  POST /instance/gateway {"registry"}  #732 : relais, routes tls-proxy rechargées, redirections Keycloak synchronisées
  POST /instance/stop {"name"}         #732 : conteneurs de l'instance retirés, données conservées
  #663 miroir froid (étape 3) : ce nœud reçoit les archives de sauvegarde totale du primaire et les restaure, services arrêtés
  GET  /mirror/status                 archives reçues, services en marche, dernière restauration
  PUT  /mirror/archive/<nom>          corps = archive (ou manifeste .manifest.json), déposée dans backups/mirror/
  GET  /mirror/archive/<nom>          renvoie une archive (retour arrière : le primaire récupère la sauvegarde du miroir)
  POST /mirror/restore {"archive": nom, "force": false}   full_backup.py restore --into <dépôt> --force (refusé si des services tournent)
  POST /mirror/backup                 full_backup.py backup --out backups/mirror (quand ce nœud est actif) -> {archive}
  POST /mirror/takeover {"host_ip"}   regenerate --host-ip puis run-all.sh all up -d : le miroir devient actif
  POST /mirror/standby                run-all.sh all down : retour en miroir froid (données conservées)

Le manager (deploy/repartition.py) enchaîne stop → import → nodes.json → apply partout.
Aucun secret n'est journalisé ; le jeton n'est jamais renvoyé.
"""
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "deploy", "generated")
NODES = os.path.join(ROOT, "deploy", "nodes.json")
PLAN = os.path.join(GEN, "node.plan.json")
NAME_FILE = os.path.join(GEN, "node.name")
DEFAULT_PORT = 6460


def load_env(path=os.path.join(ROOT, ".env")):
    """.env clé par clé (non sourçable : valeurs avec espaces non citées)."""
    env = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.rstrip("\n"))
                if m:
                    env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def node_name():
    try:
        return open(NAME_FILE, encoding="utf-8").read().strip() or socket.gethostname().split(".")[0]
    except OSError:
        return socket.gethostname().split(".")[0]


def run(cmd, check=True, capture=False, stdin=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(cmd, cwd=ROOT, check=False, stdin=stdin, env=e,
                       stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None, text=capture)
    if check and r.returncode != 0:
        raise RuntimeError("%s -> code %d%s" % (" ".join(cmd[:3]), r.returncode, (" : " + (r.stderr or "")[-400:]) if capture else ""))
    return r


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- plan / apply
def make_plan(me):
    """Génère override + plan pour ce nœud (deploy/cohorts.py override)."""
    os.makedirs(GEN, exist_ok=True)
    run([sys.executable, os.path.join(ROOT, "deploy", "cohorts.py"), "override", me], capture=True)
    return read_json(PLAN)


def compose_running():
    """Services du projet principal actuellement lancés."""
    r = run(["./scripts/run.sh", "ps", "--services", "--status", "running"], check=False, capture=True)
    return [x.strip() for x in (r.stdout or "").splitlines() if re.match(r"^[a-z0-9][a-z0-9_-]*$", x.strip())]


def apply(me, build=False):
    plan = make_plan(me)
    wanted = plan["services"] + plan["relays"]
    steps = []
    if plan["gateway"]:
        # passerelle (projet compose distinct) : tout sur le nœud core, tls-proxy seul sur une bordure
        args = ["./gateway/scripts/run.sh", "up", "-d"] + (["--build"] if build else [])
        if "keycloak" not in plan["gateway"]:
            args += plan["gateway"]
        run(args, capture=True)
        steps.append("gateway: " + " ".join(plan["gateway"]))
    if wanted:
        # --no-deps : les dépendances distantes (relais = alias DNS) ne doivent pas être lancées ici
        run(["./scripts/run.sh", "up", "-d", "--no-deps", "--remove-orphans"] + (["--build"] if build else []) + wanted, capture=True)
        steps.append("up: %d services, %d relais" % (len(plan["services"]), len(plan["relays"])))
    extra = [s for s in compose_running() if s not in wanted]
    if extra:
        run(["./scripts/run.sh", "stop"] + extra, capture=True)
        steps.append("stop (plus sur ce nœud) : " + " ".join(extra))
    for s in plan["host_network"]:
        run(["./scripts/run.sh", "up", "-d", "--no-deps"] + (["--build"] if build else []) + [s], capture=True)
        steps.append("réseau hôte : " + s)
    plan["steps"] = steps
    return plan


def git_update(me, build=True):
    """#659 : dépôt local tiré en avance rapide (origin/<branche courante>), puis apply --build. Refus si des fichiers suivis
    sont modifiés localement (jamais d'écrasement silencieux)."""
    run(["git", "checkout", "--", "shared/VERSION.json", "shared/EXPOSURE.json"], check=False, capture=True)   # régénérés par run.sh
    dirty = [l for l in (run(["git", "status", "--porcelain", "--untracked-files=no"], capture=True).stdout or "").splitlines() if l.strip()]
    if dirty:
        raise RuntimeError("fichiers suivis modifiés sur ce nœud : " + ", ".join(l[3:] if len(l) > 3 else l for l in dirty[:5]))
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True).stdout.strip() or "main"
    before = run(["git", "rev-parse", "--short", "HEAD"], capture=True).stdout.strip()
    pull = run(["git", "pull", "--ff-only", "origin", branch], capture=True)
    after = run(["git", "rev-parse", "--short", "HEAD"], capture=True).stdout.strip()
    plan = apply(me, build)
    return {"node": me, "branch": branch, "from": before, "to": after, "pull": (pull.stdout or "").strip()[-300:], "steps": plan.get("steps", [])}


def update_all(timeout=3600):
    """#659 : POST /update sur chaque autre nœud (adresse VPN, jeton du .env) ; -> {node: résultat|erreur}, échec global si un nœud échoue."""
    env = load_env(); me = node_name(); token = env.get("SI_NODE_TOKEN", ""); port = int(env.get("SI_NODE_PORT") or DEFAULT_PORT)
    if not token:
        raise RuntimeError("SI_NODE_TOKEN absent du .env")
    out, failed = {}, []
    for n in read_json(NODES).get("nodes", []):
        if n["name"] == me or not n.get("wg_address"):
            continue
        req = urllib.request.Request("http://%s:%d/update" % (n["wg_address"], port), data=json.dumps({"build": True}).encode(), method="POST",
                                     headers={"X-SI-Node-Token": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out[n["name"]] = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            out[n["name"]] = {"error": (e.read() or b"")[:300].decode("utf-8", "replace")}; failed.append(n["name"])
        except Exception as e:  # noqa: BLE001
            out[n["name"]] = {"error": str(e)[:300]}; failed.append(n["name"])
    if failed:
        raise RuntimeError("nœud(s) en échec : %s -- %s" % (", ".join(failed), json.dumps(out, ensure_ascii=False)[:800]))
    return out


# ---------------------------------------------------------------- #732 : instances d'application clonées
REGISTRY = os.path.join(ROOT, "deploy", "instances.json")


def _ins():
    sys.path.insert(0, os.path.join(ROOT, "deploy"))
    import instances
    return instances


def write_registry(reg):
    if reg is not None:
        if not isinstance(reg, dict) or not isinstance(reg.get("instances"), list):
            raise RuntimeError("registre d'instances invalide")
        with open(REGISTRY, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=2, ensure_ascii=False)


def instance_create(me, name, registry=None, build=True):
    """Sur le nœud CIBLE : registre, apply (services clonés + relais vers la source), puis clonage de la
    configuration dans le conteneur API de l'instance. Les données métier ne sont jamais copiées."""
    write_registry(registry)
    ins = _ins(); reg = ins.load_registry(REGISTRY)
    inst = next((i for i in reg["instances"] if i.get("name") == name), None)
    if not inst:
        raise RuntimeError("instance %s absente du registre" % name)
    if inst.get("node") != me:
        raise RuntimeError("instance %s prévue sur %s, pas sur %s" % (name, inst.get("node"), me))
    plan = apply(me, build)
    p = ins.plan(inst)
    missing = [x for x in p["services"] if x not in plan["services"]]
    if missing:
        raise RuntimeError("services de l'instance absents du plan de ce nœud : " + ", ".join(missing))
    out = {"node": me, "instance": p, "steps": plan.get("steps", []), "config": None}
    script = ins.config_clone_script(inst["app"])
    if script:
        api = ins.svc_name(ins.APPS[inst["app"]]["config_import"][0], name)
        r = run(["./scripts/run.sh", "exec", "-T", api, "python3", "-c", script], check=False, capture=True)
        last = ((r.stdout or "").strip().splitlines() or [""])[-1]
        try:
            out["config"] = json.loads(last) if r.returncode == 0 else {"error": ((r.stderr or "") + (r.stdout or ""))[-400:]}
        except ValueError:
            out["config"] = {"error": last[-400:]}
    return out


def instance_gateway(me, registry=None):
    """Sur la passerelle (bordure / core) : registre, apply (relais vers l'instance), routes tls-proxy rendues puis
    rechargées, et URL de redirection Keycloak poussées dans le realm vivant si Keycloak est ici."""
    write_registry(registry)
    plan = apply(me, False)
    steps = list(plan.get("steps", []))
    if "tls-proxy" in plan.get("gateway", []):
        run([sys.executable, os.path.join(ROOT, "tls-proxy", "render_nginx_conf.py")], capture=True)
        r = run(["./gateway/scripts/run.sh", "exec", "-T", "tls-proxy", "nginx", "-s", "reload"], check=False, capture=True)
        if r.returncode != 0:
            run(["./gateway/scripts/run.sh", "restart", "tls-proxy"], capture=True)
        steps.append("tls-proxy : routes rendues et rechargées")
    if "keycloak" in plan.get("gateway", []):
        run([sys.executable, os.path.join(ROOT, "keycloak", "render.py")], capture=True)
        r = run([sys.executable, os.path.join(ROOT, "keycloak", "sync_clients.py")], check=False, capture=True)
        steps.append("keycloak : redirections %s" % ("synchronisées" if r.returncode == 0 else "NON synchronisées : " + (r.stderr or r.stdout or "")[-200:]))
    return {"node": me, "steps": steps}


def instance_stop(me, name):
    """Arrête et retire les conteneurs d'une instance sur ce nœud ; données conservées dans ./instances/<nom>/."""
    ins = _ins(); reg = ins.load_registry(REGISTRY)
    inst = next((i for i in reg["instances"] if i.get("name") == name), None)
    if not inst:
        raise RuntimeError("instance %s absente du registre" % name)
    svcs = ins.plan(inst)["services"]
    run(["./scripts/run.sh", "rm", "-s", "-f"] + svcs, check=False, capture=True)
    return {"node": me, "stopped": svcs, "data_kept": ins.plan(inst)["data"]}


def node_call(node, path, body, timeout=3600):
    env = load_env(); token = env.get("SI_NODE_TOKEN", ""); port = int(env.get("SI_NODE_PORT") or DEFAULT_PORT)
    if not token:
        raise RuntimeError("SI_NODE_TOKEN absent du .env")
    req = urllib.request.Request("http://%s:%d%s" % (node["wg_address"], port, path), data=json.dumps(body).encode(), method="POST",
                                 headers={"X-SI-Node-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError("%s %s : %s" % (node["name"], path, (e.read() or b"")[:300].decode("utf-8", "replace")))


def instance_deploy(name, build=True, call=None):
    """Depuis le manager : crée l'instance sur son nœud (registre transmis), puis rafraîchit chaque passerelle."""
    call = call or node_call
    me = node_name(); ins = _ins(); reg = ins.load_registry(REGISTRY); nodes = read_json(NODES)
    probs = ins.check(reg, nodes=nodes)
    if probs:
        raise RuntimeError("registre incohérent : " + " ; ".join(probs))
    inst = next((i for i in reg["instances"] if i.get("name") == name), None)
    if not inst:
        raise RuntimeError("instance %s absente du registre" % name)
    by = {n["name"]: n for n in nodes["nodes"]}
    out = {"create": instance_create(me, name, None, build) if inst["node"] == me else call(by[inst["node"]], "/instance", {"registry": reg, "name": name, "build": build}),
           "gateways": {}}
    for g in ins.gateway_nodes(nodes):
        out["gateways"][g] = instance_gateway(me) if g == me else call(by[g], "/instance/gateway", {"registry": reg})
    return out


# ---------------------------------------------------------------- #663 : miroir froid
MIRROR_DIR = os.path.join(ROOT, "backups", "mirror")
MIRROR_STATE = os.path.join(GEN, "mirror.state.json")
ARCHIVE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(tar\.gz(\.enc)?|manifest\.json)$")


def mirror_state(update=None):
    st = {}
    try:
        st = read_json(MIRROR_STATE)
    except (OSError, ValueError):
        pass
    if update:
        st.update(update); os.makedirs(GEN, exist_ok=True)
        with open(MIRROR_STATE, "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=2, ensure_ascii=False)
    return st


def mirror_archives(d=MIRROR_DIR):
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = os.path.join(d, f)
        if os.path.isfile(p) and ARCHIVE_RE.match(f):
            out.append({"name": f, "size": os.path.getsize(p), "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(p)))})
    return out


def mirror_status():
    return {"node": node_name(), "archives": mirror_archives(), "running": compose_running(), "state": mirror_state(),
            "version": open(os.path.join(ROOT, "shared", "DELIVERY_NUMBER")).read().strip() if os.path.exists(os.path.join(ROOT, "shared", "DELIVERY_NUMBER")) else None}


def mirror_restore(archive, force=False):
    """Restauration d'une archive reçue PAR-DESSUS ce dépôt (données, volumes, .env, PKI) -- miroir froid : rien ne doit tourner."""
    if not ARCHIVE_RE.match(archive or "") or archive.endswith(".manifest.json"):
        raise RuntimeError("archive : nom d'archive .tar.gz(.enc) attendu")
    running = compose_running()
    if running and not force:
        raise RuntimeError("des services tournent sur ce nœud (%s) : miroir actif ? standby d'abord, ou force" % ", ".join(running[:5]))
    path = os.path.join(MIRROR_DIR, archive)
    if not os.path.isfile(path):
        raise RuntimeError("archive absente : " + archive)
    env = load_env(); e = {"SI_BACKUP_PASSPHRASE": env.get("SI_BACKUP_PASSPHRASE", "")} if env.get("SI_BACKUP_PASSPHRASE") else None
    t0 = time.time()
    r = run([sys.executable, os.path.join(ROOT, "scripts", "full_backup.py"), "restore", path, "--into", ROOT, "--force"], capture=True, env=e)
    st = {"last_restore": time.strftime("%Y-%m-%dT%H:%M:%S"), "last_archive": archive, "restore_seconds": int(time.time() - t0)}
    mirror_state(st)
    return dict(st, output=(r.stdout or "")[-800:])


def mirror_backup():
    """Sauvegarde totale de CE nœud (quand il est actif) vers backups/mirror, pour le retour arrière."""
    env = load_env(); e = {"SI_BACKUP_PASSPHRASE": env.get("SI_BACKUP_PASSPHRASE", "")} if env.get("SI_BACKUP_PASSPHRASE") else None
    os.makedirs(MIRROR_DIR, exist_ok=True)
    before = {a["name"] for a in mirror_archives()}
    run([sys.executable, os.path.join(ROOT, "scripts", "full_backup.py"), "backup", "--out", MIRROR_DIR], capture=True, env=e)
    new = [a for a in mirror_archives() if a["name"] not in before and not a["name"].endswith(".manifest.json")]
    if not new:
        raise RuntimeError("aucune archive produite")
    return {"archive": new[-1]["name"], "size": new[-1]["size"]}


def mirror_takeover(host_ip):
    """Le miroir devient actif : ce qui est propre à l'hôte est régénéré (HOST_IP, certificat serveur, conf nginx ; CA et sels conservés), puis tout démarre."""
    if host_ip and not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host_ip):
        raise RuntimeError("host_ip invalide")
    steps = []
    args = [sys.executable, os.path.join(ROOT, "scripts", "full_backup.py"), "regenerate"] + (["--host-ip", host_ip] if host_ip else [])
    r = run(args, capture=True); steps.append("regenerate : " + (r.stdout or "").strip().splitlines()[-1][:200] if (r.stdout or "").strip() else "regenerate")
    run(["./scripts/run-all.sh", "all", "up", "-d"], capture=True); steps.append("run-all all up -d")
    mirror_state({"active_since": time.strftime("%Y-%m-%dT%H:%M:%S"), "active": True})
    return {"steps": steps, "running": compose_running()}


def mirror_standby():
    run(["./scripts/run-all.sh", "all", "down"], capture=True)
    mirror_state({"active": False, "standby_since": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return {"running": compose_running()}


def stop_cohort(cohort):
    cohorts = read_json(os.path.join(ROOT, "deploy", "cohorts.json"))
    svcs = next((c["services"] for c in cohorts["cohorts"] if c["name"] == cohort), None)
    if svcs is None:
        raise RuntimeError("cohorte inconnue : " + cohort)
    running = compose_running()
    todo = [s for s in svcs if s in running]
    if todo:
        run(["./scripts/run.sh", "stop"] + todo, capture=True)
    return todo


# ---------------------------------------------------------------- données
def cohort_data(cohort):
    """(bind dirs absolus, volumes nommés) des services d'une cohorte, variables du .env résolues."""
    import yaml  # PyYAML : déjà requis par cohorts.py
    env = load_env()
    cohorts = read_json(os.path.join(ROOT, "deploy", "cohorts.json"))
    svcs = next((c["services"] for c in cohorts["cohorts"] if c["name"] == cohort), None)
    if svcs is None:
        raise RuntimeError("cohorte inconnue : " + cohort)
    binds, volumes = set(), set()
    for f in ("docker-compose.yml", "gateway/docker-compose.yml"):
        try:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
        except OSError:
            continue
        prefix = "supervision-si-gateway_" if f.startswith("gateway/") else env.get("COMPOSE_PROJECT_NAME", "supervision-si") + "_"
        for name, svc in (doc.get("services") or {}).items():
            if name not in svcs:
                continue
            for v in svc.get("volumes") or []:
                src = v.split(":")[0] if isinstance(v, str) else (v.get("source") or "")
                if not src:
                    continue
                src = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}", lambda m: env.get(m.group(1)) or (m.group(2) or ""), src)
                if src == "." or src.startswith(("./", "../", "/", "~")):
                    p = os.path.abspath(os.path.join(ROOT, os.path.expanduser(src)))
                    if p == ROOT or p.startswith("/var/run") or p.endswith(".sock") or not os.path.isdir(p):
                        continue  # le dépôt lui-même (.:/project), sockets, fichiers seuls : pas des données
                    binds.add(p)
                elif not src.startswith("$"):
                    volumes.add(prefix + src)
    return sorted(binds), sorted(volumes)


def export_cohort(cohort, out):
    """tar.gz : bind/<chemin relatif au dépôt> ou abs/<chemin> ; volume/<nom>.tar."""
    binds, volumes = cohort_data(cohort)
    with tarfile.open(fileobj=out, mode="w|gz") as tar:
        for p in binds:
            rel = os.path.relpath(p, ROOT)
            arc = ("bind/" + rel) if not rel.startswith("..") else ("abs" + p)
            tar.add(p, arcname=arc)
        for v in volumes:
            r = subprocess.run(["docker", "volume", "inspect", v], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode != 0:
                continue
            with tempfile.NamedTemporaryFile(dir=GEN, suffix=".tar", delete=False) as tmp:
                pass
            try:
                with open(tmp.name, "wb") as fh:
                    subprocess.run(["docker", "run", "--rm", "-v", v + ":/v:ro", "alpine", "tar", "cf", "-", "-C", "/v", "."], stdout=fh, check=True)
                tar.add(tmp.name, arcname="volume/%s.tar" % v)
            finally:
                os.unlink(tmp.name)
    return binds, volumes


def _safe_member(m, base):
    dest = os.path.abspath(os.path.join(base, m.name))
    return dest == base or dest.startswith(base + os.sep)


def import_cohort(cohort, src):
    """Restaure une archive produite par export_cohort (flux binaire)."""
    _, expected_volumes = cohort_data(cohort)
    restored = {"binds": [], "volumes": []}
    with tarfile.open(fileobj=src, mode="r|gz") as tar:
        for m in tar:
            if m.name.startswith("bind/"):
                m.name = m.name[len("bind/"):]
                if not _safe_member(m, ROOT):
                    raise RuntimeError("chemin refusé : " + m.name)
                tar.extract(m, ROOT)
                top = m.name.split("/")[0]
                if top not in restored["binds"]:
                    restored["binds"].append(top)
            elif m.name.startswith("abs/"):
                m.name = m.name[len("abs"):]
                if not _safe_member(m, "/") or m.name.startswith(("/etc", "/proc", "/sys", "/dev")):
                    raise RuntimeError("chemin refusé : " + m.name)
                tar.extract(m, "/")
            elif m.name.startswith("volume/") and m.name.endswith(".tar") and m.isfile():
                v = os.path.basename(m.name)[:-4]
                if v not in expected_volumes:
                    raise RuntimeError("volume inattendu : " + v)
                subprocess.run(["docker", "volume", "create", v], check=True, stdout=subprocess.DEVNULL)
                fh = tar.extractfile(m)
                subprocess.run(["docker", "run", "--rm", "-i", "-v", v + ":/v", "alpine", "sh", "-c", "rm -rf /v/* /v/..?* /v/.[!.]* 2>/dev/null; tar xf - -C /v"],
                               stdin=fh, check=True)
                restored["volumes"].append(v)
    return restored


def status(me):
    plan = read_json(PLAN) if os.path.exists(PLAN) else None
    nodes = read_json(NODES) if os.path.exists(NODES) else None
    mine = next((n for n in (nodes or {}).get("nodes", []) if n["name"] == me), None)
    return {"node": me, "cohorts": (mine or {}).get("cohorts"), "wg_address": (mine or {}).get("wg_address"),
            "running": compose_running(), "plan": plan and {k: plan[k] for k in ("services", "relays", "gateway", "missing")},
            "version": open(os.path.join(ROOT, "shared", "DELIVERY_NUMBER")).read().strip() if os.path.exists(os.path.join(ROOT, "shared", "DELIVERY_NUMBER")) else None,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    token = ""
    me = ""

    def log_message(self, fmt, *args):  # journal sans en-têtes (jamais le jeton)
        sys.stderr.write("%s %s %s\n" % (time.strftime("%H:%M:%S"), self.client_address[0], fmt % args))

    def _auth(self):
        if self.headers.get("X-SI-Node-Token", "") != self.token or not self.token:
            self._json(401, {"error": "jeton absent ou invalide"})
            return False
        return True

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if not self._auth():
            return
        if self.path == "/status":
            return self._json(200, status(self.me))
        if self.path == "/mirror/status":
            return self._json(200, mirror_status())
        if self.path.startswith("/mirror/archive/"):
            name = self.path[len("/mirror/archive/"):]
            p = os.path.join(MIRROR_DIR, name)
            if not ARCHIVE_RE.match(name) or not os.path.isfile(p):
                return self._json(404, {"error": "archive inconnue"})
            self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.send_header("Content-Length", str(os.path.getsize(p))); self.end_headers()
            with open(p, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile, 1 << 20)
            return
        if self.path.startswith("/export/"):
            cohort = self.path[len("/export/"):]
            try:
                cohort_data(cohort)
            except RuntimeError as e:
                return self._json(404, {"error": str(e)})
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.end_headers()
            export_cohort(cohort, self.wfile)
            return
        self._json(404, {"error": "inconnu"})

    def do_PUT(self):
        if not self._auth():
            return
        name = self.path[len("/mirror/archive/"):] if self.path.startswith("/mirror/archive/") else ""
        if not ARCHIVE_RE.match(name):
            return self._json(400, {"error": "nom d'archive invalide"})
        os.makedirs(MIRROR_DIR, exist_ok=True)
        n = int(self.headers.get("Content-Length") or 0); part = os.path.join(MIRROR_DIR, name + ".part")
        with open(part, "wb") as fh:
            left = n
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                fh.write(chunk); left -= len(chunk)
        if left:
            os.remove(part); return self._json(400, {"error": "corps incomplet"})
        os.replace(part, os.path.join(MIRROR_DIR, name))
        return self._json(201, {"name": name, "size": n})

    def do_POST(self):
        if not self._auth():
            return
        try:
            body = self._body()
            if self.path == "/mirror/restore":
                return self._json(200, mirror_restore(str(body.get("archive") or ""), bool(body.get("force"))))
            if self.path == "/mirror/backup":
                return self._json(200, mirror_backup())
            if self.path == "/mirror/takeover":
                return self._json(200, mirror_takeover(str(body.get("host_ip") or "")))
            if self.path == "/mirror/standby":
                return self._json(200, mirror_standby())
            if self.path == "/apply":
                if body.get("nodes"):
                    with open(NODES, "w", encoding="utf-8") as fh:
                        json.dump(body["nodes"], fh, indent=2, ensure_ascii=False)
                return self._json(200, apply(self.me, bool(body.get("build"))))
            if self.path == "/stop":
                return self._json(200, {"stopped": stop_cohort(body["cohort"])})
            if self.path == "/update":
                return self._json(200, git_update(self.me, body.get("build", True)))
            if self.path == "/instance":   # #732
                return self._json(200, instance_create(self.me, str(body.get("name") or ""), body.get("registry"), bool(body.get("build", True))))
            if self.path == "/instance/gateway":
                return self._json(200, instance_gateway(self.me, body.get("registry")))
            if self.path == "/instance/stop":
                return self._json(200, instance_stop(self.me, str(body.get("name") or "")))
            if self.path.startswith("/import/"):
                cohort = self.path[len("/import/"):]
                url = "http://%s:%d/export/%s" % (body["from"], int(body.get("port") or DEFAULT_PORT), cohort)
                req = urllib.request.Request(url, headers={"X-SI-Node-Token": self.token})
                with urllib.request.urlopen(req, timeout=3600) as resp:
                    return self._json(200, import_cohort(cohort, resp))
            self._json(404, {"error": "inconnu"})
        except Exception as e:  # noqa: BLE001 -- message sans secret (commandes, codes retour)
            self._json(500, {"error": str(e)[:600]})


def serve():
    env = load_env()
    me = node_name()
    nodes = read_json(NODES)
    mine = next((n for n in nodes["nodes"] if n["name"] == me), None)
    if not mine:
        sys.exit("nœud %s inconnu dans deploy/nodes.json (deploy/generated/node.name)" % me)
    Handler.token = env.get("SI_NODE_TOKEN", "")
    Handler.me = me
    if not Handler.token:
        sys.exit("SI_NODE_TOKEN absent du .env")
    port = int(env.get("SI_NODE_PORT") or DEFAULT_PORT)
    srv = ThreadingHTTPServer((mine["wg_address"], port), Handler)
    sys.stderr.write("si-node-agent %s sur %s:%d\n" % (me, mine["wg_address"], port))
    srv.serve_forever()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    me = node_name()
    if cmd == "serve":
        return serve()
    if cmd == "apply":
        print(json.dumps(apply(me, "--build" in sys.argv), indent=2, ensure_ascii=False))
    elif cmd == "stop":
        print(json.dumps({"stopped": stop_cohort(sys.argv[2])}))
    elif cmd == "export":
        export_cohort(sys.argv[2], sys.stdout.buffer)
    elif cmd == "import":
        print(json.dumps(import_cohort(sys.argv[2], sys.stdin.buffer)))
    elif cmd == "status":
        print(json.dumps(status(me), indent=2, ensure_ascii=False))
    elif cmd == "update":
        print(json.dumps(git_update(me, "--no-build" not in sys.argv), indent=2, ensure_ascii=False))
    elif cmd == "instance-deploy":   # #732 : depuis le manager
        print(json.dumps(instance_deploy(sys.argv[2], "--no-build" not in sys.argv), indent=2, ensure_ascii=False))
    elif cmd == "instance-create":
        print(json.dumps(instance_create(me, sys.argv[2], None, "--no-build" not in sys.argv), indent=2, ensure_ascii=False))
    elif cmd == "instance-gateway":
        print(json.dumps(instance_gateway(me), indent=2, ensure_ascii=False))
    elif cmd == "instance-stop":
        print(json.dumps(instance_stop(me, sys.argv[2]), indent=2, ensure_ascii=False))
    elif cmd == "update-all":
        print(json.dumps(update_all(), indent=2, ensure_ascii=False))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
