# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decideur as D  # noqa: E402

Q = {"urgent": {"type": "noul", "instructions": "Action dans les heures qui viennent ?"},
     "gravite": {"type": "score", "instructions": "Gravité", "criteria": ["faible", "moyenne", "haute", "critique"]},
     "genre": {"type": "choice", "instructions": "Domaine", "criteria": {"securite": "faille, intrusion", "disponibilite": "service coupé", "sauvegarde": "copie manquante"}}}


class Decideur(unittest.TestCase):
    def test_valider(self):
        self.assertIsNone(D.valider(Q))
        self.assertIn("type", D.valider({"x": {"type": "autre", "instructions": "i"}}))
        self.assertIn("2 à 10", D.valider({"x": {"type": "score", "instructions": "i", "criteria": ["a"]}}))
        self.assertIn("instructions", D.valider({"x": {"type": "noul"}}))

    def test_prompt_et_lecture(self):
        p = D.prompt_llm(["disque plein sur srv-a", {"titre": "CVE exploitée"}], Q)
        self.assertIn('"genre" (une option exactement parmi : securite = faille, intrusion', p)
        self.assertIn('2. {"titre": "CVE exploitée"}', p)
        rep = '<think>hmm</think>Voici : [{"urgent": 0.9, "gravite": "Haute", "genre": "disponibilite"}, {"urgent": "oui", "gravite": "critique", "genre": "sécurité"}]'
        a = D.lire_llm(rep, Q, 3)
        self.assertEqual((a[0]["urgent"]["noul"], a[0]["gravite"]["score"], a[0]["gravite"]["label"], a[0]["genre"]["choice"]), (0.9, 2, "haute", "disponibilite"))
        self.assertIsNone(a[1])                                    # « sécurité » accentué hors des options : réponse rejetée
        self.assertIsNone(a[2])                                    # état sans réponse
        self.assertEqual(D.lire_llm('{"urgent": 0.1, "gravite": "faible", "genre": "sauvegarde"} puis rien', Q, 1)[0]["genre"]["choice"], "sauvegarde")

    def test_jev(self):
        rep = {"answers": {"urgent": {"type": "noul", "noul": 0.97}, "gravite": {"type": "score", "score": 3, "legend": ["faible", "moyenne", "haute", "critique"], "confidence": 0.8},
                           "genre": {"type": "choice", "choice": "securite", "confidence": 0.9, "probabilities": {"securite": 0.9}}}, "model": "jev-1.13.0"}
        n = D.normaliser_jev(rep, Q)
        self.assertEqual((n["urgent"]["noul"], n["gravite"]["label"], n["genre"]["choice"]), (0.97, "critique", "securite"))
        appels = []
        r = D.decider_lot(["a", "b"], Q, {"fournisseur": "jev", "url": "http://decideur:8094"}, post=lambda u, c, e: appels.append((u, c, e)) or rep)
        self.assertEqual((r["modele"], len(r["reponses"]), appels[0][0], appels[0][1]["state"]), ("jev-1.13.0", 2, "http://decideur:8094/v1/systemone", "a"))
        self.assertIn("TYPESAFE_API_KEY", D.decider_lot(["a"], Q, {"fournisseur": "typesafe", "cle": ""})["erreur"])
        r = D.decider_lot(["a"], Q, {"fournisseur": "typesafe", "cle": "k"}, post=lambda u, c, e: appels.append((u, c, e)) or rep)
        self.assertEqual((appels[-1][0], appels[-1][2]), (D.TYPESAFE_URL, {"Authorization": "Bearer k"}))

    def test_llm_par_lots(self):
        vus = []

        def chat(m, url, modele):
            n = m[0]["content"].count("\n") and len([l for l in m[0]["content"].split("États :\n")[1].splitlines() if l.strip()])
            vus.append(n)
            return json.dumps([{"urgent": 0.2, "gravite": "faible", "genre": "sauvegarde"}] * n)
        r = D.decider_lot(["e%d" % i for i in range(30)], Q, {"fournisseur": "llm"}, chat=chat)
        self.assertEqual((vus, len(r["reponses"]), r["erreur"]), ([25, 5], 30, None))

        def panne(*a):
            raise ValueError("http://ollama:11434/v1 injoignable")
        self.assertIn("injoignable", D.decider_lot(["e"], Q, {"fournisseur": "llm"}, chat=panne)["erreur"])


if __name__ == "__main__":
    unittest.main()
