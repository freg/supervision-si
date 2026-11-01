"""Tests #721 : règles de conformité visuelle (sans navigateur) et génération du tour du hub."""
import unittest
import qa_design as qd


class Regles(unittest.TestCase):
    def test_contraste(self):
        self.assertEqual(qd.contrast("rgb(0, 0, 0)", "rgb(255, 255, 255)"), 21.0)
        self.assertAlmostEqual(qd.contrast("rgb(119, 119, 119)", "rgb(255, 255, 255)"), 4.48, places=2)
        self.assertGreater(qd.contrast("rgba(0, 0, 0, 0.5)", "rgb(255, 255, 255)"), 3)   # composé sur le fond
        self.assertIsNone(qd.contrast("transparent", "rgb(1, 2, 3)"))

    def test_evaluate(self):
        m = {"texts": [{"el": "p", "text": "gris", "color": "rgb(170, 170, 170)", "bg": "rgb(255, 255, 255)", "size": 13, "weight": 400},
                       {"el": "p", "text": "gris bis", "color": "rgb(170, 170, 170)", "bg": "rgb(255, 255, 255)", "size": 13, "weight": 400},
                       {"el": "h1", "text": "Titre", "color": "rgb(118, 118, 118)", "bg": "rgb(255, 255, 255)", "size": 28, "weight": 700},
                       {"el": "span", "text": "ok", "color": "rgb(20, 20, 20)", "bg": "rgb(250, 250, 250)", "size": 13, "weight": 400}],
             "page": {"scroll_h": 2400, "view_h": 900, "scroll_w": 1366, "view_w": 1366},
             "tables": [{"el": "table.x", "rows": 80, "has_thead": True, "sticky": False, "in_scroller": True, "overflows": True},
                        {"el": "table.y", "rows": 80, "has_thead": True, "sticky": True, "in_scroller": True, "overflows": True}],
             "targets": [{"el": "button", "text": "×", "w": 16, "h": 16, "inline": False}, {"el": "a", "text": "lien", "w": 30, "h": 14, "inline": True}],
             "inline": [{"el": "div", "style": "color: #c00"}], "truncated": [{"el": "td", "text": "très long…"}]}
        f = qd.evaluate(m)
        rules = [x["rule"] for x in f]
        self.assertEqual(rules.count("contraste"), 1)                      # même couple de couleurs : un seul constat ; titre 4,5:1 > 3:1 requis
        self.assertEqual(f[0]["severity"], "erreur")                        # 2,32:1 < 3
        self.assertEqual(rules, ["contraste", "page-defile", "entete-fixe", "cible-petite", "couleur-en-dur", "texte-tronque"])
        self.assertIn("1 cible", next(x for x in f if x["rule"] == "cible-petite")["message"])   # le lien en ligne n'est pas compté
        self.assertEqual(qd.score(f), 100 - 15 - 5 * 4 - 1)
        self.assertEqual(qd.evaluate({}), [])

    def test_tour(self):
        steps = qd.hub_tour_steps([{"view": "ups", "label": "Onduleurs"}, {"view": "../x"}, {"view": "cortex"}], wait_ms=800, strict=True)
        self.assertEqual([s["action"] for s in steps], ["goto", "wait", "audit"] * 2)
        self.assertEqual((steps[0]["value"], steps[1]["value"], steps[2]["value"], steps[2]["note"]), ("/?view=ups", "800", "strict", "Onduleurs"))


if __name__ == "__main__":
    unittest.main()
