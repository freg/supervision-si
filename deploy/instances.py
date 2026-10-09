#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Instances d'application clonées (livraison #731, item 117 tranche 2) -- registre et génération.

Une instance = une copie d'une application (portail tickets, GED…) sous un autre nom, sur un nœud choisi, avec ses
propres données. Le registre `deploy/instances.json` (ignoré par git, modèle : instances.example.json) liste
`{name, app, node, title}` ; ce module en déduit, sans toucher à docker-compose.yml :

  - les services clonés `<service>-<name>` (même construction, données dans `./instances/<name>/<service>`, adresses
    internes et chemins publics renommés, base SQLite forcée : jamais la base de l'instance d'origine) ;
  - une cohorte `inst-<name>` affectée au nœud de l'instance (deploy/cohorts.py l'intègre : override du nœud avec la
    définition complète des services, relais sur les autres nœuds) ;
  - les routes publiques `/tickets-<name>/`, `/api/tickets-<name>/` (tls-proxy/render_nginx_conf.py les ajoute).

  instances.py list | check            registre et anomalies (code 1 si anomalie)
  instances.py plan <name>             services, routes, données, export/import de configuration (JSON)

Le clonage de la configuration (référentiels, jamais de données métier) est fait par l'agent de nœud (tranche 3) :
GET <source>/export?scope=config puis POST <instance>/import?mode=merge.
"""
import copy
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "deploy", "instances.json")
NAME_RE = re.compile(r"^[a-z][a-z0-9]{1,19}$")
RESERVED = {"api", "auth", "admin", "portal", "hub", "static", "data", "test", "dev", "prod"}

# Applications clonables : services à cloner, route publique de chacun, variables à forcer, export de configuration.
APPS = {
    "tickets": {
        "title": "Portail tickets",
        "services": {
            "tickets-api": {"port": 5000, "path": "/api/tickets/", "kind": "api", "data": "/data",
                            "force_env": {"DB_BACKEND": "sqlite", "TICKETS_DB_PATH": "/data/tickets.db"}},
            "tickets-portal": {"port": 5173, "path": "/tickets/", "kind": "spa", "base_env": "VITE_BASE"},
        },
        "config_export": ("tickets-api", 5000, "/export?scope=config"),
        "config_import": ("tickets-api", 5000, "/import?mode=merge"),
        "front": "tickets-portal",
        "keycloak_client": "tickets-portal",
    },
    "ged": {
        "title": "GED (API ; le front reste la tuile du hub)",
        "services": {"ged-api": {"port": 5000, "path": "/api/ged/", "kind": "api", "data": "/data"}},
        "config_export": None,   # à faire : types et plan de classement (tranche 1 GED)
        "config_import": None,
        "front": None,
        "keycloak_client": None,
    },
}


def load_registry(path=REGISTRY):
    if not os.path.isfile(path):
        return {"instances": []}
    with open(path, encoding="utf-8") as fh:
        reg = json.load(fh)
    reg.setdefault("instances", [])
    return reg


def svc_name(service, name):
    return "%s-%s" % (service, name)


def inst_path(path, name):
    """/tickets/ -> /tickets-<name>/ ; /api/tickets/ -> /api/tickets-<name>/."""
    p = path.rstrip("/")
    return "%s-%s/" % (p, name)


def _rewrite(value, renames, paths):
    v = str(value)
    for old, new in renames.items():   # adresses internes : http://tickets-api:5000 -> http://tickets-api-x:5000
        v = re.sub(r"(?<=://)%s(?=[:/]|$)" % re.escape(old), new, v)
    if paths:   # chemins publics, en une passe (le plus long d'abord) : …/api/tickets -> …/api/tickets-x
        table = {o.rstrip("/"): n.rstrip("/") for o, n in paths.items()}
        rx = re.compile("(%s)(?=/|$|[?#\"'\\s])" % "|".join(re.escape(o) for o in sorted(table, key=len, reverse=True)))
        v = rx.sub(lambda m: table[m.group(1)], v)
    return v


def clone_app(services, app, name, source=None):
    """Définitions compose des services clonés de l'application `app` pour l'instance `name` -> {service: définition}."""
    spec = APPS[app]
    renames = {s: svc_name(s, name) for s in spec["services"]}
    paths = {c["path"]: inst_path(c["path"], name) for c in spec["services"].values()}
    out = {}
    for s, conf in spec["services"].items():
        if s not in services:
            raise ValueError("service %s absent du compose" % s)
        d = copy.deepcopy(services[s])
        for k in ("container_name", "ports", "profiles"):
            d.pop(k, None)
        env = d.get("environment") or []
        items = list(env.items()) if isinstance(env, dict) else [tuple(str(e).partition("=")[::2]) for e in env]
        envd = {k: _rewrite(v, renames, paths) for k, v in items}
        envd.update(conf.get("force_env") or {})
        if conf.get("base_env"):
            envd[conf["base_env"]] = inst_path(conf["path"], name)
        envd["SI_INSTANCE"] = name
        if spec.get("config_export") and spec["config_export"][0] == s:   # #732 : source de la configuration (relais créé par cohorts.py)
            envd["SI_INSTANCE_SOURCE_URL"] = "http://%s:%d" % (source or s, spec["config_export"][1])
        d["environment"] = ["%s=%s" % kv for kv in envd.items()]
        if conf.get("data"):
            vols = [v for v in d.get("volumes") or [] if not (isinstance(v, str) and v.split(":")[-1] in (conf["data"], conf["data"] + ":rw"))]
            d["volumes"] = ["./instances/%s/%s:%s" % (name, s, conf["data"])] + vols
        deps = d.get("depends_on") or []
        if isinstance(deps, dict):
            d["depends_on"] = {renames.get(k, k): v for k, v in deps.items()}
        else:
            d["depends_on"] = [renames.get(x, x) for x in deps]
        labels = d.get("labels") or {}
        if isinstance(labels, list):
            labels = dict(str(x).partition("=")[::2] for x in labels)
        labels.update({"si.instance": name, "si.instance.app": app, "si.instance.source": s})
        d["labels"] = labels
        out[renames[s]] = d
    return out


def check(registry, services=None, nodes=None, existing_paths=()):
    """Anomalies du registre (noms, applications, nœuds, doublons, collisions de routes)."""
    problems, seen, node_names = [], set(), {n["name"] for n in (nodes or {}).get("nodes", [])} if nodes else None
    used = set(existing_paths)
    for i, inst in enumerate(registry.get("instances") or [], 1):
        n, app = inst.get("name"), inst.get("app")
        if not isinstance(n, str) or not NAME_RE.match(n) or n in RESERVED:
            problems.append("instance %d : nom « %s » invalide (a-z0-9, 2 à 20, commence par une lettre, pas un mot réservé)" % (i, n))
            continue
        if n in seen:
            problems.append("instance %s en double" % n)
        seen.add(n)
        if app not in APPS:
            problems.append("instance %s : application « %s » inconnue (%s)" % (n, app, ", ".join(sorted(APPS))))
            continue
        if node_names is not None and inst.get("node") not in node_names:
            problems.append("instance %s : nœud « %s » absent de deploy/nodes.json" % (n, inst.get("node")))
        for s, c in APPS[app]["services"].items():
            p = inst_path(c["path"], n)
            if p in used:
                problems.append("instance %s : route %s déjà utilisée" % (n, p))
            used.add(p)
            if services is not None and s not in services:
                problems.append("instance %s : service source %s absent du compose" % (n, s))
    return problems


def instance_services(registry, services):
    """Tous les services clonés du registre -> ({service: définition}, {service: origine « instance:<name> »})."""
    out, origin = {}, {}
    for inst in registry.get("instances") or []:
        if inst.get("app") not in APPS or not NAME_RE.match(str(inst.get("name") or "")):
            continue
        for s, d in clone_app(services, inst["app"], inst["name"], inst.get("source")).items():
            out[s], origin[s] = d, "instance:%s" % inst["name"]
    return out, origin


def instance_cohorts(registry):
    """Cohortes `inst-<name>` (une par instance) et affectation cohorte -> nœud."""
    cohorts, nodes = [], {}
    for inst in registry.get("instances") or []:
        if inst.get("app") not in APPS:
            continue
        c = "inst-%s" % inst["name"]
        cohorts.append({"name": c, "title": "Instance %s (%s)" % (inst["name"], APPS[inst["app"]]["title"]), "zone": inst.get("zone", "local"),
                        "instance": inst["name"], "services": [svc_name(s, inst["name"]) for s in APPS[inst["app"]]["services"]]})
        nodes[c] = inst.get("node")
    return cohorts, nodes


def attach(nodes, registry):
    """Ajoute (en mémoire) la cohorte de chaque instance à son nœud."""
    _, where = instance_cohorts(registry)
    for n in nodes.get("nodes", []):
        n["cohorts"] = [c for c in n.get("cohorts") or [] if not c.startswith("inst-")] + sorted(c for c, node in where.items() if node == n["name"])
    return nodes


def routes(registry):
    """Routes publiques des instances, au format de la table SERVICES de tls-proxy/render_nginx_conf.py."""
    out = []
    for inst in registry.get("instances") or []:
        if inst.get("app") not in APPS or not NAME_RE.match(str(inst.get("name") or "")):
            continue
        for s, c in APPS[inst["app"]]["services"].items():
            out.append(("INSTANCE_%s" % inst["name"].upper(), svc_name(s, inst["name"]), c["port"], inst_path(c["path"], inst["name"]), c["kind"]))
    return out


def plan(inst):
    """Ce que l'agent de nœud et la tuile ont besoin de savoir d'une instance."""
    spec = APPS[inst["app"]]; n = inst["name"]
    p = {"name": n, "app": inst["app"], "node": inst.get("node"), "title": inst.get("title") or "",
         "services": [svc_name(s, n) for s in spec["services"]],
         "routes": {svc_name(s, n): inst_path(c["path"], n) for s, c in spec["services"].items()},
         "data": ["instances/%s/%s" % (n, s) for s, c in spec["services"].items() if c.get("data")],
         "front": inst_path(spec["services"][spec["front"]]["path"], n) if spec.get("front") else None}
    if spec.get("config_export"):
        s, port, q = spec["config_export"]
        src = inst.get("source") or s
        p["config_export"] = "http://%s:%d%s" % (src, port, q)
        s2, port2, q2 = spec["config_import"]
        p["config_import"] = "http://%s:%d%s" % (svc_name(s2, n), port2, q2)
    return p


def config_clone_script(app):
    """Script Python joué DANS le conteneur API de l'instance (#732) : attend sa santé, lit la configuration de la
    source (SI_INSTANCE_SOURCE_URL, joignable par relais) et l'importe en fusion. Rien d'autre que les référentiels."""
    spec = APPS[app]
    if not spec.get("config_export"):
        return None
    _, port, exp = spec["config_export"]
    _, port2, imp = spec["config_import"]
    return "\n".join([
        "import json, os, time, urllib.request",
        "src = os.environ['SI_INSTANCE_SOURCE_URL']; dst = 'http://127.0.0.1:%d'" % port2,
        "for _ in range(90):",
        "    try:",
        "        urllib.request.urlopen(dst + '/health', timeout=3); break",
        "    except Exception:",
        "        time.sleep(2)",
        "else:",
        "    raise SystemExit('instance non prête (santé)')",
        "data = urllib.request.urlopen(src + %r, timeout=60).read()" % exp,
        "req = urllib.request.Request(dst + %r, data=data, headers={'Content-Type': 'application/json'}, method='POST')" % imp,
        "res = urllib.request.urlopen(req, timeout=180).read()",
        "print(json.dumps({'exported_bytes': len(data), 'import': json.loads(res or b'{}')}, ensure_ascii=False))",
    ])


def keycloak_redirects(registry, hub_url):
    """URL de redirection Keycloak à ajouter par client OIDC pour les fronts des instances -> {client: [url/, …]}."""
    out = {}
    base = hub_url.rstrip("/")
    for inst in registry.get("instances") or []:
        spec = APPS.get(inst.get("app"))
        if not spec or not spec.get("front") or not spec.get("keycloak_client") or not NAME_RE.match(str(inst.get("name") or "")):
            continue
        out.setdefault(spec["keycloak_client"], []).append(base + inst_path(spec["services"][spec["front"]]["path"], inst["name"]))
    return out


def gateway_nodes(nodes):
    """Nœuds portant la passerelle (bordure ou cohorte core) : routes tls-proxy et Keycloak à rafraîchir."""
    return [n["name"] for n in (nodes or {}).get("nodes", []) if n.get("edge") or "core" in (n.get("cohorts") or [])]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "list"
    reg = load_registry()
    if cmd == "list":
        for inst in reg["instances"]:
            print("%-14s %-8s nœud %-14s %s" % (inst.get("name"), inst.get("app"), inst.get("node"), inst.get("title") or ""))
        return 0
    if cmd == "check":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import cohorts as co
        services, _ = co.load_services(with_instances=False)
        nodes = co.load_nodes() if os.path.isfile(co.NODES_FILE) else None
        probs = check(reg, services, nodes, [p for _, p in co.proxy_paths()])
        print("\n".join(probs) if probs else "ok : %d instance(s)" % len(reg["instances"]))
        return 1 if probs else 0
    if cmd == "plan" and len(argv) > 1:
        inst = next((i for i in reg["instances"] if i.get("name") == argv[1]), None)
        if not inst:
            print("instance %s absente du registre" % argv[1], file=sys.stderr)
            return 2
        print(json.dumps(plan(inst), indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
