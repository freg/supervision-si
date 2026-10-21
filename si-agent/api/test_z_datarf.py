# -*- coding: utf-8 -*-
"""#806 : assemblage de la tuile « Data RF » (collecte d'un site + sondes directes)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datarf  # noqa: E402

RF = {"canaux": [{"canal": 36, "occupation_pct": 61.0}], "alerts": [{"code": "spectre-occupe:36", "severity": "warning", "message": "canal 36 occupé"}]}


class Assemblage(unittest.TestCase):
    def test_collecte_et_directes(self):
        collectes = [("mini-pc", "minipc", "2026-10-21T15:00:00Z", {"sondes": [{"sonde": "sonde-3b", "rf_spectrum": RF, "rf_spectrum_at": "2026-10-21T14:59:00Z"}, "x"],
                                                                     "alerts": [{"code": "sonde-3b:spectre-occupe:36", "severity": "warning", "message": "sonde-3b : canal 36 occupé"}]})]
        directes = {"plugin:wifi-monitor": [("sonde-zero", "sonde-zero", "2026-10-21T15:01:00Z", {"canaux": [], "alerts": [{"code": "monitor-absente", "severity": "warning", "message": "carte absente"}]})],
                    "plugin:rf-spectrum": [("sonde-3b-ancien", "SONDE-3B", "2026-10-20T10:00:00Z", {"canaux": []})]}
        r = datarf.assembler(collectes, directes)
        self.assertEqual([s["sonde"] for s in r["sondes"]], ["sonde-3b", "sonde-zero"])
        s3 = r["sondes"][0]
        self.assertEqual((s3["via"], s3["rf_spectrum"]), ("minipc", RF))      # mesure directe plus ancienne : ignorée
        self.assertEqual(r["sondes"][1]["via"], None)
        self.assertEqual([c["message"] for c in r["constats"]], ["sonde-3b : canal 36 occupé", "sonde-zero : carte absente"])
        self.assertEqual(datarf.assembler([], {}), {"sondes": [], "constats": []})
        r = datarf.assembler([], {"plugin:wifi-probe": [("i9", "i9freg", "2026-10-21T15:00:00Z", {"link": {}})]})
        self.assertEqual(r["sondes"], [])                                       # poste avec wifi-probe seulement : pas une sonde radio


class Configuration(unittest.TestCase):   # #807
    def test_cles_du_coffre(self):
        coffre = {"wifi-campus": {"password": "clecampus1"}, "vide": {}}

        def reveler(n):
            if n not in coffre:
                raise RuntimeError("coffre : accès « %s » : HTTP 404" % n)
            return coffre[n]
        p, memo, err = datarf.preparer_config({"interfaces": {"wlan0": "client", "alfa0": "moniteur", "x": "pirate"},
                                               "ssids": [{"ssid": " Campus ", "acces": "wifi-campus", "actif": True}, {"ssid": "Invites", "actif": True},
                                                         {"ssid": "Ancien", "acces": "inconnu", "actif": False}, {"ssid": ""}]}, reveler)
        self.assertIsNone(err)
        self.assertEqual(p["interfaces"], {"wlan0": "client", "alfa0": "moniteur"})
        self.assertEqual([(s["ssid"], s["psk"]) for s in p["ssids"]], [("Campus", "clecampus1"), ("Invites", ""), ("Ancien", "")])   # désactivé : coffre non lu
        self.assertNotIn("clecampus1", str(memo))
        self.assertEqual(memo["ssids"][0]["acces"], "wifi-campus")
        self.assertIn("HTTP 404", datarf.preparer_config({"ssids": [{"ssid": "A", "acces": "inconnu"}]}, reveler)[2])
        self.assertIn("pas de mot de passe", datarf.preparer_config({"ssids": [{"ssid": "A", "acces": "vide"}]}, reveler)[2])
        self.assertEqual(datarf.commande("sonde-3b", "optline1", None, p)[:2], ("optline1", "collecteur"))
        self.assertEqual(datarf.commande("sonde-3b", None, "sonde-3b", p), ("sonde-3b", "wifi_config", p))
        import app  # noqa: F401 -- prépare les modules du central
        import store
        r = store.redact_params(datarf.commande("sonde-3b", "optline1", None, p)[2])
        self.assertNotIn("clecampus1", str(r))


class Routes(unittest.TestCase):   # #807
    def test_config_par_le_collecteur(self):
        import app as appmod
        import store
        aid = "optline1"
        store.create_agent(appmod.DB_PATH, aid, "campus")
        appmod.reveler_acces = lambda n: {"password": "clecampus1"}
        cl = appmod.app.test_client()
        r = cl.post("/datarf/config", json={"sonde": "sonde-3b", "via_agent": aid, "interfaces": {"wlan0": "client"},
                                            "ssids": [{"ssid": "Campus", "acces": "wifi-campus", "actif": True}], "actor": "alice"})
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertNotIn("clecampus1", r.get_data(as_text=True))
        cmds = cl.get("/agents/%s/commands" % aid).get_data(as_text=True)
        self.assertIn("collecteur", cmds)
        self.assertNotIn("clecampus1", cmds)
        self.assertEqual(cl.get("/datarf/config?sonde=sonde-3b").get_json()["config"]["ssids"][0]["acces"], "wifi-campus")
        self.assertEqual(cl.post("/datarf/config", json={"sonde": "sonde-3b"}).status_code, 400)
        self.assertEqual(cl.post("/datarf/config", json={"sonde": "sonde-3b", "via_agent": "inconnu", "action": "etat"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
