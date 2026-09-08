#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventaire d'EXPOSITION du SI (livraison #455) -> shared/EXPOSURE.json.

Lu par si-proxy-admin-api (/exposure) pour l'onglet « Entrées » de la
console Bastion : tout ce qui est joignable de l'extérieur du réseau
Docker, d'après les fichiers de configuration RÉELS du dépôt (jamais une
liste maintenue à la main) :

  - les routes de la passerelle TLS (liste SERVICES de
    tls-proxy/render_nginx_conf.py) : un seul port public GATEWAY_PORT ;
  - les ports publiés DIRECTEMENT sur l'hôte par docker-compose.yml
    (`ports:`), c'est-à-dire ce qui CONTOURNE la passerelle ; la valeur
    par défaut de `${VAR:-défaut}` est retenue, et le bind (127.0.0.1 =
    boucle locale seulement) est conservé ;
  - les services en `network_mode: host` (pile réseau de l'hôte).

Généré par scripts/run.sh à chaque lancement (même mécanique que
VERSION.json) et committé pour que `docker compose build` fonctionne sans
run.sh. Logique pure (parse_compose / build_exposure), testée dans
scripts/test_render_exposure.py.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_VAR = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def resolve(value, env=None):
    """'${X:-6129}:5000' -> '6129:5000' (env prioritaire si fourni)."""
    env = env or {}

    def rep(m):
        name, default = m.group(1), m.group(2)
        return env.get(name) or (default or "")
    return _VAR.sub(rep, str(value))


def parse_port(spec):
    """'127.0.0.1:6452:6452' | '6450:6450' | '5514:514/udp' -> dict."""
    s = str(spec).strip().strip('"').strip("'")
    proto = "tcp"
    if "/" in s:
        s, proto = s.rsplit("/", 1)
    parts = s.split(":")
    if len(parts) == 3:
        bind, host, cont = parts
    elif len(parts) == 2:
        bind, host, cont = "0.0.0.0", parts[0], parts[1]
    else:
        bind, host, cont = "0.0.0.0", parts[0], parts[0]
    return {"bind": bind or "0.0.0.0", "host_port": host, "container_port": cont, "proto": proto,
            "loopback_only": bind in ("127.0.0.1", "::1", "localhost")}


def parse_compose(text, env=None):
    """Parseur ligne à ligne (pas de dépendance PyYAML sur la VM) :
    services -> {ports: [...], network_mode, comment (1re ligne de
    commentaire du service, pour l'affichage)}."""
    services, cur, in_ports, in_services = {}, None, False, False
    for raw in text.split("\n"):
        line = raw.rstrip()
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services and re.match(r"^[a-zA-Z_]", line):   # autre section racine (volumes:, networks:)
            in_services = False
        if not in_services:
            continue
        m = re.match(r"^  ([a-zA-Z0-9_.-]+):\s*$", line)
        if m:
            cur = m.group(1)
            services[cur] = {"ports": [], "network_mode": None, "comment": None}
            in_ports = False
            continue
        if cur is None:
            continue
        cm = re.match(r"^    # (.*)$", line)
        if cm and services[cur]["comment"] is None:
            services[cur]["comment"] = cm.group(1).strip()
        nm = re.match(r"^    network_mode:\s*\"?([a-z]+)\"?\s*$", line)
        if nm:
            services[cur]["network_mode"] = nm.group(1)
        if re.match(r"^    ports:\s*$", line):
            in_ports = True
            continue
        if in_ports:
            pm = re.match(r"^      - (.+)$", line)
            if pm:
                services[cur]["ports"].append(parse_port(resolve(pm.group(1), env)))
                continue
            if line.strip() and not line.startswith("      "):
                in_ports = False
    return services


def build_exposure(services, gateway_services, gateway_port="6443"):
    gateway = []
    for var_name, service, container_port, path, kind in gateway_services:
        gateway.append({"path": path, "service": service if service != "__HOST_IP__" else "hôte (IP réelle)",
                        "container_port": container_port, "kind": kind, "env_var": var_name})
    direct, host_net = [], []
    for name, svc in sorted(services.items()):
        if svc["network_mode"] == "host":
            host_net.append({"service": name, "comment": svc["comment"]})
        for p in svc["ports"]:
            direct.append({"service": name, **p, "comment": svc["comment"]})
    direct.sort(key=lambda d: (d["loopback_only"], d["proto"], int(d["host_port"]) if str(d["host_port"]).isdigit() else 0))
    return {"gateway_port": gateway_port, "gateway": gateway, "direct_ports": direct, "host_network": host_net,
            "counts": {"gateway_routes": len(gateway), "direct_ports": len(direct),
                       "direct_public": sum(1 for d in direct if not d["loopback_only"]), "host_network": len(host_net)}}


def main():
    sys.path.insert(0, os.path.join(ROOT, "tls-proxy"))
    import render_nginx_conf as rnc  # noqa: E402
    env = rnc.parse_env(os.path.join(ROOT, ".env")) if hasattr(rnc, "parse_env") else {}
    with open(os.path.join(ROOT, "docker-compose.yml"), encoding="utf-8") as fh:
        services = parse_compose(fh.read(), env)
    out = build_exposure(services, rnc.SERVICES, env.get("GATEWAY_PORT") or "6443")
    out["generated_from"] = ["docker-compose.yml", "tls-proxy/render_nginx_conf.py"]
    dest = os.path.join(ROOT, "shared", "EXPOSURE.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    c = out["counts"]
    print("Exposition : %d routes passerelle, %d ports directs (%d publics), %d services en réseau hôte -> shared/EXPOSURE.json"
          % (c["gateway_routes"], c["direct_ports"], c["direct_public"], c["host_network"]))


if __name__ == "__main__":
    main()
