# -*- coding: utf-8 -*-
"""#799/#800 : parcours appris -- validation, paramètres, coffre, jeu (commande navigateur, masquage), interprétation."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import parcours as P  # noqa: E402
import store  # noqa: E402

TICKET = {"nom": "Ticket de maintenance GMAO", "description": "Crée un ticket de maintenance dans la GMAO pour un site client",
          "navigateur": "ovh1", "base_url": "https://gmao.example.org/", "acces": "gmao-test",
          "etapes": [{"action": "goto", "value": "/connexion"},
                     {"action": "fill", "selector": "#login", "value": "{{identifiant}}"},
                     {"action": "fill", "selector": "#pwd", "value": "{{mot_de_passe}}", "secret": True},
                     {"action": "press", "selector": "#pwd", "value": "Enter"},
                     {"action": "select", "selector": "#site", "value": "{{site}}", "note": "Site"},
                     {"action": "fill", "selector": "#objet", "value": "{{objet}}", "note": "Objet"},
                     {"action": "click", "selector": "#creer", "ecrit": True, "note": "Créer le ticket"}],
          "parametres": [{"nom": "identifiant", "defaut": "alice"}, {"nom": "mot_de_passe", "defaut": "fuite", "secret": True},
                         {"nom": "site", "note": "site client", "defaut": "alpha"}, {"nom": "objet", "note": "objet du ticket"}]}


class Pur(unittest.TestCase):
    def test_valider(self):
        p, err = P.valider(TICKET)
        self.assertIsNone(err)
        self.assertEqual(p["base_url"], "https://gmao.example.org")
        mdp = next(x for x in p["parametres"] if x["nom"] == "mot_de_passe")
        self.assertEqual((mdp["secret"], mdp["defaut"]), (True, ""))                    # jamais de mot de passe stocké
        p2, _ = P.valider(dict(TICKET, parametres=[]))
        self.assertEqual({x["nom"] for x in p2["parametres"]}, {"identifiant", "mot_de_passe", "site", "objet"})
        for bad, msg in ((dict(TICKET, nom=""), "nom"), (dict(TICKET, base_url="ftp://x"), "base"), (dict(TICKET, etapes=[{"action": "exec"}]), "étape 1"),
                         (dict(TICKET, navigateur="OVH 1"), "navigateur"), (dict(TICKET, parametres=[{"nom": "Mot de passe"}]), "paramètre")):
            self.assertIn(msg, P.valider(bad)[1])

    def test_appliquer_et_catalogue(self):
        p, _ = P.valider(TICKET)
        et, manq = P.appliquer(p, {"objet": "Chauffage en panne"}, {"username": "bob", "password": "S3cret"})
        self.assertEqual(manq, [])
        self.assertEqual([e.get("value") for e in et][1:3], ["bob", "S3cret"])
        self.assertTrue(et[2]["secret"])
        self.assertEqual(et[4]["value"], "alpha")
        _et, manq = P.appliquer(p, {}, None)
        self.assertEqual(manq, ["mot_de_passe", "objet"])
        cat = P.catalogue([dict(p, id=7)])
        self.assertEqual([x["nom"] for x in cat[0]["parametres"]], ["site", "objet"])  # le modèle ne voit ni identifiant ni mot de passe
        plan = P.plan_depuis_interpretation([dict(p, id=7)], {"parcours_id": "7", "valeurs": {"objet": "Chauffage", "site": "beta", "mot_de_passe": "x"}, "confiance": 0.9})
        self.assertEqual((plan["ok"], plan["valeurs"], plan["manquants"], plan["ecrit"]), (True, {"objet": "Chauffage", "site": "beta"}, [], True))
        self.assertFalse(P.plan_depuis_interpretation([dict(p, id=7)], {"parcours_id": None, "explication": "rien"})["ok"])
        self.assertFalse(P.plan_depuis_interpretation([dict(p, id=7)], {"parcours_id": 99})["ok"])
        self.assertEqual(store.redact_params({"etapes": et})["etapes"][2]["value"], "***")


class Routes(unittest.TestCase):
    def setUp(self):
        self.c = appmod.app.test_client()
        store.create_agent(appmod.DB_PATH, "par-ovh", "ovh", label="par-ovh") if not any(a["agent_id"] == "par-ovh" for a in store.list_agents(appmod.DB_PATH)) else None
        store.set_setting(appmod.DB_PATH, "navigateurs", [{"nom": "ovh1", "agent_id": "par-ovh", "libelle": "OVH", "accueil": ""}])
        self.orig = (appmod.reveler_acces, appmod.interpreter_demande)
        appmod.reveler_acces = lambda nom: {"username": "bob", "password": "S3cret"}
        appmod.interpreter_demande = lambda texte, cat: {"parsed": {"parcours_id": cat[0]["id"], "valeurs": {"objet": "Chauffage en panne", "site": "beta"},
                                                                    "confiance": 0.8, "explication": "ticket de maintenance"}, "model": "qwen3:14b"}

    def tearDown(self):
        appmod.reveler_acces, appmod.interpreter_demande = self.orig

    def test_parcours_complet(self):
        r = self.c.post("/parcours", json={"parcours": TICKET, "actor": "freg"})
        self.assertEqual(r.status_code, 201)
        pid = r.get_json()["parcours"]["id"]
        self.assertEqual(self.c.post("/parcours", json={"parcours": TICKET}).status_code, 400)   # nom en double
        plan = self.c.post("/parcours/interpreter", json={"texte": "ouvre la GMAO et crée un ticket chauffage chez beta"}).get_json()
        self.assertEqual((plan["parcours_id"], plan["valeurs"]["site"], plan["modele"]), (pid, "beta", "qwen3:14b"))
        self.assertEqual(self.c.post(f"/parcours/{pid}/jouer", json={}).status_code, 400)            # objet manquant
        r = self.c.post(f"/parcours/{pid}/jouer", json={"valeurs": plan["valeurs"], "actor": "freg"})
        self.assertEqual(r.status_code, 201)
        j = r.get_json()
        self.assertTrue(j["arret_avant_ecriture"])
        cmd = self.c.get("/commands/" + j["commande"]).get_json()
        self.assertEqual(cmd["type"], "navigateur")
        pwd = [e for e in cmd["params"]["etapes"] if e.get("selector") == "#pwd"][0]
        self.assertEqual(pwd["value"], "***")                                                     # jamais renvoyé au hub
        self.assertTrue(self.c.post(f"/parcours/{pid}/jouer", json={"valeurs": plan["valeurs"], "confirmer": True}).get_json()["arret_avant_ecriture"] is False)
        self.assertEqual(self.c.get("/parcours").get_json()["parcours"][0]["jeux"], 2)
        self.assertEqual(self.c.post(f"/parcours/{pid}/jouer", json={"navigateur": "absent", "valeurs": plan["valeurs"]}).status_code, 400)
        self.assertEqual(self.c.delete(f"/parcours/{pid}").get_json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()
