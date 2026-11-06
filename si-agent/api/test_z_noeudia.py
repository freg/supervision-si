# -*- coding: utf-8 -*-
"""#996 : nœuds IA déployés depuis le hub -- archive, jeton, commande gardée par « intervention », routes signées."""
import io
import os
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import noeudia as N  # noqa: E402


def archive(fichiers, prefixe="hermes-web/"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for nom, contenu in fichiers.items():
            data = contenu.encode("utf-8")
            ti = tarfile.TarInfo(prefixe + nom)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


KIT = {"hermes_web/__init__.py": '__version__ = "0.29.0"\n', "deploy/noeud/compose.yml": "services: {}\n"}


class Pur(unittest.TestCase):
    def test_jeton(self):
        j = N.jeton("s3cr3t", "prodia")
        self.assertEqual(len(j), 48); self.assertEqual(j, N.jeton("s3cr3t", "prodia"))
        self.assertNotEqual(j, N.jeton("s3cr3t", "preprodia")); self.assertNotEqual(j, N.jeton("autre", "prodia"))
        self.assertIsNone(N.jeton("", "prodia")); self.assertIsNone(N.jeton("s", "../x"))

    def test_analyser_kit(self):
        m, e = N.analyser_kit(archive(KIT))
        self.assertIsNone(e); self.assertEqual(m["version"], "0.29.0"); self.assertEqual(len(m["sha256"]), 64)
        self.assertIn("0.29", N.analyser_kit(archive({"hermes_web/__init__.py": '__version__ = "0.28.0"\n'}))[1])
        self.assertIn("hermes_web", N.analyser_kit(archive({"x.txt": "y"}))[1])
        self.assertIn("illisible", N.analyser_kit(b"pas une archive")[1])
        self.assertIn("vide", N.analyser_kit(b"")[1])

    def test_valider_demande(self):
        self.assertEqual(N.valider_demande({"action": "etat"}), ({"action": "etat", "port": 8092}, None))
        p, e = N.valider_demande({"action": "deployer", "nom": "prodia", "port": "8093"})
        self.assertEqual(p, {"action": "deployer", "nom": "prodia", "port": 8093, "modele": "qwen3:4b"})
        for b in ({"action": "x"}, {"action": "deployer", "nom": "Pro"}, {"action": "deployer", "nom": "p", "port": 22},
                  {"action": "deployer", "nom": "p", "modele": "a;b"}):
            self.assertIsNotNone(N.valider_demande(b)[1], b)


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_si_agent_api as T
        cls.T = T
        os.environ["IA_NOEUDS_SECRET"] = "s3cr3t-de-test"
        T.app_mod.NOEUD_IA_DIR = tempfile.mkdtemp()

    def setUp(self):
        self.base = self.T.ApiBase("setUp")
        self.T.ApiBase.setUp(self.base)
        self.c = self.base.c

    def test_parcours(self):
        T, c = self.T, self.c
        a = self.base.enroll("prodia-ia")
        sec = a["secret"]
        # sans archive / sans intervention
        self.assertEqual(c.post("/agents/prodia-ia/noeud-ia", json={"action": "deployer", "nom": "prodia"}).status_code, 403)
        self.assertEqual(c.put("/agents/prodia-ia", json={"remote_shell": "intervention"}).status_code, 200)
        r = c.post("/agents/prodia-ia/noeud-ia", json={"action": "deployer", "nom": "prodia"})
        self.assertEqual(r.status_code, 409, r.get_json()); self.assertIn("archive", r.get_json()["error"])
        # dépôt de l'archive
        self.assertEqual(c.post("/noeud-ia/kit", data={"archive": (io.BytesIO(b"nul"), "x.tar.gz")}, content_type="multipart/form-data").status_code, 400)
        data = archive(KIT)
        r = c.post("/noeud-ia/kit", data={"archive": (io.BytesIO(data), "hermes-web.tar.gz"), "actor": "freg"}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_json()); self.assertEqual(r.get_json()["version"], "0.29.0")
        # jeton refusé tant qu'aucun déploiement n'est demandé
        p = "/api/v1/agents/prodia-ia/noeud-ia/jeton"
        h = T.protocol.auth_headers("prodia-ia", sec, "GET", p, b"")
        self.assertEqual(c.get(p, headers=h).status_code, 404)
        r = c.post("/agents/prodia-ia/noeud-ia", json={"action": "deployer", "nom": "prodia", "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json())
        cmd = T.store.get_command(T.app_mod.DB_PATH, r.get_json()["command"])
        self.assertEqual(cmd["type"], "noeud_ia"); self.assertEqual(cmd["params"]["sha256"], N.analyser_kit(data)[0]["sha256"])
        self.assertNotIn(N.jeton("s3cr3t-de-test", "prodia"), str(cmd))       # jamais le jeton dans la commande
        # routes signées : jeton et archive
        self.assertEqual(c.get(p).status_code, 401)
        h = T.protocol.auth_headers("prodia-ia", sec, "GET", p, b"")
        self.assertEqual(c.get(p, headers=h).get_json(), {"jeton": N.jeton("s3cr3t-de-test", "prodia")})
        pk = "/api/v1/agents/prodia-ia/noeud-ia/kit"
        r = c.get(pk, headers=T.protocol.auth_headers("prodia-ia", sec, "GET", pk, b""))
        self.assertEqual(r.status_code, 200); self.assertEqual(r.get_data(), data)
        # vue d'ensemble
        v = c.get("/noeud-ia").get_json()
        self.assertTrue(v["secret"]); self.assertEqual(v["noeuds"]["prodia-ia"]["nom"], "prodia")
        self.assertEqual(v["etats"]["prodia-ia"]["commande"]["type"], "noeud_ia")


if __name__ == "__main__":
    unittest.main()
