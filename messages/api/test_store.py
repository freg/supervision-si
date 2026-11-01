# -*- coding: utf-8 -*-
"""Tests #903 : stockage des messages (portée, expiration, suppression)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

T = 1_800_000_000.0


class Messages(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.c = store.connect(os.path.join(self.d.name, "m.sqlite"))

    def tearDown(self):
        self.c.close()
        self.d.cleanup()

    def test_portee_et_visibilite(self):
        store.creer(self.c, "alice", "Alice", "bonjour tout le monde", portee="tous", now=T)
        store.creer(self.c, "alice", "Alice", "note pour moi", portee="moi", now=T + 1)
        store.creer(self.c, "bob", "Bob", "note de bob", portee="moi", now=T + 2)
        self.assertEqual([m["corps"] for m in store.lister(self.c, "alice", now=T + 3)], ["note pour moi", "bonjour tout le monde"])
        self.assertEqual([m["corps"] for m in store.lister(self.c, "bob", now=T + 3)], ["note de bob", "bonjour tout le monde"])
        self.assertEqual([m["corps"] for m in store.lister(self.c, "carol", now=T + 3)], ["bonjour tout le monde"])

    def test_expiration(self):
        permanent = store.creer(self.c, "a", "A", "permanent", duree_s=None, now=T)
        store.creer(self.c, "a", "A", "temporaire", duree_s=3600, now=T)
        self.assertIsNone(permanent["expire"])
        self.assertEqual(len(store.lister(self.c, "a", now=T + 60)), 2)
        self.assertEqual([m["corps"] for m in store.lister(self.c, "a", now=T + 3601)], ["permanent"])   # le temporaire a disparu

    def test_suppression(self):
        m = store.creer(self.c, "alice", "Alice", "x", now=T)
        self.assertEqual(store.supprimer(self.c, m["id"], "bob"), (False, "seul l'auteur (ou un administrateur) peut supprimer ce message"))
        self.assertTrue(store.supprimer(self.c, m["id"], "bob", est_admin=True)[0])                      # admin
        self.assertEqual(store.supprimer(self.c, "absent", "alice")[1], "introuvable")
        m = store.creer(self.c, "alice", "Alice", "y", now=T)
        self.assertTrue(store.supprimer(self.c, m["id"], "alice")[0])

    def test_vide(self):
        with self.assertRaises(ValueError):
            store.creer(self.c, "a", "A", "   ", now=T)


if __name__ == "__main__":
    unittest.main()
