# -*- coding: utf-8 -*-
"""#851 : route de charge (client Nebula simulé, sources partielles tolérées) et appareils névralgiques."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))
TMP = tempfile.mkdtemp()
os.environ["NEBULA_DB_PATH"] = os.path.join(TMP, "nebula.db")
os.environ["NEBULA_POLL_DISABLED"] = "1"
os.environ["NEBULA_API_KEY"] = "x"
import app as app_mod  # noqa: E402
import nebula_client  # noqa: E402

S = "s" * 16


class Fake:
    def list_organizations(self): return [{"orgId": "o" * 16, "mode": "PRO"}]
    def list_sites(self, org): return [{"siteId": S, "name": "Site test"}]
    def list_devices_from_org(self, org): return [{"siteId": S, "devices": [{"devId": "a1", "name": "Borne 1", "type": "AP"}, {"devId": "s1", "name": "Coeur", "type": "SW"}, {"devId": "g1", "name": "USG", "type": "FIREWALL"}]}]
    def ap_clients_v2(self, site, period): return {"data": [{"mac_address": "02:00:5e:00:00:01", "connected_device_id": "a1", "ssid": "Campus", "upload": 100, "download": 900}]}
    def get_site_clients(self, site, features=None, period="2h"): return [{"mac_address": "02:00:5e:00:00:02", "vlan": 51}]
    def sw_clients(self, site, period="1d"): raise nebula_client.NebulaError("clients des commutateurs indisponibles")
    def sw_traffic_usage(self, site, dev, period): return {"devId": dev, "uplinkTxUsage": 1000, "uplinkRxUage": 2000}
    def gw_traffic_usage(self, site, dev, period): raise nebula_client.NebulaError("HTTP 404")


class Route(unittest.TestCase):
    def test_charge_et_nevralgiques(self):
        fake = Fake()
        app_mod._connect = lambda: fake
        app_mod._vlan_map_cached = lambda sid, refresh=False: {"vlans": [{"vid": 10, "ssids": [{"name": "Campus"}]}]}
        c = app_mod.app.test_client()
        self.assertEqual(c.get("/sites/%s/charge?period=1h" % S).status_code, 400)
        r = c.get("/sites/%s/charge?period=2h" % S).get_json()
        self.assertEqual((r["bornes"][0]["clients"], r["ssids"][0]["vlan"], r["commutateurs"][0]["descendant_o"]), (1, 10, 2000.0))
        self.assertIn("non disponible", r["passerelles"][0]["erreur"])
        self.assertEqual(len(r["erreurs"]), 1)                                     # clients des commutateurs
        self.assertEqual({v["vlan"] for v in r["vlans"]}, {10, 51})
        self.assertEqual(c.put("/sites/%s/nevralgiques" % S, json={"mac": "x"}).status_code, 400)
        d = c.put("/sites/%s/nevralgiques" % S, json={"mac": "02-00-5E-00-00-07", "nom": "led-ctrl", "raison": "pilote 4 écrans"}).get_json()
        self.assertEqual(d["nevralgiques"]["02:00:5e:00:00:07"]["nom"], "led-ctrl")
        self.assertEqual(len(c.get("/sites/%s/nevralgiques" % S).get_json()["nevralgiques"]), 1)
        c.put("/sites/%s/nevralgiques" % S, json={"mac": "02:00:5e:00:00:07", "nevralgique": False})
        self.assertEqual(c.get("/sites/%s/nevralgiques" % S).get_json()["nevralgiques"], {})


if __name__ == "__main__":
    unittest.main()
