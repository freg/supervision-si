# -*- coding: utf-8 -*-
"""Tests #872 : historique des clients Nebula (fusion des trois sources, sessions, requête filtrée/triée, purge)."""
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import client_history as ch  # noqa: E402

H = 3600
T0 = 1_791_000_000      # instant fixe
GW = "02:00:00:aa:bb:01"


def releve(conn, now, gw_ip="192.0.2.50", gw=True, port="7"):
    clients = [{"macAddress": "02-00-00-AA-BB-02", "ipv4Address": "192.0.2.60", "manufacturer": "Exemple Phone", "lastSeen": now * 1000}]
    sw = []
    if gw:
        clients.append({"mac_address": GW.upper(), "ipv4": gw_ip, "manufacturer": "Multi-Tech Systems", "description": "passerelle-lora", "last_seen": now - 60})
        sw.append({"mac_address": GW, "connected_device_id": "SW1", "connected_port": port, "vlan": 20})
    ap = [{"mac_address": "020000aabb02", "connected_device_id": "AP1", "ssid": "wifi-general", "vlan": 10}]
    return ch.ingest(conn, "site-alpha", ch.merge(clients, ap, sw, {"SW1": "sw-batiment-5", "AP1": "borne-hall"}, now=now), now=now)


class ClientHistory(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")

    def test_fusion_sources(self):
        f = ch.merge([{"macAddress": "02:00:00:AA:BB:01", "ipv4Address": "192.0.2.50"}], [],
                     [{"mac_address": "020000aabb01", "connected_device_id": "SW1", "connected_port": 3}], {"SW1": "sw1"}, now=T0)
        self.assertEqual(list(f), [GW])
        self.assertEqual((f[GW]["ip"], f[GW]["device"], f[GW]["port"], f[GW]["sources"]), ("192.0.2.50", "sw1", "3", "clients,commutateurs"))
        self.assertEqual(ch.merge([{"mac": "pas une mac"}], now=T0), {})

    def test_sessions_et_disparition(self):
        for k in range(5):                      # 5 relèves horaires : une seule session
            releve(self.c, T0 + k * H)
        for k in range(5, 30):                  # la passerelle disparaît ensuite
            releve(self.c, T0 + k * H, gw=False)
        s = ch.sessions(self.c, "site-alpha", GW)
        self.assertEqual(len(s), 1)
        self.assertEqual((s[0]["device"], s[0]["port"], s[0]["ip"]), ("sw-batiment-5", "7", "192.0.2.50"))
        r = ch.query(self.c, site_id="site-alpha", absent_since=T0 + 10 * H)
        self.assertEqual([x["mac"] for x in r["rows"]], [GW])                  # « plus vue depuis »
        self.assertEqual(r["rows"][0]["seen_count"], 5)

    def test_changement_de_raccordement_nouvelle_session(self):
        releve(self.c, T0)
        releve(self.c, T0 + H, port="9")
        releve(self.c, T0 + 2 * H, gw_ip="192.0.2.51", port="9")
        self.assertEqual([x["port"] for x in ch.sessions(self.c, "site-alpha", GW)], ["9", "9", "7"])
        self.assertEqual(ch.query(self.c, q="passerelle")["rows"][0]["ip"], "192.0.2.51")

    def test_trou_long_nouvelle_session(self):
        releve(self.c, T0)
        releve(self.c, T0 + 10 * H)
        self.assertEqual(len(ch.sessions(self.c, "site-alpha", GW)), 2)

    def test_requete_filtres_tri(self):
        releve(self.c, T0)
        self.assertEqual(ch.query(self.c, q="aabb01")["total"], 1)                # MAC sans séparateurs
        self.assertEqual(ch.query(self.c, q="AA-BB-01")["total"], 1)
        self.assertEqual(ch.query(self.c, manufacturer="multi")["rows"][0]["mac"], GW)
        self.assertEqual(ch.query(self.c, device="batiment")["total"], 1)
        self.assertEqual([x["mac"] for x in ch.query(self.c, sort="manufacturer", order="asc")["rows"]], ["02:00:00:aa:bb:02", GW])
        self.assertEqual(ch.query(self.c, since=T0 + 5 * H)["total"], 0)
        self.assertEqual(ch.query(self.c, since=T0 - H, until=T0 + H)["total"], 2)
        self.assertEqual(ch.query(self.c, sort="'; DROP TABLE x; --")["total"], 2)   # tri inconnu -> défaut, jamais injecté
        self.assertEqual(ch.manufacturers(self.c)[0]["n"], 1)

    def test_debut_de_mot_d_abord(self):
        releve(self.c, T0)
        ch.ingest(self.c, "site-alpha", ch.merge([{"macAddress": "02:00:00:aa:bb:09", "description": "ma-passerelle"}], now=T0), now=T0)
        self.assertEqual(ch.query(self.c, q="passerelle")["rows"][0]["name"], "passerelle-lora")

    def test_purge(self):
        releve(self.c, T0)
        self.assertGreater(ch.purge(self.c, now=T0 + 500 * 86400), 0)
        self.assertEqual(ch.query(self.c)["total"], 0)


if __name__ == "__main__":
    unittest.main()
