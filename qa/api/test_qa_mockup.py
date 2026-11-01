"""Maquettes (#728) : correctifs calculés depuis les constats, validation des variantes, étapes de présentation."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(__file__))
import qa_mockup as m
from qa_design import contrast

F = [{"rule": "contraste", "severity": "erreur", "message": "x", "el": "span.muted", "fg": "rgb(170, 170, 170)", "bg": "rgb(255, 255, 255)", "need": 4.5},
     {"rule": "contraste", "severity": "erreur", "message": "x", "el": "td>bad", "fg": "rgb(170, 170, 170)", "bg": "rgb(255, 255, 255)", "need": 4.5},
     {"rule": "entete-fixe", "severity": "avertissement", "message": "x", "el": "table.qa-table"},
     {"rule": "cible-petite", "severity": "avertissement", "message": "x", "els": ["button.qa-mini", "a"]},
     {"rule": "page-defile", "severity": "avertissement", "message": "la page défile"}]


class T(unittest.TestCase):
    def test_fix_color(self):
        c = m.fix_color("rgb(170, 170, 170)", "rgb(255, 255, 255)", 4.7)
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreaterEqual(contrast("rgb(%d, %d, %d)" % (r, g, b), "rgb(255, 255, 255)"), 4.7)
        self.assertGreater(r, 90)                                   # le plus proche possible de la couleur d'origine
        c2 = m.fix_color("rgb(90, 90, 90)", "rgb(20, 20, 20)", 4.7)  # fond sombre : vers le blanc
        self.assertGreater(int(c2[1:3], 16), 90)
        self.assertIsNone(m.fix_color("pas une couleur", "rgb(0,0,0)", 4.5))

    def test_propose_and_variants(self):
        css, notes = m.propose(F)
        self.assertIn("span.muted { color: #", css); self.assertNotIn("td>bad", css)           # sélecteur non sûr ignoré
        self.assertIn("table.qa-table thead th { position: sticky", css); self.assertIn("button.qa-mini, a { min-width: 24px", css)
        self.assertEqual(len(notes), 2); self.assertTrue(any("page-defile" in n for n in notes))   # sélecteur non sûr : en note
        v = m.auto_variants(F); self.assertEqual([x["name"] for x in v], ["Corrections de conformité", "Contraste renforcé (AAA)"])
        self.assertEqual(m.auto_variants([]), [])

    def test_clean_variants(self):
        self.assertEqual(m.clean_variants([{"css": "a{}"}])[0]["name"], "Variante 1")
        for bad in ("<style>a{}</style>", "@import 'x.css';", "a{background:url(https://x/y.png)}"):
            with self.assertRaises(ValueError): m.clean_variants([{"name": "x", "css": bad}])
        with self.assertRaises(ValueError): m.clean_variants([])
        self.assertEqual(m.clean_variants([{"name": "x", "css": "a{background:url(data:image/png;base64,AA)}"}])[0]["origin"], "manuel")

    def test_presentation(self):
        audit = lambda score, rules: {"index": 2, "action": "audit", "ok": True, "shot": "step2.png", "score": score, "findings": [{"rule": r} for r in rules]}
        base = {"id": 1, "status": "ok", "results": [{"index": 1, "action": "goto", "ok": True, "shot": "step1.png"}, audit(70, ["contraste", "contraste", "cible-petite"])]}
        v0 = {"id": 5, "status": "ok", "results": [audit(95, ["cible-petite"])]}
        mk = {"name": "M", "status": "presentee", "variants": [{"name": "A", "css": "a{}"}, {"name": "B", "css": "b{}"}]}
        sl = m.presentation(mk, base, {0: v0}, {0: {"significant": 1, "steps": []}})
        self.assertEqual([s["kind"] for s in sl], ["avant", "proposition", "variante", "regles", "decision"])
        self.assertEqual((sl[0]["score"], len(sl[0]["shots"])), (70, 2))
        self.assertEqual((sl[1]["score"], sl[1]["delta"], sl[1]["diff"]["significant"]), (95, 25, 1))
        self.assertFalse(sl[2]["rendered"]); self.assertIsNone(sl[2]["delta"])
        self.assertEqual(sl[3]["rows"], [{"rule": "cible-petite", "before": 1, "after": [1, None]}, {"rule": "contraste", "before": 2, "after": [0, None]}])
        subj, desc = m.ticket_text(dict(mk, decision_comment="ok pour moi"), {"name": "Tour"}, {"name": "Hub"}, mk["variants"][0], sl)
        self.assertEqual(subj, "[QA maquette] Tour — A"); self.assertIn("95/100 (+25", desc); self.assertIn("a{}", desc); self.assertIn("ok pour moi", desc)


if __name__ == "__main__":
    unittest.main()
