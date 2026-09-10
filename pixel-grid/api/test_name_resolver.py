"""Tests du résolveur nom -> localisation (livraison #426) : python3 -m pytest
pixel-grid/api/test_name_resolver.py, ou python3 -m unittest depuis ce dossier."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from name_resolver import AUTO_THRESHOLD, candidates, resolve, score_tokens, tokens  # noqa: E402

LOCS = ["Parc/Batiment 5", "Arobase 3", "@5", "Siège/Bâtiment A", "Siège/Bâtiment B/Étage 2",
        "Agence Saint-Malo", "Agence Nantes", "Agence Nancy", "DC Lyon", "__default__"]


class TokensTest(unittest.TestCase):
    def test_semantique_et_forme(self):
        self.assertEqual(tokens("UPS-Arobase-05", drop_types=True), ["arobase", "5"])
        self.assertEqual(tokens("@5"), ["arobase", "5"])
        self.assertEqual(tokens("Parc/Batiment 5"), ["parc", "batiment", "5"])
        self.assertEqual(tokens("sw-tp5-core", drop_types=True), ["batiment", "5"])
        self.assertEqual(tokens("batA"), ["batiment", "a"])
        self.assertEqual(tokens("Bâtiment cinq"), ["batiment", "5"])
        self.assertEqual(tokens("  "), [])

    def test_nombres_contraignent(self):
        self.assertGreater(score_tokens(["arobase", "5"], ["arobase", "5"]), 0.99)
        self.assertLess(score_tokens(["arobase", "3"], ["arobase", "5"]), 0.2, "Arobase-3 ne désigne pas Arobase 5")
        self.assertEqual(score_tokens(["arobase"], ["arobase", "5"]), 0.5, "sans nombre : plausible, pas certain")
        self.assertEqual(score_tokens([], ["x"]), 0.0)


class ResolveTest(unittest.TestCase):
    def best(self, name, site=None, aliases=None):
        b, _ = resolve(name, LOCS, site=site, aliases=aliases)
        return b

    def test_exemple_de_la_demande(self):
        b = self.best("UPS-Arobase-5")
        self.assertEqual((b["localisation"], b["status"]), ("@5", "auto"))
        self.assertEqual(self.best("UPS-Arobase-3")["localisation"], "Arobase 3")

    def test_site_declare_prime(self):
        b = self.best("nas", site="Arobase-5")
        self.assertEqual((b["localisation"], b["via"]), ("@5", "site"))

    def test_orthographe_et_semantique(self):
        self.assertEqual(self.best("sw-tp5-core")["localisation"], "Parc/Batiment 5")
        self.assertEqual(self.best("srv-stmalo-01")["localisation"], "Agence Saint-Malo")
        self.assertEqual(self.best("ap-nantes-2")["localisation"], "Agence Nantes")
        self.assertNotEqual(self.best("sw-nancy-1")["localisation"], "Agence Nantes")
        self.assertEqual(self.best("imprimante-batA")["localisation"], "Siège/Bâtiment A")
        self.assertEqual(self.best("ups-siege-b-etg2")["localisation"], "Siège/Bâtiment B/Étage 2")
        for name in ("sw-tp5-core", "srv-stmalo-01", "ap-nantes-2", "imprimante-batA"):
            self.assertGreaterEqual(self.best(name)["score"], AUTO_THRESHOLD, name)

    def test_rien_de_credible(self):
        self.assertIsNone(self.best("pc-compta"))
        self.assertIsNone(self.best("192.168.1.35"))
        self.assertIsNone(self.best("routeur.lan"))

    def test_ambigu_suggere_seulement(self):
        b, cands = resolve("UPS-Arobase", LOCS)
        self.assertEqual(b["status"], "suggested")
        self.assertEqual({c["localisation"] for c in cands[:2]}, {"@5", "Arobase 3"})

    def test_alias_declare(self):
        b = self.best("ups-batiment-cinq", aliases={"tp5": "@5"})
        self.assertEqual((b["localisation"], b["method"]), ("@5", "alias"), "à score égal, l'alias déclaré l'emporte")
        b = self.best("srv-annexe-nord", aliases={"annexe nord": "DC Lyon"})
        self.assertEqual((b["localisation"], b["method"], b["status"]), ("DC Lyon", "alias", "auto"))

    def test_default_jamais_candidat(self):
        self.assertFalse(any(c["localisation"] == "__default__" for c in candidates("default", LOCS)))


if __name__ == "__main__":
    unittest.main()
