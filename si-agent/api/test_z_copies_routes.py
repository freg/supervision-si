# -*- coding: utf-8 -*-
"""#856 : routes /copies/* et /migration/risques, /migration/acces -- relevés simulés."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ["ACCES_THREAD"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import test_z_copies as TC  # noqa: E402

PRE = [("ag1", "deb13", "2026-10-26T10:00:00", {"nodes": [{"name": "pve-2", "quorum": {"quorate": True},
                                                            "guests": [{"vmid": 100, "status": "running", "name": "THD85", "conf": {"ips": ["198.51.100.7"]}}]}]})]


class Routes(unittest.TestCase):
    def setUp(self):
        self.avant = appmod.infra.latest
        appmod.infra.latest = lambda conn, t: TC.REP if t == "plugin:copies-inventory" else PRE if t == "plugin:pve-preflight" else []
        self.c = appmod.app.test_client()

    def tearDown(self):
        appmod.infra.latest = self.avant

    def test_inventaire_et_regles(self):
        r = self.c.get("/copies/inventaire").get_json()
        self.assertTrue(any(i["key"] == "pve-3/101" for i in r["invites"]))
        self.assertEqual(self.c.put("/copies/regles", json={"regles": {"origines": []}}).status_code, 400)
        self.assertEqual(self.c.put("/copies/regles", json={"regles": {"dans": {"pbs10": "pve10"}}}).get_json()["regles"]["dans"], {"pbs10": "pve10"})
        self.assertEqual(self.c.get("/copies/inventaire").get_json()["regles"]["dans"], {"pbs10": "pve10"})

    def test_risques_et_acces(self):
        self.assertEqual(self.c.put("/migration/acces", json={"key": "pve-2/100", "cibles": ["pas une cible !"]}).status_code, 400)
        self.assertEqual(self.c.put("/migration/acces", json={"key": "pve-2/100", "cibles": ["https://thd.exemple.fr/", "198.51.100.7:22"]}).status_code, 200)
        self.c.put("/migration/cible", json={"cible": "pve-3"})
        r = self.c.get("/migration/risques").get_json()
        self.assertEqual(r["cible"], "pve-3")
        self.assertEqual(r["manuels"]["pve-2/100"], ["https://thd.exemple.fr/", "198.51.100.7:22"])
        self.assertTrue(r["lignes"])
        self.assertEqual(r["lignes"][0]["niveau"], "critique")

    def test_sans_releve(self):
        appmod.infra.latest = lambda conn, t: []
        r = self.c.get("/copies/inventaire").get_json()
        self.assertIn("copies-inventory", r["error"])
        self.assertTrue(r["manuel"].startswith("pas de lien : opération manuelle"))


if __name__ == "__main__":
    unittest.main()
