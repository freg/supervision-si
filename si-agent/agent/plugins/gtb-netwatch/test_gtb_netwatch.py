"""Tests de la sonde gtb-netwatch (#739) : lecture pcap/pcapng, décodage, verdicts TCP/UDP/ICMP, entrants, constats."""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("gtb_netwatch", os.path.join(HERE, "gtb_netwatch.py"))
gn = importlib.util.module_from_spec(spec); spec.loader.exec_module(gn)

LOCAL = "192.0.2.5"


def ip4(a):
    return bytes(int(x) for x in a.split("."))


def ipv4(src, dst, proto, l4, ipid=1):
    return struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(l4), ipid, 0, 64, proto, 0, ip4(src), ip4(dst)) + l4


def tcp(src, sport, dst, dport, flags, seq=1000, ipid=1):
    return ipv4(src, dst, 6, struct.pack(">HHIIBBHHH", sport, dport, seq, 0, 0x50, flags, 8192, 0, 0), ipid)


def udp(src, sport, dst, dport, ipid=1):
    return ipv4(src, dst, 17, struct.pack(">HHHH", sport, dport, 12, 0) + b"\x81\x0a\x00\x04", ipid)


def icmp(src, dst, code, orig):
    return ipv4(src, dst, 1, struct.pack(">BBHI", 3, code, 0, 0) + orig[:28])


def eth(ip):
    return b"\x02" * 6 + b"\x02\x00\x00\x00\x00\x01" + b"\x08\x00" + ip


def pcapng(frames):
    def blk(t, body):
        body += b"\x00" * ((4 - len(body) % 4) % 4)
        return struct.pack("<II", t, len(body) + 12) + body + struct.pack("<I", len(body) + 12)
    out = blk(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    out += blk(1, struct.pack("<HHI", 1, 0, 128) + struct.pack("<HHB3x", 9, 1, 6) + struct.pack("<HH", 0, 0))
    for ts, fr in frames:
        us = int(ts * 1e6)
        out += blk(6, struct.pack("<IIIII", 0, us >> 32, us & 0xFFFFFFFF, len(fr), len(fr)) + fr)
    return out


SYN, RST, ACK = 0x02, 0x04, 0x10


def scenario():
    t = 1000.0
    p = []
    p += [(t, tcp(LOCAL, 50001, "192.0.2.10", 502, SYN)), (t + .01, tcp("192.0.2.10", 502, LOCAL, 50001, RST | ACK))]   # refusé
    p += [(t + .01, tcp(LOCAL, 50001, "192.0.2.10", 502, SYN))]                                                       # doublon pktmon (même ipid/seq)
    p += [(t, tcp(LOCAL, 50002, "192.0.2.11", 4840, SYN)), (t + 1, tcp(LOCAL, 50002, "192.0.2.11", 4840, SYN, ipid=2)),
          (t + 3, tcp(LOCAL, 50002, "192.0.2.11", 4840, SYN, ipid=3))]                                                # sans réponse
    p += [(t, tcp(LOCAL, 50003, "192.0.2.12", 1433, SYN)), (t + .01, tcp("192.0.2.12", 1433, LOCAL, 50003, SYN | ACK)),
          (t + 5, tcp("192.0.2.12", 1433, LOCAL, 50003, RST | ACK, ipid=9))]                                           # coupée par le distant
    s = tcp(LOCAL, 50004, "192.0.2.13", 47808, SYN)
    p += [(t, s), (t + .2, icmp("192.0.2.1", LOCAL, 1, s))]                                                           # ICMP hôte injoignable
    p += [(t + 2, tcp("192.0.2.20", 40000, LOCAL, 4911, SYN)), (t + 2.01, tcp(LOCAL, 4911, "192.0.2.20", 40000, RST | ACK))]   # entrant refusé
    p += [(t + 2, tcp("192.0.2.21", 40001, LOCAL, 1911, SYN))]                                                        # entrant ignoré
    p += [(t, udp(LOCAL, 47808, "192.0.2.30", 47808)), (t + 1, udp(LOCAL, 47808, "192.0.2.30", 47808, 2))]             # UDP sans réponse
    p += [(t, udp(LOCAL, 47808, "192.0.2.31", 47808)), (t + .05, udp("192.0.2.31", 47808, LOCAL, 47808))]             # UDP répondu
    u = udp(LOCAL, 50100, "192.0.2.32", 161)
    p += [(t, u), (t + .01, icmp("192.0.2.32", LOCAL, 3, u))]                                                         # port UDP fermé
    p += [(t, udp(LOCAL, 47808, "192.0.2.255", 47808))]                                                               # Who-Is diffusé
    p += [(t + 10, tcp(LOCAL, 50009, "192.0.2.40", 80, SYN)), (t + 10.01, tcp("192.0.2.40", 80, LOCAL, 50009, SYN | ACK))]  # ok
    return [(ts, eth(ip)) for ts, ip in p]


class Netwatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "c.pcapng")
        with open(self.path, "wb") as fh:
            fh.write(pcapng(scenario()))

    def verdicts(self):
        pk = gn.read_packets(self.path)
        eps, inbound, stats = gn.analyse(pk, [LOCAL], gn.port_set("gtb"), procs={(50001, "192.0.2.10", 502): "Neutrino.exe"})
        return {(e["remote"], e["port"], e["proto"]): e for e in eps}, {i["remote"]: i for i in inbound}, stats

    def test_read_pcapng_and_pcap(self):
        pk = gn.read_packets(self.path)
        self.assertEqual(len(pk), len(scenario()))
        self.assertAlmostEqual(pk[0][0], 1000.0, places=3)
        classic = os.path.join(self.tmp, "c.pcap")
        with open(classic, "wb") as fh:
            fh.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 128, 1))
            for ts, fr in scenario():
                fh.write(struct.pack("<IIII", int(ts), int((ts % 1) * 1e6), len(fr), len(fr)) + fr)
        self.assertEqual(len(gn.read_packets(classic)), len(scenario()))

    def test_tcp_verdicts(self):
        e, _i, stats = self.verdicts()
        r = e[("192.0.2.10", 502, "tcp")]
        self.assertEqual((r["attempts"], r["refused"]), (1, 1)); self.assertEqual(r["processes"], ["Neutrino.exe"])
        n = e[("192.0.2.11", 4840, "tcp")]
        self.assertEqual(n["no_answer"], 1); self.assertEqual(n["syn_retries"], 2)
        self.assertEqual(e[("192.0.2.12", 1433, "tcp")]["reset_remote"], 1)
        u = e[("192.0.2.13", 47808, "tcp")]
        self.assertEqual(u["unreachable"], 1); self.assertEqual(u["icmp"]["from"], "192.0.2.1"); self.assertIn("hôte", u["icmp"]["text"])
        self.assertEqual(e[("192.0.2.40", 80, "tcp")]["ok"], 1)
        self.assertEqual(stats["packets"], len(scenario()) - 1)        # doublon écarté

    def test_udp_and_inbound(self):
        e, i, stats = self.verdicts()
        self.assertEqual(e[("192.0.2.30", 47808, "udp")]["no_answer"], 2)
        self.assertEqual(e[("192.0.2.31", 47808, "udp")]["ok"], 1)
        self.assertEqual(e[("192.0.2.32", 161, "udp")]["refused"], 1)
        self.assertEqual(stats["broadcasts"][0]["dst"], "192.0.2.255")
        self.assertEqual(i["192.0.2.20"]["state"], "refused"); self.assertEqual(i["192.0.2.21"]["state"], "ignored")

    def test_findings(self):
        e, i, _s = self.verdicts()
        f = gn.findings_for(list(e.values()), list(i.values()))
        codes = {x["code"] for x in f}
        self.assertTrue({"tcp-refused", "tcp-no-answer", "unreachable", "tcp-reset-remote", "udp-no-answer", "udp-refused",
                         "inbound-refused", "inbound-dropped"} <= codes)
        self.assertTrue(any("Neutrino.exe" in x["text"] for x in f if x["code"] == "tcp-refused"))

    def test_targets_and_ports(self):
        pk = gn.read_packets(self.path)
        eps, _i, _s = gn.analyse(pk, [LOCAL], {502}, gn.target_nets("192.0.2.10/32"))
        self.assertEqual([(x["remote"], x["port"]) for x in eps], [("192.0.2.10", 502)])
        self.assertIsNone(gn.port_set("all")); self.assertIn(47808, gn.port_set("gtb")); self.assertEqual(gn.port_set("10-12"), {10, 11, 12})

    def test_cli_on_file(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "gtb_netwatch.py"), "--pcap", self.path], capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        self.assertEqual(d["backend"], "file"); self.assertTrue(d["alerts"]); self.assertTrue(d["endpoints"])


if __name__ == "__main__":
    unittest.main()
