# -*- coding: utf-8 -*-
"""Tests #758 : anticipation Wi-Fi (prévision de pic, affluence inhabituelle, battements, disponibilité, DHCP)."""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import anticipation as an  # noqa: E402

OCC = {"ap_warn": 25, "ap_crit": 40}
NOW = datetime(2026, 10, 14, 8, 50)          # mercredi 8 h 50


def samples():
    """Trois mercredis précédents : 45 clients sur ap1 entre 10 h et 11 h, 10 sinon ; ap2 toujours 5."""
    out = []
    for w in (1, 2, 3):
        day = NOW - timedelta(weeks=w)
        for h in range(7, 18):
            for m in (0, 30):
                t = day.replace(hour=h, minute=m).timestamp()
                out.append(("ap1", t, 45 if h == 10 else 10))
                out.append(("ap2", t, 5))
    return out


class Anticipation(unittest.TestCase):
    def setUp(self):
        self.ant = an.normalize({"dhcp_pools": {"campus": 200, "vide": 0, "": 5}})
        self.prof = an.profile(samples())

    def test_normalize(self):
        self.assertEqual(self.ant["dhcp_pools"], {"campus": 200}); self.assertEqual(self.ant["horizon_hours"], 2)
        self.assertEqual(an.normalize({"horizon_hours": 99})["horizon_hours"], 12)

    def test_forecast(self):
        e = an.expected(self.prof, "ap1", NOW.replace(hour=10))
        self.assertEqual((e["p50"], e["p90"], e["weeks"]), (45, 45, 3))
        rows = an.forecast(self.prof, {"ap1": "Borne Amphi"}, "s1", "Campus", NOW, OCC, self.ant)
        self.assertEqual(len(rows), 1); r = rows[0]
        self.assertEqual((r["id"], r["severity"], r["at_hour"]), ("prev:ap1", "haute", "10:00"))
        self.assertIn("vers 10h", r["message"]); self.assertIn("mercredi", r["message"])
        self.assertEqual(an.forecast(self.prof, {}, "s1", "Campus", NOW.replace(hour=6), OCC, self.ant), [])   # horizon 2 h : 7 h, 8 h
        self.assertIsNone(an.expected(self.prof, "ap1", NOW.replace(hour=10), min_weeks=4))

    def test_unusual(self):
        rows = an.unusual(self.prof, [{"dev_id": "ap2", "clients": 30}, {"dev_id": "ap1", "clients": 12}], {}, "s1", "Campus", NOW, self.ant)
        self.assertEqual([r["id"] for r in rows], ["unusual:ap2"]); self.assertIn("habituellement 5", rows[0]["message"])
        self.assertEqual(an.unusual(self.prof, [{"dev_id": "ap2", "clients": 9}], {}, "s1", "C", NOW, self.ant), [])   # +4 < unusual_min

    def test_flapping_availability(self):
        now = NOW.timestamp(); H = 3600
        tr = [("ap1", "online", "offline", now - 5 * H), ("ap1", "offline", "online", now - 4.9 * H), ("ap1", "online", "alerting", now - 3 * H),
              ("ap1", "alerting", "online", now - 2.9 * H), ("ap1", "online", "offline", now - 1 * H), ("ap1", "offline", "online", now - 0.5 * H),
              ("ap2", "online", "offline", now - 30 * H)]
        rows = an.flapping(tr, {"ap1": "Borne Amphi"}, "s1", "Campus", now, self.ant)
        self.assertEqual([(r["id"], r["flaps"], r["severity"]) for r in rows], [("flap:ap1", 3, "moyenne")])
        av = an.availability(tr, {"ap1": "online", "ap2": "offline", "ap3": "online"}, now, 1)
        self.assertAlmostEqual(av["ap1"], round(100 * (1 - (0.1 + 0.1 + 0.5) / 24), 2))
        self.assertEqual(av["ap2"], 0.0); self.assertEqual(av["ap3"], 100.0)
        self.assertAlmostEqual(an.availability(tr, {}, now, 7)["ap2"], round(100 * (1 - 30 / (7 * 24)), 2))

    def test_dhcp(self):
        snaps = {"s1": {"aps": [{"by_ssid": {"campus": 120, "invite": 3}}, {"by_ssid": {"campus": 45}}]}}
        table, rows = an.dhcp(snaps, self.ant)
        self.assertEqual(table, [{"ssid": "campus", "pool": 200, "clients": 165, "pct": 82.5}])
        self.assertEqual((rows[0]["id"], rows[0]["severity"]), ("dhcp:campus", "moyenne"))
        _t, rows = an.dhcp({"s1": {"aps": [{"by_ssid": {"campus": 195}}]}}, self.ant)
        self.assertEqual(rows[0]["severity"], "haute")


if __name__ == "__main__":
    unittest.main()
