# -*- coding: utf-8 -*-
"""Tests #903 : routes du blog (auth ouverte à tous les connectés, création, visibilité, suppression)."""
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
_D = tempfile.TemporaryDirectory()
os.environ["MESSAGES_DB"] = os.path.join(_D.name, "m.sqlite")
import app as appmod  # noqa: E402


class FauxVerifier:
    def verify(self, token):
        # jeton de test « user » ou « user:groupe » (ex. "alice" ou "chef:administrateurs")
        if not token:
            from auth import AuthError
            raise AuthError("jeton requis")
        nom, _, grp = token.partition(":")
        return {"username": nom, "name": nom.title(), "groups": [grp] if grp else []}


class Blog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        appmod.verifier = FauxVerifier()
        cls.c = appmod.app.test_client()

    def h(self, who):
        return {"Authorization": "Bearer " + who}

    def test_flux(self):
        r = self.c.post("/messages", json={"corps": "coucou", "portee": "tous"}, headers=self.h("alice"))
        self.assertEqual(r.status_code, 201)
        mid = r.get_json()["id"]
        self.c.post("/messages", json={"corps": "pour moi", "portee": "moi"}, headers=self.h("alice"))
        self.c.post("/messages", json={"corps": "secret bob", "portee": "moi"}, headers=self.h("bob"))
        vus_bob = [m["corps"] for m in self.c.get("/messages", headers=self.h("bob")).get_json()["messages"]]
        self.assertIn("coucou", vus_bob)
        self.assertIn("secret bob", vus_bob)
        self.assertNotIn("pour moi", vus_bob)                      # note privée d'alice invisible pour bob
        self.assertEqual(self.c.delete("/messages/" + mid, headers=self.h("bob")).status_code, 403)   # pas l'auteur
        self.assertEqual(self.c.delete("/messages/" + mid, headers=self.h("chef:administrateurs")).status_code, 200)  # admin

    def test_sans_jeton(self):
        self.assertEqual(self.c.get("/messages").status_code, 401)

    def test_duree_nommee(self):
        r = self.c.post("/messages", json={"corps": "éphémère", "duree_s": "1h"}, headers=self.h("alice"))
        self.assertIsNotNone(r.get_json()["expire"])


if __name__ == "__main__":
    unittest.main()
