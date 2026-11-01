# -*- coding: utf-8 -*-
"""Tests #747 : occupation des bornes Wi-Fi (relevé, seuils, alertes Nebula, récapitulatif) et boucle d'envoi."""
import os
import sqlite3
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import alerting  # noqa: E402
import occupancy  # noqa: E402

DEVICES = [{"devId": "ap1", "name": "Borne Amphi", "mac": "02:00:00:00:00:10", "type": "AP"},
           {"devId": "ap2", "name": "Borne Hall", "mac": "02:00:00:00:00:20", "type": "AP"},
           {"devId": "sw1", "name": "Switch cœur", "mac": "02:00:00:00:00:30", "type": "SW"}]


def clients(n_amphi, n_hall, weak_amphi=0):
    out = []
    for i in range(n_amphi):
        out.append({"macAddress": "02:aa:00:00:01:%02x" % i, "status": "online", "apName": "Borne Amphi", "band": "5G", "ssid": "campus",
                    "signalStrength": -80 if i < weak_amphi else -55})
    for i in range(n_hall):
        out.append({"macAddress": "02:aa:00:00:02:%02x" % i, "status": "online", "apMac": "02:00:00:00:00:20", "band": "2.4G", "ssid": "invite"})
    out.append({"macAddress": "02:aa:00:00:03:01", "status": "offline", "apName": "Borne Hall"})   # déconnecté : pas compté
    return out


class Occupation(unittest.TestCase):
    def cfg(self, **kw):
        c = alerting.normalize({"occupancy": dict({"enabled": True, "ap_warn": 10, "ap_crit": 20, "weak_pct": 40, "weak_min_clients": 5}, **kw)})
        return c["occupancy"]

    def test_normalize(self):
        o = alerting.normalize({})["occupancy"]
        self.assertFalse(o["enabled"]); self.assertEqual(o["ap_warn"], 25); self.assertEqual(o["recap"]["time"], "18:00")
        o = alerting.normalize({"occupancy": {"ap_warn": 30, "ap_crit": 5, "recap": {"time": "25:00", "weekdays": [7, 1, 9], "hours": 999}}})["occupancy"]
        self.assertEqual(o["ap_crit"], 30); self.assertEqual(o["recap"]["time"], "18:00")
        self.assertEqual(o["recap"]["weekdays"], [1, 7]); self.assertEqual(o["recap"]["hours"], 168)

    def test_snapshot(self):
        s = occupancy.snapshot(clients(12, 3, weak_amphi=6), DEVICES)
        self.assertEqual([(a["name"], a["clients"]) for a in s["aps"]], [("Borne Amphi", 12), ("Borne Hall", 3)])
        self.assertEqual(s["total"], 15); self.assertEqual(s["aps"][0]["weak"], 6)
        self.assertEqual(s["aps"][1]["by_ssid"], {"invite": 3})

    def test_breaches_seuils_et_nebula(self):
        s = occupancy.snapshot(clients(22, 11, weak_amphi=10), DEVICES)
        now = 1_800_000_000
        st = {"ap2": {"status": "offline", "since": now - 600}, "sw1": {"status": "alerting", "since": now - 60}, "ap1": {"status": "online", "since": 0}}
        rows = occupancy.breaches("s1", "Site Alpha", s, st, {"ap2": "Borne Hall", "sw1": "Switch cœur"}, self.cfg(), now)
        ids = {r["id"]: r for r in rows}
        self.assertEqual(ids["occ-crit:ap1"]["severity"], "haute"); self.assertIn("Borne Amphi", ids["occ-crit:ap1"]["message"])
        self.assertEqual(ids["occ-warn:ap2"]["severity"], "moyenne")
        self.assertIn("occ-weak:ap1", ids)                       # 10/22 = 45 % sous -75 dBm
        self.assertEqual(ids["neb-status:ap2"]["kind"], "nebula")  # hors ligne depuis 10 min > 5 min
        self.assertNotIn("neb-status:sw1", ids)                   # en alerte depuis 1 min seulement

    def test_suivi_et_retour(self):
        track = {"enabled": True, "min_severity": "moyenne", "delay_minutes": 0, "repeat_hours": 0, "notify_recovery": True}
        s = occupancy.snapshot(clients(22, 0), DEVICES)
        rows = occupancy.breaches("s1", "A", s, {}, {}, self.cfg(), 1000)
        state, raised, rec = alerting.track({}, rows, 1000, track)
        self.assertEqual(len(raised), 1)
        state, raised, rec = alerting.track(state, rows, 1600, track)
        self.assertEqual(raised, [])                               # pas de doublon
        state, raised, rec = alerting.track(state, [], 2200, track)
        self.assertEqual(len(rec), 1)                              # retour à la normale

    def test_recap(self):
        t0 = datetime(2026, 10, 14, 8, 0).timestamp()
        samples = [("ap1", t0 + i * 600, n, "s1") for i, n in enumerate([2, 10, 30, 12])] + [("ap2", t0 + i * 600, 0, "s1") for i in range(4)]
        r = occupancy.recap(samples, t0, {"ap1": "Borne Amphi", "ap2": "Borne Hall"})
        self.assertEqual(r["aps"][0]["max"], 30); self.assertEqual(r["aps"][0]["avg"], 13.5)
        self.assertEqual(r["idle"], ["Borne Hall"]); self.assertEqual(r["site_peak"]["clients"], 30)
        txt = occupancy.recap_text(r, "Titre", 24)
        self.assertIn("Pic du site : 30 clients", txt); self.assertIn("Borne Hall", txt)
        self.assertIn("Aucun relevé", occupancy.recap_text(occupancy.recap([], 0), "T", 24))


class Boucle(unittest.TestCase):
    """occupancy_pass de report_routes avec des crochets factices (sans Flask réel ni Nebula)."""
    def setUp(self):
        import tempfile
        self.db = os.path.join(tempfile.mkdtemp(), "t.db")
        import report_routes
        from flask import Flask
        self.rr = report_routes
        self.sent = []
        report_routes._notify = lambda action, subject, body, cfg, attachments=None, severity=None: self.sent.append((action, subject, body)) or {"status": "sent", "recipients": 1}

        def conn():
            c = sqlite3.connect(self.db); c.row_factory = sqlite3.Row; return c
        self.n = 22
        hooks = {"conn": conn, "sites": lambda: [{"siteId": "s1", "name": "Site Alpha"}], "anomalies": lambda s, r: ([], {}, {}),
                 "manage": lambda b: (True, None), "configured": lambda: True, "lock_dir": os.path.dirname(self.db),
                 "occupancy_inputs": lambda sid: (clients(self.n, 2), DEVICES, {}, {})}
        report_routes.register(Flask(__name__), hooks, start_loop=False)
        report_routes.kv_set("settings", {"recipients": ["a@exemple.fr"], "occupancy": {"enabled": True, "ap_warn": 10, "ap_crit": 20,
                                                                                         "recap": {"enabled": True, "time": "18:00", "weekdays": [1, 2, 3, 4, 5, 6, 7]}}})

    def test_passages(self):
        cfg = self.rr.settings()
        d = lambda h, m: datetime(2026, 10, 14, h, m)   # noqa: E731
        out = self.rr.occupancy_pass(cfg, d(9, 0).timestamp(), d(9, 0))
        self.assertEqual(out["sampled"], 2); self.assertEqual(out["alerts"], 1)
        self.assertEqual(self.sent[0][0], "nebula.occupation-seuil")
        out = self.rr.occupancy_pass(cfg, d(9, 2).timestamp(), d(9, 2))   # avant la période : pas de relevé
        self.assertEqual(out["sampled"], 0)
        self.n = 3
        out = self.rr.occupancy_pass(cfg, d(9, 12).timestamp(), d(9, 12))
        self.assertEqual(out["recovered"], 1); self.assertEqual(self.sent[-1][0], "nebula.retour-normale")
        out = self.rr.occupancy_pass(cfg, d(18, 5).timestamp(), d(18, 5))  # créneau du récapitulatif
        self.assertIsNotNone(out["recap"]); self.assertEqual(self.sent[-1][0], "nebula.occupation-recap")
        self.assertIn("Borne Amphi", self.sent[-1][2])


if __name__ == "__main__":
    unittest.main()
