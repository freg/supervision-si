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


class PBS(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        for a in ("pbs10", "pc-paul2"):
            try:
                store.create_agent(A.DB_PATH, a, "siege")
            except ValueError:
                pass

    def test_reglage_sans_secret(self):
        r = self.c.put("/postes-sauvegarde-pbs", json={"pousseur": "pbs10", "repository": "u@pbs!t@pbs10:backup",
                        "namespace": "postes", "fingerprint": "AB:CD", "acces": "pbs-token", "base_partage": "/mnt/share/sauvegardes", "actor": "francois"})
        self.assertEqual(r.status_code, 200)
        g = self.c.get("/postes-sauvegarde-pbs").get_json()["reglage"]
        self.assertEqual(g["pousseur"], "pbs10")
        self.assertEqual(g["namespace"], "postes")
        import json as _j
        self.assertNotIn("secret", _j.dumps(g).lower())

    def test_push_utilise_la_derniere_archive(self):
        self.c.put("/postes-sauvegarde-pbs", json={"pousseur": "pbs10", "repository": "u@pbs!t@pbs10:backup",
                   "namespace": "postes", "base_partage": "/mnt/share/sauvegardes"})
        # pas d'archive -> refus
        self.assertEqual(self.c.post("/agents/pc-paul2/sauvegarde/pbs", json={"action": "push"}).status_code, 400)
        store.ingest_measurements(A.DB_PATH, "pc-paul2", [{"task": "sauvegarde-poste", "at": "2026-10-30T11:00:00Z", "agent_id": "pc-paul2",
            "data": {"archive": {"nom": "sauvegarde-pc-paul2-20261030.zip", "octets": 1000}, "destinations": [{"type": "unc", "ok": True}]}}])
        r = self.c.post("/agents/pc-paul2/sauvegarde/pbs", json={"action": "push", "actor": "francois"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["archive"], "sauvegarde-pc-paul2-20261030.zip")
        cmd = [x for x in store.list_commands(A.DB_PATH, "pbs10") if x["type"] == "pbs-push" and (x.get("params") or {}).get("action") == "push"][0]
        self.assertEqual(cmd["params"]["backup_id"], "pc-paul2")
        self.assertEqual(cmd["params"]["fichier"], "/mnt/share/sauvegardes/sauvegarde-pc-paul2-20261030.zip")
        self.assertEqual(cmd["params"]["namespace"], "postes")

    def test_preflight_et_non_configure(self):
        store.set_setting(A.DB_PATH, "postes-sauvegarde-pbs", {})
        self.assertEqual(self.c.post("/agents/pc-paul2/sauvegarde/pbs", json={"action": "preflight"}).status_code, 400)
        self.c.put("/postes-sauvegarde-pbs", json={"pousseur": "pbs10", "repository": "u@pbs!t@pbs10:backup", "namespace": "postes"})
        r = self.c.post("/agents/pc-paul2/sauvegarde/pbs", json={"action": "preflight"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["action"], "preflight")
        cmd = [x for x in store.list_commands(A.DB_PATH, "pbs10") if x["type"] == "pbs-push" and (x.get("params") or {}).get("action") == "preflight"][0]
        self.assertEqual(cmd["params"]["action"], "preflight")

    def test_caviardage_token(self):
        red = store.redact_params({"repository": "u@pbs!t@h:backup", "token_secret": "TOPSECRET", "backup_id": "x"})
        import json as _j
        self.assertNotIn("TOPSECRET", _j.dumps(red))
        self.assertEqual(red["token_secret"], "***")


class Restauration(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        for a, rs in (("pc-r-off", "off"), ("pc-r-lec", "lecture"), ("pc-r-int", "intervention")):
            try:
                store.create_agent(A.DB_PATH, a, "siege")
            except ValueError:
                pass
            store.update_agent(A.DB_PATH, a, remote_shell=rs)

    def test_gate(self):
        src = {"source": {"chemin": "E:\\sauvegarde-pc.zip"}}
        self.assertEqual(self.c.post("/agents/pc-r-off/restauration/lancer", json={"mode": "simulation", **src}).status_code, 403)
        # lecture : simulation OK, appliquer refusé
        self.assertEqual(self.c.post("/agents/pc-r-lec/restauration/lancer", json={"mode": "simulation", **src}).status_code, 200)
        self.assertEqual(self.c.post("/agents/pc-r-lec/restauration/lancer", json={"mode": "appliquer", **src}).status_code, 403)
        # intervention : appliquer OK
        r = self.c.post("/agents/pc-r-int/restauration/lancer", json={"mode": "appliquer", "options": {"registre": True, "appdata": False, "montages": True}, **src})
        self.assertEqual(r.status_code, 200)
        cmd = [x for x in store.list_commands(A.DB_PATH, "pc-r-int") if x["type"] == "restauration-poste"][0]
        self.assertEqual(cmd["params"]["mode"], "appliquer")
        self.assertEqual(cmd["params"]["source"]["chemin"], "E:\\sauvegarde-pc.zip")

    def test_sans_chemin(self):
        self.assertEqual(self.c.post("/agents/pc-r-int/restauration/lancer", json={"mode": "simulation", "source": {}}).status_code, 400)

    def test_caviardage_source(self):
        red = store.redact_params({"source": {"chemin": "\\\\nas\\bk.zip", "unc": {"user": "u", "secret": "TOP-SECRET"}}, "mode": "appliquer"})
        import json as _j
        self.assertNotIn("TOP-SECRET", _j.dumps(red))
        self.assertEqual(red["source"]["unc"]["secret"], "***")
