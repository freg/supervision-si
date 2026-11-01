"""Tests #640 : accès aux ressources (parse conntrack, agrégation client/ressource, constats)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resource_access as r  # noqa: E402

CONNTRACK = """ipv4     2 tcp      6 431999 ESTABLISHED src=192.168.0.50 dst=203.0.113.9 sport=51000 dport=443 src=203.0.113.9 dst=192.168.0.50 sport=443 dport=51000 bytes=1200 [ASSURED] mark=0 use=1
ipv4     2 tcp      6 60 TIME_WAIT src=192.168.0.51 dst=203.0.113.9 sport=52000 dport=80 bytes=300 src=203.0.113.9 dst=192.168.0.51 sport=80 dport=52000 bytes=900 mark=0 use=1
ipv4     2 udp      17 29 src=192.168.0.50 dst=8.8.8.8 sport=40000 dport=53 bytes=80 src=8.8.8.8 dst=192.168.0.50 sport=53 dport=40000 bytes=120 mark=0 use=1
ipv4     2 tcp      6 431999 ESTABLISHED src=192.168.0.50 dst=192.168.0.10 sport=53000 dport=445 bytes=5000 mark=0 use=1
"""


class ParseTests(unittest.TestCase):
    def test_parse(self):
        flows = r.parse_conntrack(CONNTRACK)
        self.assertEqual(len(flows), 4)
        f = flows[0]
        self.assertEqual((f["proto"], f["src"], f["dst"], f["dport"], f["bytes"]), ("tcp", "192.168.0.50", "203.0.113.9", 443, 1200))
        self.assertEqual(flows[1]["bytes"], 1200)  # 300 + 900 (deux compteurs)

    def test_is_local(self):
        nets = r._nets(r.DEFAULT_LOCAL)
        self.assertTrue(r.is_local("192.168.0.50", nets)); self.assertFalse(r.is_local("203.0.113.9", nets))


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.nets = r._nets(r.DEFAULT_LOCAL)
        self.agg = r.aggregate(r.parse_conntrack(CONNTRACK), self.nets, names_map={"203.0.113.9": "cdn-video"})

    def test_resources_et_clients(self):
        keys = {x["key"] for x in self.agg["resources"]}
        self.assertIn("203.0.113.9:443/tcp", keys); self.assertIn("203.0.113.9:80/tcp", keys); self.assertIn("8.8.8.8:53/udp", keys)
        self.assertNotIn("192.168.0.10:445/tcp", keys)  # local↔local exclu
        res443 = [x for x in self.agg["resources"] if x["key"] == "203.0.113.9:443/tcp"][0]
        self.assertEqual(res443["name"], "cdn-video"); self.assertEqual(res443["clients"], ["192.168.0.50"])
        c50 = [c for c in self.agg["clients"] if c["ip"] == "192.168.0.50"][0]
        self.assertEqual(c50["resources"], 2)  # 443 + 53 (445 est local, exclu)

    def test_findings(self):
        al = r.findings(self.agg, previous_keys=["203.0.113.9:443/tcp", "8.8.8.8:53/udp"], heavy_mb=0)
        codes = {a["code"] for a in al}
        self.assertIn("resource-cleartext", codes)   # port 80
        self.assertIn("resource-new", codes)          # le :80 est nouveau vs previous
        new = [a for a in al if a["code"] == "resource-new"][0]
        self.assertIn("cdn-video:80", new["message"])
        self.assertIn("talker-heavy", codes)          # heavy_mb=0 -> tout le monde
        # sans historique : pas de resource-new
        self.assertNotIn("resource-new", {a["code"] for a in r.findings(self.agg, previous_keys=[], heavy_mb=1e9)})

    def test_summary(self):
        s = r.summarize(self.agg, r.findings(self.agg, [], heavy_mb=1e9))
        self.assertEqual(s["resources"], 3); self.assertEqual(s["state"], "warning")  # cleartext


if __name__ == "__main__":
    unittest.main()
