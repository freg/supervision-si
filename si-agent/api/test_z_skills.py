# -*- coding: utf-8 -*-
"""#827 skills : défauts branchés sur le code, validation, versions, restauration, priorités, essai."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import priorites as P  # noqa: E402
import skills as S  # noqa: E402


class Pur(unittest.TestCase):
    def test_valider(self):
        sysd = {d["id"]: d for d in S.defauts()}
        self.assertIsNone(S.valider({"texte": "Consigne"}, sysd["priorites-preparation"])[1])
        self.assertIn("inconnues", S.valider({"texte": json.dumps({"autre": {"instructions": "x"}})}, sysd["priorites-decideur"])[1])
        self.assertIn("JSON", S.valider({"texte": "pas du json"}, sysd["priorites-decideur"])[1])
        self.assertIn("identifiant", S.valider({"id": "A B", "usage": "assistant", "texte": "x"})[1])
        self.assertIn("usage", S.valider({"id": "mon-skill", "usage": "autre", "texte": "x"})[1])
        s, e = S.valider({"id": "mon-skill", "usage": "assistant", "texte": "Réponds court."})
        self.assertEqual((s["type"], s["systeme"]), ("consigne", 0))

    def test_questions_effectives(self):
        q = P.questions_effectives({"urgent": {"instructions": "Seulement si un service client est coupé."}, "gravite": {"criteria": ["a", "b"]}, "intrus": {"x": 1}})
        self.assertEqual(q["urgent"]["instructions"], "Seulement si un service client est coupé.")
        self.assertEqual(q["gravite"]["criteria"], P.QUESTIONS["gravite"]["criteria"])   # nombre de critères imposé
        self.assertNotIn("intrus", q)
        self.assertEqual(q["urgent"]["type"], "noul")


class Api(unittest.TestCase):
    def test_parcours(self):
        c = appmod.app.test_client()
        lst = {s["id"]: s for s in c.get("/skills").json["skills"]}
        self.assertFalse(lst["priorites-explication"]["personnalise"])
        self.assertEqual(lst["priorites-explication"]["texte"], P.CONSIGNE_EXPLICATION)
        self.assertEqual(c.put("/skills/priorites-explication", json={"texte": "Explique en trois lignes.", "par": "alice"}).status_code, 200)
        self.assertEqual(c.put("/skills/priorites-explication", json={"texte": "Explique en deux lignes."}).json["version"], 2)
        self.assertEqual(S.textes_actifs(("priorites-explication",)), {"priorites-explication": "Explique en deux lignes."})
        h = c.get("/skills/priorites-explication/historique").json["versions"]
        self.assertEqual([v["version"] for v in h], [2, 1])
        self.assertEqual(c.post("/skills/priorites-explication/restaurer", json={"version": 1}).json["version"], 3)
        self.assertEqual(S.textes_actifs(("priorites-explication",))["priorites-explication"], "Explique en trois lignes.")
        # la consigne personnalisée sert aux priorités
        vus = []
        P.calculer([{"id": 1, "kind": "disk-full", "severity": "critical", "message": "disque plein", "agent_id": "a", "at": "2026-10-22T10:00:00Z"}], {}, [],
                   chat=lambda m: (vus.append(m[0]["content"]), "[]")[1],
                   decider=lambda e, q: {"fournisseur": "t", "modele": "m", "erreur": None, "reponses": [{"urgent": {"noul": 0.9}, "gravite": {"score": 0.9, "label": "haute"}}] * len(e)},
                   modeles={})
        self.assertTrue(any(x.startswith("Explique en trois lignes.") for x in vus), vus)
        # désactivé : retour au code
        c.put("/skills/priorites-explication", json={"texte": "Explique en trois lignes.", "actif": False})
        self.assertEqual(S.textes_actifs(("priorites-explication",)), {})
        self.assertEqual(c.delete("/skills/priorites-explication").status_code, 200)
        # skill personnel
        self.assertEqual(c.post("/skills", json={"id": "veille-resume", "usage": "veille", "texte": "Résume en 3 points."}).status_code, 201)
        self.assertEqual(c.post("/skills", json={"id": "veille-resume", "usage": "veille", "texte": "x"}).status_code, 409)
        self.assertEqual(c.put("/skills/inconnu", json={"usage": "veille", "texte": "x"}).status_code, 404)
        avant = S.essayer_hook
        S.essayer_hook = lambda sk, t: {"sortie": sk["texte"] + " | " + t, "modele": "m", "duree_s": 0}
        try:
            self.assertEqual(c.post("/skills/veille-resume/essai", json={"texte": "article", "brouillon": "Brouillon."}).json["sortie"], "Brouillon. | article")
        finally:
            S.essayer_hook = avant
        self.assertEqual(c.post("/skills/veille-resume/essai", json={}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
