# -*- coding: utf-8 -*-
"""Tests #686 : matrice SSID x VLAN prévue / observée / prouvée (valeurs fictives)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import ssidmatrix  # noqa: E402

VMAP = {"vlans": [
    {"vid": 1, "ssids": [], "subnet": "192.0.2.0/24"},
    {"vid": 20, "ssids": [{"name": "Bureau", "enabled": True}], "subnet": "198.51.100.1/24", "gateway_interface": "vlan20"},
    {"vid": 30, "ssids": [{"name": "Invites", "enabled": True, "guest": True}], "subnet": "203.0.113.1/24", "guest": True},
    {"vid": 40, "ssids": [{"name": "Atelier", "enabled": True}], "subnet": "10.40.0.1/24"},
    {"vid": 50, "ssids": [{"name": "Ancien", "enabled": False}], "subnet": None},
    {"vid": 60, "ssids": [], "subnet": "10.60.0.1/24"},
], "anomalies_detail": [
    {"kind": "ssid_vlan_not_on_link", "message": "VLAN 40 (SSID Atelier) n'est pas porté par la liaison sw-a port 1 ↔ sw-b port 2.", "details": {"vlan": 40}},
]}

CLIENTS = [
    {"ssid": "Bureau", "ipv4Address": "198.51.100.23"},
    {"ssidName": "Bureau", "ipv4Address": "198.51.100.24"},
    {"ssid_name": "Invites", "ipv4_address": "198.51.100.40"},       # client invité dans le sous-réseau du bureau
    {"ssid": "Labo", "ipv4Address": "10.9.9.9"},                     # SSID inconnu du plan
    {"ssid": "Bureau", "ipv4Address": "169.254.3.4"},                # APIPA : ignorée
    {"macAddress": "xx"},                                            # filaire : ignoré
]

PROOF = """#ssid-vlan-check;2026-10-06T10:00:00
Atelier;40;-;KO: Secrets were required
Ancien;50;-;OK;
Bureau;20;198.51.100.77/24;OK;192.0.2.10=OK,192.0.2.11:7070=KO
Invites;30;203.0.113.9/24;OK;192.0.2.10=KO
"""


class Matrix(unittest.TestCase):
    def setUp(self):
        self.m = ssidmatrix.build_matrix(VMAP, CLIENTS, ssidmatrix.parse_check_csv(PROOF))
        self.by = {r["ssid"]: r for r in self.m["ssids"]}

    def test_parse(self):
        p = ssidmatrix.parse_check_csv(PROOF)
        self.assertEqual(p["at"], "2026-10-06T10:00:00")
        self.assertFalse(p["rows"]["Atelier"]["association"]); self.assertEqual(p["rows"]["Atelier"]["error"], "Secrets were required")
        self.assertEqual(p["rows"]["Bureau"]["targets"], {"192.0.2.10": True, "192.0.2.11:7070": False})
        self.assertIsNone(p["rows"]["Ancien"]["address"])
        self.assertEqual(ssidmatrix.parse_check_csv("n'importe quoi\n;;"), {"at": None, "rows": {}})

    def test_bureau_observe_mais_cible_ko(self):
        b = self.by["Bureau"]
        self.assertEqual((b["observed"]["clients"], b["observed"]["with_ip"], b["observed"]["in_plan"]), (3, 2, 2))
        self.assertTrue(b["proven"]["in_plan"])
        self.assertEqual(b["verdict"], "écart"); self.assertIn("192.0.2.11:7070", b["gaps"][0])

    def test_invites_hors_plan_et_isolation_attendue(self):
        i = self.by["Invites"]
        self.assertEqual(i["observed"]["off_plan_subnets"], ["198.51.100.0/24"])
        self.assertEqual(i["verdict"], "écart")
        self.assertTrue(any("isolation attendue" in n for n in i["notes"]))
        self.assertFalse(any("injoignables" in g for g in i["gaps"]))

    def test_atelier_transport_et_association(self):
        a = self.by["Atelier"]
        self.assertEqual(a["verdict"], "écart")
        self.assertTrue(any(g.startswith("Transport du VLAN 40") for g in a["gaps"]))
        self.assertTrue(any("association refusée" in g for g in a["gaps"]))

    def test_ssid_hors_plan_et_sans_bail(self):
        self.assertIn("SSID absent du plan", self.by["Labo"]["gaps"][0])
        self.assertTrue(any("aucun bail" in g for g in self.by["Ancien"]["gaps"]))
        self.assertEqual(self.m["vlans_without_ssid"], [60])

    def test_verdicts_positifs(self):
        vmap = {"vlans": [{"vid": 20, "ssids": [{"name": "Bureau", "enabled": True}], "subnet": "198.51.100.1/24"},
                          {"vid": 21, "ssids": [{"name": "Salle", "enabled": True}], "subnet": "198.51.101.1/24"},
                          {"vid": 22, "ssids": [{"name": "Vide", "enabled": True}], "subnet": "198.51.102.1/24"},
                          {"vid": 23, "ssids": [{"name": "Off", "enabled": False}], "subnet": "198.51.103.1/24"}]}
        m = ssidmatrix.build_matrix(vmap, [{"ssid": "Bureau", "ipv4Address": "198.51.100.5"}],
                                    ssidmatrix.parse_check_csv("Salle;21;198.51.101.8/24;OK;"))
        self.assertEqual({r["ssid"]: r["verdict"] for r in m["ssids"]},
                         {"Bureau": "observé", "Salle": "prouvé", "Vide": "à prouver", "Off": "désactivé"})
        self.assertEqual(m["summary"], {"observé": 1, "prouvé": 1, "à prouver": 1, "désactivé": 1})

    def test_entrees_vides(self):
        self.assertEqual(ssidmatrix.build_matrix(None, None, None)["ssids"], [])


if __name__ == "__main__":
    unittest.main()
