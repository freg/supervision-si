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


MOBILE_P = {"jours": 14, "jours_vus": 5, "heures_par_jour": 5.0, "continu": False, "part_nuit": 0.0, "wifi": True, "bornes": ["a", "b"],
            "ssids": ["w"], "volumes": {"mesures": 25, "regularite_cv": 1.4, "part_descendant": 0.6}}
FIXE_P = {"jours": 14, "jours_vus": 14, "heures_par_jour": 24.0, "continu": True, "part_nuit": 0.25, "filaire": True, "wifi": False,
          "bornes": ["sw"], "volumes": {"mesures": 0}}


class TypeAppareil(unittest.TestCase):
    def t(self, fiche, p=None, **kw):
        return cg.categoriser_type(fiche, p, **kw)

    def test_tablette(self):
        r = self.t({"mac": "6e:00:00:00:00:01", "name": "Galaxy-Tab-A11", "os": "Android"}, MOBILE_P)
        self.assertEqual(r["categorie"], "tablette")

    def test_mobile(self):
        r = self.t({"mac": "6e:00:00:00:00:02", "name": "Galaxy-S23", "os": "Android"}, MOBILE_P)
        self.assertEqual(r["categorie"], "mobile")

    def test_casque_vr(self):
        r = self.t({"mac": "6e:00:00:00:00:03", "name": "Quest 3", "manufacturer": "Meta Platforms Inc"})
        self.assertEqual(r["categorie"], "casque VR")

    def test_portable(self):
        r = self.t({"mac": "aa:00:00:00:00:04", "name": "MacBook-Pro-Marie", "os": "macOS"}, MOBILE_P)
        self.assertEqual(r["categorie"], "portable")

    def test_ordinateur_fixe(self):
        r = self.t({"mac": "aa:00:00:00:00:05", "name": "DESKTOP-OFFICE", "os": "Windows 10", "manufacturer": "Dell Inc"}, FIXE_P)
        self.assertEqual(r["categorie"], "ordinateur fixe")

    def test_equipement_reseau(self):
        r = self.t({"mac": "70:49:a2:00:00:06", "name": "WBE660S-EU0101F-4", "manufacturer": "Zyxel Communications"})
        self.assertEqual(r["categorie"], "équipement réseau")

    def test_supervision_par_mac_de_flotte(self):
        r = self.t({"mac": "84:9e:56:00:00:07", "manufacturer": "Cloud Network Technology", "os": "Debian"}, FIXE_P, supervision=True)
        self.assertEqual(r["categorie"], "équipement supervision")
        self.assertTrue(any("flotte des agents" in x["texte"] for x in r["hypotheses"][0]["preuves"]))

    def test_supervision_par_nom_minipc(self):
        r = self.t({"mac": "aa:00:00:00:00:08", "name": "optline1", "os": "Debian GNU/Linux 13", "manufacturer": "GMKtec"}, FIXE_P)
        self.assertEqual(r["categorie"], "équipement supervision")

    def test_hors_type_imprimante(self):
        r = self.t({"mac": "aa:00:00:00:00:09", "name": "HP LJMFP M776", "manufacturer": "HP Inc"})
        self.assertIsNone(r["categorie"])
        self.assertEqual(r["niveau"], "aucune")

    def test_confirmation_fixe_le_type(self):
        r = self.t({"mac": "aa:00:00:00:00:0a", "name": "x"}, decision={"categorie": "mobile", "par": "freg"})
        self.assertEqual((r["categorie"], r["confiance"], r["niveau"]), ("mobile", 100, "confirmée"))
        # une décision d'un autre axe (catégorie) n'est pas appliquée au type
        r2 = self.t({"mac": "aa:00:00:00:00:0b", "name": "x"}, decision={"categorie": "poste Windows", "par": "freg"})
        self.assertIsNone(r2["decision"])


if __name__ == "__main__":
    unittest.main()
