"""Tests #618 : analyseur de capture (pcap synthétique construit à la main + pcapng) et sonde web-trace."""
import json
import os
import struct
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import trace_analyzer as ta  # noqa: E402
import web_trace as wt  # noqa: E402


def ip4(s):
    return bytes(int(x) for x in s.split("."))


def tcp(src, dst, sport, dport, flags, seq=0, ack=0, payload=b""):
    tcph = struct.pack("!HHIIHHHH", sport, dport, seq, ack, (5 << 12) | flags, 65535, 0, 0) + payload
    total = 20 + len(tcph)
    iph = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 0, 0, 64, 6, 0, ip4(src), ip4(dst))
    return b"\x00" * 12 + b"\x08\x00" + iph + tcph


def udp(src, dst, sport, dport, payload):
    udph = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    iph = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udph), 0, 0, 64, 17, 0, ip4(src), ip4(dst))
    return b"\x00" * 12 + b"\x08\x00" + iph + udph


def dns_query(tid, name):
    q = b"".join(bytes([len(l)]) + l.encode() for l in name.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0) + q + b"\x00\x01\x00\x01"


def dns_answer(tid, name, ip, rcode=0):
    q = b"".join(bytes([len(l)]) + l.encode() for l in name.split(".")) + b"\x00"
    ans = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + ip4(ip) if rcode == 0 else b""
    return struct.pack("!HHHHHH", tid, 0x8180 | rcode, 1, 1 if rcode == 0 else 0, 0, 0) + q + b"\x00\x01\x00\x01" + ans


def client_hello(sni):
    host = sni.encode()
    sni_ext = struct.pack("!HH", 0, 5 + len(host)) + struct.pack("!HBH", 3 + len(host), 0, len(host)) + host
    body = b"\x03\x03" + b"\x00" * 32 + b"\x00" + b"\x00\x02\x13\x01" + b"\x01\x00" + struct.pack("!H", len(sni_ext)) + sni_ext
    hs = b"\x01" + struct.pack("!I", len(body))[1:] + body
    return b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs


def pcap(packets):
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for ts, raw in packets:
        out += struct.pack("<IIII", int(ts), int((ts % 1) * 1e6), len(raw), len(raw)) + raw
    return out


def pcapng(packets):
    shb = struct.pack("<IIIhhq", 0x0A0D0D0A, 28, 0x1A2B3C4D, 1, 0, -1) + struct.pack("<I", 28)
    idb_body = struct.pack("<HHI", 1, 0, 65535) + struct.pack("<HHB", 9, 1, 6) + b"\x00\x00\x00" + struct.pack("<HH", 0, 0)
    idb = struct.pack("<II", 1, 8 + len(idb_body) + 4) + idb_body + struct.pack("<I", 8 + len(idb_body) + 4)
    out = shb + idb
    for ts, raw in packets:
        t = int(ts * 1e6)
        pad = (4 - len(raw) % 4) % 4
        body = struct.pack("<IIIII", 0, t >> 32, t & 0xFFFFFFFF, len(raw), len(raw)) + raw + b"\x00" * pad
        out += struct.pack("<II", 6, 8 + len(body) + 4) + body + struct.pack("<I", 8 + len(body) + 4)
    return out


C, S, S2, DNSS = "192.0.2.20", "198.51.100.10", "198.51.100.11", "192.0.2.1"
SCEN = [
    (1.000, udp(C, DNSS, 5000, 53, dns_query(1, "intra.exemple"))), (1.050, udp(DNSS, C, 53, 5000, dns_answer(1, "intra.exemple", S))),
    (1.100, udp(C, DNSS, 5001, 53, dns_query(2, "nope.exemple"))), (1.120, udp(DNSS, C, 53, 5001, dns_answer(2, "nope.exemple", S, rcode=3))),
    (2.000, tcp(C, S, 40000, 443, 0x02, seq=1)), (2.030, tcp(S, C, 443, 40000, 0x12, seq=1, ack=2)), (2.031, tcp(C, S, 40000, 443, 0x10, seq=2, ack=2)),
    (2.040, tcp(C, S, 40000, 443, 0x18, seq=2, ack=2, payload=client_hello("intra.exemple"))), (2.090, tcp(S, C, 443, 40000, 0x18, seq=2, ack=300, payload=b"\x16\x03\x03\x00\x50\x02" + b"\x00" * 20)),
    (3.000, tcp(C, S2, 40001, 80, 0x02, seq=1)), (3.010, tcp(S2, C, 80, 40001, 0x12, seq=1, ack=2)),
    (3.020, tcp(C, S2, 40001, 80, 0x18, seq=2, ack=2, payload=b"GET /api/v1/items HTTP/1.1\r\nHost: api.exemple\r\n\r\n")),
    (3.020, tcp(C, S2, 40001, 80, 0x18, seq=2, ack=2, payload=b"GET /api/v1/items HTTP/1.1\r\nHost: api.exemple\r\n\r\n")),  # retransmission
    (3.520, tcp(S2, C, 80, 40001, 0x18, seq=2, ack=60, payload=b"HTTP/1.1 503 Service Unavailable\r\n\r\n")),
    (4.000, tcp(C, "203.0.113.9", 40002, 3389, 0x02, seq=1)), (5.000, tcp(C, "203.0.113.9", 40002, 3389, 0x02, seq=1)),
    (6.000, tcp(S, C, 443, 40000, 0x04, seq=5, ack=5)),
]


class AnalyzerTests(unittest.TestCase):
    def test_pcap_et_pcapng_identiques(self):
        a = ta.analyze(pcap(SCEN)); b = ta.analyze(pcapng(SCEN))
        self.assertEqual(a["packets"], len(SCEN)); self.assertEqual(a["hosts"], b["hosts"]); self.assertEqual(a["dns"], b["dns"])

    def test_scenario(self):
        r = ta.analyze(pcap(SCEN))
        self.assertEqual(r["local_ips"], [C]); self.assertEqual(r["duration_s"], 5.0)
        by = {(h["ip"], h["port"]): h for h in r["hosts"]}
        s = by[(S, 443)]
        self.assertEqual(s["name"], "intra.exemple"); self.assertEqual(s["rtt_ms"], 30.0); self.assertEqual(s["proto"], "https"); self.assertEqual(s["rst"], 1)
        s2 = by[(S2, 80)]
        self.assertEqual(s2["name"], "api.exemple"); self.assertEqual(s2["retrans"], 1)
        rdp = by[("203.0.113.9", 3389)]
        self.assertEqual((rdp["flows"], rdp["syn_failed"], rdp["proto"]), (1, 1, "rdp"))
        self.assertEqual(r["http"], [{"host": "api.exemple", "method": "GET", "path": "/api/v1/items", "status": 503, "ttfb_ms": 500.0}])
        self.assertEqual(r["tls"][0]["sni"], "intra.exemple"); self.assertEqual(r["tls"][0]["hello_ms"], 50.0)
        self.assertEqual((r["dns"]["queries"], r["dns"]["responses"], r["dns"]["failures"], r["dns"]["nxdomain"], r["dns"]["avg_ms"]), (2, 2, 1, 1, 35.0))
        codes = {f["code"] for f in r["findings"]}
        self.assertEqual(codes, {"connect-failed", "dns-failures", "http-error"})
        self.assertEqual(r["summary"]["state"], "critical"); self.assertEqual(r["protocols"]["https"], 6); self.assertEqual(r["protocols"]["dns"], 4)

    def test_parsers_robustes(self):
        self.assertIsNone(ta.tls_sni(b"\x16\x03\x01\x00\x05\x01xx"))
        self.assertIsNone(ta.dns_parse(b"\x00\x01"))
        self.assertIsNone(ta.http_request(b"BLOB"))
        self.assertEqual(ta.http_status(b"HTTP/1.1 200 OK\r\n"), 200)
        self.assertEqual(list(ta.iter_packets(b"xx")), []); self.assertEqual(ta.analyze(b"")["packets"], 0)
        self.assertEqual(ta.decode(b"\x00" * 12 + b"\x86\xdd" + b"\x00" * 40)["proto"], "ipv6")


class WebTraceTests(unittest.TestCase):
    def test_plan_capture(self):
        argv, path = wt.capture_plan("win32", 20, "C:\\tmp")
        self.assertEqual(argv[0][:3], ["pktmon", "start", "--capture"]); self.assertTrue(path.endswith(".etl"))
        argv, path = wt.capture_plan("linux", 20, "/tmp")
        self.assertEqual(argv[0][0], "tcpdump"); self.assertIn("-G", argv[0]); self.assertTrue(path.endswith(".pcap"))
        self.assertEqual(wt.clamp_seconds("999"), 300); self.assertEqual(wt.clamp_seconds("x"), 30)

    def test_cli_sans_outil(self):
        env = {**os.environ, "PATH": "/nonexistent"}
        p = subprocess.run([sys.executable, os.path.join(HERE, "web_trace.py"), "--seconds", "1"], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(p.returncode, 0); out = json.loads(p.stdout); self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
