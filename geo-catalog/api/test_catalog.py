# -*- coding: utf-8 -*-
"""Tests de la logique pure du catalogue (livraison #429) :
python3 -m unittest test_catalog (depuis geo-catalog/api/)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402

BAN = {"source": "ban", "precision": "housenumber", "lat": 45.7605, "lon": 4.8302, "score": 0.92, "label": "5 rue x"}
STORED = {"source": "geolocations", "precision": "stored", "lat": 45.76, "lon": 4.83, "label": "saisie"}
COMMUNE = {"source": "commune", "precision": "commune", "lat": 45.77, "lon": 4.84, "score": 0.9, "label": "Villexemple"}
FAR = {"source": "osm", "precision": "osm", "lat": 48.85, "lon": 2.35, "score": 0.4, "label": "Paris"}


class InterpretTests(unittest.TestCase):
    def test_reference_la_plus_precise_et_concordance(self):
        i = catalog.interpret([STORED, BAN, COMMUNE])
        self.assertEqual(i["best"]["source"], "ban")
        self.assertEqual(i["precision"], "housenumber")
        self.assertGreaterEqual(i["confidence"], 90)
        self.assertEqual([a["source"] for a in i["agreement"]], ["geolocations", "commune"], "triées par distance")
        self.assertTrue(any("concordante" in r for r in i["reasons"]))

    def test_saisie_seule_moyenne(self):
        i = catalog.interpret([STORED])
        self.assertEqual((i["precision"], i["confidence"]), ("stored", 60))
        self.assertTrue(any("sans référence indépendante" in r for r in i["reasons"]))

    def test_contradiction_baisse(self):
        i = catalog.interpret([BAN, FAR])
        self.assertLess(i["confidence"], 60)
        self.assertTrue(any("contradictoire" in r for r in i["reasons"]))

    def test_decision_humaine_prime(self):
        i = catalog.interpret([FAR], {"status": "corrected", "lat": 45.76, "lon": 4.83})
        self.assertEqual((i["precision"], i["confidence"], i["lat"]), ("manual", 100, 45.76))
        self.assertEqual(catalog.interpret([], {"status": "validated", "lat": 1, "lon": 2})["confidence"], 95)
        self.assertEqual(catalog.interpret([], {"status": "auto", "lat": 1, "lon": 2})["confidence"], 0, "auto sans référence = rien")

    def test_geocodage_faible_ne_deplace_pas_une_saisie(self):
        weak = {"source": "ban", "precision": "housenumber", "lat": 45.76, "lon": 4.83, "score": 0.52, "label": "12 rue du Siège Villexemple"}
        brest = {"source": "geolocations", "precision": "stored", "lat": 48.39, "lon": -4.49, "label": "saisie"}
        i = catalog.interpret([weak, brest])
        self.assertEqual(i["best"]["source"], "geolocations", "la saisie reste la position")
        self.assertTrue(any("écartée" in r for r in i["reasons"]))
        self.assertLess(i["confidence"], 60, "mais la contradiction reste visible dans la justesse")
        strong = dict(weak, score=0.95)
        self.assertEqual(catalog.interpret([strong, brest])["best"]["source"], "ban", "un géocodage sûr de lui l'emporte")

    def test_rien(self):
        i = catalog.interpret([])
        self.assertEqual((i["lat"], i["confidence"], i["precision"]), (None, 0, "unknown"))
        self.assertIsNone(catalog.interpret([{"source": "x", "precision": "poi", "lat": None, "lon": None}])["best"])


class HelpersTests(unittest.TestCase):
    def test_requetes(self):
        self.assertEqual(catalog.geocode_query("Parc/Batiment-5 75000"), "Batiment 5")
        self.assertEqual(catalog.leaf("/A/B/C"), "C")
        self.assertEqual(catalog.postal_code("BIO17-17300-ISLANDE-RB3011"), "17300")
        self.assertIsNone(catalog.postal_code("192.168.1.1"))
        self.assertEqual(catalog.commune_query("Agence 17300"), "17300")
        self.assertEqual(catalog.ban_precision("street"), "street")
        self.assertEqual(catalog.ban_precision("bizarre"), "unknown")
        self.assertAlmostEqual(catalog.haversine_m(0, 0, 0, 1), 111195, delta=50)
        self.assertEqual(catalog.normalize("Batiment-5 / Bât. A"), "batiment 5 bat. a")


if __name__ == "__main__":
    unittest.main()
