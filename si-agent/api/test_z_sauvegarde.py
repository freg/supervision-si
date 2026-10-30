# -*- coding: utf-8 -*-
"""#930 : sauvegarde des postes -- sélection des confs, montages depuis poste-windows, routes, caviardage.
`cd si-agent/api && python3 -m unittest test_z_sauvegarde`."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
os.environ.setdefault("SI_AGENT_CA_FILE", os.path.join(tempfile.mkdtemp(), "ca.crt"))
sys.path.insert(0, HERE)
import app as A  # noqa: E402
import store  # noqa: E402
import sauvegarde_conf as sc  # noqa: E402


class Selection(unittest.TestCase):
    def test_catalogue_deduit_edite(self):
        base = sc.cibles()
        self.assertIn("Thunderbird", [c["app"] for c in base])
        ded = sc.cibles(logiciels=[{"nom": "CAO X", "editeur": "ACME"}], inclure_catalogue=False, inclure_deduit=True)
        self.assertEqual([c["app"] for c in ded], ["CAO X"])
        self.assertTrue(any(r"HKCU\Software\ACME" in c["cles"] for c in ded))
        edit = [{"app": "Firefox", "cles": [], "dossiers": [r"%APPDATA%\Mozilla\Firefox\Profiles\x"]}]
        fx = next(c for c in sc.cibles(liste_editee=edit) if c["app"] == "Firefox")
        self.assertEqual(fx["dossiers"], [r"%APPDATA%\Mozilla\Firefox\Profiles\x"])

    def test_valider(self):
        _, err = sc.valider([{"app": "X"}])
        self.assertIn("au moins une clé", err)
        _, err = sc.valider([{"cles": ["k"]}])
        self.assertIn("app", err)
        ok, err = sc.valider([{"app": "X", "cles": ["HKCU\\Software\\X"]}])
        self.assertIsNone(err)
        self.assertEqual(ok[0]["app"], "X")

    def test_montages_du_releve(self):
        m = sc.montages_du_releve({"partages": [1], "lecteurs": [1, 2], "imprimantes": [], "logiciels": [1]})
        self.assertEqual((len(m["lecteurs"]), len(m["partages"]), len(m["imprimantes"])), (2, 1, 0))


class Routes(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        try:
            store.create_agent(A.DB_PATH, "pc-bk", "siege")
        except ValueError:
            pass

    def test_reglage_et_lancement(self):
        r = self.c.put("/postes-sauvegarde", json={"confs": [{"app": "AppMaison", "cles": ["HKLM\\SOFTWARE\\AppMaison"], "dossiers": []}],
                                                   "inclure_catalogue": True, "inclure_deduit": True, "actor": "francois"})
        self.assertEqual(r.status_code, 200)
        g = self.c.get("/postes-sauvegarde").get_json()
        self.assertTrue(g["reglage"]["inclure_deduit"])
        self.assertTrue(any(c["app"] == "Thunderbird" for c in g["catalogue"]))
        # relevé poste-windows (montages + logiciels) injecté
        store.ingest_measurements(A.DB_PATH, "pc-bk", [{"task": "plugin:poste-windows", "at": "2026-10-30T10:00:00Z", "agent_id": "pc-bk",
            "data": {"reinstallation": {"partages": [{"nom": "Data", "chemin": "D:\\Data", "acces": []}],
                     "lecteurs": [{"lettre": "Z:", "chemin": "\\\\srv\\p"}], "imprimantes": [],
                     "logiciels": [{"nom": "Super", "editeur": "ACME"}]}}}])
        r = self.c.post("/agents/pc-bk/sauvegarde/lancer", json={"destinations": {"usb": "E:\\bk"}, "actor": "francois"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertGreaterEqual(d["confs"], 2)        # catalogue + AppMaison + déduit ACME
        self.assertEqual(d["montages"], {"lecteurs": 1, "partages": 1, "imprimantes": 0})
        self.assertIsNone(d["note_poste_windows"])
        cmd = [x for x in store.list_commands(A.DB_PATH, "pc-bk") if x["type"] == "sauvegarde-poste"][0]
        self.assertTrue(any(c["app"] == "AppMaison" for c in cmd["params"]["confs"]))
        self.assertEqual(cmd["params"]["montages"]["lecteurs"][0]["lettre"], "Z:")

    def test_sans_destination_et_sans_releve(self):
        store.create_agent(A.DB_PATH, "pc-bk2", "siege")
        self.c.put("/postes-sauvegarde", json={"confs": [], "inclure_catalogue": True})
        r = self.c.post("/agents/pc-bk2/sauvegarde/lancer", json={"actor": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("destination", r.get_json()["error"])
        r = self.c.post("/agents/pc-bk2/sauvegarde/lancer", json={"destinations": {"usb": "E:\\"}})
        self.assertEqual(r.status_code, 200)
        self.assertIn("poste-windows", r.get_json()["note_poste_windows"])   # pas de relevé -> note
        self.assertEqual(r.get_json()["montages"], {"lecteurs": 0, "partages": 0, "imprimantes": 0})

    def test_caviardage_identifiants_partage(self):
        red = store.redact_params({"confs": [], "destinations": {"usb": "E:", "unc": {"chemin": "\\\\nas\\b", "user": "superv", "secret": "TOP-SECRET"}}})
        import json as _j
        self.assertNotIn("TOP-SECRET", _j.dumps(red))
        self.assertEqual(red["destinations"]["unc"]["secret"], "***")
        self.assertEqual(red["destinations"]["unc"]["user"], "superv", "l'identifiant n'est pas un secret")


if __name__ == "__main__":
    unittest.main()
