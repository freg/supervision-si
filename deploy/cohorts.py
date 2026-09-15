#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cartographie des cohortes et plan de déploiement par nœud (livraisons #509, #513).

Lit docker-compose.yml (et gateway/docker-compose.yml), en déduit pour chaque
service ses dépendances (depends_on, URL `scheme://<service>:port` et
variables `*_HOST=<service>` dans l'environnement), ses ports internes
(table de tls-proxy, URL, expose, image), ses volumes (bind mounts = données
locales au nœud) et son mode réseau, puis les confronte à
`deploy/cohorts.json` (cohortes : tuile -> services, isolation) et à
`deploy/nodes.json` (nœud -> cohortes, adresse VPN).

  cohorts.py report                 rapport lisible : cohortes, dépendances croisées, données, anomalies
  cohorts.py check                  code 1 si un service n'est dans aucune cohorte ou dans deux, ou si une
                                    dépendance croisée viole l'isolation
  cohorts.py services <cohorte,…>   services de ces cohortes + toutes leurs dépendances (profil light, un seul hôte)
  cohorts.py node <nœud>            services de CE nœud (sans dépendances distantes), une par ligne
  cohorts.py override <nœud> [-o F] génère deploy/generated/node.override.yml : publication des services
                                    locaux sur l'adresse VPN du nœud + un relais (alias DNS) par service
                                    distant utilisé ici ; écrit aussi node.plan.json (services, relais)

Aucune modification de docker-compose.yml : chaque nœud lance compose avec
l'override généré (scripts/run.sh l'ajoute automatiquement s'il existe).
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
NODES_FILE = os.path.join(ROOT, "deploy", "nodes.json")
PROXY_TABLE = os.path.join(ROOT, "tls-proxy", "render_nginx_conf.py")
URL_RE = re.compile(r"[a-z][a-z0-9+.-]*://(?:[^@/\s]+@)?([a-z0-9][a-z0-9-]*)(?::(\d+))?(?:/|$)")
IMAGE_PORTS = (("postgres", 5432), ("memcached", 11211), ("elasticsearch", 9200), ("redis", 6379), ("mariadb", 3306), ("mysql", 3306), ("keycloak", 8080))
RELAY_IMAGE = "alpine/socat:1.8.0.0"
PORT_BASE = 20000  # ports VPN : PORT_BASE + 10 * rang du service + rang du port interne


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
        deps, ports = set(), set()
        d = svc.get("depends_on") or []
        deps |= set(d.keys() if isinstance(d, dict) else d)
        env = env_items(svc)
        envd = dict(env)
        for k, v in env:
            for m in URL_RE.finditer(v):
                if m.group(1) in names and m.group(1) != name:
                    deps.add(m.group(1))
            if v in names and v != name and k.upper().endswith("HOST"):  # MEMCACHED_HOST=memcached
                deps.add(v)
        binds, named = [], []
        for vol in svc.get("volumes") or []:
            src = vol.split(":")[0] if isinstance(vol, str) else (vol.get("source") or "")
            if not src:
                continue
            (binds if src.startswith((".", "/", "$", "~")) else named).append(src)
        for e in svc.get("expose") or []:
            ports.add(int(str(e).split("/")[0]))
        img = str(svc.get("image") or "")
        for needle, port in IMAGE_PORTS:
            if needle in img:
                ports.add(port)
        info[name] = {"depends": sorted(deps), "binds": binds, "named": named, "ports": ports, "env": envd,
                      "host_network": svc.get("network_mode") == "host", "published": svc.get("ports") or [],
                      "build": bool(svc.get("build")), "image": svc.get("image")}
    # ports internes vus depuis les autres services (URL, *_HOST/*_PORT) et depuis tls-proxy
    for name, i in info.items():
        for k, v in i["env"].items():
            for m in URL_RE.finditer(v):
                if m.group(1) in info and m.group(2):
                    info[m.group(1)]["ports"].add(int(m.group(2)))
            if v in info and k.upper().endswith("HOST"):
                pk = k[:-4] + "PORT"
                if str(i["env"].get(pk, "")).isdigit():
                    info[v]["ports"].add(int(i["env"][pk]))
    for svc, port in proxy_table():
        if svc in info:
            info[svc]["ports"].add(port)
    for i in info.values():
        i["ports"] = sorted(i["ports"])
    return info


def proxy_table():
    """[(service, port interne)] lus dans la table de tls-proxy/render_nginx_conf.py."""
    try:
        src = open(PROXY_TABLE, encoding="utf-8").read()
    except OSError:
        return []
    return [(m.group(1), int(m.group(2))) for m in re.finditer(r'\("[A-Z0-9_]+",\s*"([a-z0-9-]+)",\s*(\d+)', src)]


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
                flags.append("HOST NETWORK -- lancé à part sur son nœud")
            if i["binds"]:
                flags.append("données locales : " + ", ".join(i["binds"]))
            if i["named"]:
                flags.append("volumes nommés : " + ", ".join(i["named"]))
            lines.append("   - %-26s %s" % (s, " ; ".join(flags)))
        ext = [(s, d, where.get(d, "?")) for s in c["services"] for d in info.get(s, {}).get("depends", []) if where.get(d) != c["name"]]
        if ext:
            lines.append("   dépend de : " + ", ".join("%s→%s (%s)" % (s, d, cd) for s, d, cd in sorted(set(ext))))
    return "\n".join(lines)


def load_nodes(path=NODES_FILE):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def node_map(nodes):
    """cohorte -> nœud, nom -> nœud."""
    by_cohort, by_name = {}, {}
    for n in nodes["nodes"]:
        by_name[n["name"]] = n
        for c in n.get("cohorts") or []:
            by_cohort[c] = n["name"]
    return by_cohort, by_name


def vpn_port(info, service, port):
    """Port publié sur l'adresse VPN : stable (rang alphabétique du service, rang du port interne)."""
    names = sorted(info)
    ports = sorted(info[service]["ports"]) if service in info else [port]
    return PORT_BASE + 10 * names.index(service) + min(9, ports.index(port) if port in ports else 0)


def override(cohorts, services, info, where, origin, nodes, me):
    """Override compose du nœud `me` : services locaux (ceux de ses cohortes, hors gateway/ et
    hors réseau hôte) publiés sur l'adresse VPN, relais socat (alias DNS = nom du service) vers
    chaque service distant utilisé ici. Retourne (override, plan)."""
    by_cohort, by_name = node_map(nodes)
    node = by_name.get(me)
    if not node:
        raise SystemExit("nœud %s inconnu dans deploy/nodes.json" % me)
    local = [s for c in cohorts["cohorts"] if c["name"] in (node.get("cohorts") or []) for s in c["services"]
             if s in info and not info[s]["host_network"]]
    local_main = [s for s in local if not origin[s].startswith("gateway/")]
    local_gateway = [s for s in local if origin[s].startswith("gateway/")]
    host_only = [s for c in cohorts["cohorts"] if c["name"] in (node.get("cohorts") or []) for s in c["services"] if s in info and info[s]["host_network"]]
    edge = bool(node.get("edge"))
    if edge and "tls-proxy" not in local_gateway and "tls-proxy" in services:
        local_gateway.append("tls-proxy")  # bordure : jumeau de la passerelle (#510)
    # services distants à relayer : dépendances des services locaux + backends de la bordure
    needed = set()
    for s in local:
        needed |= set(info[s]["depends"])
    if "tls-proxy" in local_gateway:
        needed |= {svc for svc, _ in proxy_table() if svc in info}
        needed |= set(info.get("tls-proxy", {}).get("depends", []))
    needed -= set(local)
    out, out_gateway = {"services": {}}, {"services": {}}
    plan = {"node": me, "wg_address": node["wg_address"], "edge": edge, "services": sorted(local_main),
            "gateway": sorted(local_gateway), "host_network": host_only, "relays": [], "published": {}, "missing": []}
    for s in local_main:  # publication VPN des services locaux joignables
        if not info[s]["ports"]:
            continue
        pub = ["%s:%d:%d" % (node["wg_address"], vpn_port(info, s, p), p) for p in info[s]["ports"]]
        out["services"][s] = {"ports": pub}
        plan["published"][s] = pub
    for s in local_gateway:  # Keycloak publié sur le VPN pour la bordure distante (#510)
        if info.get(s, {}).get("ports") and s != "tls-proxy":
            pub = ["%s:%d:%d" % (node["wg_address"], vpn_port(info, s, p), p) for p in info[s]["ports"]]
            out_gateway["services"][s] = {"ports": pub}
            plan["published"][s] = pub
    for d in sorted(needed):
        host = by_name.get(by_cohort.get(where.get(d)))
        if not host:
            plan["missing"].append(d)  # cohorte non affectée à un nœud : pas de relais, service injoignable ici
            continue
        if not info[d]["ports"]:
            plan["missing"].append(d + " (port interne inconnu)")
            continue
        cmd = " & ".join("socat TCP-LISTEN:%d,fork,reuseaddr TCP:%s:%d" % (p, host["wg_address"], vpn_port(info, d, p)) for p in info[d]["ports"]) + " & wait"
        rname = "relay-" + d
        out["services"][rname] = {"image": RELAY_IMAGE, "entrypoint": ["/bin/sh", "-c"], "command": [cmd],
                                  "networks": {"default": {"aliases": [d]}}, "restart": "unless-stopped",
                                  "labels": {"si.relay": d, "si.relay.node": host["name"]}}
        plan["relays"].append(rname)
    return out, out_gateway, plan


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
    if cmd in ("node", "override"):
        if problems:
            print("cohortes incohérentes :\n - " + "\n - ".join(problems), file=sys.stderr)
            return 1
        me = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None
        if not me:
            print("nom du nœud requis (deploy/nodes.json)", file=sys.stderr)
            return 2
        nodes = load_nodes(sys.argv[sys.argv.index("--nodes") + 1] if "--nodes" in sys.argv else NODES_FILE)
        out, out_gateway, plan = override(cohorts, services, info, where, origin, nodes, me)
        if cmd == "node":
            for x in plan["services"]:
                print(x)
            return 0
        gen = os.path.join(ROOT, "deploy", "generated")
        path = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else os.path.join(gen, "node.override.yml")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# GÉNÉRÉ par deploy/cohorts.py override %s -- ne pas éditer, relancer le script.\n" % me)
            yaml.safe_dump(out, fh, allow_unicode=True, sort_keys=False, width=200)
        with open(os.path.join(os.path.dirname(path) or ".", "gateway.override.yml"), "w", encoding="utf-8") as fh:
            fh.write("# GÉNÉRÉ par deploy/cohorts.py override %s -- passerelle (gateway/docker-compose.yml).\n" % me)
            yaml.safe_dump(out_gateway, fh, allow_unicode=True, sort_keys=False, width=200)
        with open(os.path.join(os.path.dirname(path) or ".", "node.plan.json"), "w", encoding="utf-8") as fh:
            json.dump(plan, fh, indent=2, ensure_ascii=False)
        print("%s : %d services locaux, %d relais, %d publiés sur %s%s" % (
            path, len(plan["services"]), len(plan["relays"]), len(plan["published"]), plan["wg_address"],
            (" ; SANS RELAIS (cohorte non affectée / port inconnu) : " + ", ".join(plan["missing"])) if plan["missing"] else ""))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
