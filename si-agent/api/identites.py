# -*- coding: utf-8 -*-
"""Identités réseau des agents (livraison #1001) -- logique PURE : interfaces (nom, MAC, IP) et voisins ARP/NDP (IP, MAC)
tirés de la dernière mesure `netview`, pour la recherche unifiée et la concordance des cibles (nebula-api)."""

MAX_VOISINS = 500


def _mac(m):
    m = str(m or "").strip().lower()
    return None if m in ("", "00:00:00:00:00:00") else m


def extraire(agent, latest):
    nv = (latest or {}).get("netview") or {}
    data = nv.get("data") or {}
    itfs = []
    for i in data.get("interfaces") or []:
        ips = [a.get("ip") for a in i.get("addresses") or [] if a.get("ip")]
        mac = _mac(i.get("mac"))
        if mac or ips:
            itfs.append({"nom": i.get("name"), "mac": mac, "ips": ips, "etat": i.get("state")})
    voisins = [{"ip": n.get("ip"), "mac": _mac(n.get("mac")), "dev": n.get("dev")}
               for n in data.get("neighbors") or [] if n.get("ip") and _mac(n.get("mac"))][:MAX_VOISINS]
    return {"agent_id": agent.get("agent_id"), "hostname": agent.get("hostname"), "site": agent.get("site"),
            "last_seen_at": agent.get("last_seen_at"), "netview_at": nv.get("at"), "interfaces": itfs, "voisins": voisins}
