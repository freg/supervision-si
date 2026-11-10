# -*- coding: utf-8 -*-
"""Tests #1003 : catégorisation par les éléments et le comportement, singularité par rapport à la population."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import categorie as cg  # noqa: E402

MACHINE = {"jours": 14, "jours_vus": 14, "heures_par_jour": 24.0, "continu": True, "part_nuit": 0.25, "filaire": True, "wifi": False,
           "bornes": ["sw"], "volumes": {"mesures": 0}}
TABLETTE = {"jours": 14, "jours_vus": 5, "heures_par_jour": 5.0, "continu": False, "part_nuit": 0.0, "wifi": True, "bornes": ["a", "b"],
            "ssids": ["atelier"], "volumes": {"mesures": 25, "regularite_cv": 1.4, "part_descendant": 0.9}}


class Categorie(unittest.TestCase):
    def test_tablette_android_mac_aleatoire(self):
        r = cg.categoriser({"mac": "6e:00:00:00:00:01", "name": "Galaxy-Tab-A11", "os": "Android"}, TABLETTE)
        self.assertEqual(r["categorie"], "mobile Android")
        self.assertGreater(r["confiance"], 50)
        self.assertIn("système annoncé « Android »", [p["texte"] for p in r["hypotheses"][0]["preuves"]])

    def test_minipc_derriere_adaptateur_usb(self):
        r = cg.categoriser({"mac": "80:1f:02:00:00:01", "manufacturer": "Edimax Technology Co. Ltd."}, MACHINE)
        self.assertEqual(r["categorie"], "machine Linux / sans écran")
        self.assertTrue(any("adaptateur" in p["texte"] for p in r["hypotheses"][0]["preuves"]))

    def test_poste_windows(self):
        r = cg.categoriser({"mac": "00:aa:00:00:00:01", "name": "DESKTOP-4F2K", "os": "Windows 11", "manufacturer": "Intel Corporate"},
                           dict(TABLETTE, bornes=["a"], volumes={"mesures": 0}))
        self.assertEqual(r["categorie"], "poste Windows")

    def test_singularite_pese_plus(self):
        fiche = {"mac": "00:aa:00:00:00:01", "manufacturer": "Samsung Electronics"}
        commun = cg.population([cg.traits(fiche, None)] * 9 + [cg.traits({"mac": "00:bb:00:00:00:01", "manufacturer": "Intel"}, None)])
        rare = cg.population([cg.traits({"mac": "00:bb:00:00:00:01", "manufacturer": "Intel"}, None)] * 99 + [cg.traits(fiche, None)])
        s_commun = cg.categoriser(fiche, None, commun)["hypotheses"][0]["score"]
        s_rare = cg.categoriser(fiche, None, rare)
        self.assertLess(s_commun, s_rare["hypotheses"][0]["score"])
        self.assertEqual([s["attribut"] for s in s_rare["singularites"]], ["fabricant"])
        self.assertIn("1 %", s_rare["singularites"][0]["texte"])

    def test_rien_a_dire(self):
        r = cg.categoriser({"mac": "00:aa:00:00:00:09"}, None)
        self.assertEqual((r["categorie"], r["confiance"], r["hypotheses"]), (None, 0, []))

    def test_compatible(self):
        self.assertTrue(cg.compatible("tablette", "mobile Android"))
        self.assertFalse(cg.compatible("tablette", "machine Linux / sans écran"))
        self.assertIsNone(cg.compatible(None, "mobile Android"))


if __name__ == "__main__":
    unittest.main()
