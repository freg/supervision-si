#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cartographie des cohortes et génération de la pile Swarm (livraison #509).

Lit docker-compose.yml (et gateway/docker-compose.yml s'il existe), en
déduit pour chaque service ses dépendances (depends_on + toute variable
d'environnement pointant `http(s)://<service>:port`), ses volumes
(bind mounts = données locales au nœud) et son mode réseau, puis les
confronte à `deploy/cohorts.json` (cohortes déclarées : tuile ->
services, placement, isolation).

  cohorts.py report            rapport lisible : cohortes, dépendances croisées, données, anomalies
  cohorts.py check             code 1 si un service n'est dans aucune cohorte ou dans deux, ou si une
                               dépendance croisée viole l'isolation
  cohorts.py services <cohorte,…>   liste des services de ces cohortes + toutes leurs dépendances (compose), une par ligne
  cohorts.py stack [-o FILE]   génère deploy/generated/stack.yml pour `docker stack deploy`
                               (build retiré, image = ${SI_REGISTRY}/si/<service>:${SI_TAG}, contraintes de
                               placement par cohorte, services en network_mode: host exclus et listés)

Aucune modification de docker-compose.yml : la pile Swarm est dérivée.
"""
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("PyYAML requis (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE_FILES = ["docker-compose.yml", "gateway/docker-compose.yml"]
COHORTS_FILE = os.path.join(ROOT, "deploy", "cohorts.json")
URL_RE = re.compile(r"https?://([a-z0-9][a-z0-9-]*)(?::\d+)?(?:/|$)")


def load_services():
    services, origin = {}, {}
    for f in COMPOSE_FILES:
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        for name, svc in (doc.get("services") or {}).items():
            services[name] = svc or {}
            origin[name] = f
    return services, origin


def env_items(svc):
    env = svc.get("environment") or {}
    if isinstance(env, dict):
        return [(k, str(v)) for k, v in env.items()]
    out = []
    for item in env:
        k, _, v = str(item).partition("=")
        out.append((k, v))
    return out


def analyse(services):
    names = set(services)
    info = {}
    for name, svc in services.items():
        deps = set()
        d = svc.get("depends_on") or []
        deps |= set(d.keys() if isinstance(d, dict) else d)
        for _, v in env_items(svc):
            for m in URL_RE.finditer(v):
                if m.group(1) in names and m.group(1) != name:
                    deps.add(m.group(1))
        binds, named = [], []
        for vol in svc.get("volumes") or []:
            src = vol.split(":")[0] if isinstance(vol, str) else (vol.get("source") or "")
            if not src:
                continue
            (binds if src.startswith((".", "/", "$", "~")) else named).append(src)
        info[name] = {"depends": sorted(deps), "binds": binds, "named": named,
                      "host_network": svc.get("network_mode") == "host", "ports": svc.get("ports") or [],
                      "build": bool(svc.get("build")), "image": svc.get("image")}
    return info


def load_cohorts():
    with open(COHORTS_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def assign(cohorts, services):
    """service -> cohorte ; anomalies (absent / en double)."""
    where, problems = {}, []
    for c in cohorts["cohorts"]:
        for s in c["services"]:
            if s in where:
                problems.append("%s est dans deux cohortes (%s, %s)" % (s, where[s], c["name"]))
            where[s] = c["name"]
    for s in services:
        if s not in where:
            problems.append("%s n'est dans aucune cohorte" % s)
    for s in where:
        if s not in services:
            problems.append("%s (cohorte %s) n'existe pas dans le compose" % (s, where[s]))
    return where, problems


def cross_deps(info, where):
    """[(cohorte, service, cohorte_cible, service_cible)] pour chaque dépendance qui sort de la cohorte."""
    out = []
    for s, i in info.items():
        for d in i["depends"]:
            if where.get(d) and where.get(s) and where[d] != where[s]:
                out.append((where[s], s, where[d], d))
    return out


def check(cohorts, info, where):
    problems = []
    by_name = {c["name"]: c for c in cohorts["cohorts"]}
    for cs, s, cd, d in cross_deps(info, where):
        if by_name[cs].get("isolated") and cd not in (by_name[cs].get("allowed_dependencies") or []):
            problems.append("cohorte isolée %s : %s dépend de %s (%s) -- à autoriser dans allowed_dependencies ou à regrouper" % (cs, s, d, cd))
    for c in cohorts["cohorts"]:
        zone = c.get("zone", "local")
        if zone == "ovh" and any(info[s]["binds"] for s in c["services"] if s in info) and not c.get("data_on_node"):
            problems.append("cohorte %s en zone ovh avec données locales : préciser data_on_node" % c["name"])
    return problems


def report(cohorts, info, where, origin):
    lines = []
    for c in cohorts["cohorts"]:
        lines.append("== %s -- %s [zone %s%s%s]" % (c["name"], c.get("title", ""), c.get("zone", "local"),
                                                    ", isolée" if c.get("isolated") else "", ", épinglée (données)" if c.get("pinned") else ""))
        for s in c["services"]:
            i = info.get(s)
            if not i:
                lines.append("   ? %s (absent du compose)" % s)
                continue
            flags = []
            if i["host_network"]:
                flags.append("HOST NETWORK -- hors Swarm")
            if i["binds"]:
                flags.append("données locales : " + ", ".join(i["binds"]))
            if i["named"]:
                flags.append("volumes nommés : " + ", ".join(i["named"]))
            lines.append("   - %-26s %s" % (s, " ; ".join(flags)))
        ext = [(s, d, where.get(d, "?")) for s in c["services"] for d in info.get(s, {}).get("depends", []) if where.get(d) != c["name"]]
        if ext:
            lines.append("   dépend de : " + ", ".join("%s→%s (%s)" % (s, d, cd) for s, d, cd in sorted(set(ext))))
    return "\n".join(lines)


def stack(cohorts, services, info, where, registry="${SI_REGISTRY:-127.0.0.1:5000}", tag="${SI_TAG:-latest}"):
    out = {"version": "3.8", "services": {}, "networks": {"default": {"external": True, "name": "${SUPERVISION_SI_NETWORK_NAME:-supervision-si-net}"}}}
    skipped, dropped = [], []
    named_volumes = set()
    by_name = {c["name"]: c for c in cohorts["cohorts"]}
    for name, svc in services.items():
        i = info[name]
        if i["host_network"]:
            skipped.append(name)
            continue
        s = dict(svc)
        s.pop("build", None)
        s.pop("depends_on", None)  # Swarm ignore depends_on ; les services retentent d'eux-mêmes
        s.pop("container_name", None)
        s.pop("restart", None)
        s.pop("network_mode", None)
        s["image"] = "%s/si/%s:%s" % (registry, name, tag) if i["build"] else (i["image"] or name)
        c = by_name.get(where.get(name))
        constraints = ["node.labels.si.cohort.%s == true" % c["name"]] if c else []
        if c and c.get("zone"):
            constraints.append("node.labels.si.zone == %s" % c["zone"])
        if name in (cohorts.get("edge_services") or []):
            # #510 : services de bordure (tls-proxy) -- une instance sur CHAQUE nœud
            # étiqueté si.edge (super pour le LAN, jumeau OVH pour l'entrée publique),
            # même image, même résolution des backends par le réseau overlay
            constraints = ["node.labels.si.edge == true"]
            s["deploy"] = {"mode": "global", "restart_policy": {"condition": "any", "delay": "5s"}, "placement": {"constraints": constraints}}
        else:
            s["deploy"] = {"mode": "replicated", "replicas": 1, "restart_policy": {"condition": "any", "delay": "5s"},
                           "placement": {"constraints": constraints}}
        # ports publiés en mode host (pas d'ingress mesh : un port = un nœud, comme aujourd'hui)
        if s.get("ports"):
            # un port lié à une adresse précise (127.0.0.1:…, ${SI_DB_BIND}) n'existe pas en
            # Swarm : ces publications locales (bases PostgreSQL pour psql) sont retirées,
            # les services se joignent par leur nom sur le réseau overlay
            kept = [p for p in s["ports"] if not (isinstance(p, str) and (p.startswith("${SI_DB_BIND") or re.match(r"^\d+\.\d+\.\d+\.\d+:", p)))]
            if len(kept) != len(s["ports"]):
                dropped.append(name)
            s["ports"] = [_port_host_mode(p) for p in kept]
            if not s["ports"]:
                del s["ports"]
        for v in i["named"]:
            named_volumes.add(v)
        out["services"][name] = s
    if named_volumes:
        out["volumes"] = {v: {} for v in sorted(named_volumes)}
    return out, skipped, dropped


_PORT_RE = re.compile(r"^(?:(?P<ip>\d+\.\d+\.\d+\.\d+):)?(?P<pub>\$\{[^}]+\}|\d+(?:-\d+)?)(?::(?P<target>\$\{[^}]+\}|\d+))?(?:/(?P<proto>udp|tcp))?$")


def _port_host_mode(p):
    """« 6443:6443 », « ${GATEWAY_PORT:-6443}:5000 », « 5514:5514/udp » ->
    syntaxe longue en mode host (les variables sont substituées par
    `docker stack deploy` depuis l'environnement du shell, voir deploy.sh)."""
    if isinstance(p, dict):
        return dict(p, mode="host")
    m = _PORT_RE.match(str(p))
    if not m:
        return p
    return {"target": m.group("target") or m.group("pub"), "published": m.group("pub"), "mode": "host", "protocol": m.group("proto") or "tcp"}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    services, origin = load_services()
    info = analyse(services)
    cohorts = load_cohorts()
    where, problems = assign(cohorts, services)
    problems += check(cohorts, info, where)
    if cmd == "report":
        print(report(cohorts, info, where, origin))
        print("\n%d service(s), %d cohorte(s), %d dépendance(s) croisée(s)" % (len(services), len(cohorts["cohorts"]), len(cross_deps(info, where))))
        if problems:
            print("\nANOMALIES :\n - " + "\n - ".join(problems))
        return 0
    if cmd == "check":
        if problems:
            print("\n".join(problems))
            return 1
        print("ok : %d services répartis en %d cohortes" % (len(services), len(cohorts["cohorts"])))
        return 0
    if cmd == "services":
        wanted = set((sys.argv[2] if len(sys.argv) > 2 else "core").split(","))
        chosen = [s for c in cohorts["cohorts"] if c["name"] in wanted for s in c["services"] if s in info]
        todo, seen = list(chosen), set()
        while todo:  # fermeture transitive des dépendances : compose les démarrera de toute façon
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            todo.extend(d for d in info.get(x, {}).get("depends", []) if d not in seen)
        skipped = [x for x in seen if info[x]["host_network"]]
        want_gateway = "--gateway" in sys.argv  # services de gateway/docker-compose.yml (Keycloak, tls-proxy…)
        for x in sorted(seen):
            if x not in skipped and (origin[x].startswith("gateway/")) == want_gateway:
                print(x)
        if skipped:
            print("# hors compose (network_mode: host, à lancer à part) : " + ", ".join(skipped), file=sys.stderr)
        return 0
    if cmd == "stack":
        if problems:
            print("cohortes incohérentes :\n - " + "\n - ".join(problems), file=sys.stderr)
            return 1
        out, skipped, dropped = stack(cohorts, services, info, where)
        path = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else os.path.join(ROOT, "deploy", "generated", "stack.yml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# GÉNÉRÉ par deploy/cohorts.py -- ne pas éditer, relancer le script.\n")
            yaml.safe_dump(out, fh, allow_unicode=True, sort_keys=False, width=200)
        print("%s : %d services ; hors Swarm (network_mode: host, à lancer avec compose sur leur nœud) : %s ; ports liés à une adresse locale retirés : %s"
              % (path, len(out["services"]), ", ".join(skipped) or "aucun", ", ".join(dropped) or "aucun"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
