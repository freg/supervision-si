# -*- coding: utf-8 -*-
"""Découverte PASSIVE du réseau depuis l'hôte (livraison #428, backlog 66) :
ce que l'hôte SAIT de son réseau sans émettre un seul paquet -- interfaces
et adresses, routes (passerelle, routes directes vers d'autres
sous-réseaux : le cas « sous-réseau isolé/filtré mais accessible par route
directe »), voisins ARP/NDP déjà résolus par le noyau, connexions
établies (avec qui l'hôte parle, sur quels ports, quel processus), DNS.

Aucune commande active (ping, balayage) : c'est le rôle du plugin
`network-neighbors`, désactivé par défaut. Mesure `netview`, toutes les
`netview_interval_seconds` (300 s).

Parseurs purs (sortie JSON de `ip -j`, texte de `ss`) testés sans machine.
"""
import ipaddress
import json
import re

from . import host


def _run_json(cmd, argv):
    r = cmd(argv)
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


# ---- interfaces ---------------------------------------------------------------

def parse_ip_addr(data):
    """`ip -j addr` -> [{name, mac, state, mtu, addresses: [{ip, prefix, family, scope}]}],
    loopback exclu."""
    out = []
    for it in data or []:
        name = it.get("ifname")
        if not name or "LOOPBACK" in (it.get("flags") or []):
            continue
        addrs = []
        for a in it.get("addr_info") or []:
            if a.get("scope") == "host":
                continue
            addrs.append({"ip": a.get("local"), "prefix": a.get("prefixlen"), "family": a.get("family"), "scope": a.get("scope")})
        out.append({"name": name, "mac": it.get("address"), "state": (it.get("operstate") or "").lower() or None,
                    "mtu": it.get("mtu"), "addresses": addrs})
    return out


# ---- routes -------------------------------------------------------------------

def parse_ip_route(data):
    """`ip -j route` -> [{dst, gateway, dev, protocol, scope, metric, kind}] ;
    kind = default | direct (sous-réseau attaché) | via (routé par une passerelle)."""
    out = []
    for r in data or []:
        dst = r.get("dst")
        if not dst:
            continue
        gw = r.get("gateway")
        kind = "default" if dst == "default" else ("via" if gw else "direct")
        out.append({"dst": dst, "gateway": gw, "dev": r.get("dev"), "protocol": r.get("protocol"), "scope": r.get("scope"),
                    "metric": r.get("metric"), "kind": kind})
    return out


# ---- voisins ------------------------------------------------------------------

def parse_ip_neigh(data):
    """`ip -j neigh` -> [{ip, mac, dev, state}] ; FAILED/INCOMPLETE écartés,
    états mis en minuscules (reachable, stale, delay, permanent…)."""
    out = []
    for n in data or []:
        ip = n.get("dst")
        states = [s.lower() for s in (n.get("state") or [])]
        if not ip or any(s in ("failed", "incomplete") for s in states):
            continue
        out.append({"ip": ip, "mac": n.get("lladdr"), "dev": n.get("dev"), "state": states[0] if states else None})
    return out


# ---- connexions établies ----------------------------------------------------

_SS_PROC = re.compile(r'users:\(\("([^"]+)",pid=(\d+)')


def parse_ss_connections(text):
    """`ss -Htanup state established` (ou `ss -Htanup` filtré) ->
    [{proto, local_ip, local_port, remote_ip, remote_port, process, pid}]."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        # avec ou sans colonne d'état selon la forme de la commande
        if parts[1].isalpha() and parts[1].upper() in ("ESTAB", "ESTABLISHED", "SYN-SENT", "TIME-WAIT", "CLOSE-WAIT", "UNCONN", "LISTEN"):
            if parts[1].upper() not in ("ESTAB", "ESTABLISHED"):
                continue
            local, remote = parts[4], parts[5] if len(parts) > 5 else ""
        else:
            local, remote = parts[3], parts[4]
        if ":" not in local or ":" not in remote:
            continue
        lip, lport = local.rsplit(":", 1)
        rip, rport = remote.rsplit(":", 1)
        try:
            lport, rport = int(lport), int(rport)
        except ValueError:
            continue
        m = _SS_PROC.search(line)
        out.append({"proto": proto, "local_ip": lip.strip("[]"), "local_port": lport, "remote_ip": rip.strip("[]"), "remote_port": rport,
                    "process": m.group(1) if m else None, "pid": int(m.group(2)) if m else None})
    return out


# ---- DNS ------------------------------------------------------------------------

def parse_resolv_conf(text):
    servers, search = [], []
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("nameserver "):
            servers.append(line.split(None, 1)[1].strip())
        elif line.startswith(("search ", "domain ")):
            search.extend(line.split()[1:])
    return {"servers": servers, "search": search}


# ---- synthèse -------------------------------------------------------------------

def _net_of(ip, prefix):
    try:
        return str(ipaddress.ip_network("%s/%s" % (ip, prefix), strict=False))
    except ValueError:
        return None


def summarize(interfaces, routes, neighbors, connections):
    """Ce que l'hôte voit : sous-réseaux attachés, sous-réseaux joignables
    par route directe (hors défaut), passerelle par défaut et son état
    ARP, pairs (IP distantes des connexions, groupées avec ports et
    processus), voisins hors des sous-réseaux attachés (indice de proxy
    ARP / route directe)."""
    attached = []
    for itf in interfaces:
        for a in itf["addresses"]:
            if a["family"] == "inet" and a["ip"] and a["prefix"] is not None:
                n = _net_of(a["ip"], a["prefix"])
                if n and n not in attached:
                    attached.append(n)
    neigh_by_ip = {n["ip"]: n for n in neighbors}
    default = [r for r in routes if r["kind"] == "default"]
    gateway = default[0]["gateway"] if default else None
    reachable = []
    for r in routes:
        if r["kind"] == "via" and r["dst"] not in attached:
            reachable.append({"subnet": r["dst"], "gateway": r["gateway"], "dev": r["dev"],
                              "gateway_state": (neigh_by_ip.get(r["gateway"]) or {}).get("state")})
    peers = {}
    for c in connections:
        try:
            if ipaddress.ip_address(c["remote_ip"]).is_loopback:
                continue
        except ValueError:
            continue
        p = peers.setdefault(c["remote_ip"], {"ip": c["remote_ip"], "connections": 0, "ports": [], "processes": [], "local": None})
        p["connections"] += 1
        port = "%s/%s" % (c["proto"], c["remote_port"])
        if port not in p["ports"] and len(p["ports"]) < 12:
            p["ports"].append(port)
        if c.get("process") and c["process"] not in p["processes"]:
            p["processes"].append(c["process"])
        p["local"] = any(ipaddress.ip_address(c["remote_ip"]) in ipaddress.ip_network(n) for n in attached) if attached else None
    outside = [n for n in neighbors if n["ip"] and not any(_in(n["ip"], a) for a in attached)]
    return {
        "attached_subnets": attached,
        "default_gateway": gateway,
        "default_gateway_state": (neigh_by_ip.get(gateway) or {}).get("state") if gateway else None,
        "reachable_subnets": reachable,
        "peers": sorted(peers.values(), key=lambda p: -p["connections"]),
        "neighbors_outside_attached": outside,
        "counts": {"interfaces": len(interfaces), "neighbors": len(neighbors), "connections": len(connections), "peers": len(peers)},
    }


def _in(ip, net):
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(net)
    except ValueError:
        return False


def collect(cmd=host.run_cmd, files=host.read_file):
    """Une mesure `netview`. `partial` liste les sources absentes."""
    partial = []
    addr = _run_json(cmd, ["ip", "-j", "addr"])
    route = _run_json(cmd, ["ip", "-j", "route"])
    neigh = _run_json(cmd, ["ip", "-j", "neigh"])
    if addr is None:
        partial.append("ip-addr")
    if route is None:
        partial.append("ip-route")
    if neigh is None:
        partial.append("ip-neigh")
    r = cmd(["ss", "-Htanup", "state", "established"])
    if r.returncode < 0:
        partial.append("ss")
        conns = []
    else:
        conns = parse_ss_connections(r.stdout)
    interfaces = parse_ip_addr(addr)
    routes = parse_ip_route(route)
    neighbors = parse_ip_neigh(neigh)
    data = {
        "interfaces": interfaces, "routes": routes, "neighbors": neighbors,
        "connections": conns[:500], "dns": parse_resolv_conf(files("/etc/resolv.conf")),
        "summary": summarize(interfaces, routes, neighbors, conns), "partial": partial,
    }
    return data
