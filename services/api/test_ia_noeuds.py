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


class Registre996(unittest.TestCase):
    """#996 : registre des nœuds déployés depuis le hub (scripts/ia_registre.py) et publications du bastion."""
    def setUp(self):
        sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
        import ia_registre as R
        self.R = R

    def test_valider_declarer(self):
        R = self.R
        self.assertIsNone(R.valider({"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30", "shim": "campus"}))
        self.assertIn("shim", R.valider({"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30"}))
        self.assertIn("accès", R.valider({"nom": "prodia", "acces": "vpn", "adresse": "x"}))
        self.assertIn("adresse", R.valider({"nom": "prodia", "acces": "direct", "adresse": "a b;c"}))
        n = R.declarer([], {"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30", "shim": "campus"})
        n[0]["publie"] = 6491
        n = R.declarer(n, {"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30", "shim": "campus", "port": 8092})
        self.assertEqual(n[0]["publie"], 6491)                     # même cible : port publié gardé
        n = R.declarer(n, {"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.31", "shim": "campus"})
        self.assertNotIn("publie", n[0])

    def test_publications(self):
        R = self.R
        noeuds = [{"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30", "port": 8092, "shim": "campus"},
                  {"nom": "preprodia", "acces": "direct", "adresse": "192.0.2.20", "port": 8092}]
        spec, n, ch = R.publications("6488=campus:192.0.2.10:8006,6491=ia:192.0.2.5:11434", noeuds)
        self.assertTrue(ch); self.assertEqual(spec, "6488=campus:192.0.2.10:8006,6491=ia:192.0.2.5:11434,6492=campus:192.0.2.30:8092")
        self.assertEqual(n[0]["publie"], 6492); self.assertNotIn("publie", n[1])
        spec2, n2, ch2 = R.publications(spec, n)
        self.assertFalse(ch2); self.assertEqual(spec2, spec)
        self.assertEqual(R.env_remplacer("A=1\nSI_PROXY_PUBLISH=\nB=2\n", "SI_PROXY_PUBLISH", spec), "A=1\nSI_PROXY_PUBLISH=%s\nB=2\n" % spec)
        self.assertEqual(R.env_remplacer("A=1", "X", "y"), "A=1\nX=y\n")
        self.assertEqual(R.env_valeur("SI_PROXY_PUBLISH='6488=a:b:1'\n", "SI_PROXY_PUBLISH"), "6488=a:b:1")

    def test_routes(self):
        import tempfile
        import test_app as T
        A = T.appmod
        A.verifier = T.auth.KeycloakVerifier("u", ["freg"], fetch=lambda _u: T.jwks(), allowed_groups=["administrateurs"], what="la tour")
        A.ia_verifier = T.auth.KeycloakVerifier("u", [], fetch=lambda _u: T.jwks(), allowed_groups=["ia"], what="les nœuds IA")
        lances = []
        orig = A.launch_job, A.verifier
        A.launch_job = lambda kind, label, steps, user, extra=None: (lances.append(steps), {"id": "j1"})[1]
        self.addCleanup(lambda: (setattr(A, "launch_job", orig[0]), setattr(A, "verifier", orig[1])))
        cl = A.app.test_client()
        adm = {"Authorization": "Bearer " + T.token("freg", ["administrateurs"])}
        self.assertEqual(cl.post("/ia/declarer", json={"nom": "prodia"}, headers={"Authorization": "Bearer " + T.token("eve", ["ia"])}).status_code, 403)
        self.assertEqual(cl.post("/ia/declarer", json={"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30"}, headers=adm).status_code, 400)
        r = cl.post("/ia/declarer", json={"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30", "shim": "campus"}, headers=adm)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual([s["cmd"] for s in lances[-1]], ["python3 scripts/ia_registre.py publier", "./scripts/run.sh up -d si-proxy",
                                                          "./gateway/scripts/run.sh up -d --force-recreate tls-proxy"])
        cl.post("/ia/declarer", json={"nom": "preprodia", "acces": "direct", "adresse": "192.0.2.20"}, headers=adm)
        self.assertEqual(len(lances[-1]), 1)
        self.assertEqual([e["nom"] for e in cl.get("/ia/registre", headers=adm).get_json()["noeuds"]], ["preprodia", "prodia"])
        A.IA_NOEUDS = []
        r = cl.get("/ia/noeuds", headers={"Authorization": "Bearer " + T.token("eve", ["ia"])})
        self.assertEqual(r.get_json()["noeuds"], ["preprodia", "prodia"])
