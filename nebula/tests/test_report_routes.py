# -*- coding: utf-8 -*-
"""Tests #703 : routes de rapport et boucle d'alertes, sur une application Flask
de test (hooks simulés, notify-api simulé)."""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
from flask import Flask  # noqa: E402

import report_routes as rr  # noqa: E402

DB = os.path.join(tempfile.mkdtemp(), "t.db")
ITEMS = {"s1": [{"id": "a1", "kind": "gateway_ip_not_host", "element": "VLAN 22", "severity": "haute", "message": "VLAN 22 : adresse du réseau", "action": "172.16.22.1/24", "state": None}]}


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


class FakeNotify(object):
    def __init__(self):
        self.sent = []

    def notify(self, action, subject, body="", context=None, severity=None, wait=False, to=None, attachments=None):
        self.sent.append({"action": action, "subject": subject, "body": body, "to": to, "attachments": attachments})
        return {"status": "queued", "recipients": len(to or []), "reason": ""}

    def register_actions(self, actions):
        self.actions = actions


class Routes(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB):
            os.unlink(DB)
        self.items = {k: list(v) for k, v in ITEMS.items()}
        self.fake = FakeNotify()
        rr.notify_client = self.fake
        app = Flask("t")
        rr.register(app, {"conn": conn, "sites": lambda: [{"siteId": "s1", "name": "Site Alpha"}],
                          "anomalies": lambda sid, refresh=False: (self.items.get(sid, []), [], {}),
                          "manage": lambda body: (body.get("groups") == ["admin_hub"], "droit 'manage' requis"),
                          "configured": lambda: True, "lock_dir": tempfile.mkdtemp()}, start_loop=False)
        self.c = app.test_client()
        self.adm = {"groups": ["admin_hub"], "user": "freg"}

    def put(self, settings, who=None):
        return self.c.put("/report/settings", json=dict(who or self.adm, settings=settings))

    def test_reglages_et_droits(self):
        self.assertEqual(self.put({"recipients": ["a@exemple.fr"]}, {"groups": ["x"]}).status_code, 403)
        self.assertEqual(self.put({"recipients": "a@exemple.fr; faux"}).status_code, 400)
        r = self.put({"recipients": "a@exemple.fr", "daily": {"enabled": True, "time": "07:30"}, "urgent": {"enabled": True, "delay_minutes": 0}})
        self.assertEqual(r.status_code, 200, r.get_json())
        g = self.c.get("/report/settings").get_json()
        self.assertEqual((g["settings"]["recipients"], g["settings"]["daily"]["time"]), (["a@exemple.fr"], "07:30"))
        self.assertTrue(g["next_daily"]); self.assertEqual(g["log"][0]["event"], "settings")
        self.assertEqual([a["id"] for a in self.fake.actions][0], "nebula.anomalie-urgente")

    def test_exports(self):
        for fmt, magic in (("csv", "﻿".encode()), ("xlsx", b"PK"), ("pdf", b"%PDF")):
            r = self.c.get("/report/anomalies?format=" + fmt)
            self.assertEqual(r.status_code, 200); self.assertTrue(r.data.startswith(magic), fmt)
            self.assertIn("attachment; filename=anomalies-reseau-", r.headers["Content-Disposition"])
        j = self.c.get("/report/anomalies").get_json()
        self.assertEqual((j["counts"]["haute"], j["rows"][0]["site"]), (1, "Site Alpha"))

    def test_urgence_retour_et_recapitulatif(self):
        self.put({"recipients": "a@exemple.fr", "urgent": {"enabled": True, "delay_minutes": 10}, "daily": {"enabled": True, "time": "08:00", "weekdays": [3], "formats": ["xlsx", "pdf"]}})
        mer = datetime(2026, 10, 7, 8, 0, 30)
        rr.check_once(1000, mer)                                     # récapitulatif dû (mercredi 08:00), urgence pas encore
        self.assertEqual([s["action"] for s in self.fake.sent], ["nebula.recapitulatif"])
        d = self.fake.sent[0]
        self.assertEqual(d["to"], ["a@exemple.fr"]); self.assertEqual([a[0][-4:] for a in d["attachments"]], ["xlsx", ".pdf"])
        self.assertIn("1 anomalie(s)", d["subject"])
        rr.check_once(1000 + 5 * 60, mer)                            # même créneau : pas de second récapitulatif
        self.assertEqual(len(self.fake.sent), 1)
        rr.check_once(1000 + 10 * 60, mer)
        self.assertEqual(self.fake.sent[-1]["action"], "nebula.anomalie-urgente"); self.assertIn("Site Alpha", self.fake.sent[-1]["subject"])
        rr.check_once(1000 + 20 * 60, mer)
        self.assertEqual(len(self.fake.sent), 2)                     # une seule alerte
        self.items["s1"] = []
        rr.check_once(1000 + 30 * 60, mer)
        self.assertEqual(self.fake.sent[-1]["action"], "nebula.retour-normale")
        events = [e["event"] for e in self.c.get("/report/settings").get_json()["log"]]
        self.assertEqual(events[:3], ["recovered", "urgent", "daily"])

    def test_envoi_immediat(self):
        self.assertEqual(self.c.post("/report/send", json=self.adm).status_code, 400)        # pas de destinataire
        self.put({"recipients": "a@exemple.fr"})
        self.assertEqual(self.c.post("/report/send", json={"groups": ["x"]}).status_code, 403)
        r = self.c.post("/report/send", json=self.adm)
        self.assertEqual(r.status_code, 200, r.get_json()); self.assertTrue(self.fake.sent[-1]["subject"].startswith("[TEST]"))


if __name__ == "__main__":
    unittest.main()
