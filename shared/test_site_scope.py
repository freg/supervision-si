"""Tests A1 (#620) : périmètre de site par groupe -- logique pure et garde Flask avec vérificateur simulé."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import site_scope as ss  # noqa: E402


class PureTests(unittest.TestCase):
    def test_load_groups(self):
        self.assertEqual(ss.load_groups('{"site-alpha": ["alpha"], "multi": "a", "": ["x"], "vide": []}'), {"site-alpha": ["alpha"], "multi": ["a"]})
        self.assertEqual(ss.load_groups("pas du json"), {}); self.assertEqual(ss.load_groups(""), {})

    def test_resolve(self):
        sg = {"site-alpha": ["alpha"], "site-groupe": ["groupe", "beta"]}
        full = ["administrateurs"]
        self.assertIsNone(ss.resolve(["administrateurs", "site-alpha"], sg, full))
        self.assertIsNone(ss.resolve(["techniciens"], sg, full))  # aucun groupe à périmètre : tout (modèle historique)
        self.assertEqual(ss.resolve(["/site-alpha"], sg, full), ["alpha"])
        self.assertEqual(ss.resolve(["site-alpha", "site-groupe"], sg, full), ["alpha", "beta", "groupe"])

    def test_check(self):
        self.assertEqual(ss.check(None, "x", None), ("x", None))
        self.assertEqual(ss.check(None, None, ["alpha"]), ("alpha", None))
        self.assertEqual(ss.check(None, "alpha", ["alpha"]), ("alpha", None))
        self.assertIsNotNone(ss.check(None, "beta", ["alpha"])[1])
        self.assertIsNotNone(ss.check("beta", None, ["alpha"])[1])
        self.assertEqual(ss.check("alpha", None, ["alpha", "z"])[0], "alpha")


class GuardTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask, jsonify, request
        os.environ["SITE_SCOPE_GROUPS"] = '{"site-alpha": ["alpha"]}'
        os.environ["SITE_SCOPE_FULL_GROUPS"] = "administrateurs"
        self.tokens = {"tok-num": {"username": "n", "name": "n", "groups": ["site-alpha"]}, "tok-adm": {"username": "a", "name": "a", "groups": ["administrateurs"]}}

        class FakeVerifier:
            def __init__(self, *a, **k): self.allowed_users = []; self.allowed_groups = set()
            def verify(inner, token):
                if token not in self.tokens:
                    raise ss.AuthError("jeton invalide")
                return self.tokens[token]

        class FakeAuthError(Exception):
            def __init__(self, m, status=401): super().__init__(m); self.status = status
        ss.KeycloakVerifier, ss.AuthError = FakeVerifier, FakeAuthError
        ss.bearer_from_header = lambda v: (v or "").replace("Bearer ", "") or None
        app = Flask("t")
        sites = {"a1": "alpha", "a2": "beta"}
        ss.install(app, "http://jwks", resolve_site=lambda p: sites.get(p.split("/")[2]) if p.startswith("/agents/") else None)

        @app.route("/fleet")
        def fleet():
            return jsonify({"site": request.args.get("site"), "user": getattr(__import__("flask").g, "user", {}).get("username")})

        @app.route("/agents/<aid>")
        def agent(aid):
            return jsonify({"agent": aid})

        @app.route("/api/v1/agents/<aid>/config")
        def agent_face(aid):
            return jsonify({"ok": True})
        self.c = app.test_client()

    def get(self, path, token=None):
        return self.c.get(path, headers={"Authorization": "Bearer " + token} if token else {})

    def test_sans_jeton_inchange(self):
        r = self.get("/fleet"); self.assertEqual(r.status_code, 200); self.assertIsNone(r.get_json()["site"])

    def test_perimetre_injecte_et_refuse(self):
        r = self.get("/fleet", "tok-num"); self.assertEqual(r.get_json(), {"site": "alpha", "user": "n"})
        r = self.get("/fleet?site=alpha", "tok-num"); self.assertEqual(r.status_code, 200)
        r = self.get("/fleet?site=beta", "tok-num"); self.assertEqual(r.status_code, 403); self.assertEqual(r.get_json()["site_scope"], ["alpha"])
        self.assertEqual(self.get("/agents/a1", "tok-num").status_code, 200)
        self.assertEqual(self.get("/agents/a2", "tok-num").status_code, 403)
        self.assertEqual(self.get("/agents/zz", "tok-num").status_code, 200)  # site inconnu : pas de blocage aveugle

    def test_admin_et_face_agents(self):
        r = self.get("/fleet?site=beta", "tok-adm"); self.assertEqual(r.status_code, 200); self.assertEqual(r.get_json()["site"], "beta")
        self.assertEqual(self.get("/agents/a2", "tok-adm").status_code, 200)
        self.assertEqual(self.get("/api/v1/agents/a2/config", "tok-num").status_code, 200)
        self.assertEqual(self.get("/fleet", "tok-inconnu").status_code, 401)


if __name__ == "__main__":
    unittest.main()
