#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « accès aux ressources » (livraison #640, item 106, famille explorer).

Inspirée de ntopng, mais NATIVE et sans conteneur : elle lit la table
`conntrack` du poste (`/proc/net/nf_conntrack`, sinon `conntrack -L`) et
restitue QUI accède à QUOI -- flux par client (src) et par ressource
(dst:port/proto), volumes, protocole, et enrichissement par les noms DNS
appris (dns-observe). Elle observe ce qui PASSE PAR CE POSTE : sur une
passerelle ou un port miroir, c'est le LAN ; sur un simple client, c'est ce
poste. À placer donc sur la passerelle/relais ou un SPAN pour une vue réseau.

Constats (`alerts`, repris en événements par le central) :
  resource-new       : nouvelle ressource externe contactée (vs passage précédent)
  resource-cleartext : accès en clair (HTTP 80, FTP 21, Telnet 23…) vers une ressource externe
  talker-heavy       : client dépassant le seuil de volume (--heavy-mb)
  resource-silent    : ressource vue régulièrement, absente ce passage (histoire locale)

Lecture seule, stdlib. Pure (testable) : parse_conntrack, aggregate, findings.
Usage : resource_access.py [--local 10.0.0.0/8,192.168.0.0/16] [--names-map dst=nom,…]
        [--heavy-mb 500] [--min-bytes 0] [--state FICHIER]
"""
import ipaddress
import json
import os
import re
import subprocess
import sys
import time

STATE_DEFAULT = "/var/lib/si-agent/resource-access.state.json"
CLEARTEXT = {80: "HTTP", 21: "FTP", 23: "Telnet", 110: "POP3", 143: "IMAP", 8080: "HTTP-alt", 3389: "RDP"}
DEFAULT_LOCAL = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8", "fe80::/10", "::1/128", "fc00::/7"]
LINE_RE = re.compile(r"\b(tcp|udp)\b.*?\bsrc=(\S+)\s+dst=(\S+)\s+sport=(\d+)\s+dport=(\d+)")
BYTES_RE = re.compile(r"\bbytes=(\d+)")


def _nets(cidrs):
    out = []
    for c in cidrs:
        try:
            out.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            pass
    return out


def is_local(ip, nets):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in n for n in nets)


def parse_conntrack(text):
    """/proc/net/nf_conntrack (ou conntrack -L) -> [{proto, src, dst, sport, dport, bytes}].
    bytes = somme des compteurs bytes= de la ligne (0 si nf_conntrack_acct désactivé)."""
    flows = []
    for line in (text or "").splitlines():
        m = LINE_RE.search(line)
        if not m:
            continue
        proto, src, dst, sport, dport = m.group(1), m.group(2), m.group(3), int(m.group(4)), int(m.group(5))
        nbytes = sum(int(b) for b in BYTES_RE.findall(line))
        flows.append({"proto": proto, "src": src, "dst": dst, "sport": sport, "dport": dport, "bytes": nbytes})
    return flows


def aggregate(flows, local_nets, names_map=None, min_bytes=0):
    """-> {resources:[{key,dst,port,proto,name,clients,flows,bytes}], clients:[{ip,resources,bytes,flows}]}.
    Une « ressource » = destination NON locale (dst hors plages locales). Le client = src local."""
    names_map = names_map or {}
    res, cli = {}, {}
    for f in flows:
        # orienter : la ressource est le côté non-local ; le client, le côté local
        if not is_local(f["dst"], local_nets) and is_local(f["src"], local_nets):
            client, dst, port = f["src"], f["dst"], f["dport"]
        elif not is_local(f["src"], local_nets) and is_local(f["dst"], local_nets):
            client, dst, port = f["dst"], f["src"], f["sport"]
        else:
            continue  # local↔local ou externe↔externe : hors périmètre « accès ressource »
        rkey = "%s:%d/%s" % (dst, port, f["proto"])
        r = res.setdefault(rkey, {"key": rkey, "dst": dst, "port": port, "proto": f["proto"],
                                  "name": names_map.get(dst), "clients": set(), "flows": 0, "bytes": 0})
        r["clients"].add(client); r["flows"] += 1; r["bytes"] += f["bytes"]
        c = cli.setdefault(client, {"ip": client, "resources": set(), "flows": 0, "bytes": 0})
        c["resources"].add(rkey); c["flows"] += 1; c["bytes"] += f["bytes"]
    resources = sorted(({**r, "clients": sorted(r["clients"])} for r in res.values() if r["bytes"] >= min_bytes),
                       key=lambda x: (-x["bytes"], -x["flows"]))
    clients = sorted(({"ip": c["ip"], "resources": len(c["resources"]), "flows": c["flows"], "bytes": c["bytes"]} for c in cli.values()),
                     key=lambda x: (-x["bytes"], -x["flows"]))
    return {"resources": resources, "clients": clients}


def findings(agg, previous_keys=None, heavy_mb=500):
    """Constats : nouvelles ressources, accès en clair, gros consommateurs."""
    alerts = []
    prev = set(previous_keys or [])
    new = [r for r in agg["resources"] if r["key"] not in prev]
    if prev and new:
        alerts.append({"code": "resource-new", "severity": "info",
                       "message": "nouvelle(s) ressource(s) externe(s) contactée(s) : %s" % ", ".join((r["name"] or r["dst"]) + ":%d" % r["port"] for r in new[:8])})
    clear = [r for r in agg["resources"] if r["port"] in CLEARTEXT]
    if clear:
        alerts.append({"code": "resource-cleartext", "severity": "warning",
                       "message": "accès en clair vers une ressource externe : %s" % ", ".join("%s %s:%d" % (CLEARTEXT[r["port"]], r["name"] or r["dst"], r["port"]) for r in clear[:8])})
    heavy = [c for c in agg["clients"] if c["bytes"] >= heavy_mb * 1_000_000]
    for c in heavy[:8]:
        alerts.append({"code": "talker-heavy", "severity": "info",
                       "message": "%s : %.0f Mo sur %d flux" % (c["ip"], c["bytes"] / 1e6, c["flows"])})
    return alerts


def summarize(agg, alerts):
    total = sum(r["bytes"] for r in agg["resources"])
    state = "warning" if any(a["severity"] == "warning" for a in alerts) else "ok"
    return {"state": state, "resources": len(agg["resources"]), "clients": len(agg["clients"]), "bytes": total, "alerts": len(alerts)}


# ---------------------------------------------------------------------------
# collecte (I/O)
# ---------------------------------------------------------------------------
def read_conntrack():
    for path in ("/proc/net/nf_conntrack",):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            pass
    try:
        r = subprocess.run(["conntrack", "-L"], capture_output=True, text=True, timeout=20)
        if r.returncode == 0:
            return r.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def load_names_map(spec):
    """« dst=nom,dst2=nom2 » ou fichier JSON {dst: nom} ; sinon vide."""
    m = {}
    if not spec:
        return m
    if os.path.isfile(spec):
        try:
            return json.load(open(spec, encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    for pair in spec.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            m[k.strip()] = v.strip()
    return m


def collect(local, names_map, heavy_mb, min_bytes, state_path):
    nets = _nets(local or DEFAULT_LOCAL)
    flows = parse_conntrack(read_conntrack())
    agg = aggregate(flows, nets, names_map=names_map, min_bytes=min_bytes)
    previous = []
    try:
        with open(state_path, encoding="utf-8") as fh:
            previous = json.load(fh).get("keys", [])
    except (OSError, ValueError):
        pass
    alerts = findings(agg, previous_keys=previous, heavy_mb=heavy_mb)
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump({"keys": [r["key"] for r in agg["resources"]], "at": time.time()}, fh)
    except OSError:
        pass
    return {**agg, "alerts": alerts, "summary": summarize(agg, alerts),
            "note": "flux vus par ce poste ; vue réseau seulement sur passerelle/miroir"}


def main(argv):
    local, names_map, heavy_mb, min_bytes, state = None, {}, 500.0, 0, STATE_DEFAULT
    i = 0
    while i < len(argv):
        a, v = argv[i], argv[i + 1] if i + 1 < len(argv) else None
        if a == "--local" and v is not None:
            local = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--names-map" and v is not None:
            names_map = load_names_map(v); i += 2; continue
        if a == "--heavy-mb" and v is not None:
            heavy_mb = float(v); i += 2; continue
        if a == "--min-bytes" and v is not None:
            min_bytes = int(v); i += 2; continue
        if a == "--state" and v is not None:
            state = v; i += 2; continue
        i += 1
    try:
        print(json.dumps(collect(local, names_map, heavy_mb, min_bytes, state)))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "collecte échouée : %s" % exc, "alerts": []}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
