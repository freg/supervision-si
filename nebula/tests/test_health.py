# -*- coding: utf-8 -*-
"""Santé du réseau Nebula (livraison #546) : transitions, disponibilité, tableau."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import health  # noqa: E402


class Diff(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(health.normalize_status("Online"), "online")
        self.assertEqual(health.normalize_status(True), "online")
        self.assertEqual(health.normalize_status(None), "offline")
        self.assertEqual(health.normalize_status(" ALERTING "), "alerting")

    def test_transitions_only_on_change(self):
        cur = [{"devId": "a", "currentStatus": "online"}, {"devId": "b", "currentStatus": "offline"}, {"noid": 1}]
        now, tr = health.diff_statuses({}, cur, at=100)
        self.assertEqual(now, {"a": "online", "b": "offline"})
        self.assertEqual([(t["dev_id"], t["from"], t["to"]) for t in tr], [("a", None, "online"), ("b", None, "offline")])
        now2, tr2 = health.diff_statuses(now, [{"devId": "a", "currentStatus": "online"}, {"devId": "b", "currentStatus": "online"}], at=160)
        self.assertEqual(tr2, [{"dev_id": "b", "from": "offline", "to": "online", "at": 160}])
        self.assertEqual(health.diff_statuses(now2, cur[:2], at=220)[1][0]["to"], "offline")


class Availability(unittest.TestCase):
    def test_rate_and_incidents(self):
        trs = [{"at": 1000, "to": "offline"}, {"at": 1600, "to": "online"}, {"at": 5000, "to": "offline"}]
        rate, down, inc = health.availability(trs, 0, 6000)
        self.assertEqual(down, 600 + 1000)
        self.assertEqual(inc, 2)
        self.assertAlmostEqual(rate, 1 - 1600 / 6000, places=4)
        # transition avant la fenêtre : fixe l'état initial
        rate, down, inc = health.availability([{"at": 10, "to": "offline"}], 100, 200)
        self.assertEqual((rate, down, inc), (0.0, 100, 0))
        self.assertEqual(health.availability([], 0, 100), (1.0, 0, 0))
        self.assertEqual(health.availability([], 100, 100), (1.0, 0, 0))


class Board(unittest.TestCase):
    def test_board_phrases(self):
        devices = [{"devId": "a", "name": "Borne studio", "model": "WBE660S", "type": "AP"}, {"devId": "b", "name": "Coeur", "model": "XS3800-28", "type": "SW"}, {"devId": "c", "name": "Nouveau"}]
        statuses = {"a": {"status": "offline", "since": 3000}, "b": {"status": "online", "since": 0}}
        trs = [{"dev_id": "a", "from": "online", "to": "offline", "at": 3000}]
        b = health.health_board(devices, statuses, trs, 0, 6000, now=6000)
        self.assertEqual(b["resume"], "1 équipement hors ligne sur 3.")
        self.assertEqual(b["phrases"], ["Borne studio (WBE660S) : hors ligne depuis 50 min."])
        self.assertEqual(b["devices"][0]["name"], "Borne studio")  # hors ligne d'abord
        self.assertEqual(b["devices"][0]["availability"], 0.5)
        self.assertEqual(b["incidents"], 1)
        self.assertEqual(next(r for r in b["devices"] if r["name"] == "Nouveau")["status"], "inconnu")
        self.assertEqual(b["devices"][-1]["name"], "Coeur")  # en ligne en dernier
        ok = health.health_board(devices[:2], {"a": {"status": "online"}, "b": {"status": "online"}}, [], 0, 100)
        self.assertEqual(ok["resume"], "Tout le réseau est en ligne (2 équipements).")
        self.assertEqual(health.health_board([], {}, [], 0, 1)["resume"], "Aucun équipement connu.")


if __name__ == "__main__":
    unittest.main()
