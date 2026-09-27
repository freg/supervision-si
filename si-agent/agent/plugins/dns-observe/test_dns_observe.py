"""Tests #639 : observabilité DNS (codec, apprentissage, comparaison, distribution)."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dns_observe as d  # noqa: E402


def make_response(tid, ips):
    pkt = struct.pack(">HHHHHH", tid, 0x8180, 1, len(ips), 0, 0)
    pkt += b"\x03www\x02fr\x00" + struct.pack(">HH", 1, 1)
    for ip in ips:
        pkt += b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + bytes(int(x) for x in ip.split("."))
    return pkt


class CodecTests(unittest.TestCase):
    def test_build_parse(self):
        q = d.build_query("www.fr", 0x1234)
        self.assertEqual(q[:2], b"\x12\x34"); self.assertIn(b"\x03www", q)
        rcode, ips = d.parse_answer(make_response(0x1234, ["192.0.2.1", "192.0.2.9"]), 0x1234)
        self.assertEqual(rcode, 0); self.assertEqual(ips, ["192.0.2.1", "192.0.2.9"])  # trié
        self.assertRaises(ValueError, d.parse_answer, make_response(0x1234, []), 0x9999)  # mauvais id


OBS = [
    {"source": "eth0", "resolver": "192.0.2.1", "kind": "distributed", "name": "app.fr", "ok": True, "rcode": "ok", "ips": ["203.0.113.5"]},
    {"source": "wlan0", "resolver": "192.0.2.2", "kind": "distributed", "name": "app.fr", "ok": True, "rcode": "ok", "ips": ["203.0.113.9"]},
    {"source": "wlan1", "resolver": "192.0.2.3", "kind": "distributed", "name": "app.fr", "ok": False, "rcode": "nxdomain", "ips": []},
    {"source": "eth0", "resolver": "8.8.8.8", "kind": "public", "name": "ok.fr", "ok": True, "rcode": "ok", "ips": ["203.0.113.1"]},
]


class AnalysisTests(unittest.TestCase):
    def test_learn_et_distribution(self):
        kb = d.learn(OBS)
        self.assertEqual(len(kb["app.fr"]["answers"]), 2)  # deux réponses distinctes
        self.assertEqual(len(kb["app.fr"]["fail"]), 1)
        by_src, by_dest = d.distribution(OBS)
        self.assertEqual(by_src["wlan1"]["fail"], 1)
        self.assertEqual(by_dest["203.0.113.5"], ["app.fr"])

    def test_compare_constats(self):
        alerts, _kb, state = d.compare(OBS)
        codes = {a["code"] for a in alerts}
        self.assertIn("dns-divergent", codes)          # app.fr → deux IP selon la source
        self.assertIn("dns-partial-nxdomain", codes)   # échoue sur wlan1
        self.assertIn("app.fr|192.0.2.1", state)
        # tout en échec -> dns-all-down
        allbad = [{"source": "eth0", "resolver": "192.0.2.1", "kind": "distributed", "name": "x.fr", "ok": False, "rcode": "servfail", "ips": []}]
        self.assertIn("dns-all-down", {a["code"] for a in d.compare(allbad)[0]})

    def test_expected_et_changement(self):
        alerts = d.compare(OBS, expected_dns=["192.0.2.1"])[0]
        self.assertIn("dns-unexpected-resolver", {a["code"] for a in alerts})  # 192.0.2.2/.3 hors liste
        prev = {"app.fr|192.0.2.1": "203.0.113.99"}
        alerts = d.compare(OBS, previous=prev)[0]
        chg = [a for a in alerts if a["code"] == "dns-answer-changed"]
        self.assertEqual(len(chg), 1); self.assertIn("203.0.113.99 → 203.0.113.5", chg[0]["message"])

    def test_summary(self):
        alerts = d.compare(OBS)[0]
        s = d.summarize(OBS, alerts)
        self.assertEqual((s["queries"], s["resolved"]), (4, 3)); self.assertEqual(s["state"], "warning")


if __name__ == "__main__":
    unittest.main()
