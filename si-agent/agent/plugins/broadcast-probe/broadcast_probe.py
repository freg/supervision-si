# -*- coding: utf-8 -*-
"""Sonde « annonces réseau » (livraison #568) -- bibliothèque standard seulement.

Écoute passive d'une fenêtre : socket brut AF_PACKET (Linux, privilège) qui
ne garde que les trames de diffusion et de multidiffusion ; repli sans
privilège (ou Windows) : écoute UDP sur mDNS 5353, SSDP 1900, LLMNR 5355,
NetBIOS 137/138, WS-Discovery 3702. Analyseurs purs testés
(si-agent/agent/test_broadcast_probe.py). Sortie : {"at", "seconds",
"mode", "frames", "protocols": [...], "announcers": [...], "findings",
"alerts"}."""
import json
import os
import select
import socket
import struct
import sys
import time
from collections import defaultdict

UDP_PROTO = {67: "dhcp", 68: "dhcp", 137: "netbios-ns", 138: "netbios-dgm", 1900: "ssdp", 3702: "ws-discovery", 5353: "mdns", 5355: "llmnr",
             5678: "mikrotik-ndp", 6454: "artnet", 7070: "anydesk", 50001: "anydesk-discovery", 17500: "dropbox", 27036: "steam", 27015: "steam",
             1947: "hasp", 3289: "canon-bjnp", 8612: "canon-bjnp", 8610: "canon-bjnp", 161: "snmp", 162: "snmp-trap", 123: "ntp", 5246: "capwap", 5247: "capwap", 10001: "ubiquiti-discovery", 4096: "?", 9: "wake-on-lan", 7: "wake-on-lan",
             5060: "sip", 1534: "?", 6000: "x11", 32414: "plex", 41794: "crestron", 1985: "hsrp", 1984: "?", 520: "rip", 3222: "glbp"}
MULTICAST_IPV6 = {"ff02::1": "all-nodes", "ff02::2": "all-routers", "ff02::fb": "mdns", "ff02::1:3": "llmnr", "ff02::c": "ssdp", "ff02::16": "mld"}


# ------------------------------------------------------------------ analyseurs
def mac_str(b):
    return ":".join("%02x" % x for x in b[:6])


def parse_frame(frame):
    """Trame Ethernet -> {"src_mac", "dst_mac", "proto", "src_ip", "dst_ip", "info"} ou None si unicast."""
    if len(frame) < 14:
        return None
    dst, src, etype = frame[:6], frame[6:12], struct.unpack(">H", frame[12:14])[0]
    payload = frame[14:]
    if etype == 0x8100 and len(payload) >= 4:  # VLAN
        etype = struct.unpack(">H", payload[2:4])[0]; payload = payload[4:]
    is_bcast = dst == b"\xff" * 6
    is_mcast = bool(dst[0] & 1) and not is_bcast
    if not (is_bcast or is_mcast):
        return None
    out = {"src_mac": mac_str(src), "dst_mac": mac_str(dst), "proto": "ethertype-0x%04x" % etype, "src_ip": None, "dst_ip": None, "info": {}}
    if etype == 0x0806 and len(payload) >= 28:
        op = struct.unpack(">H", payload[6:8])[0]
        out.update(proto="arp", src_ip=socket.inet_ntoa(payload[14:18]), dst_ip=socket.inet_ntoa(payload[24:28]),
                   info={"op": {1: "request", 2: "reply"}.get(op, str(op)), "sender_mac": mac_str(payload[8:14]), "gratuitous": payload[14:18] == payload[24:28]})
    elif etype == 0x0800 and len(payload) >= 20:
        ihl = (payload[0] & 0x0f) * 4; ipproto = payload[9]
        out.update(src_ip=socket.inet_ntoa(payload[12:16]), dst_ip=socket.inet_ntoa(payload[16:20]))
        if ipproto == 17 and len(payload) >= ihl + 8:
            sport, dport = struct.unpack(">HH", payload[ihl:ihl + 4]); data = payload[ihl + 8:]
            out["proto"] = UDP_PROTO.get(dport) or UDP_PROTO.get(sport) or "udp-%d" % dport
            out["info"] = udp_info(out["proto"], data, sport, dport)
        elif ipproto == 2:
            out["proto"] = "igmp"
        elif ipproto == 112:
            out["proto"] = "vrrp"
        elif ipproto == 89:
            out["proto"] = "ospf"
        else:
            out["proto"] = "ip-%d" % ipproto
    elif etype == 0x86dd and len(payload) >= 40:
        nh = payload[6]
        out.update(src_ip=socket.inet_ntop(socket.AF_INET6, payload[8:24]), dst_ip=socket.inet_ntop(socket.AF_INET6, payload[24:40]))
        data = payload[40:]
        if nh == 58 and data:
            t = data[0]
            out["proto"] = {133: "icmpv6-rs", 134: "icmpv6-ra", 135: "icmpv6-ns", 136: "icmpv6-na", 130: "mld", 131: "mld", 143: "mld"}.get(t, "icmpv6-%d" % t)
        elif nh == 17 and len(data) >= 8:
            sport, dport = struct.unpack(">HH", data[:4])
            out["proto"] = UDP_PROTO.get(dport) or UDP_PROTO.get(sport) or "udp6-%d" % dport
            out["info"] = udp_info(out["proto"], data[8:], sport, dport)
        else:
            out["proto"] = "ipv6-%d" % nh
    elif etype == 0x88cc:
        out.update(proto="lldp", info=parse_lldp(payload))
    elif etype <= 1500 and len(payload) >= 3:  # LLC : STP, CDP
        if payload[:3] == b"\x42\x42\x03":
            out.update(proto="stp", info=parse_stp(payload[3:]))
        elif payload[:3] == b"\xaa\xaa\x03" and len(payload) >= 8 and payload[6:8] == b"\x20\x00":
            out.update(proto="cdp", info=parse_cdp(payload[8:]))
        else:
            out["proto"] = "llc"
    return out


def dns_name(data, off, depth=0):
    parts = []
    while off < len(data) and depth < 20:
        n = data[off]
        if n == 0:
            return ".".join(parts), off + 1
        if n & 0xc0 == 0xc0:
            ptr = struct.unpack(">H", data[off:off + 2])[0] & 0x3fff
            sub, _ = dns_name(data, ptr, depth + 1)
            parts.append(sub); return ".".join(parts), off + 2
        parts.append(data[off + 1:off + 1 + n].decode("utf-8", "replace")); off += 1 + n
    return ".".join(parts), off


def parse_dns_names(data, limit=40):
    """Noms (questions + réponses) d'un paquet DNS/mDNS/LLMNR -> {"names": [...], "services": [...], "is_response"}."""
    try:
        flags, qd, an, ns, ar = struct.unpack(">HHHHH", data[2:12])
    except struct.error:
        return {"names": [], "services": [], "is_response": False}
    names = []; services = set(); off = 12
    try:
        for _ in range(qd):
            n, off = dns_name(data, off); names.append(n); off += 4
        for _ in range(min(an + ns + ar, limit)):
            n, off = dns_name(data, off)
            rtype, _cls, _ttl, rdlen = struct.unpack(">HHIH", data[off:off + 10]); off += 10
            names.append(n)
            if rtype == 12:  # PTR
                target, _ = dns_name(data, off); names.append(target)
                if "._" in n or n.startswith("_"):
                    services.add(n.split(".local")[0])
            elif rtype == 33 and rdlen > 6:  # SRV
                target, _ = dns_name(data, off + 6); names.append(target)
            off += rdlen
    except (struct.error, IndexError):
        pass
    return {"names": [x for x in names if x][:limit], "services": sorted(services), "is_response": bool(flags & 0x8000)}


def parse_ssdp(data):
    txt = data.decode("latin-1", "replace")
    lines = txt.split("\r\n")
    hdr = {}
    for l in lines[1:]:
        if ":" in l:
            k, v = l.split(":", 1); hdr[k.strip().lower()] = v.strip()
    return {"method": lines[0].split(" ")[0] if lines else "", "nt": hdr.get("nt") or hdr.get("st"), "usn": hdr.get("usn"), "server": hdr.get("server"), "location": hdr.get("location")}


def nbns_name(data, off=12):
    try:
        n = data[off]
        enc = data[off + 1:off + 1 + n].decode("latin-1")
        raw = bytes(((ord(enc[i]) - 65) << 4) | (ord(enc[i + 1]) - 65) for i in range(0, len(enc) - 1, 2))
        return raw[:15].decode("latin-1").rstrip(), raw[15] if len(raw) > 15 else None
    except (IndexError, ValueError):
        return None, None


def parse_nbns(data):
    try:
        flags = struct.unpack(">H", data[2:4])[0]
        opcode = (flags >> 11) & 0x0f
        name, suffix = nbns_name(data)
        return {"opcode": {0: "query", 5: "registration", 6: "release", 7: "wack", 8: "refresh"}.get(opcode, str(opcode)), "name": name, "suffix": suffix}
    except (struct.error, IndexError):
        return {}


def parse_dhcp(data):
    try:
        op = data[0]; xid = data[4:8].hex()
        info = {"op": {1: "discover/request", 2: "offer/ack"}.get(op, str(op)), "client_mac": mac_str(data[28:34]), "xid": xid}
        if data[236:240] != b"\x63\x82\x53\x63":
            return info
        off = 240
        while off < len(data):
            t = data[off]
            if t == 255:
                break
            if t == 0:
                off += 1; continue
            ln = data[off + 1]; v = data[off + 2:off + 2 + ln]; off += 2 + ln
            if t == 53 and v:
                info["type"] = {1: "discover", 2: "offer", 3: "request", 4: "decline", 5: "ack", 6: "nak", 7: "release", 8: "inform"}.get(v[0], str(v[0]))
            elif t == 54 and len(v) == 4:
                info["server_id"] = socket.inet_ntoa(v)
            elif t == 12:
                info["hostname"] = v.decode("utf-8", "replace")
            elif t == 60:
                info["vendor"] = v.decode("latin-1", "replace")[:40]
        return info
    except (struct.error, IndexError):
        return {}


def parse_lldp(data):
    out = {}
    off = 0
    try:
        while off + 2 <= len(data):
            th = struct.unpack(">H", data[off:off + 2])[0]; t, ln = th >> 9, th & 0x1ff; v = data[off + 2:off + 2 + ln]; off += 2 + ln
            if t == 0:
                break
            if t == 1:
                out["chassis"] = mac_str(v[1:7]) if v and v[0] == 4 and len(v) >= 7 else v[1:].decode("latin-1", "replace")
            elif t == 2:
                out["port"] = v[1:].decode("latin-1", "replace")
            elif t == 5:
                out["sysname"] = v.decode("utf-8", "replace")
            elif t == 4:
                out["port_desc"] = v.decode("utf-8", "replace")
    except (struct.error, IndexError):
        pass
    return out


def parse_cdp(data):
    out = {}
    off = 4
    try:
        while off + 4 <= len(data):
            t, ln = struct.unpack(">HH", data[off:off + 4]); v = data[off + 4:off + ln]; off += ln if ln >= 4 else 4
            if t == 1:
                out["device_id"] = v.decode("utf-8", "replace")
            elif t == 3:
                out["port"] = v.decode("utf-8", "replace")
            elif t == 6:
                out["platform"] = v.decode("utf-8", "replace")
    except (struct.error, IndexError):
        pass
    return out


def parse_stp(data):
    try:
        proto, ver, typ = struct.unpack(">HBB", data[:4])
        out = {"type": {0: "config", 2: "rstp", 128: "tcn"}.get(typ, str(typ))}
        if typ in (0, 2) and len(data) >= 35:
            flags = data[4]
            out.update(root=mac_str(data[7:13]), root_priority=struct.unpack(">H", data[5:7])[0], bridge=mac_str(data[19:25]), topology_change=bool(flags & 0x01))
        return out
    except struct.error:
        return {}


def udp_info(proto, data, sport, dport):
    try:
        if proto in ("mdns", "llmnr"):
            return parse_dns_names(data)
        if proto == "ssdp":
            return parse_ssdp(data)
        if proto == "netbios-ns":
            return parse_nbns(data)
        if proto == "dhcp":
            return parse_dhcp(data)
        if proto == "ws-discovery":
            txt = data.decode("utf-8", "replace")
            return {"action": "hello" if "Hello" in txt else "probe" if "Probe" in txt else "bye" if "Bye" in txt else "?"}
    except Exception:  # noqa: BLE001 -- analyse au mieux, jamais bloquante
        return {}
    return {}


# ------------------------------------------------------------------ agrégation
def aggregate(events, seconds):
    """[parse_frame(...)] -> protocoles, annonceurs, constats."""
    proto_count = defaultdict(int); proto_src = defaultdict(set)
    ann = {}
    dhcp_servers = {}; ra_routers = {}; arp_ip_macs = defaultdict(set); stp_tcn = 0; stp_roots = set(); lldp = {}
    for e in events:
        if not e:
            continue
        proto_count[e["proto"]] += 1; proto_src[e["proto"]].add(e["src_mac"])
        a = ann.setdefault(e["src_mac"], {"mac": e["src_mac"], "ips": set(), "names": set(), "services": set(), "protocols": defaultdict(int), "frames": 0})
        a["frames"] += 1; a["protocols"][e["proto"]] += 1
        if e.get("src_ip") and not e["src_ip"].startswith("0.0.0.0") and e["src_ip"] != "::":
            a["ips"].add(e["src_ip"])
        info = e.get("info") or {}
        if e["proto"] == "arp":
            if info.get("op") == "reply" or info.get("gratuitous"):
                arp_ip_macs[e["src_ip"]].add(info.get("sender_mac") or e["src_mac"])
        elif e["proto"] in ("mdns", "llmnr"):
            for n in info.get("names") or []:
                if n and not n.startswith("_") and "._" not in n and n.count(".") <= 2:
                    a["names"].add(n.rstrip("."))
            a["services"].update(info.get("services") or [])
        elif e["proto"] == "ssdp":
            if info.get("server"):
                a["names"].add(("upnp: " + info["server"])[:60])
            if info.get("nt"):
                a["services"].add(info["nt"][:60])
        elif e["proto"] == "netbios-ns":
            if info.get("name") and info.get("opcode") in ("registration", "refresh"):
                a["names"].add(info["name"])
        elif e["proto"] == "dhcp":
            if info.get("type") in ("offer", "ack") and info.get("server_id"):
                dhcp_servers[info["server_id"]] = e["src_mac"]
            if info.get("hostname"):
                a["names"].add(info["hostname"])
        elif e["proto"] == "icmpv6-ra":
            ra_routers[e["src_mac"]] = e.get("src_ip")
        elif e["proto"] == "stp":
            if info.get("type") == "tcn" or info.get("topology_change"):
                stp_tcn += 1
            if info.get("root"):
                stp_roots.add(info["root"])
        elif e["proto"] == "lldp":
            if info.get("sysname"):
                a["names"].add(info["sysname"]); lldp[e["src_mac"]] = info
        elif e["proto"] == "cdp":
            if info.get("device_id"):
                a["names"].add(info["device_id"])
    announcers = []
    for a in ann.values():
        announcers.append({"mac": a["mac"], "ips": sorted(a["ips"]), "names": sorted(a["names"])[:8], "services": sorted(a["services"])[:20],
                           "protocols": dict(sorted(a["protocols"].items(), key=lambda kv: -kv[1])), "frames": a["frames"], "per_minute": round(a["frames"] * 60.0 / max(seconds, 1), 1)})
    announcers.sort(key=lambda x: -x["frames"])
    findings = []
    if len(dhcp_servers) > 1:
        findings.append({"code": "dhcp_multiple", "severity": "critical", "text": "plusieurs serveurs DHCP répondent : %s" % ", ".join("%s (%s)" % kv for kv in sorted(dhcp_servers.items()))})
    if ra_routers:
        findings.append({"code": "ipv6_ra", "severity": "info" if len(ra_routers) == 1 else "warning", "text": "annonces de routeur IPv6 (RA) de %s" % ", ".join("%s (%s)" % (m, ip) for m, ip in ra_routers.items())})
    for ip, macs in arp_ip_macs.items():
        if len(macs) > 1:
            findings.append({"code": "arp_conflict", "severity": "warning", "text": "conflit ARP : %s revendiquée par %s" % (ip, ", ".join(sorted(macs)))})
    if stp_tcn:
        findings.append({"code": "stp_topology_change", "severity": "warning", "text": "%d changement(s) de topologie STP sur la fenêtre" % stp_tcn})
    if len(stp_roots) > 1:
        findings.append({"code": "stp_multiple_roots", "severity": "warning", "text": "plusieurs racines STP annoncées : %s" % ", ".join(sorted(stp_roots))})
    total = sum(proto_count.values())
    for a in announcers:
        if a["per_minute"] > 600:
            findings.append({"code": "storm", "severity": "warning", "text": "rafale : %s émet %s trames diffusées par minute" % (a["names"][0] if a["names"] else a["mac"], a["per_minute"])})
    if total and total / max(seconds, 1) > 50:
        findings.append({"code": "broadcast_rate", "severity": "info", "text": "%.0f trames diffusées par seconde sur le segment" % (total / max(seconds, 1))})
    protocols = [{"proto": p, "frames": n, "sources": len(proto_src[p])} for p, n in sorted(proto_count.items(), key=lambda kv: -kv[1])]
    return {"protocols": protocols, "announcers": announcers, "findings": findings, "frames": total, "dhcp_servers": dhcp_servers, "lldp": lldp}


# ------------------------------------------------------------------ capture
def capture_raw(seconds):
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
    s.setblocking(False)
    end = time.time() + seconds; events = []
    while time.time() < end and len(events) < 200000:
        r, _, _ = select.select([s], [], [], 0.5)
        if not r:
            continue
        try:
            frame = s.recv(65535)
        except OSError:
            continue
        e = parse_frame(frame)
        if e:
            events.append(e)
    s.close()
    return events


def capture_udp(seconds):
    """Repli sans privilège : écoute des groupes multicast usuels."""
    socks = []
    groups = [("224.0.0.251", 5353, "mdns"), ("239.255.255.250", 1900, "ssdp"), ("224.0.0.252", 5355, "llmnr"), ("239.255.255.250", 3702, "ws-discovery"), (None, 137, "netbios-ns"), (None, 138, "netbios-dgm")]
    for grp, port, proto in groups:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            s.bind(("", port))
            if grp:
                s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(grp) + socket.inet_aton("0.0.0.0"))
            s.setblocking(False); socks.append((s, proto, port))
        except OSError:
            continue
    end = time.time() + seconds; events = []
    while time.time() < end and socks:
        r, _, _ = select.select([x[0] for x in socks], [], [], 0.5)
        for s in r:
            proto, port = next((p, pt) for (ss, p, pt) in socks if ss is s)
            try:
                data, (ip, sport) = s.recvfrom(65535)
            except OSError:
                continue
            events.append({"src_mac": "ip:" + ip, "dst_mac": "multicast", "proto": proto, "src_ip": ip, "dst_ip": None, "info": udp_info(proto, data, sport, port)})
    for s, _, _ in socks:
        s.close()
    return events


def collect(seconds):
    mode = "raw"
    try:
        events = capture_raw(seconds)
    except (OSError, AttributeError):
        mode = "udp"; events = capture_udp(seconds)
    agg = aggregate(events, seconds)
    alerts = [{"code": f["code"], "severity": f["severity"], "message": f["text"]} for f in agg["findings"] if f["severity"] in ("warning", "critical")]
    return dict(agg, at=int(time.time()), seconds=seconds, mode=mode, alerts=alerts)


def main(argv):
    seconds = 60
    i = 0
    while i < len(argv):
        if argv[i] == "--seconds" and i + 1 < len(argv):
            try:
                seconds = max(5, min(600, int(argv[i + 1])))
            except ValueError:
                pass
            i += 2; continue
        i += 1
    try:
        print(json.dumps(collect(seconds)))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
