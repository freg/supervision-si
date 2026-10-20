# -*- coding: utf-8 -*-
"""#798 : registre des navigateurs d'hôte (validation, routes) et commande « navigateur » acceptée par le central."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import navigateurs as N  # noqa: E402
import store  # noqa: E402


class Pur(unittest.TestCase):
    def test_valider(self):
        l, err = N.valider([{"nom": "ovh1", "agent_id": "a1", "accueil": "https://www.example.org/"}], {"a1"})
        self.assertIsNone(err)
        self.assertEqual(l[0]["libelle"], "ovh1")
        for bad, msg in (([{"nom": "OVH", "agent_id": "a1"}], "nom"), ([{"nom": "x", "agent_id": ""}], "agent_id"),
                         ([{"nom": "x", "agent_id": "zz"}], "inconnu"), ([{"nom": "x", "agent_id": "a1"}] * 2, "double"),
                         ([{"nom": "x", "agent_id": "a1", "accueil": "javascript:alert(1)"}], "accueil"), ("x", "liste")):
            self.assertIn(msg, N.valider(bad, {"a1"})[1])


class Routes(unittest.TestCase):
    def test_parcours(self):
        c = appmod.app.test_client()
        store.create_agent(appmod.DB_PATH, "nav-ovh", "ovh", label="nav-ovh")
        self.assertEqual(c.get("/navigateurs").get_json(), {"navigateurs": []})
        r = c.put("/navigateurs", json={"navigateurs": [{"nom": "ovh1", "agent_id": "nav-ovh", "libelle": "VM OVH (vue de l'extérieur)"}], "actor": "freg"})
        self.assertEqual(r.status_code, 200)
        n = r.get_json()["navigateurs"][0]
        self.assertEqual((n["nom"], n["agent_id"], n["libelle"]), ("ovh1", "nav-ovh", "VM OVH (vue de l'extérieur)"))
        self.assertEqual(c.put("/navigateurs", json={"navigateurs": [{"nom": "x", "agent_id": "absent"}]}).status_code, 400)
        r = c.post("/agents/nav-ovh/commands", json={"type": "navigateur", "params": {"action": "aller", "url": "https://www.example.org/"}})
        self.assertIn(r.status_code, (200, 201))


if __name__ == "__main__":
    unittest.main()
