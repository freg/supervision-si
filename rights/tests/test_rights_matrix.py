"""Matrice des droits, restrictions, sujets utilisateur (livraison #559)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import store  # noqa: E402


class Matrix(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "r.db")
        store.ensure_schema(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ouvert_par_defaut_puis_restreint(self):
        ids = ["nebula", "tickets", "cortex"]
        # personne non restreinte : tout
        self.assertEqual(store.visible_ids(self.db, ["site-alpha"], "hub-tile", ids, user="bob"), ids)
        self.assertFalse(store.is_restricted(self.db, ["site-alpha"], "bob"))
        # groupe restreint : rien tant que rien n'est accordé
        self.assertTrue(store.set_restricted(self.db, "group:site-alpha", True, "freg"))
        self.assertTrue(store.is_restricted(self.db, ["site-alpha"], "bob"))
        self.assertEqual(store.visible_ids(self.db, ["site-alpha"], "hub-tile", ids, user="bob"), [])
        # octroi au groupe -> une tuile
        store.set_grant(self.db, "hub-tile", "nebula", "site-alpha", "view", True, "freg")
        self.assertEqual(store.visible_ids(self.db, ["site-alpha"], "hub-tile", ids, user="bob"), ["nebula"])
        # un groupe ouvert en plus suffit à tout ouvrir
        self.assertEqual(store.visible_ids(self.db, ["site-alpha", "techniciens"], "hub-tile", ids, user="bob"), ids)
        # login restreint individuellement, octroi par login
        store.set_restricted(self.db, "user:carol", True)
        self.assertTrue(store.is_restricted(self.db, ["techniciens"], "carol"))
        store.set_grant(self.db, "hub-tile", "tickets", "user:carol", "view", True)
        self.assertEqual(store.visible_ids(self.db, ["techniciens"], "hub-tile", ids, user="carol"), ["tickets"])
        self.assertTrue(store.has_permission(self.db, ["techniciens"], "hub-tile", "tickets", "view", user="carol"))
        self.assertFalse(store.has_permission(self.db, ["techniciens"], "hub-tile", "cortex", "view", user="carol"))
        # révocation idempotente
        store.set_grant(self.db, "hub-tile", "tickets", "user:carol", "view", False)
        self.assertEqual(store.visible_ids(self.db, ["techniciens"], "hub-tile", ids, user="carol"), [])
        # jamais restreints
        self.assertFalse(store.set_restricted(self.db, "group:admin_hub", True))
        self.assertFalse(store.is_restricted(self.db, ["site-alpha", "administrateurs"], "root"))
        self.assertEqual(store.visible_ids(self.db, ["admin_hub"], "hub-tile", ids), ids)
        store.set_restricted(self.db, "group:site-alpha", False)
        self.assertFalse(store.is_restricted(self.db, ["site-alpha"], "bob"))

    def test_catalogue(self):
        store.set_catalog(self.db, "hub-tile", [{"identifier": "nebula", "label": "Nebula", "theme": "Réseau", "actions": ["view", "manage"]}, {"identifier": "", "label": "x"}, {"identifier": "cortex", "label": "Cortex"}])
        cat = store.get_catalog(self.db, "hub-tile")
        self.assertEqual([c["identifier"] for c in cat], ["nebula", "cortex"])
        self.assertEqual(cat[0]["actions"], ["view", "manage"]); self.assertEqual(cat[1]["actions"], ["view"])
        store.set_catalog(self.db, "hub-tile", [{"identifier": "cortex", "label": "Cortex"}])
        self.assertEqual(len(store.get_catalog(self.db, "hub-tile")), 1)


if __name__ == "__main__":
    unittest.main()
