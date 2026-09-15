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

API (jeton dans l'en-tête X-SI-Node-Token, en clair MAIS uniquement sur le VPN WireGuard) :
  GET  /status                        nœud, cohortes, conteneurs, plan courant
  POST /apply    {"nodes": {...}, "build": false}   remplace deploy/nodes.json puis applique
  POST /stop     {"cohort": "tickets"}
  GET  /export/<cohorte>              flux tar.gz
  POST /import/<cohorte> {"from": "10.99.0.2"}      va chercher l'export sur le nœud source et le restaure

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

    def do_POST(self):
        if not self._auth():
            return
        try:
            body = self._body()
            if self.path == "/apply":
                if body.get("nodes"):
                    with open(NODES, "w", encoding="utf-8") as fh:
                        json.dump(body["nodes"], fh, indent=2, ensure_ascii=False)
                return self._json(200, apply(self.me, bool(body.get("build"))))
            if self.path == "/stop":
                return self._json(200, {"stopped": stop_cohort(body["cohort"])})
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
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
