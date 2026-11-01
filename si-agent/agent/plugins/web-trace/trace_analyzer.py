# -*- coding: utf-8 -*-
"""Analyse d'une capture réseau (pcap ou pcapng) SUR LE POSTE, sans dépendance
(livraison #618) : ce qu'un utilisateur a « fait sur le réseau » pendant la
fenêtre -- hôtes joints (nom par SNI TLS, en-tête Host HTTP ou réponse DNS),
protocoles, erreurs (connexions sans réponse, RST, retransmissions, DNS en
échec, codes HTTP ≥ 400 en clair) et latences (RTT de la poignée de main TCP
par serveur, DNS, premier octet HTTP en clair, ServerHello TLS).

Seul le RÉSUMÉ quitte le poste : jamais la capture ni les contenus. Les URL
ne sont visibles qu'en HTTP clair ; en HTTPS on a le nom d'hôte (SNI) et
les temps. Couvre Ethernet / IPv4 / TCP / UDP (IPv6 compté, non décodé).
"""
import struct
from collections import defaultdict

PROTO_PORTS = {53: "dns", 80: "http", 443: "https", 445: "smb", 3389: "rdp", 22: "ssh", 25: "smtp", 587: "smtp", 993: "imaps", 143: "imap",
               110: "pop3", 995: "pop3s", 389: "ldap", 636: "ldaps", 88: "kerberos", 123: "ntp", 67: "dhcp", 68: "dhcp", 5985: "winrm", 5986: "winrm",
               8080: "http-alt", 8443: "https-alt", 1433: "mssql", 3306: "mysql", 5432: "postgres", 161: "snmp", 5353: "mdns", 137: "netbios", 138: "netbios", 1900: "ssdp"}
HTTP_METHODS = (b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ", b"OPTIONS ", b"PATCH ")


# -- lecture pcap / pcapng -----------------------------------------------------

def iter_packets(data):
    """bytes -> itérateur (timestamp_s, link_type, raw). pcap classique (little/big endian,
    µs ou ns) et pcapng (SHB, IDB, EPB, SPB)."""
    if len(data) < 4:
        return
    magic = data[:4]
    if magic == b"\x0a\x0d\x0d\x0a":
        yield from _iter_pcapng(data)
    elif magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        yield from _iter_pcap(data)


def _iter_pcap(data):
    magic = data[:4]
    big = magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d")
    nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
    e = ">" if big else "<"
    link = struct.unpack(e + "I", data[20:24])[0]
    off = 24
    while off + 16 <= len(data):
        ts_s, ts_f, incl, _orig = struct.unpack(e + "IIII", data[off:off + 16])
        off += 16
        raw = data[off:off + incl]
        off += incl
        yield ts_s + ts_f / (1e9 if nano else 1e6), link, raw


def _iter_pcapng(data):
    off = 0
    e = "<"
    ifaces = []
    while off + 12 <= len(data):
        btype = struct.unpack(e + "I", data[off:off + 4])[0] if data[off:off + 4] != b"\x0a\x0d\x0d\x0a" else 0x0A0D0D0A
        if btype == 0x0A0D0D0A:  # section header : détermine l'endianness
            e = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            ifaces = []
        blen = struct.unpack(e + "I", data[off + 4:off + 8])[0]
        if blen < 12 or off + blen > len(data):
            break
        body = data[off + 8:off + blen - 4]
        if btype == 1:  # interface description : link type + résolution (option 9)
            link = struct.unpack(e + "H", body[:2])[0]
            tsres = 6
            o = 8
            while o + 4 <= len(body):
                code, ln = struct.unpack(e + "HH", body[o:o + 4])
                if code == 0:
                    break
                if code == 9 and ln >= 1:
                    v = body[o + 4]
                    tsres = (v & 0x7F) if not (v & 0x80) else -(v & 0x7F)
                o += 4 + ((ln + 3) // 4) * 4
            ifaces.append((link, tsres))
        elif btype == 6 and len(body) >= 20:  # enhanced packet block
            ifid, ts_hi, ts_lo, cap, _orig = struct.unpack(e + "IIIII", body[:20])
            link, tsres = ifaces[ifid] if ifid < len(ifaces) else (1, 6)
            ts = ((ts_hi << 32) | ts_lo) / (10 ** tsres if tsres >= 0 else 2 ** (-tsres))
            yield ts, link, body[20:20 + cap]
        elif btype == 3 and len(body) >= 4:  # simple packet block
            link, _ = ifaces[0] if ifaces else (1, 6)
            yield 0.0, link, body[4:]
        off += blen


# -- décodage ------------------------------------------------------------------

def decode(raw, link=1):
    """-> dict {src, dst, proto, sport, dport, flags, seq, ack, payload, ip_len} ou None."""
    if link == 1 and len(raw) >= 14:  # Ethernet
        eth = struct.unpack("!H", raw[12:14])[0]
        off = 14
        if eth == 0x8100 and len(raw) >= 18:
            eth = struct.unpack("!H", raw[16:18])[0]; off = 18
        if eth == 0x86DD:
            return {"proto": "ipv6"}
        if eth != 0x0800:
            return {"proto": "other-l2"}
        ip = raw[off:]
    elif link == 101:  # raw IP
        ip = raw
    elif link == 113 and len(raw) >= 16:  # Linux cooked
        ip = raw[16:]
    else:
        return None
    if len(ip) < 20 or (ip[0] >> 4) != 4:
        return None
    ihl = (ip[0] & 0x0F) * 4
    total = struct.unpack("!H", ip[2:4])[0]
    proto = ip[9]
    src = ".".join(str(b) for b in ip[12:16]); dst = ".".join(str(b) for b in ip[16:20])
    tp = ip[ihl:total] if total >= ihl else ip[ihl:]
    d = {"src": src, "dst": dst, "ip_len": total}
    if proto == 6 and len(tp) >= 20:
        sport, dport, seq, ack, doff_flags = struct.unpack("!HHIIH", tp[:14])
        doff = (doff_flags >> 12) * 4
        d.update({"proto": "tcp", "sport": sport, "dport": dport, "seq": seq, "ack": ack, "flags": doff_flags & 0x1FF, "payload": tp[doff:]})
    elif proto == 17 and len(tp) >= 8:
        sport, dport = struct.unpack("!HH", tp[:4])
        d.update({"proto": "udp", "sport": sport, "dport": dport, "payload": tp[8:]})
    elif proto == 1:
        d.update({"proto": "icmp", "payload": tp})
    else:
        d.update({"proto": "ip-%d" % proto})
    return d


def tls_sni(payload):
    """ClientHello TLS -> nom du serveur (SNI) ou None."""
    try:
        if len(payload) < 44 or payload[0] != 0x16 or payload[5] != 0x01:
            return None
        p = 5 + 4 + 2 + 32  # record + handshake header + version + random
        sid = payload[p]; p += 1 + sid
        cs = struct.unpack("!H", payload[p:p + 2])[0]; p += 2 + cs
        cm = payload[p]; p += 1 + cm
        ext_len = struct.unpack("!H", payload[p:p + 2])[0]; p += 2
        end = p + ext_len
        while p + 4 <= end and p + 4 <= len(payload):
            et, el = struct.unpack("!HH", payload[p:p + 4]); p += 4
            if et == 0 and p + 5 <= len(payload):
                nl = struct.unpack("!H", payload[p + 3:p + 5])[0]
                return payload[p + 5:p + 5 + nl].decode("ascii", "replace").lower()
            p += el
    except (struct.error, IndexError):
        return None
    return None


def dns_parse(payload):
    """-> {id, response, rcode, qname, answers: [ip]} ou None."""
    try:
        if len(payload) < 12:
            return None
        tid, flags, qd, an = struct.unpack("!HHHH", payload[:8])
        p = 12
        labels = []
        while p < len(payload):
            ln = payload[p]
            if ln == 0:
                p += 1; break
            if ln & 0xC0:
                p += 2; break
            labels.append(payload[p + 1:p + 1 + ln].decode("ascii", "replace")); p += 1 + ln
        qname = ".".join(labels).lower()
        p += 4
        answers = []
        for _ in range(an):
            if p + 12 > len(payload):
                break
            if payload[p] & 0xC0:
                p += 2
            else:
                while p < len(payload) and payload[p]:
                    p += 1 + payload[p]
                p += 1
            rtype, _rc, _ttl, rdl = struct.unpack("!HHIH", payload[p:p + 10]); p += 10
            if rtype == 1 and rdl == 4:
                answers.append(".".join(str(b) for b in payload[p:p + 4]))
            p += rdl
        return {"id": tid, "response": bool(flags & 0x8000), "rcode": flags & 0x000F, "qname": qname, "answers": answers}
    except (struct.error, IndexError):
        return None


def http_request(payload):
    if not payload.startswith(HTTP_METHODS):
        return None
    try:
        head = payload.split(b"\r\n\r\n", 1)[0].decode("latin-1")
    except Exception:  # noqa: BLE001
        return None
    lines = head.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) < 2:
        return None
    host = next((l.split(":", 1)[1].strip() for l in lines[1:] if l.lower().startswith("host:")), "")
    return {"method": parts[0], "path": parts[1][:200], "host": host.lower()}


def http_status(payload):
    if not payload.startswith(b"HTTP/1."):
        return None
    try:
        return int(payload[9:12])
    except ValueError:
        return None


# -- analyse ------------------------------------------------------------------

def analyze(data, local_ips=None, slow_rtt_ms=200, slow_dns_ms=300):
    """Capture -> résumé. `local_ips` : adresses du poste (sinon déduites : côté qui envoie les SYN)."""
    local = set(local_ips or [])
    flows = {}            # (src,sport,dst,dport) -> état TCP
    servers = defaultdict(lambda: {"ip": None, "names": set(), "protos": set(), "flows": 0, "bytes": 0, "rtts": [], "syn_failed": 0, "rst": 0, "retrans": 0})
    dns_q, dns = {}, {"queries": 0, "responses": 0, "failures": 0, "nxdomain": 0, "latencies": [], "names": {}}
    http, tls = [], []
    http_pending = {}     # flow -> (t, request)
    tls_pending = {}      # flow -> (t, sni)
    proto_count = defaultdict(int)
    packets = 0; first = last = None; ipv6 = 0
    for ts, link, raw in iter_packets(data):
        packets += 1
        first = ts if first is None else first; last = ts
        d = decode(raw, link)
        if not d:
            continue
        if d.get("proto") == "ipv6":
            ipv6 += 1; continue
        proto = d.get("proto")
        if proto not in ("tcp", "udp"):
            proto_count[proto or "?"] += 1; continue
        src, dst, sport, dport = d["src"], d["dst"], d["sport"], d["dport"]
        if proto == "udp":
            name = PROTO_PORTS.get(dport) or PROTO_PORTS.get(sport) or "udp"
            proto_count[name] += 1
            if 53 in (sport, dport):
                q = dns_parse(d["payload"])
                if not q:
                    continue
                if not q["response"]:
                    dns["queries"] += 1; dns_q[(q["id"], q["qname"])] = ts
                else:
                    dns["responses"] += 1
                    t0 = dns_q.pop((q["id"], q["qname"]), None)
                    if t0 is not None:
                        dns["latencies"].append((ts - t0) * 1000)
                    if q["rcode"] != 0:
                        dns["failures"] += 1; dns["nxdomain"] += 1 if q["rcode"] == 3 else 0
                    for ip in q["answers"]:
                        dns["names"].setdefault(ip, q["qname"])
            continue
        flags = d["flags"]; syn, ack, rst, fin = flags & 0x02, flags & 0x10, flags & 0x04, flags & 0x01
        payload = d.get("payload") or b""
        proto_count[PROTO_PORTS.get(dport) or PROTO_PORTS.get(sport) or "tcp"] += 1
        if syn and not ack:
            local.add(src)
            key = (src, sport, dst, dport)
            f = flows.get(key)
            if f is None:
                flows[key] = {"t_syn": ts, "t_synack": None, "seqs": set(), "server": dst, "sport_srv": dport, "bytes": 0}
                sv = servers[(dst, dport)]; sv["ip"] = dst; sv["flows"] += 1
                sv["protos"].add(PROTO_PORTS.get(dport, "tcp/%d" % dport))
            else:
                f["syn_retries"] = f.get("syn_retries", 0) + 1
            continue
        # sens client -> serveur ou serveur -> client
        key_c = (src, sport, dst, dport); key_s = (dst, dport, src, sport)
        f = flows.get(key_c); direction = "c2s"
        if f is None:
            f = flows.get(key_s); direction = "s2c"
        if f is None:
            continue
        sv = servers[(f["server"], f["sport_srv"])]
        sv["bytes"] += d.get("ip_len") or 0
        if direction == "s2c" and syn and ack and f["t_synack"] is None:
            f["t_synack"] = ts; sv["rtts"].append((ts - f["t_syn"]) * 1000)
        if rst:
            sv["rst"] += 1
        if payload and direction == "c2s":
            if d["seq"] in f["seqs"]:
                sv["retrans"] += 1
            f["seqs"].add(d["seq"])
            req = http_request(payload)
            if req:
                if req["host"]:
                    sv["names"].add(req["host"])
                http_pending[key_c] = (ts, req)
            sni = tls_sni(payload)
            if sni:
                sv["names"].add(sni); tls_pending[key_c] = (ts, sni)
        if payload and direction == "s2c":
            st = http_status(payload)
            if st is not None and key_s in http_pending:
                t0, req = http_pending.pop(key_s)
                http.append({"host": req["host"] or f["server"], "method": req["method"], "path": req["path"], "status": st, "ttfb_ms": round((ts - t0) * 1000, 1)})
            if key_s in tls_pending and payload[:1] == b"\x16" and len(payload) > 5 and payload[5] == 0x02:
                t0, sni = tls_pending.pop(key_s)
                tls.append({"sni": sni, "ip": f["server"], "hello_ms": round((ts - t0) * 1000, 1)})
    # connexions sans réponse
    for key, f in flows.items():
        if f["t_synack"] is None:
            servers[(f["server"], f["sport_srv"])]["syn_failed"] += 1
    # noms via DNS
    hosts = []
    for (ip, port), sv in servers.items():
        names = set(sv["names"])
        if not names and ip in dns["names"]:
            names.add(dns["names"][ip])
        rtts = sv["rtts"]
        hosts.append({"ip": ip, "port": port, "name": sorted(names)[0] if names else None, "names": sorted(names)[:5], "proto": sorted(sv["protos"])[0] if sv["protos"] else "tcp",
                      "flows": sv["flows"], "bytes": sv["bytes"], "rtt_ms": round(sum(rtts) / len(rtts), 1) if rtts else None, "rtt_max_ms": round(max(rtts), 1) if rtts else None,
                      "syn_failed": sv["syn_failed"], "rst": sv["rst"], "retrans": sv["retrans"]})
    hosts.sort(key=lambda h: (-h["syn_failed"], -h["bytes"]))
    lat = dns["latencies"]
    findings = []
    for h in hosts:
        label = h["name"] or h["ip"]
        if h["syn_failed"] and h["syn_failed"] >= h["flows"]:
            findings.append({"code": "connect-failed", "severity": "critical", "detail": "%s:%d : %d connexion(s) sans réponse" % (label, h["port"], h["syn_failed"])})
        elif h["syn_failed"]:
            findings.append({"code": "connect-partial", "severity": "warning", "detail": "%s:%d : %d/%d connexion(s) sans réponse" % (label, h["port"], h["syn_failed"], h["flows"])})
        if h["rtt_ms"] and h["rtt_ms"] > slow_rtt_ms:
            findings.append({"code": "slow-rtt", "severity": "warning", "detail": "%s : RTT %.0f ms" % (label, h["rtt_ms"])})
        if h["retrans"] >= 3:
            findings.append({"code": "retransmissions", "severity": "warning", "detail": "%s : %d retransmission(s)" % (label, h["retrans"])})
        if h["rst"] >= 3:
            findings.append({"code": "resets", "severity": "info", "detail": "%s : %d RST" % (label, h["rst"])})
    if dns["failures"]:
        findings.append({"code": "dns-failures", "severity": "warning", "detail": "%d réponse(s) DNS en échec (%d NXDOMAIN)" % (dns["failures"], dns["nxdomain"])})
    if dns_q:
        findings.append({"code": "dns-unanswered", "severity": "warning", "detail": "%d requête(s) DNS sans réponse" % len(dns_q)})
    if lat and sum(lat) / len(lat) > slow_dns_ms:
        findings.append({"code": "slow-dns", "severity": "warning", "detail": "DNS %.0f ms en moyenne" % (sum(lat) / len(lat))})
    for r in http:
        if r["status"] >= 400:
            findings.append({"code": "http-error" if r["status"] >= 500 else "http-client-error", "severity": "warning", "detail": "%s %s%s → %d" % (r["method"], r["host"], r["path"], r["status"])})
    for r in tls:
        if r["hello_ms"] > 1000:
            findings.append({"code": "slow-tls", "severity": "info", "detail": "%s : ServerHello en %.0f ms" % (r["sni"], r["hello_ms"])})
    return {"packets": packets, "duration_s": round((last - first), 1) if first is not None and last is not None else 0, "ipv6_packets": ipv6,
            "local_ips": sorted(local), "protocols": dict(sorted(proto_count.items(), key=lambda kv: -kv[1])),
            "hosts": hosts[:60], "dns": {"queries": dns["queries"], "responses": dns["responses"], "failures": dns["failures"], "nxdomain": dns["nxdomain"],
                                         "unanswered": len(dns_q), "avg_ms": round(sum(lat) / len(lat), 1) if lat else None, "max_ms": round(max(lat), 1) if lat else None},
            "http": http[:100], "tls": tls[:100], "findings": findings,
            "summary": {"hosts": len(hosts), "connect_failed": sum(h["syn_failed"] for h in hosts), "http_requests": len(http), "tls_handshakes": len(tls),
                        "state": "critical" if any(f["severity"] == "critical" for f in findings) else "warning" if any(f["severity"] == "warning" for f in findings) else "ok"}}
