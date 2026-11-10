# -*- coding: utf-8 -*-
"""Tests #1002 : activité par client (volumes Wi-Fi des relèves, profil de présence et de volumes). Données inventées."""
import os
import sqlite3
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import activite as ac  # noqa: E402
import client_history as ch  # noqa: E402

# lundi 2 novembre 2026, minuit heure locale du conteneur de test
LUNDI = int(time.mktime((2026, 11, 2, 0, 0, 0, 0, 0, -1)))
H = 3600


class Activite(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")

    def test_machine_toujours_presente(self):
        for h in range(0, 7 * 24, 1):           # une semaine, présente chaque heure, petit volume constant
            now = LUNDI + h * H + 600
            ch.ingest(self.c, "s", ch.merge([{"mac": "00:aa:bb:00:00:01", "lastSeen": now}], sw_clients=[{"mac": "00:aa:bb:00:00:01", "connected_device_id": "SW", "connected_port": "27"}], now=now), now=now)
        p = ac.profil(self.c, "s", "00:aa:bb:00:00:01", jours=7, now=LUNDI + 7 * 24 * H)
        self.assertTrue(p["continu"])
        self.assertTrue(p["filaire"])
        self.assertEqual(p["jours_vus"], 7)
        self.assertEqual(p["part_weekend"], round(2 / 7, 2))
        self.assertEqual(p["histogramme"][3], 7)

    def test_tablette_heures_atelier_et_volumes(self):
        mac = "6e:00:00:00:00:02"
        for jour in range(5):
            for h in (9, 10, 11, 14, 15):
                now = LUNDI + jour * 86400 + h * H + 300
                ch.ingest(self.c, "s", ch.merge([{"mac": mac, "lastSeen": now}], [{"mac": mac, "ssid": "atelier", "connected_device_id": "AP"}], now=now), now=now)
                ac.ingest(self.c, "s", [{"mac_address": mac, "upload": 1e6 * h, "download": 9e6 * h}], 7200, now=now)
        p = ac.profil(self.c, "s", mac, jours=7, now=LUNDI + 7 * 86400)
        self.assertFalse(p["continu"])
        self.assertEqual(p["part_nuit"], 0.0)
        self.assertEqual(p["part_weekend"], 0.0)
        self.assertEqual(p["histogramme"][9], 5)
        self.assertEqual(p["volumes"]["mesures"], 25)
        self.assertEqual(p["volumes"]["part_descendant"], 0.9)
        self.assertGreater(p["volumes"]["regularite_cv"], 0.1)
        self.assertEqual(p["ssids"], ["atelier"])

    def test_ingest_ignore_sans_volume_et_purge(self):
        self.assertEqual(ac.ingest(self.c, "s", [{"mac": "x"}, {"mac": "00:11:22:33:44:55"}], 7200, now=LUNDI), 0)
        ac.ingest(self.c, "s", [{"mac": "00:11:22:33:44:55", "download": 5}], 7200, now=LUNDI)
        ac.ingest(self.c, "s", [], 7200, now=LUNDI + 61 * 86400)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM nebula_client_activite").fetchone()[0], 0)

    def test_profil_vide(self):
        p = ac.profil(self.c, "s", "00:11:22:33:44:55", now=LUNDI)
        self.assertEqual((p["jours_vus"], p["volumes"]["moyenne_heure"], p["continu"]), (0, None, False))


if __name__ == "__main__":
    unittest.main()
