# -*- coding: utf-8 -*-
"""#828 apprentissage : étiquettes depuis les décisions humaines, exemples au format de production, découpage, mesure, API."""
import json
import os
import sys
import tempfile
import time
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import apprentissage as A  # noqa: E402
import priorites as P  # noqa: E402

ARTS = [
    {"id": 1, "titre": "Faille exploitée OpenSSH", "niveau": "alerte", "publie": 1.7e9, "statut": "a_traiter", "statut_par": "alice", "kev": True,
     "impacts": {"actifs": ["srv-a"], "priorite": "P1"}},
    {"id": 2, "titre": "Bruit marketing", "publie": 1.7e9, "rejet": {"type": "source"}},
    {"id": 3, "titre": "Avis sans objet", "publie": 1.7e9, "statut": "non_applicable", "statut_par": "bob"},
    {"id": 4, "titre": "Signalé automatiquement", "publie": 1.7e9, "statut": "a_traiter", "statut_par": "veille", "impacts": {"actifs": ["x"]}},
    {"id": 5, "titre": "Pas décidé", "publie": 1.7e9},
    {"id": 6, "titre": "Traité, pas chez nous", "publie": 1.7e9, "statut": "traite", "statut_par": "alice"},
]


class Pur(unittest.TestCase):
    def test_etiquettes(self):
        self.assertEqual([A.etiquette(a) for a in ARTS], [
            {"urgent": True, "gravite": "critique"}, {"urgent": False, "gravite": "faible"}, {"urgent": False, "gravite": "faible"},
            None, None, {"urgent": False, "gravite": "faible"}])

    def test_exemples_et_mesure(self):
        ex, st = A.construire(ARTS, P.QUESTIONS)
        self.assertEqual((st["exemples"], st["urgents"], st["gravites"]), (4, 1, {"critique": 1, "faible": 3}))
        e = ex[0]
        self.assertIn("Faille exploitée OpenSSH", e["messages"][0]["content"])
        self.assertIn('"urgent"', e["messages"][0]["content"])                      # consigne du décideur de production
        self.assertEqual(json.loads(e["messages"][1]["content"]), [{"urgent": 0.9, "gravite": "critique"}])
        self.assertEqual(A.part(1), A.part(1))
        self.assertEqual({A.part(i) for i in range(500)}, {"train", "test"})
        m = A.mesurer(ex[:2], [{"urgent": {"noul": 0.8}, "gravite": {"label": "critique"}}, None])
        self.assertEqual((m["n"], m["valides"], m["accord_urgent"], m["accord_gravite"]), (2, 1, 1.0, 1.0))


class Api(unittest.TestCase):
    def test_parcours(self):
        c = appmod.app.test_client()
        avant = A.source_articles
        A.source_articles = lambda jours: [dict(a, id=a["id"] * 1000 + k) for k in range(30) for a in ARTS]
        try:
            j = c.get("/apprentissage/jeu").json
            self.assertEqual(j["stats"]["exemples"], 120)
            lignes = c.get("/apprentissage/jeu?format=jsonl&part=train").data.decode().strip().split("\n")
            self.assertEqual(len(lignes), j["stats"]["train"])
            self.assertEqual(json.loads(lignes[0])["messages"][1]["role"], "assistant")
            self.assertEqual(c.post("/apprentissage/entrainements", json={"nom": "x"}).status_code, 400)
            e = c.post("/apprentissage/entrainements", json={"nom": "décideur LoRA 1", "modele_base": "Qwen3-4B", "hote": "ia-prod", "jeu": j["stats"]}).json
            self.assertEqual(c.post("/apprentissage/entrainements/%d/evaluer" % e["id"], json={}).status_code, 400)   # pas de modèle produit
            c.put("/apprentissage/entrainements/%d" % e["id"], json={"nom": "décideur LoRA 1", "modele_base": "Qwen3-4B", "statut": "termine", "modele_produit": "decideur-lora:1"})
            A.evaluer_lot = lambda etats_, q, m: [{"urgent": {"noul": 0.9 if "OpenSSH" in s else 0.1}, "gravite": {"label": "critique" if "OpenSSH" in s else "faible"}} for s in etats_]
            r = c.post("/apprentissage/entrainements/%d/evaluer" % e["id"], json={})
            self.assertEqual(r.status_code, 202)
            for _ in range(50):
                ev = [x for x in c.get("/apprentissage/entrainements").json["entrainements"] if x["id"] == e["id"]][0]["evaluation"]
                if ev:
                    break
                time.sleep(0.05)
            self.assertEqual((ev["modele"], ev["accord_urgent"], ev["accord_gravite"]), ("decideur-lora:1", 1.0, 1.0))
            self.assertEqual(c.put("/apprentissage/entrainements/999", json={"nom": "x", "modele_base": "y"}).status_code, 404)
        finally:
            A.source_articles = avant


if __name__ == "__main__":
    unittest.main()
