#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin si-agent « gtb-netwatch » (#739) : tentatives d'ouverture de ports distants d'un poste de GTB/GTC
(superviseur type Neutrino GLT, automates BACnet/IP, Modbus/TCP…) et leurs échecs.

Pendant `--seconds` (défaut 120) :
  1. capture BORNÉE des seuls en-têtes (128 octets) : SYN, SYN-ACK et RST TCP, ICMP, et UDP des ports de GTB
     - Windows 10 2004+ (dont 22H2) : `pktmon` intégré (rien à installer), converti en pcapng par `pktmon etl2pcap` ;
     - Linux, ou Windows avec Npcap : `tcpdump` (ou `dumpcap`) ;
     - `--pcap FICHIER` : analyse d'une capture existante, sans rien capturer ;
  2. relevé des connexions TCP chaque seconde avec leur processus (Get-NetTCPConnection / ss) pour attribuer
     chaque tentative à son programme (Neutrino…).
Analyse, par connexion puis par extrémité distante :
  TCP sortant  : acceptée (SYN-ACK), REFUSÉE (RST : service arrêté / port fermé), SANS RÉPONSE (SYN répétés : hôte
                 éteint, pare-feu, route), INJOIGNABLE (ICMP : réseau/hôte/port, « administrativement interdit »),
                 COUPÉE (RST après établissement, côté distant ou local) ;
  TCP entrant  : un automate qui cherche à joindre ce poste (remontée d'alarmes) : refusé (port local fermé :
                 application non à l'écoute) ou ignoré (pare-feu Windows) ;
  UDP          : requêtes sans réponse, ICMP « port injoignable » ; diffusions (BACnet Who-Is…) comptées à part.
Sortie JSON : {at, backend, seconds, local_ips, endpoints, inbound, findings, alerts, stats, error}.
Lecture seule : aucun paquet émis, contenu des paquets jamais conservé (en-têtes seulement, fichier supprimé).

Arguments : [--seconds 120] [--targets 192.0.2.0/24,198.51.100.7] [--ports all|gtb|47808,502,…] (défaut all) [--process neutrino]
            [--backend auto|pktmon|tcpdump|dumpcap] [--interface IFACE] [--pcap FICHIER] [--keep DOSSIER]
"""
import ipaddress
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time

PORTS = {  # ports usuels d'une GTB/GTC (libellés) -- `--ports` en ajoute
    47808: "BACnet/IP", 47809: "BACnet/IP (2)", 47810: "BACnet/IP (3)", 502: "Modbus/TCP", 3671: "KNXnet/IP",
    4840: "OPC UA", 4843: "OPC UA TLS", 135: "RPC/DCOM (OPC DA)", 1433: "SQL Server", 1434: "SQL Browser",
    161: "SNMP", 162: "SNMP trap", 445: "SMB", 80: "HTTP", 443: "HTTPS", 102: "S7/ISO-TSAP", 1911: "Fox (Niagara)",
    4911: "Fox TLS", 10001: "série/IP", 20000: "DNP3", 2404: "IEC-104", 123: "NTP", 53: "DNS", 25: "SMTP", 587: "SMTP sub",
}
UDP_PORTS_GTB = [47808, 47809, 47810, 3671, 161, 162, 123, 20000]
ICMP_UNREACH = {0: "réseau injoignable", 1: "hôte injoignable", 2: "protocole injoignable", 3: "port injoignable",
                4: "fragmentation requise", 6: "réseau inconnu", 7: "hôte inconnu", 9: "réseau interdit (admin)",
                10: "hôte interdit (admin)", 13: "communication interdite (pare-feu)"}
SNAP = 128
NO_ANSWER_GRACE = 3.0


def sh(argv, timeout=30, **kw):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **kw)
    except (OSError, subprocess.SubprocessError) as exc:
        class R:  # noqa: D401
            returncode, stdout, stderr = -1, "", str(exc)
        return R()


def parse_args(argv):
    o = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            k = a[2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                o[k] = argv[i + 1]; i += 2; continue
            o[k] = "1"
        i += 1
    return o


def port_set(spec):
    spec = (spec or "gtb").strip().lower()
    if spec == "all":
        return None
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if part == "gtb":
            out |= set(PORTS)
        elif "-" in part:
            a, b = part.split("-", 1); out |= set(range(int(a), int(b) + 1))
        elif part.isdigit():
            out.add(int(part))
    return out


def target_nets(spec):
    nets = []
    for p in (spec or "").split(","):
        p = p.strip()
        if p and p.lower() not in ("any", "auto", "all"):
            try:
                nets.append(ipaddress.ip_network(p, strict=False))
            except ValueError:
                pass
    return nets


# ------------------------------------------------------------------ lecture pcap / pcapng (pure Python)

def read_packets(path):
    """-> [(ts, linktype, bytes)] pour pcap classique ou pcapng."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 24:
        return []
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        e = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
        lt = struct.unpack(e + "I", data[20:24])[0] & 0xFFFF
        out, off = [], 24
        while off + 16 <= len(data):
            s, us, incl, _orig = struct.unpack(e + "IIII", data[off:off + 16])
            off += 16
            out.append((s + us / (1e9 if nano else 1e6), lt, data[off:off + incl]))
            off += incl
        return out
    if magic != b"\x0a\x0d\x0d\x0a":
        raise ValueError("format de capture inconnu")
    out, off, e, ifs = [], 0, "<", []
    while off + 12 <= len(data):
        btype = struct.unpack("<I", data[off:off + 4])[0]
        if btype == 0x0A0D0D0A:
            e = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            ifs = []
        blen = struct.unpack(e + "I", data[off + 4:off + 8])[0]
        if blen < 12 or off + blen > len(data):
            break
        body = data[off + 8:off + blen - 4]
        if btype == 1:                                   # IDB
            lt = struct.unpack(e + "H", body[:2])[0]
            res = 1e-6
            o = 8
            while o + 4 <= len(body):                    # options : if_tsresol (9)
                code, ln = struct.unpack(e + "HH", body[o:o + 4])
                if code == 0:
                    break
                if code == 9 and ln >= 1:
                    v = body[o + 4]
                    res = (2 ** -(v & 0x7F)) if v & 0x80 else 10 ** -v
                o += 4 + ((ln + 3) & ~3)
            ifs.append((lt, res))
        elif btype == 6 and len(body) >= 20:             # EPB
            iid, hi, lo, cap, _orig = struct.unpack(e + "IIIII", body[:20])
            lt, res = ifs[iid] if iid < len(ifs) else (1, 1e-6)
            out.append((((hi << 32) | lo) * res, lt, body[20:20 + cap]))
        elif btype == 3 and len(body) >= 4:              # SPB
            lt, _res = ifs[0] if ifs else (1, 1e-6)
            out.append((0.0, lt, body[4:]))
        off += blen
    return out


def ip_payload(lt, frame):
    """-> octets IPv4 ou None (Ethernet, VLAN, Linux cooked v1/v2, IP brut, BSD loopback)."""
    if lt == 1:
        if len(frame) < 14:
            return None
        et, o = struct.unpack(">H", frame[12:14])[0], 14
        while et in (0x8100, 0x88A8) and len(frame) >= o + 4:
            et, o = struct.unpack(">H", frame[o + 2:o + 4])[0], o + 4
        return frame[o:] if et == 0x0800 else None
    if lt == 113:
        return frame[16:] if len(frame) > 16 and struct.unpack(">H", frame[14:16])[0] == 0x0800 else None
    if lt == 276:
        return frame[20:] if len(frame) > 20 and struct.unpack(">H", frame[0:2])[0] == 0x0800 else None
    if lt in (101, 228, 12):
        return frame if frame[:1] and frame[0] >> 4 == 4 else None
    if lt == 0:
        return frame[4:] if len(frame) > 4 and frame[4] >> 4 == 4 else None
    return None


def decode(ip, quoted=False):
    """-> dict paquet IPv4 (TCP/UDP/ICMP) ou None. `quoted` : en-tête cité dans un ICMP (8 octets de TCP seulement)."""
    if len(ip) < 20 or ip[0] >> 4 != 4:
        return None
    ihl = (ip[0] & 15) * 4
    proto = ip[9]
    p = {"src": "%d.%d.%d.%d" % tuple(ip[12:16]), "dst": "%d.%d.%d.%d" % tuple(ip[16:20]), "proto": proto,
         "ipid": struct.unpack(">H", ip[4:6])[0]}
    l4 = ip[ihl:]
    if proto == 6 and quoted and len(l4) >= 4:
        p.update(sport=struct.unpack(">H", l4[0:2])[0], dport=struct.unpack(">H", l4[2:4])[0])
    elif proto == 6 and len(l4) >= 14:
        p.update(sport=struct.unpack(">H", l4[0:2])[0], dport=struct.unpack(">H", l4[2:4])[0],
                 seq=struct.unpack(">I", l4[4:8])[0], flags=l4[13])
    elif proto == 17 and len(l4) >= 4:
        p.update(sport=struct.unpack(">H", l4[0:2])[0], dport=struct.unpack(">H", l4[2:4])[0])
    elif proto == 1 and len(l4) >= 8:
        p.update(itype=l4[0], icode=l4[1])
        inner = l4[8:]
        if len(inner) >= 20 and inner[0] >> 4 == 4:      # en-tête d'origine cité par l'ICMP
            q = decode(inner, quoted=True)
            if q is not None:
                p["orig"] = q
    else:
        return None
    return p


# ------------------------------------------------------------------ analyse

FIN, SYN, RST, ACK = 0x01, 0x02, 0x04, 0x10


def is_bcast(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_multicast or ip.endswith(".255") or ip == "255.255.255.255"


def analyse(packets, local_ips, ports=None, targets=None, end_ts=None, procs=None):
    """packets = [(ts, linktype, frame)] -> (endpoints, inbound, stats). procs = {(lport, rip, rport): nom}."""
    local = set(local_ips or [])
    targets = targets or []
    procs = procs or {}
    seen, pk = {}, []
    for ts, lt, fr in packets:
        ip = ip_payload(lt, fr)
        p = decode(ip) if ip else None
        if not p:
            continue
        k = (p["src"], p["dst"], p["proto"], p["ipid"], p.get("sport"), p.get("dport"), p.get("seq"), p.get("flags"), p.get("itype"))
        if k in seen and abs(seen[k] - ts) < 0.5:        # pktmon : même paquet vu par plusieurs composants
            continue
        seen[k] = ts
        p["ts"] = ts
        pk.append(p)
    pk.sort(key=lambda x: x["ts"])
    if not local:                                        # déduit : qui émet des SYN est local
        local = {p["src"] for p in pk if p["proto"] == 6 and p.get("flags", 0) & SYN and not p["flags"] & ACK}
    end_ts = end_ts or (pk[-1]["ts"] if pk else time.time())

    def wanted(remote, port):
        if targets and not any(ipaddress.ip_address(remote) in n for n in targets if remote.count(".") == 3):
            return False
        return True

    flows, inflows, udp, bc = {}, {}, {}, {}
    icmps = []
    for p in pk:
        if p["proto"] == 1:
            icmps.append(p); continue
        out = p["src"] in local
        rip = p["dst"] if out else p["src"]
        if rip in local:
            continue
        if p["proto"] == 6:
            f = p["flags"]
            if out:
                key = (p["src"], p["sport"], p["dst"], p["dport"])
            else:
                key = (p["dst"], p["dport"], p["src"], p["sport"])
            fl = flows.get(key)
            if f & SYN and not f & ACK:
                if out:
                    fl = flows.setdefault(key, {"dir": "out", "syn": 0, "synack": 0, "rst_in": 0, "rst_out": 0, "first": p["ts"], "last_syn": p["ts"], "icmp": None})
                else:
                    fl = inflows.setdefault(key, {"dir": "in", "syn": 0, "synack": 0, "rst_in": 0, "rst_out": 0, "first": p["ts"], "last_syn": p["ts"], "icmp": None})
                fl["syn"] += 1; fl["last_syn"] = p["ts"]
                continue
            fl = flows.get(key) if out or key in flows else None
            fl = fl or inflows.get(key)
            if fl is None:
                if f & RST:                                # RST d'une session déjà ouverte avant la capture
                    fl = flows.setdefault(key, {"dir": "out", "syn": 0, "synack": 0, "rst_in": 0, "rst_out": 0, "first": p["ts"], "last_syn": None, "icmp": None, "preexisting": True})
                else:
                    continue
            if f & SYN and f & ACK:
                fl["synack"] += 1
            elif f & RST:
                fl["rst_out" if out else "rst_in"] += 1
                fl.setdefault("rst_after_ok", bool(fl["synack"]) or fl.get("preexisting", False))
        elif p["proto"] == 17:
            svc_out = p["dport"]; svc_in = p["sport"]
            if out and is_bcast(p["dst"]):
                b = bc.setdefault((p["dst"], svc_out), {"packets": 0}); b["packets"] += 1
                continue
            if out:
                u = udp.setdefault((rip, svc_out), {"out": 0, "in": 0, "icmp": None, "first": p["ts"], "last_out": p["ts"], "lport": p["sport"]})
                u["out"] += 1; u["last_out"] = p["ts"]
            else:
                u = udp.get((rip, svc_in)) or udp.get((rip, p["dport"]))
                if u is not None:
                    u["in"] += 1
    for p in icmps:                                       # ICMP : rattaché à la connexion citée
        o = p.get("orig")
        if p.get("itype") not in (3, 11) or not o:
            continue
        why = ICMP_UNREACH.get(p["icode"], "code %s" % p["icode"]) if p["itype"] == 3 else "TTL expiré (boucle de routage ?)"
        info = {"type": p["itype"], "code": p["icode"], "text": why, "from": p["src"]}
        if o["proto"] == 6 and (o["src"], o.get("sport"), o["dst"], o.get("dport")) in flows:
            flows[(o["src"], o["sport"], o["dst"], o["dport"])]["icmp"] = info
        elif o["proto"] == 17 and (o["dst"], o.get("dport")) in udp:
            udp[(o["dst"], o["dport"])]["icmp"] = info

    eps = {}

    def ep(rip, rport, proto):
        return eps.setdefault((rip, rport, proto), {"remote": rip, "port": rport, "proto": proto, "service": PORTS.get(rport, ""),
                                                   "attempts": 0, "ok": 0, "refused": 0, "no_answer": 0, "unreachable": 0,
                                                   "reset_remote": 0, "reset_local": 0, "pending": 0, "icmp": None,
                                                   "processes": [], "first": None, "last": None})

    for (lip, lport, rip, rport), fl in flows.items():
        if ports is not None and rport not in ports or not wanted(rip, rport):
            continue
        e = ep(rip, rport, "tcp")
        e["first"] = min(e["first"] or fl["first"], fl["first"]); e["last"] = max(e["last"] or fl["first"], fl["first"])
        pr = procs.get((lport, rip, rport))
        if pr and pr not in e["processes"]:
            e["processes"].append(pr)
        if fl.get("preexisting"):
            e["reset_remote" if fl["rst_in"] else "reset_local"] += 1
            continue
        e["attempts"] += 1
        if fl["icmp"]:
            e["unreachable"] += 1; e["icmp"] = fl["icmp"]
        elif fl["synack"]:
            e["ok"] += 1
            if fl["rst_in"]:
                e["reset_remote"] += 1
            elif fl["rst_out"]:
                e["reset_local"] += 1
        elif fl["rst_in"]:
            e["refused"] += 1
        elif fl["last_syn"] is not None and end_ts - fl["last_syn"] >= NO_ANSWER_GRACE:
            e["no_answer"] += 1
            e["syn_retries"] = max(e.get("syn_retries", 0), fl["syn"] - 1)
        else:
            e["pending"] += 1
    for (rip, rport), u in udp.items():
        if ports is not None and rport not in ports or not wanted(rip, rport):
            continue
        e = ep(rip, rport, "udp")
        e["attempts"] += u["out"]; e["first"] = u["first"]; e["last"] = u["last_out"]
        if u["icmp"]:
            e["unreachable"] += 1; e["icmp"] = u["icmp"]
            if u["icmp"]["code"] == 3:
                e["refused"] += 1
        elif u["in"]:
            e["ok"] += u["in"]
        elif end_ts - u["last_out"] >= NO_ANSWER_GRACE:
            e["no_answer"] += u["out"]
        else:
            e["pending"] += u["out"]
    inbound = []
    for (lip, lport, rip, rport), fl in inflows.items():
        if not wanted(rip, lport):
            continue
        st = "accepted" if fl["synack"] else ("refused" if fl["rst_out"] else
                                              ("ignored" if end_ts - fl["last_syn"] >= NO_ANSWER_GRACE else "pending"))
        inbound.append({"remote": rip, "local_port": lport, "service": PORTS.get(lport, ""), "state": st, "syn": fl["syn"], "at": fl["first"]})
    stats = {"packets": len(pk), "tcp_flows": len(flows), "inbound_flows": len(inflows), "udp_pairs": len(udp),
             "broadcasts": [{"dst": d, "port": p, "service": PORTS.get(p, ""), "packets": v["packets"]} for (d, p), v in bc.items()],
             "local_ips": sorted(local)}
    return sorted(eps.values(), key=lambda e: (-(e["refused"] + e["no_answer"] + e["unreachable"]), e["remote"], e["port"])), inbound, stats


def findings_for(endpoints, inbound):
    out = []
    for e in endpoints:
        who = "%s:%s/%s%s" % (e["remote"], e["port"], e["proto"], (" (%s)" % e["service"]) if e["service"] else "")
        by = (" ; programme : %s" % ", ".join(e["processes"])) if e["processes"] else ""
        tgt = "%s:%s/%s" % (e["remote"], e["port"], e["proto"])      # code d'alerte court et stable (≤ 64 car.)
        failed = e["refused"] + e["no_answer"] + e["unreachable"]
        sev = "critical" if failed and not e["ok"] else "warning"
        if e["unreachable"] and e["icmp"]:
            out.append({"code": "unreachable", "severity": sev, "target": tgt,
                        "text": "%s : %s, signalé par %s%s -- route ou filtrage entre le poste et l'équipement" % (who, e["icmp"]["text"], e["icmp"]["from"], by)})
        if e["refused"] and e["proto"] == "tcp":
            out.append({"code": "tcp-refused", "severity": sev, "target": tgt,
                        "text": "%s refuse la connexion (RST) %d fois sur %d -- service arrêté, port fermé ou mauvais port configuré%s" % (who, e["refused"], e["attempts"], by)})
        if e["no_answer"] and e["proto"] == "tcp":
            out.append({"code": "tcp-no-answer", "severity": sev, "target": tgt,
                        "text": "%s ne répond pas (%d tentative(s), %d relance(s) SYN) -- équipement éteint, pare-feu qui jette, ou route absente%s" % (
                            who, e["no_answer"], e.get("syn_retries", 0), by)})
        if e["reset_remote"]:
            out.append({"code": "tcp-reset-remote", "severity": "warning", "target": tgt,
                        "text": "%s coupe les sessions établies (RST distant ×%d) -- redémarrage, limite de sessions ou délai d'inactivité%s" % (who, e["reset_remote"], by)})
        if e["reset_local"]:
            out.append({"code": "tcp-reset-local", "severity": "info", "target": tgt,
                        "text": "le poste abandonne ses sessions vers %s (RST local ×%d) -- délai de l'application ou erreur de protocole%s" % (who, e["reset_local"], by)})
        if e["proto"] == "udp" and e["no_answer"] and not e["ok"]:
            out.append({"code": "udp-no-answer", "severity": "warning", "target": tgt,
                        "text": "%s : %d requête(s) UDP sans réponse -- équipement absent, mauvais port ou réseau BACnet (BBMD) non relayé" % (who, e["no_answer"])})
        if e["proto"] == "udp" and e["refused"]:
            out.append({"code": "udp-refused", "severity": sev, "target": tgt, "text": "%s : port UDP fermé (ICMP port injoignable)" % who})
    for i in inbound:
        who = "%s -> port local %s%s" % (i["remote"], i["local_port"], (" (%s)" % i["service"]) if i["service"] else "")
        tgt = "%s>%s" % (i["remote"], i["local_port"])
        if i["state"] == "refused":
            out.append({"code": "inbound-refused", "severity": "warning", "target": tgt,
                        "text": "%s : refusé, rien n'écoute sur ce port (application GLT arrêtée ou mal configurée ?) -- %d tentative(s)" % (who, i["syn"])})
        elif i["state"] == "ignored":
            out.append({"code": "inbound-dropped", "severity": "warning", "target": tgt,
                        "text": "%s : sans réponse, paquets jetés (pare-feu Windows ?) -- %d tentative(s)" % (who, i["syn"])})
    return out


# ------------------------------------------------------------------ relevé des connexions et processus

PS_WATCH = r"""
$ErrorActionPreference='SilentlyContinue'; $end=(Get-Date).AddSeconds(%d); $seen=@{}
while((Get-Date) -lt $end){
  foreach($c in Get-NetTCPConnection){
    if($c.RemoteAddress -in '0.0.0.0','::','127.0.0.1','::1'){continue}
    $k="$($c.LocalPort)|$($c.RemoteAddress)|$($c.RemotePort)|$($c.State)"
    if(-not $seen.ContainsKey($k)){ $seen[$k]=1
      [pscustomobject]@{t=[DateTimeOffset]::Now.ToUnixTimeSeconds();s=[string]$c.State;lp=$c.LocalPort;ra=[string]$c.RemoteAddress;rp=$c.RemotePort;pid=$c.OwningProcess} | ConvertTo-Json -Compress }
  }
  Start-Sleep -Milliseconds 800
}
Get-Process | ForEach-Object { [pscustomobject]@{proc=$_.ProcessName;id=$_.Id;path=[string]$_.Path} | ConvertTo-Json -Compress }
"""


def watch_connections(seconds):
    """-> (procs {(lport, rip, rport): nom}, attempts [{state, lport, remote, rport, process}])."""
    rows, names = [], {}
    if os.name == "nt":
        r = sh(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PS_WATCH % seconds], timeout=seconds + 60)
        for line in (r.stdout or "").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if "proc" in d:
                names[d["id"]] = d["proc"]
            else:
                rows.append(d)
    elif shutil.which("ss"):
        end, seen = time.time() + seconds, set()
        while time.time() < end:
            r = sh(["ss", "-tanpH"], timeout=10)
            for line in (r.stdout or "").splitlines():
                m = re.match(r"(\S+)\s+\d+\s+\d+\s+(\S+):(\d+)\s+(\S+):(\d+)\s*(.*)", line)
                if not m:
                    continue
                st, _la, lp, ra, rp, rest = m.groups()
                if ra in ("*", "0.0.0.0", "127.0.0.1"):
                    continue
                pm = re.search(r'\("([^"]+)",pid=(\d+)', rest)
                k = (lp, ra, rp, st)
                if k not in seen:
                    seen.add(k)
                    rows.append({"s": st, "lp": int(lp), "ra": ra.strip("[]"), "rp": int(rp), "pid": int(pm.group(2)) if pm else None,
                                 "name": pm.group(1) if pm else None})
            time.sleep(1)
    procs, attempts = {}, []
    for d in rows:
        name = d.get("name") or names.get(d.get("pid")) or (str(d.get("pid")) if d.get("pid") else None)
        if name:
            procs[(int(d["lp"]), d["ra"], int(d["rp"]))] = name
        if str(d.get("s")).lower().replace("_", "-") in ("synsent", "syn-sent"):
            attempts.append({"lport": d["lp"], "remote": d["ra"], "rport": d["rp"], "process": name})
    return procs, attempts


def local_ipv4():
    ips = set()
    if os.name == "nt":
        r = sh(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { $_.IPAddress }"], timeout=30)
        ips |= {x.strip() for x in (r.stdout or "").split() if x.strip().count(".") == 3}
    else:
        r = sh(["ip", "-j", "-4", "addr"], timeout=10)
        try:
            for it in json.loads(r.stdout or "[]"):
                ips |= {a["local"] for a in it.get("addr_info", []) if a.get("family") == "inet"}
        except ValueError:
            pass
    return sorted(i for i in ips if not i.startswith("127.") and not i.startswith("169.254."))


# ------------------------------------------------------------------ captures

def capture_pktmon(seconds, workdir, targets, udp_ports):
    etl, pcap = os.path.join(workdir, "gtb.etl"), os.path.join(workdir, "gtb.pcapng")
    sh(["pktmon", "filter", "remove"])
    filters = []
    if targets:
        for n in targets[:30]:
            filters.append(["-i", str(n.network_address) if n.prefixlen == 32 else str(n)])
    else:
        filters += [["-t", "TCP", "SYN"], ["-t", "TCP", "RST"], ["-t", "ICMP"]]
        filters += [["-t", "UDP", "-p", str(p)] for p in udp_ports[:25]]
    for i, f in enumerate(filters):
        r = sh(["pktmon", "filter", "add", "gtb%d" % i] + f)
        if r.returncode != 0:
            return None, "pktmon filter add %s : %s" % (" ".join(f), (r.stdout or r.stderr).strip()[:200])
    r = sh(["pktmon", "start", "--capture", "--comp", "nics", "--pkt-size", str(SNAP), "--file-name", etl, "--file-size", "64"])
    if r.returncode != 0:
        sh(["pktmon", "filter", "remove"])
        return None, "pktmon start : %s" % ((r.stdout or r.stderr).strip()[:300])
    try:
        time.sleep(seconds)
    finally:
        sh(["pktmon", "stop"], timeout=120)
        sh(["pktmon", "filter", "remove"])
    r = sh(["pktmon", "etl2pcap", etl, "--out", pcap], timeout=300)
    if r.returncode != 0 or not os.path.exists(pcap):
        return None, "pktmon etl2pcap : %s" % ((r.stdout or r.stderr).strip()[:300])
    return pcap, None


def bpf(targets, udp_ports):
    base = "(tcp[tcpflags] & (tcp-syn|tcp-rst) != 0) or icmp"
    if udp_ports:
        base += " or (udp and (%s))" % " or ".join("port %d" % p for p in udp_ports)
    if targets:
        base = "(%s) and (%s)" % (base, " or ".join("net %s" % n for n in targets))
    return base


def capture_tcpdump(seconds, workdir, targets, udp_ports, iface, tool):
    pcap = os.path.join(workdir, "gtb.pcap")
    exe = shutil.which(tool)
    if not exe:
        return None, "%s absent" % tool
    if tool == "dumpcap":
        argv = [exe, "-q", "-s", str(SNAP), "-a", "duration:%d" % seconds, "-a", "filesize:65536", "-w", pcap, "-f", bpf(targets, udp_ports)]
        if iface:
            argv[1:1] = ["-i", iface]
        r = sh(argv, timeout=seconds + 60)
    else:
        argv = [exe, "-n", "-s", str(SNAP), "-w", pcap, "-C", "64", "-W", "1"] + (["-i", iface] if iface else []) + [bpf(targets, udp_ports)]
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except OSError as exc:
            return None, str(exc)
        time.sleep(seconds)
        proc.terminate()
        try:
            _o, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill(); err = ""
        class R:  # noqa: D401
            returncode = 0 if os.path.exists(pcap) else 1
            stderr = err
        r = R()
    if not os.path.exists(pcap):
        return None, "%s : %s" % (tool, (r.stderr or "").strip()[:300])
    return pcap, None


def pick_backend(want):
    if want and want != "auto":
        return want
    if os.name == "nt":
        return "pktmon" if shutil.which("pktmon") else ("dumpcap" if shutil.which("dumpcap") else "tcpdump")
    return "tcpdump"


def main(argv=None):
    o = parse_args(sys.argv[1:] if argv is None else argv)
    seconds = max(10, min(int(o.get("seconds", "120")), 900))
    ports = port_set(o.get("ports", "all"))     # défaut : tous les ports TCP (protocoles propriétaires) ; gtb = libellés
    targets = target_nets(o.get("targets", ""))
    udp_ports = sorted(set(UDP_PORTS_GTB) | ({p for p in ports if p not in PORTS} if ports else set()))
    proc_filter = (o.get("process") or "").lower()
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "backend": None, "seconds": seconds,
           "targets": [str(n) for n in targets], "ports": "all" if ports is None else sorted(ports), "local_ips": [],
           "endpoints": [], "inbound": [], "syn_sent_seen": [], "findings": [], "alerts": [], "stats": {}, "error": None}
    workdir = tempfile.mkdtemp(prefix="gtb-netwatch-")
    procs, attempts = {}, []
    try:
        out["local_ips"] = local_ipv4()
        if o.get("pcap"):
            out["backend"], pcap, err = "file", o["pcap"], None
        else:
            out["backend"] = pick_backend(o.get("backend"))
            res = {}
            w = threading.Thread(target=lambda: res.update(r=watch_connections(seconds)), daemon=True)
            w.start()
            if out["backend"] == "pktmon":
                pcap, err = capture_pktmon(seconds, workdir, targets, udp_ports)
            else:
                pcap, err = capture_tcpdump(seconds, workdir, targets, udp_ports, o.get("interface"), out["backend"])
            w.join(timeout=90)
            procs, attempts = res.get("r", ({}, []))
        if err:
            out["error"] = err
        if pcap:
            pkts = read_packets(pcap)
            eps, inbound, stats = analyse(pkts, out["local_ips"], ports, targets, procs=procs)
            if proc_filter:
                eps = [e for e in eps if not e["processes"] or any(proc_filter in p.lower() for p in e["processes"])]
            out.update(endpoints=eps, inbound=inbound, stats=stats)
            if o.get("keep"):
                os.makedirs(o["keep"], exist_ok=True)
                shutil.copy(pcap, os.path.join(o["keep"], "gtb-netwatch-%s%s" % (time.strftime("%Y%m%d-%H%M%S"), os.path.splitext(pcap)[1])))
        out["syn_sent_seen"] = [a for a in attempts if not proc_filter or proc_filter in str(a.get("process", "")).lower()][:200]
        out["findings"] = findings_for(out["endpoints"], out["inbound"])
        out["alerts"] = [{"code": "%s@%s" % (f["code"], f["target"]), "severity": f["severity"], "message": f["text"]}
                         for f in out["findings"] if f["severity"] in ("warning", "critical")]
    except Exception as exc:  # noqa: BLE001 -- sortie JSON lisible plutôt qu'une trace
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if not out["error"] or out["endpoints"] else 2


if __name__ == "__main__":
    sys.exit(main())
