# -*- coding: utf-8 -*-
"""#776 : client DNS minimal (UDP, sans dépendance) -- interroger un serveur précis : les serveurs FAISANT AUTORITÉ d'une
zone (ce que voit le monde après propagation) et des résolveurs publics (ce que voient les clients aujourd'hui).

Pur : build_query, parse_response (tests sans réseau) ; query() envoie ; authoritative() trouve la zone et ses serveurs ;
resolve_at() suit les CNAME jusqu'aux adresses."""
import random
import socket
import struct

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "AAAA": 28}
NAMES = {v: k for k, v in TYPES.items()}
PUBLIC = ("1.1.1.1", "8.8.8.8", "9.9.9.9")


def build_query(name, qtype="A", rd=True, qid=None):
    qid = random.randint(0, 65535) if qid is None else qid
    hdr = struct.pack(">HHHHHH", qid, 0x0100 if rd else 0, 1, 0, 0, 0)
    q = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.strip(".").split(".") if p) + b"\x00"
    return hdr + q + struct.pack(">HH", TYPES[qtype], 1)


def _name(buf, off, depth=0):
    labels, jumped, end = [], False, off
    while True:
        if depth > 20 or off >= len(buf):
            raise ValueError("nom DNS mal formé")
        ln = buf[off]
        if ln & 0xC0 == 0xC0:
            ptr = ((ln & 0x3F) << 8) | buf[off + 1]
            if not jumped:
                end = off + 2
            jumped, off, depth = True, ptr, depth + 1
            continue
        if ln == 0:
            if not jumped:
                end = off + 1
            return ".".join(labels), end
        labels.append(buf[off + 1:off + 1 + ln].decode("ascii", "replace"))
        off += 1 + ln


def parse_response(buf):
    """-> {id, rcode, aa, tc, answers, authority, additional} ; enregistrement = {name, type, ttl, data}."""
    if len(buf) < 12:
        raise ValueError("réponse DNS trop courte")
    qid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", buf[:12])
    off = 12
    for _ in range(qd):
        _n, off = _name(buf, off)
        off += 4
    out = {"id": qid, "rcode": flags & 0xF, "aa": bool(flags & 0x0400), "tc": bool(flags & 0x0200), "answers": [], "authority": [], "additional": []}
    for sect, n in (("answers", an), ("authority", ns), ("additional", ar)):
        for _ in range(n):
            nm, off = _name(buf, off)
            t, _c, ttl, rdl = struct.unpack(">HHIH", buf[off:off + 10])
            off += 10
            rd = buf[off:off + rdl]
            if t == 1 and rdl == 4:
                data = socket.inet_ntoa(rd)
            elif t == 28 and rdl == 16:
                data = socket.inet_ntop(socket.AF_INET6, rd)
            elif t in (2, 5):
                data = _name(buf, off)[0]
            elif t == 6:
                data = _name(buf, off)[0]
            else:
                data = rd.hex()
            out[sect].append({"name": nm.lower(), "type": NAMES.get(t, str(t)), "ttl": ttl, "data": data.lower() if isinstance(data, str) else data})
            off += rdl
    return out


def query(server, name, qtype="A", rd=True, timeout=3.0, sock_factory=None):
    q = build_query(name, qtype, rd)
    s = (sock_factory or (lambda: socket.socket(socket.AF_INET6 if ":" in server else socket.AF_INET, socket.SOCK_DGRAM)))()
    try:
        s.settimeout(timeout)
        s.sendto(q, (server, 53))
        data, _a = s.recvfrom(4096)
    finally:
        s.close()
    r = parse_response(data)
    if r["id"] != struct.unpack(">H", q[:2])[0]:
        raise ValueError("réponse DNS d'une autre question")
    return r


def authoritative(name, resolver="1.1.1.1", q=query):
    """Zone et serveurs faisant autorité pour `name` -> {zone, ns: [{name, ip}]} (remonte les étiquettes)."""
    labels = name.strip(".").lower().split(".")
    for i in range(len(labels) - 1):
        zone = ".".join(labels[i:])
        r = q(resolver, zone, "NS")
        ns = sorted({a["data"] for a in r["answers"] if a["type"] == "NS" and a["name"] == zone})
        if ns:
            out = []
            for n in ns:
                try:
                    ips = [a["data"] for a in q(resolver, n, "A")["answers"] if a["type"] == "A"]
                except (OSError, ValueError):
                    ips = []
                out.append({"name": n, "ip": ips[0] if ips else None})
            return {"zone": zone, "ns": out}
    return {"zone": None, "ns": []}


def resolve_at(server, name, rd=True, q=query, follow=None, depth=0):
    """Adresses A de `name` vues par `server` (CNAME suivis, au besoin par `follow`) -> {addresses, cname, ttl, rcode}."""
    r = q(server, name, "A", rd)
    cn = [a["data"] for a in r["answers"] if a["type"] == "CNAME"]
    addrs = sorted({a["data"] for a in r["answers"] if a["type"] == "A"})
    ttl = min([a["ttl"] for a in r["answers"]] or [0]) or None
    if not addrs and cn and depth < 5:
        sub = resolve_at(follow or server, cn[-1], True, q, follow, depth + 1)
        return {"addresses": sub["addresses"], "cname": cn[0], "ttl": ttl or sub["ttl"], "rcode": sub["rcode"]}
    return {"addresses": addrs, "cname": cn[0] if cn else None, "ttl": ttl, "rcode": r["rcode"]}


def provider_of(ns_names):
    """Fournisseur probable d'après les serveurs faisant autorité (pour dire OÙ modifier)."""
    j = " ".join(ns_names or []).lower()
    for pat, label in (("ovh.net", "OVH (espace client › Noms de domaine › Zone DNS)"), ("anycast.me", "OVH (espace client › Noms de domaine › Zone DNS)"),
                       ("online.net", "Scaleway / Online (console › Domains)"), ("scaleway.com", "Scaleway (console › Domains)"),
                       ("gandi.net", "Gandi"), ("cloudflare.com", "Cloudflare"), ("awsdns", "AWS Route 53"), ("azure-dns", "Azure DNS")):
        if pat in j:
            return label
    return "serveur DNS autonome (BIND ou autre) : modifier la zone sur ces serveurs"
