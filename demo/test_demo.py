# -*- coding: utf-8 -*-
"""Tests #982 : parcours de démonstration (validation, variables, URL) et fabrication diaporama + pptx."""
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import demo_lib as L  # noqa: E402


class Parcours(unittest.TestCase):
    def test_parcours_livres_valides(self):
        ids = [pid for pid, _ in L.lister(os.path.join(ICI, "parcours"))]
        self.assertEqual(ids, ["idruide", "maj-terminal", "vlan-ssid"])
        for pid in ids:
            p, err = L.charger(os.path.join(ICI, "parcours", pid + ".json"))
            self.assertEqual(err, [], pid)

    def test_variables_et_url(self):
        p, err = L.charger(os.path.join(ICI, "parcours", "maj-terminal.json"), {"terminal": "E22 LabCo"})
        self.assertIn("E22 LabCo", p["etapes"][1]["titre"])
        self.assertEqual(p["etapes"][4]["saisir"][0]["texte"], "E11-AmpIm")      # valeur par défaut du parcours
        self.assertEqual(L.url_etape("https://hub.exemple/", {"vue": "nebula", "params": {"tab": "vlan", "x": ""}}), "https://hub.exemple/?view=nebula&tab=vlan")
        self.assertEqual(L.substituer("{inconnue}", {}), "{inconnue}")
        self.assertIn("étape 1 : « vue » manquante", L.valider({"id": "a", "titre": "b", "etapes": [{"titre": "t"}]}))
        self.assertIn("étape 1 : champ(s) inconnu(s) clic", L.valider({"id": "a", "titre": "b", "etapes": [{"titre": "t", "vue": "v", "clic": 1}]}))

    def test_diaporama_et_pptx(self):
        try:
            import pptx  # noqa: F401
            from PIL import Image
        except ImportError:
            self.skipTest("python-pptx / Pillow absents")
        import build
        d = tempfile.mkdtemp()
        for i in (1, 2):
            Image.new("RGB", (1600, 900), (30, 40, 50)).save(os.path.join(d, "%02d.png" % i))
        m = {"id": "essai", "titre": "Essai <&>", "sous_titre": "s", "public": "Campus", "date": "06/11/2026 10:00", "livraison": "982",
             "etapes": [{"image": "01.png", "titre": "Un", "legende": "l1"}, {"image": "02.png", "titre": "Deux", "legende": ""}]}
        with open(os.path.join(d, "manifeste.json"), "w", encoding="utf-8") as fh:
            json.dump(m, fh)
        html, pp = build.construire(d)
        t = open(html, encoding="utf-8").read()
        self.assertEqual(t.count("<section"), 3)
        self.assertIn("Essai &lt;&amp;&gt;", t)
        self.assertIn("data:image/png;base64,", t)
        from pptx import Presentation
        prs = Presentation(pp)
        self.assertEqual(len(prs.slides), 3)
        self.assertEqual(prs.slides[1].notes_slide.notes_text_frame.text, "l1")


if __name__ == "__main__":
    unittest.main()
