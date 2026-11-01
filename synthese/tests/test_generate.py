# -*- coding: utf-8 -*-
"""Tests du générateur « Infos synthèse SI » (#523) sur le jeu fictif data.example/."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import generate as g  # noqa: E402

DATA = os.path.join(os.path.dirname(HERE), "data.example")


class Generate(unittest.TestCase):
    def setUp(self):
        self.doc = g.build(g.read_sources(DATA), now=0, links=g.load_links(DATA))

    def test_detection_et_comptes(self):
        kinds = sorted((s["source"], s["kind"]) for s in self.doc["sources"])
        self.assertEqual(dict(kinds)["ovh-ip.csv"], "ovh_ips")
        self.assertEqual(dict(kinds)["ovh-services.csv"], "ovh_services")
        self.assertEqual(dict(kinds)["ipam-serveurs.csv"], "ipam_subnet")
        self.assertEqual(dict(kinds)["ipam-devices.csv"], "ipam_devices")
        self.assertEqual(dict(kinds)["zones/exemple.fr.txt"], "zone")
        self.assertEqual(self.doc["unrecognized"], [])
        s = self.doc["summary"]
        self.assertEqual((s["zones"], s["records"], s["ovh_ips"], s["ovh_services"], s["ipam_subnets"], s["ipam_hosts"], s["ipam_devices"]), (2, 13, 3, 4, 1, 3, 2))

    def test_zone(self):
        z = {x["zone"]: x for x in self.doc["zones"]}
        ex = z["exemple.fr"]
        self.assertEqual(ex["provider"], "ovh")
        self.assertEqual(z["alpha-conseil.fr"]["provider"], "online")
        r = {x["fqdn"] + "/" + x["type"]: x for x in ex["records"]}
        self.assertEqual(r["glpi.exemple.fr/A"]["value"], "203.0.113.11")
        self.assertEqual(r["glpi.exemple.fr/A"]["comment"], "ancien serveur")
        self.assertEqual(r["mail.exemple.fr/MX"]["value"], "10 mx1.mail.ovh.net.")
        self.assertEqual(r["www.exemple.fr/CNAME"]["ttl"], 3600)
        self.assertIn("v=spf1", r["exemple.fr/TXT"]["value"])
        self.assertEqual(r["exemple.fr/SOA"]["name"], "@")

    def test_ovh_ipam_et_index(self):
        ips = {o["ip"]: o for o in self.doc["ovh_ips"]}
        self.assertEqual(ips["203.0.113.11"]["type"], "FAILOVER")
        self.assertEqual(ips["203.0.113.10"]["dns_count"], 2)
        sv = [s for s in self.doc["ovh_services"] if s["type"] == "IP"][0]
        self.assertEqual((sv["ip"], sv["effective_iso"], sv["dns_count"]), ("203.0.113.10", "2026-10-01", 2))
        sn = self.doc["ipam"]["subnets"][0]
        self.assertEqual((sn["title"], sn["cidr"], sn["vlan"]), ("Alpha Servers", "192.0.2.0/28", "35 - servers"))
        self.assertEqual(sn["hosts"][2]["reverse"], "hub.exemple.fr")
        dev = self.doc["ipam"]["devices"][0]
        self.assertEqual((dev["name"], dev["type"], dev["vendor"], dev["model"]), ("ALPHA-CORE-01", "Router", "Cisco Systems", "R7201"))
        ix = self.doc["index"]
        self.assertEqual(ix["203.0.113.10"]["dns"], ["exemple.fr", "hub.exemple.fr"])
        self.assertEqual(ix["203.0.113.10"]["ovh"]["type"], "DEDICATED")
        self.assertEqual(ix["203.0.113.10"]["services"][0]["service"], "ip-203.0.113.10")
        self.assertEqual(ix["192.0.2.10"]["ipam"][0]["hostname"], "super")
        self.assertEqual(ix["192.0.2.254"]["devices"], ["ALPHA-CORE-01"])
        self.assertEqual(list(ix)[0], "192.0.2.1", "index trié par adresse")
        self.assertEqual(self.doc["links"]["ipam_url"], "https://ipam.exemple.fr/")
        self.assertIn("{zone}", self.doc["links"]["ovh_zone"])


if __name__ == "__main__":
    unittest.main()
