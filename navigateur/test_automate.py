"""Tests #798 : étapes de l'automate du navigateur (validation, jeu sur une page simulée, arrêt avant écriture)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import automate as A  # noqa: E402


class Page:
    def __init__(self, textes=None, echec=None):
        self.url, self.journal, self.textes, self.echec = "about:blank", [], textes or {}, echec

    def set_default_timeout(self, ms): self.delai = ms
    def goto(self, url, **kw): self.url = url; self.journal.append(("goto", url))
    def click(self, sel):
        if sel == self.echec:
            raise TimeoutError("Timeout 15000ms exceeded.\nwaiting for locator")
        self.journal.append(("click", sel))
    def fill(self, sel, val): self.journal.append(("fill", sel, val))
    def wait_for_load_state(self, *a): pass
    def wait_for_selector(self, sel, state=None): self.journal.append(("attente", sel, state))
    def inner_text(self, sel): return self.textes.get(sel, "")
    def input_value(self, sel): return "x"
    def screenshot(self, **kw): return b"jpeg"
    def title(self): return "Titre"


class Automate(unittest.TestCase):
    def test_verification(self):
        e = A.verifier_etapes([{"action": "goto", "value": "/connexion"}, {"action": "fill", "selector": "#id", "value": "alice"},
                               {"action": "click", "selector": "button[type=submit]", "ecrit": True}])
        self.assertEqual([x["action"] for x in e], ["goto", "fill", "click"])
        self.assertTrue(e[2]["ecrit"])
        for mauvais in ([], [{"action": "exec", "value": "rm"}], [{"action": "click"}], [{"action": "wait", "value": "bientôt"}], "x"):
            with self.assertRaises(ValueError):
                A.verifier_etapes(mauvais)

    def test_jeu(self):
        p = Page(textes={"body": "Bienvenue alice"})
        et = A.verifier_etapes([{"action": "goto", "value": "/"}, {"action": "fill", "selector": "#u", "value": "alice"},
                                {"action": "expect_text", "value": "Bienvenue"}, {"action": "screenshot"}])
        r = A.jouer(p, et, "https://site.example")
        self.assertEqual(r["statut"], "ok")
        self.assertEqual(p.journal[0], ("goto", "https://site.example/"))
        self.assertTrue(r["resultats"][3]["capture"])
        self.assertEqual(r["titre"], "Titre")

    def test_echec_et_arret_avant_ecriture(self):
        p = Page(echec="#ok")
        r = A.jouer(p, A.verifier_etapes([{"action": "goto", "value": "https://a.example/x"}, {"action": "click", "selector": "#ok"}, {"action": "click", "selector": "#apres"}]))
        self.assertEqual((r["statut"], len(r["resultats"])), ("ko", 2))
        self.assertIn("Timeout", r["resultats"][1]["error"])
        self.assertNotIn("\n", r["resultats"][1]["error"])
        p = Page()
        r = A.jouer(p, A.verifier_etapes([{"action": "fill", "selector": "#objet", "value": "Chauffage"}, {"action": "click", "selector": "#creer", "ecrit": True}]),
                    arret_avant_ecriture=True)
        self.assertEqual(r["statut"], "confirmation")
        self.assertNotIn(("click", "#creer"), p.journal)
        self.assertTrue(r["resultats"][-1]["attente"])


class Apprentissage(unittest.TestCase):   # #799 -- vérifié aussi dans un vrai Chromium (CDP) : enregistrement, rejeu, arrêt avant écriture
    BRUT = [{"action": "goto", "value": "https://gmao.example.org/connexion"},
            {"action": "fill", "selector": "#login", "value": "alice", "note": "Identifiant", "champ": "login", "type": "text"},
            {"action": "fill", "selector": "#login", "value": "alice", "note": "Identifiant", "champ": "login", "type": "text"},
            {"action": "fill", "selector": "input[name=\"pwd\"]", "value": "", "note": "Mot de passe", "secret": True, "type": "password"},
            {"action": "press", "selector": "input[name=\"pwd\"]", "value": "Enter", "ecrit": False},
            {"action": "fill", "selector": "#obj", "value": "Chauffage", "note": "Objet du ticket"},
            {"action": "select", "selector": "select[name=\"site\"]", "value": "b12", "note": "Site"},
            {"action": "fill", "selector": "#obj", "value": "Chauffage", "note": "Objet du ticket"},
            {"action": "fill", "selector": "#obj", "value": "Chauffage bât. B", "note": "Objet du ticket"},
            {"action": "click", "selector": "#creer", "note": "Créer le ticket", "ecrit": True}]

    def test_nettoyage_et_parametres(self):
        et = A.nettoyer_enregistrement(self.BRUT)
        self.assertEqual(sum(1 for x in et if x.get("selector") == "#login"), 1)
        par, params, base = A.parametrer(et)
        self.assertEqual(base, "https://gmao.example.org")
        self.assertEqual(par[0], {"action": "goto", "value": "/connexion"})
        self.assertEqual([p["nom"] for p in params], ["identifiant", "mot_de_passe", "objet_du_ticket", "site"])
        self.assertEqual(params[1], {"nom": "mot_de_passe", "defaut": "", "secret": True, "note": "Mot de passe"})
        objets = [x["value"] for x in par if x.get("selector") == "#obj"]
        self.assertTrue(objets and all(v == "{{objet_du_ticket}}" for v in objets))     # même champ = même paramètre
        self.assertTrue(par[-1]["ecrit"])
        self.assertFalse(any("champ" in x or "type" in x for x in par))
        self.assertEqual(A.verifier_etapes(par)[-1]["action"], "click")

    def test_geste_secret_jamais_garde(self):
        n = A.Navigateur("http://127.0.0.1:1")
        n.rec["actif"] = True
        n._geste(None, {"action": "fill", "selector": "#p", "value": "motdepasse", "secret": True})
        self.assertEqual(n.rec["brut"][0]["value"], "")
        n.rec["actif"] = False
        n._geste(None, {"action": "click", "selector": "#x"})
        self.assertEqual(len(n.rec["brut"]), 1)


if __name__ == "__main__":
    unittest.main()
