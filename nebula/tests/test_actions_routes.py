# -*- coding: utf-8 -*-
"""Module d'action (#852) : exécution par l'API avec sauvegarde, chien de garde (vérifiée / retour arrière), plan
manuel vérifié par relecture, annulation, journal -- client Nebula simulé."""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
from flask import Flask  # noqa: E402

import actions_routes as ar  # noqa: E402

DB = os.path.join(tempfile.mkdtemp(), "a.db")
NOW_MS = int(time.time() * 1000)
LINK = {"id": "a1", "kind": "link_missing_vlan", "element": "GS2220 p49", "message": "VLAN 30 absent", "severity": "haute", "action": "ajouter",
        "details": {"missing_dev": "sw2", "missing_on": "GS2220", "missing_port": 49, "vlans": [30]}}
GW = {"id": "a2", "kind": "gateway_ip_not_host", "element": "VLAN 21", "message": "adresse du réseau", "severity": "haute", "action": "corriger",
      "details": {"vlan": 21, "interface": "VLAN21_inst", "address": "198.51.100.0/24", "suggest": "198.51.100.1/24"}}


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


class Fake:
    def __init__(self):
        self.port = {"portNum": 49, "trunk": True, "allowedVLAN": ["1", "10"]}
        self.ecrits, self.statut, self.casser = [], "online", False

    def sw_port_settings(self, site, dev): return [dict(self.port)]
    def sw_set_port_settings(self, site, dev, p):
        self.ecrits.append(dict(p))
        if not self.casser:
            self.port = dict(p)
    def get_online_status(self, site): return [{"devId": "sw2", "currentStatus": self.statut}]
    def get_site_clients(self, site, features=None, period="2h"): return [{"mac_address": "02:00:5e:00:00:01", "vlan": 30, "last_seen": NOW_MS}]
    def sw_clients(self, site, period): return {"data": []}
    def ap_clients_v2(self, site, period): return []


class Routes(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB):
            os.unlink(DB)
        self.fake, self.items, self.etats, self.notes = Fake(), [dict(LINK), dict(GW)], [], []
        self.ecriture = True
        app = Flask("t")
        ar.register(app, {"conn": conn, "client": lambda: self.fake, "anomalies": lambda sid, refresh=False: (self.items, [], {}), "ssid_vlan": lambda sid: {},
                          "manage": lambda b: (b.get("user") != "intrus", "droit requis"), "allow_write": lambda: self.ecriture,
                          "set_state": lambda *a: self.etats.append(a), "invalidate": lambda: None, "notify": lambda *a: self.notes.append(a[1])},
                    demarrer_surveillance=False)
        self.c = app.test_client()

    def test_api_verifiee_puis_annulee(self):
        p = self.c.get("/sites/s/actions/plan/a1").get_json()
        self.assertEqual((p["plan"]["mode"], p["impact"]["actifs"], p["ecriture_autorisee"]), ("api", 1, True))
        self.assertEqual(self.c.post("/sites/s/actions/executer", json={"aid": "a1"}).status_code, 409)       # confirmation
        self.assertEqual(self.c.post("/sites/s/actions/executer", json={"aid": "a1", "confirm": True, "user": "intrus"}).status_code, 403)
        r = self.c.post("/sites/s/actions/executer", json={"aid": "a1", "confirm": True, "user": "freg"})
        self.assertEqual(r.status_code, 202)
        act = r.get_json()
        self.assertEqual((act["etat"], act["avant"]["allowedVLAN"], self.fake.port["allowedVLAN"]), ("surveillance", ["1", "10"], ["1", "10", "30"]))
        fin = ar.surveiller(act["id"], [1, 2], dormir=lambda s: None)
        self.assertEqual(fin["etat"], "verifiee", fin["journal"])
        self.assertEqual(self.etats[0][2], "applied")
        self.assertIn("vérifiée", self.notes[-1])
        r = self.c.post("/actions/%s/annuler" % act["id"], json={"user": "freg"}).get_json()
        self.assertEqual((r["etat"], self.fake.port["allowedVLAN"]), ("annulee", ["1", "10"]))
        self.assertEqual(len(self.c.get("/actions?site=s").get_json()["actions"]), 1)

    def test_retour_arriere_automatique(self):
        act = self.c.post("/sites/s/actions/executer", json={"aid": "a1", "confirm": True, "user": "freg"}).get_json()
        self.fake.statut = "offline"                        # le commutateur décroche après la modification
        fin = ar.surveiller(act["id"], [1, 2], dormir=lambda s: None)
        self.assertEqual(fin["etat"], "annulee")
        self.assertEqual(self.fake.ecrits[-1]["allowedVLAN"], ["1", "10"])
        self.assertTrue(any("RETOUR ARRIÈRE" in j["texte"] for j in fin["journal"]))
        self.assertIn("annulée", self.notes[-1])

    def test_ecriture_desactivee_et_manuel(self):
        self.ecriture = False
        self.assertEqual(self.c.post("/sites/s/actions/executer", json={"aid": "a1", "confirm": True}).status_code, 403)
        self.assertEqual(self.c.post("/sites/s/actions/executer", json={"aid": "a2", "confirm": True}).status_code, 400)
        m = self.c.post("/sites/s/actions/manuel", json={"aid": "a2", "user": "freg"}).get_json()
        self.assertEqual((m["etat"], m["plan"]["mode"]), ("attente_manuel", "manuel"))
        v = self.c.post("/actions/%s/verifier" % m["id"]).get_json()
        self.assertEqual(v["etat"], "non_resolue")                          # toujours signalée
        self.items = [dict(LINK)]
        v = self.c.post("/actions/%s/verifier" % m["id"]).get_json()
        self.assertEqual((v["etat"], self.etats[-1][2]), ("verifiee", "applied"))
        self.assertEqual(self.c.post("/actions/%s/annuler" % m["id"], json={}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
