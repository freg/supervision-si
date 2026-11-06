# -*- coding: utf-8 -*-
"""Tests #984 : tuile Démonstrations (parcours, visites, fichiers servis, commande)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demos as D  # noqa: E402


class Demos(unittest.TestCase):
    def setUp(self):
        self.p = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.p, "demo", "parcours"))
        with open(os.path.join(self.p, "demo", "parcours", "idruide.json"), "w", encoding="utf-8") as fh:
            json.dump({"titre": "Idruide", "variables": {"site": "x"}, "etapes": [{}, {}]}, fh)
        v = os.path.join(self.p, "demo", "sorties", "idruide-20261106-1000")
        os.makedirs(v)
        with open(os.path.join(v, "manifeste.json"), "w", encoding="utf-8") as fh:
            json.dump({"id": "idruide", "titre": "Idruide", "date": "06/11/2026 10:00", "livraison": "984",
                       "etapes": [{"image": "01.png", "titre": "Un", "remarques": ["élément introuvable : x"]}]}, fh)
        for f in ("diaporama.html", "idruide.pptx", "01.png"):
            open(os.path.join(v, f), "w").close()
        os.makedirs(os.path.join(self.p, "demo", "sorties", "../evasion-20261106-1000"), exist_ok=True)

    def test_listes(self):
        self.assertEqual([(x["id"], x["etapes"], x["variables"]) for x in D.parcours(self.p)], [("idruide", 2, {"site": "x"})])
        v = D.visites(self.p)
        self.assertEqual((v[0]["dossier"], v[0]["pptx"], v[0]["diaporama"], v[0]["apercu"]), ("idruide-20261106-1000", "idruide.pptx", True, "01.png"))
        self.assertEqual(v[0]["remarques"], ["Un : élément introuvable : x"])
        self.assertEqual(D.parcours("/inexistant"), [])

    def test_supprimer(self):
        self.assertEqual(D.supprimer(self.p, "../evasion-20261106-1000"), "nom de visite non conforme")
        self.assertEqual(D.supprimer(self.p, "idruide-20261106-0900"), "visite inconnue")
        os.makedirs(os.path.join(self.p, "demo", "sorties", "vide-20261106-1000"))
        self.assertEqual(D.supprimer(self.p, "vide-20261106-1000"), "visite inconnue")      # pas de manifeste : on n'y touche pas
        self.assertIsNone(D.supprimer(self.p, "idruide-20261106-1000"))
        self.assertEqual(D.visites(self.p), [])
        self.assertTrue(os.path.isdir(os.path.join(self.p, "demo", "evasion-20261106-1000")))

    def test_fichiers_controles(self):
        self.assertTrue(D.fichier(self.p, "idruide-20261106-1000", "diaporama.html"))
        self.assertIsNone(D.fichier(self.p, "idruide-20261106-1000", "../../../etc/passwd"))
        self.assertIsNone(D.fichier(self.p, "..", "diaporama.html"))
        self.assertIsNone(D.fichier(self.p, "idruide-20261106-1000", "journal.txt"))          # absent
        self.assertEqual(D.type_mime("x.pptx")[:24], "application/vnd.openxmlf")

    def test_commande(self):
        c, e = D.commande("maj-terminal", {"terminal": "E22 LabCo", "nom_reseau": "E22-LabCo"}, {"maj-terminal"})
        self.assertIsNone(e)
        self.assertEqual(c, "./scripts/demo.sh maj-terminal --var nom_reseau=E22-LabCo --var 'terminal=E22 LabCo'")
        self.assertIn("variable refusée", D.commande("maj-terminal", {"terminal": "x; rm -rf /"}, {"maj-terminal"})[1])
        self.assertIn("parcours inconnu", D.commande("x", {}, {"maj-terminal"})[1])


if __name__ == "__main__":
    unittest.main()
