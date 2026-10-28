# -*- coding: utf-8 -*-
"""Tests #896 : épreuves de charge en format réduit (quelques secondes, quelques Mo)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poste_charge as pc  # noqa: E402


class Charge(unittest.TestCase):
    def test_cpu(self):
        r = pc.epreuve_cpu(1, coeurs=2)
        self.assertEqual((r["coeurs"], r["erreurs_calcul"]), (2, 0))
        self.assertGreater(r["iterations"], 0)

    def test_memoire(self):
        r = pc.epreuve_memoire(50, 8, libre=16 * 2 ** 20)
        self.assertEqual((r["mo"], r["blocs_errones"]), (8, 0))

    def test_disque(self):
        with tempfile.TemporaryDirectory() as d:
            r = pc.epreuve_disque(4, d)
            self.assertTrue(r["identique"])
            self.assertEqual(os.listdir(d), [])                       # fichier effacé
            r = pc.epreuve_disque(4, os.path.join(d, "absent"))
            self.assertIsNotNone(r["erreur"])

    def test_main(self):
        with tempfile.TemporaryDirectory() as d:
            out = pc.main(["--cpu-s", "5", "--mem-pct", "5", "--mem-max-mo", "8", "--disque-mo", "16", "--dossier", d])
        self.assertEqual(out["verdict"], "aucun défaut reproduit")
        self.assertEqual(out["alerts"], [])


if __name__ == "__main__":
    unittest.main()
