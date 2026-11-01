# -*- coding: utf-8 -*-
"""Module d'action (#852) : plans (API / manuel), impact immédiat, contrôles du chien de garde ; recherche sur tout."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import actions  # noqa: E402
import recherche  # noqa: E402

NOW = 1_800_000_000
LINK = {"kind": "link_missing_vlan", "details": {"missing_dev": "sw2", "missing_on": "GS2220-acces", "missing_port": 49, "vlans": [30, "40"]}}
GW = {"kind": "gateway_ip_not_host", "details": {"vlan": 21, "interface": "VLAN21_inst", "address": "198.51.100.0/24", "suggest": "198.51.100.1/24"}}


class Plans(unittest.TestCase):
    def test_plans(self):
        p = actions.plan(LINK)
        self.assertEqual((p["mode"], p["perimetre"]["vlans"], p["perimetre"]["port"]), ("api", [30, 40], 49))
        self.assertIn("retour arrière", p["etapes"][-1])
        g = actions.plan(GW)
        self.assertEqual((g["mode"], g["perimetre"]["vlans"], g["perimetre"]["apres"]), ("manuel", [21], "198.51.100.1/24"))
        self.assertIn("lecture seule", g["pourquoi_manuel"])
        self.assertIn("198.51.100.1", g["etapes"][1])
        self.assertEqual(actions.plan({"kind": "autre", "action": "faire X", "details": {}})["etapes"][0], "faire X")

    def test_impact(self):
        per = actions.plan(LINK)["perimetre"]
        clients = [{"mac_address": "02:00:5e:00:00:01", "vlan": 30, "last_seen": (NOW - 60) * 1000, "os_hostname": "poste-a"},
                   {"mac_address": "02:00:5e:00:00:02", "vlan": 99, "last_seen": (NOW - 60) * 1000}]
        sw = [{"mac_address": "02:00:5e:00:00:03", "connected_device_id": "sw2", "connected_port": "49", "last_seen": NOW - 4000}]
        ap = [{"mac_address": "02:00:5e:00:00:04", "ssid": "Général", "last_seen": NOW - 30, "upload": 10e6, "download": 50e6}]
        i = actions.impact(per, clients, sw, ap, {"Général": 40}, NOW)
        self.assertEqual((i["recents"], i["actifs"], i["niveau"], i["octets_2h"]), (3, 2, "faible", 60e6))
        self.assertEqual([c["source"] for c in i["clients"]], ["Wi-Fi Général", "site", "port 49"])
        self.assertEqual(actions.impact(per, [], [], [], {}, NOW)["niveau"], "aucun")
        beaucoup = [{"mac_address": "02:00:5e:00:01:%02x" % n, "vlan": 30, "last_seen": NOW} for n in range(5)]
        self.assertEqual(actions.impact(per, beaucoup, maintenant=NOW)["niveau"], "fort")

    def test_controles(self):
        per = actions.plan(LINK)["perimetre"]
        ok = actions.controles(per, {"dev_status": "online", "port": {"allowedVLAN": ["1", "30", "40"]}, "clients_avant": 4, "clients_apres": 3, "anomalie_presente": False})
        self.assertTrue(actions.bilan(ok))
        ko = actions.controles(per, {"dev_status": "offline", "port": {"allowedVLAN": ["1", "30"]}, "clients_avant": 4, "clients_apres": 0})
        self.assertEqual([c["ok"] for c in ko], [False, False, False])
        self.assertIn("40", ko[1]["detail"])
        self.assertTrue(actions.bilan(actions.controles({"vlans": [21]}, {"anomalie_presente": False})))


class Recherche(unittest.TestCase):
    def test_tout(self):
        clients = [{"name": "LED-CTRL", "mac": "02:00:5E:00:00:07", "ip": "198.51.100.20", "manufacturer": "Dell Inc.", "signal": -67, "last_seen": 1_761_210_000_000, "vlan": 51},
                   {"name": "imprimante", "mac": "02:00:5e:00:00:08", "manufacturer": "HP", "status": "online"}]
        src = [("client", lambda o: o["name"], lambda o: {"tab": "vlan", "mac": o["mac"]}, clients),
               ("vlan", lambda o: "VLAN %s" % o["vid"], lambda o: {"tab": "vlan"}, [{"vid": 51, "subnet": "198.51.100.0/24", "ssids": [{"name": "Atelier"}]}])]
        self.assertEqual([r["titre"] for r in recherche.chercher("dell", src)], ["LED-CTRL"])
        self.assertEqual([r["titre"] for r in recherche.chercher("0200 5e00 0007", src)] or [r["titre"] for r in recherche.chercher("02005e000007", src)], ["LED-CTRL"])
        self.assertEqual([r["titre"] for r in recherche.chercher("02-00-5e-00-00-08", src)], ["imprimante"])
        self.assertEqual([r["titre"] for r in recherche.chercher("-67 dbm", src)], ["LED-CTRL"])
        self.assertEqual({r["titre"] for r in recherche.chercher("198.51.100", src)}, {"LED-CTRL", "VLAN 51"})
        d = recherche.aplatir({"last_seen": 1_761_210_000_000})[0][1]
        self.assertRegex(d, r"^\d\d/\d\d/2025 \d\d:\d\d$")
        self.assertEqual([r["titre"] for r in recherche.chercher(d[:5], src)], ["LED-CTRL"])
        self.assertEqual([r["titre"] for r in recherche.chercher("atelier 51", src)], ["VLAN 51"])
        self.assertEqual(recherche.chercher("  ", src), [])
        self.assertTrue(all(len(r["champs"]) >= 1 for r in recherche.chercher("dell", src)))


if __name__ == "__main__":
    unittest.main()
