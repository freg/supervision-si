# -*- coding: utf-8 -*-
"""Charge du réseau (#851) : agrégation par borne, SSID, VLAN, commutateur ; occupation simultanée."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import charge  # noqa: E402

DEV = [{"devId": "a1", "name": "borne hall", "type": "AP"}, {"devId": "a2", "name": "borne studio", "type": "AP"},
       {"devId": "s1", "name": "coeur", "type": "SW"}, {"devId": "g1", "name": "pare-feu", "type": "GW"}]
AP = [{"mac_address": "02:00:5E:00:00:01", "connected_device_id": "a1", "ssid": "Général", "upload": 1_000_000, "download": 9_000_000},
      {"mac_address": "02-00-5e-00-00-01", "connected_device_id": "a1", "ssid": "Général", "upload": 0, "download": 800_000},
      {"mac_address": "02:00:5e:00:00:02", "connected_device_id": "a1", "ssid": "Invités", "upload": "200000", "download": None}]


class Charge(unittest.TestCase):
    def test_agreger(self):
        r = charge.agreger("2h", DEV, ap_clients=AP, clients=[{"mac_address": "02:00:5e:00:00:09", "vlan": 51}],
                           sw_clients=[{"mac_address": "02:00:5e:00:00:0a", "vlan": "51"}],
                           sw_usage={"s1": {"uplinkTxUsage": 3_600_000_000, "uplinkRxUage": 0}}, gw_usage={"g1": {"erreur": "HTTP 404"}},
                           ssid_vlan={"Général": 10, "Invités": 99}, occupation={"a1": {"moyenne": 4.5, "max": 9, "releves": 24}})
        b = {x["dev_id"]: x for x in r["bornes"]}
        self.assertEqual((b["a1"]["clients"], b["a1"]["descendant_o"], b["a1"]["simultanes_moy"]), (2, 9_800_000.0, 4.5))
        self.assertEqual((b["a2"]["clients"], b["a2"]["debit_mbps"]), (0, 0.0))          # borne sans client listée
        self.assertEqual(b["a1"]["debit_mbps"], round(11_000_000 * 8 / 7200 / 1e6, 3))
        s = {x["ssid"]: x for x in r["ssids"]}
        self.assertEqual((s["Général"]["clients"], s["Général"]["vlan"], s["Invités"]["montant_o"]), (1, 10, 200000.0))
        v = {x["vlan"]: x for x in r["vlans"]}
        self.assertEqual((v[51]["clients"], v[51]["filaires"]), (2, 1))
        self.assertEqual((v[10]["clients"], v[10]["ssids"], v[10]["wifi_descendant_o"]), (1, ["Général"], 9_800_000.0))
        self.assertEqual(r["commutateurs"][0]["debit_mbps"], 4.0)                         # 3,6 Go en 2 h = 4 Mbit/s
        self.assertEqual(r["passerelles"][0]["erreur"], "HTTP 404")
        self.assertEqual(r["total"]["clients_wifi"], 2)

    def test_occupation(self):
        o = charge.occupation([("a1", 100, 4), ("a1", 200, 6), ("a1", 50, 40), ("a2", 300, 0)], 90)
        self.assertEqual(o, {"a1": {"moyenne": 5.0, "max": 6, "releves": 2}, "a2": {"moyenne": 0.0, "max": 0, "releves": 1}})


if __name__ == "__main__":
    unittest.main()
