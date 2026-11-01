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


class Infra(unittest.TestCase):
    """#759 : ports vers les bornes, micrologiciels, licences, bandes et signal."""
    def test_ap_ports(self):
        links = [{"a": "sw1", "a_port": 3, "b": "ap1", "device": True, "b_kind": "AP"}, {"a": "sw1", "a_port": 4, "b": "ap2", "device": True, "b_kind": "AP"},
                 {"a": "sw1", "a_port": 24, "b": "sw2", "external": False}]
        ports = {"sw1": [{"portNum": 3, "linkSpeed": "100M", "poeStatus": "Overload"}, {"portNum": 4, "speed": "1G", "poe": "on"}]}
        names = {"ap1": "Borne Amphi", "ap2": "Borne Hall", "sw1": "Switch cœur"}
        table, now_map, rows = an.ap_ports(links, ports, names, {"ap1": "sw1:3", "ap3": "sw1:9"}, {"ap3": True})
        self.assertEqual(now_map, {"ap1": "sw1:3", "ap2": "sw1:4"})
        self.assertEqual([t["speed_mbps"] for t in table], [100, 1000])
        ids = sorted(r["id"] for r in rows)
        self.assertEqual(ids, ["lldp-lost:ap3", "port-poe:ap1", "port-speed:ap1"])
        self.assertEqual(an._mbps("Auto (1000F)"), 1000); self.assertEqual(an._mbps("2.5G"), 2500); self.assertIsNone(an._mbps("auto"))

    def test_firmware_licenses(self):
        devs = [{"name": "a", "model": "NWA210AX", "firmwareVersion": "6.70"}, {"name": "b", "model": "NWA210AX", "productInfo": {"fwVersion": "6.80"}},
                {"name": "c", "model": "GS2220", "firmwareVersion": "4.80"}, {"name": "d", "model": "GS2220"}]
        table, rows = an.firmware(devs)
        self.assertEqual(table[1]["versions"], {"6.70": ["a"], "6.80": ["b"]})
        self.assertEqual([r["id"] for r in rows], ["fw-mixed:NWA210AX"])
        now = datetime(2026, 10, 14).timestamp()
        t, rows = an.licenses("Org", {"name": "Org", "license": {"type": "Pro Pack", "expireDate": "2026-11-01"}, "nebulaSecurityExpiry": 1798761600000}, now)
        self.assertEqual({r["field"] for r in t}, {"license.type", "license.expireDate", "nebulaSecurityExpiry"})
        self.assertEqual([(r["id"], r["severity"]) for r in rows], [("lic:Org:license.expireDate", "haute"), ("lic:Org:nebulaSecurityExpiry", "moyenne")])

    def test_band_signal(self):
        cl = [{"macAddress": "02:00:00:00:00:%02x" % i, "band": "2.4G", "signalStrength": -82} for i in range(4)] + [{"macAddress": "02:00:00:00:01:01", "band": "5G", "signal": -50}]
        prev = {}
        for _ in range(3):
            table, prev, rows = an.band_signal({"ap1": cl}, {"ap1": "Borne"}, -75, prev)
        self.assertEqual((table[0]["share24"], len(table[0]["sticky"])), (80, 4))
        self.assertEqual(sorted(r["id"] for r in rows), ["band24:ap1", "sticky:ap1"])
        table, prev2, rows = an.band_signal({"ap1": cl[4:]}, {}, -75, prev)
        self.assertEqual(prev2, {}); self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
