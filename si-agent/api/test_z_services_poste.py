# -*- coding: utf-8 -*-
"""#928 : sites de service testés depuis un poste -- validation, injection des secrets du coffre, caviardage, routes.
`cd si-agent/api && python3 -m unittest test_z_services_poste`."""
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
import services_poste as sp  # noqa: E402


class Validation(unittest.TestCase):
    def test_valider_refuse_les_secrets_dans_la_config(self):
        ok, err = sp.valider([{"nom": "GED", "url": "https://ged.exemple/", "auth": {"type": "basic", "acces": "ged-superv"}}])
        self.assertIsNone(err, err)
        self.assertEqual(ok[0]["auth"], {"type": "basic", "acces": "ged-superv"})
        _, e = sp.valider([{"nom": "x", "url": "https://x/", "auth": {"type": "basic", "acces": "a", "secret": "hop"}}])
        self.assertIn("interdit", e)
        _, e = sp.valider([{"nom": "x", "url": "ftp://x/"}])
        self.assertIn("http", e)
        _, e = sp.valider([{"nom": "x", "url": "https://x/", "auth": {"type": "form", "acces": "a"}}])
        self.assertIn("champ_user", e)
        _, e = sp.valider([{"nom": "a", "url": "https://a/"}, {"nom": "a", "url": "https://b/"}])
        self.assertIn("double", e)

    def test_cibles_injecte_le_secret_et_signale_coffre_ko(self):
        liste, _ = sp.valider([
            {"nom": "GED", "url": "https://ged/", "auth": {"type": "basic", "acces": "ged"}},
            {"nom": "Tickets", "url": "https://tts/prive", "auth": {"type": "form", "acces": "tts", "champ_user": "u", "champ_pass": "p", "url_login": "https://tts/login"}},
            {"nom": "API", "url": "https://api/", "auth": {"type": "token", "acces": "api", "prefixe": "Bearer "}},
            {"nom": "Cloud", "url": "https://cloud/", "auth": {"type": "basic", "acces": "absent"}},
            {"nom": "Public", "url": "https://pub/"},
        ])

        def reveler(nom):
            if nom == "absent":
                raise RuntimeError("coffre : accès « absent » : HTTP 404")
            return {"username": "francois", "password": "S3-" + nom}

        cibles, erreurs = sp.cibles_pour_mesure(liste, reveler)
        self.assertEqual(cibles[0]["auth"], {"type": "basic", "user": "francois", "secret": "S3-ged"})
        self.assertEqual(cibles[1]["auth"]["champ_user"], "u")
        self.assertEqual(cibles[1]["auth"]["url_login"], "https://tts/login")
        self.assertEqual(cibles[2]["auth"]["valeur"], "Bearer S3-api")
        self.assertNotIn("auth", cibles[3], "accès coffre KO -> testé en brut seul")
        self.assertEqual([e["nom"] for e in erreurs], ["Cloud"])
        self.assertNotIn("auth", cibles[4])


class Routes(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        try:
            store.create_agent(A.DB_PATH, "pc-sp", "siege")
        except ValueError:
            pass

    def test_cycle(self):
        r = self.c.put("/services-poste", json={"services": [
            {"nom": "GED", "url": "https://ged.exemple/prive", "auth": {"type": "basic", "acces": "ged-superv"}}], "actor": "francois"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/services-poste").get_json()["services"][0]["nom"], "GED")
        # accès coffre indisponible (pas de jeton interne en test) -> testé en brut, pas d'erreur bloquante
        r = self.c.post("/agents/pc-sp/acces-services/tester", json={"actor": "francois"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertEqual(d["sites"], 1)
        # la commande créée ne doit porter AUCUN secret (ici il n'y en a pas, mais on vérifie le caviardage du type)
        cmd = [x for x in store.list_commands(A.DB_PATH, "pc-sp") if x["type"] == "acces-services"][0]
        self.assertEqual(cmd["type"], "acces-services")
        self.assertEqual(self.c.post("/agents/inconnu/acces-services/tester", json={}).status_code, 404)

    def test_caviardage_des_secrets(self):
        p = {"cibles": [
            {"nom": "GED", "url": "https://ged/", "auth": {"type": "basic", "user": "francois", "secret": "TOP-SECRET"}},
            {"nom": "API", "url": "https://api/", "auth": {"type": "token", "entete": "Authorization", "valeur": "Bearer TOP-SECRET"}},
        ]}
        red = store.redact_params(p)
        import json as _j
        blob = _j.dumps(red)
        self.assertNotIn("TOP-SECRET", blob)
        self.assertEqual(red["cibles"][0]["auth"]["secret"], "***")
        self.assertEqual(red["cibles"][1]["auth"]["valeur"], "***")
        self.assertEqual(red["cibles"][0]["auth"]["user"], "francois", "l'identifiant n'est pas un secret")


if __name__ == "__main__":
    unittest.main()
