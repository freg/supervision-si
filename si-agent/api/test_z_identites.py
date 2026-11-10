# -*- coding: utf-8 -*-
"""#1001 : identités réseau des agents (interfaces, voisins) tirées de la mesure netview."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identites  # noqa: E402


class Identites(unittest.TestCase):
    def test_extraire(self):
        latest = {"netview": {"at": "2026-11-10T09:00:00", "data": {
            "interfaces": [{"name": "eth0", "mac": "00:1A:2B:3C:4D:5E", "state": "up", "addresses": [{"ip": "192.0.2.10", "prefix": 24}]},
                           {"name": "tun0", "mac": None, "addresses": [{"ip": "10.8.0.2"}]},
                           {"name": "dummy", "mac": "00:00:00:00:00:00", "addresses": []}],
            "neighbors": [{"ip": "192.0.2.1", "mac": "AA:BB:CC:00:00:01", "dev": "eth0"}, {"ip": "192.0.2.9", "mac": None}]}}}
        r = identites.extraire({"agent_id": "a1", "hostname": "sonde", "site": "campus"}, latest)
        self.assertEqual([(i["nom"], i["mac"], i["ips"]) for i in r["interfaces"]], [("eth0", "00:1a:2b:3c:4d:5e", ["192.0.2.10"]), ("tun0", None, ["10.8.0.2"])])
        self.assertEqual(r["voisins"], [{"ip": "192.0.2.1", "mac": "aa:bb:cc:00:00:01", "dev": "eth0"}])

    def test_sans_netview(self):
        self.assertEqual(identites.extraire({"agent_id": "a2"}, {})["interfaces"], [])


if __name__ == "__main__":
    unittest.main()
