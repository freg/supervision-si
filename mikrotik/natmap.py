# -*- coding: utf-8 -*-
"""Carte des redirections NAT (livraison #606) -- logique PURE : à partir des
règles NAT de chaque routeur (RouterOS, REST ou SSH), construire une vue
« entrée → routeur → cible » exploitable par le hub : flux normalisés,
regroupement par cible, conflits (même port d'entrée pris deux fois sur un
routeur), règles désactivées, sortants (masquerade / src-nat) à part."""
import re


def _ports(value):
    """« 80 », « 8000-8010 », « 22,2222 » -> liste de chaînes ; vide -> ["*"]."""
    v = str(value or "").strip()
    if not v:
        return ["*"]
    return [p.strip() for p in v.split(",") if p.strip()]


def normalize(router, rule):
    """Une règle RouterOS -> flux {router, id, chain, action, proto, in_iface,
    dst_address, dst_ports:[], to_address, to_ports:[], src_address, comment,
    disabled, invalid, packets, bytes, kind}. kind : inbound | outbound | other."""
    r = rule or {}
    action = r.get("action") or "?"
    chain = r.get("chain") or "?"
    kind = "inbound" if action in ("dst-nat", "redirect", "netmap") or chain == "dstnat" else "outbound" if action in ("src-nat", "masquerade") or chain == "srcnat" else "other"
    to_addr = r.get("to-addresses") or ("routeur" if action == "redirect" else "")
    return {
        "router": router, "id": r.get(".id") or "", "chain": chain, "action": action, "proto": r.get("protocol") or "*",
        "in_iface": r.get("in-interface") or r.get("in-interface-list") or "", "out_iface": r.get("out-interface") or r.get("out-interface-list") or "",
        "dst_address": r.get("dst-address") or "", "dst_ports": _ports(r.get("dst-port")), "to_address": to_addr, "to_ports": _ports(r.get("to-ports")),
        "src_address": r.get("src-address") or "", "comment": r.get("comment") or "", "disabled": str(r.get("disabled")).lower() in ("true", "yes"),
        "invalid": str(r.get("invalid")).lower() in ("true", "yes"), "packets": _int(r.get("packets")), "bytes": _int(r.get("bytes")), "kind": kind,
    }


def _int(v):
    try:
        return int(str(v).replace(" ", "")) if v not in (None, "") else None
    except ValueError:
        return None


def conflicts(flows):
    """Sur un même routeur, deux règles entrantes ACTIVES visant le même
    (proto, adresse d'entrée, port d'entrée) -> la seconde ne sera jamais
    atteinte. -> [{router, key, rules:[ids]}]."""
    seen = {}
    for f in flows:
        if f["kind"] != "inbound" or f["disabled"]:
            continue
        for p in f["dst_ports"]:
            key = (f["router"], f["proto"], f["dst_address"] or "*", p)
            seen.setdefault(key, []).append(f["id"] or f["comment"] or "?")
    return [{"router": k[0], "key": "%s %s:%s" % (k[1], k[2], k[3]), "rules": v} for k, v in seen.items() if len(v) > 1 and "*" not in k[3]]


def build(routers_rules, names=None):
    """routers_rules : [{name, host, site, reachable, error, rules:[...]}] ->
    {routers:[{name, host, site, reachable, error, inbound, outbound, disabled}],
     flows:[...], targets:[{address, name, site, flows:[...]}], conflicts, counts}.
    `names` : {ip: libellé} (agents, registres) pour nommer les cibles."""
    names = names or {}
    flows, routers = [], []
    for rr in routers_rules:
        fl = [normalize(rr["name"], r) for r in (rr.get("rules") or [])]
        flows += fl
        routers.append({"name": rr["name"], "host": rr.get("host"), "site": rr.get("site"), "reachable": rr.get("reachable", True), "error": rr.get("error"),
                        "inbound": sum(1 for f in fl if f["kind"] == "inbound" and not f["disabled"]), "outbound": sum(1 for f in fl if f["kind"] == "outbound" and not f["disabled"]),
                        "disabled": sum(1 for f in fl if f["disabled"])})
    targets = {}
    for f in flows:
        if f["kind"] != "inbound":
            continue
        key = f["to_address"] or "?"
        t = targets.setdefault(key, {"address": key, "name": names.get(key, ""), "flows": []})
        t["flows"].append(f)
    tl = sorted(targets.values(), key=lambda t: (t["address"] == "routeur", _ipkey(t["address"])))
    return {"routers": routers, "flows": flows, "targets": tl, "conflicts": conflicts(flows),
            "counts": {"inbound": sum(1 for f in flows if f["kind"] == "inbound" and not f["disabled"]), "outbound": sum(1 for f in flows if f["kind"] == "outbound"),
                       "disabled": sum(1 for f in flows if f["disabled"]), "targets": len(tl), "conflicts": len(conflicts(flows))}}


def _ipkey(a):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)", str(a))
    return tuple(int(x) for x in m.groups()) if m else (999, str(a))


def filter_flows(flows, query):
    """Filtre texte (début de mot d'abord) sur routeur, ports, adresses, commentaire, protocole."""
    q = str(query or "").strip().lower()
    if not q:
        return flows
    def text(f):
        return " ".join([f["router"], f["proto"], f["dst_address"], ",".join(f["dst_ports"]), f["to_address"], ",".join(f["to_ports"]), f["comment"], f["in_iface"], f["action"]]).lower()
    starts = [f for f in flows if any(w.startswith(q) for w in re.split(r"[\s:,./-]+", text(f)))]
    contains = [f for f in flows if f not in starts and q in text(f)]
    return starts + contains
