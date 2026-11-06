# -*- coding: utf-8 -*-
"""#988 : nœuds IA -- noms, groupes, jeton (en-tête ou cookie) et routes /ia/acces, /ia/noeuds de services-api."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ia_noeuds as IA  # noqa: E402


class Pur(unittest.TestCase):
    def test_noeuds(self):
        self.assertEqual(IA.noeuds("prodia=http://192.0.2.10:8092, preprodia=http://si-proxy:6491"), ["prodia", "preprodia"])
        self.assertEqual(IA.noeuds(""), [])
        self.assertEqual(IA.noeuds("Pro dia=x,prodia=y,prodia=z,../x=y"), ["prodia"])

    def test_groupes(self):
        self.assertEqual(IA.groupes(None), ["ia", "administrateurs", "admin_hub"])
        self.assertEqual(IA.groupes("/ia, dev"), ["ia", "dev"])

    def test_jeton(self):
        self.assertEqual(IA.jeton("Bearer abc", {"si_ia_jeton": "zzz"}), "abc")
        self.assertEqual(IA.jeton("", {"si_ia_jeton": "zzz"}), "zzz")
        self.assertEqual(IA.jeton("Basic x", {}), None)
        self.assertEqual(IA.jeton(None, None), None)


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_app as T   # environnement, faux docker et clé de signature du test principal
        cls.T = T
        T.appmod.ia_verifier = T.auth.KeycloakVerifier("u", [], fetch=lambda _u: T.jwks(), allowed_groups=["ia", "administrateurs"], what="les nœuds IA")
        T.appmod.IA_NOEUDS = ["prodia", "preprodia"]
        cls.cl = T.appmod.app.test_client()

    def test_acces(self):
        T = self.T
        self.assertEqual(self.cl.get("/ia/acces").status_code, 401)
        self.assertEqual(self.cl.get("/ia/acces", headers={"Authorization": "Bearer " + T.token("bob", ["numeria"])}).status_code, 403)
        self.assertEqual(self.cl.get("/ia/acces", headers={"Authorization": "Bearer " + T.token("bob", ["/ia"])}).status_code, 204)
        self.cl.set_cookie("si_ia_jeton", T.token("carol", ["ia"]))
        self.assertEqual(self.cl.get("/ia/acces").status_code, 204)
        self.cl.delete_cookie("si_ia_jeton")

    def test_noeuds(self):
        T = self.T
        r = self.cl.get("/ia/noeuds", headers={"Authorization": "Bearer " + T.token("eve", ["dev"])})
        self.assertEqual(r.status_code, 403)
        self.assertIn("ia", r.get_json()["groupes"])
        r = self.cl.get("/ia/noeuds", headers={"Authorization": "Bearer " + T.token("eve", ["ia"])})
        self.assertEqual(r.get_json(), {"noeuds": ["prodia", "preprodia"], "personne": "eve"})

    def test_reste_garde_admin(self):
        T = self.T   # le groupe « ia » n'ouvre pas la tour de contrôle
        T.appmod.verifier = T.auth.KeycloakVerifier("u", ["freg"], fetch=lambda _u: T.jwks(), allowed_groups=["administrateurs"], what="la tour")
        self.assertEqual(self.cl.get("/services", headers={"Authorization": "Bearer " + T.token("eve", ["ia"])}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
