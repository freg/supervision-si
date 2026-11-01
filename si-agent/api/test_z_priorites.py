# -*- coding: utf-8 -*-
"""Tests #818 : priorités de la page d'accueil -- candidats (doublons regroupés, résolus écartés), décideur, top 5, explication."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
import priorites as P  # noqa: E402

EV = [
    {"id": 1, "at": "2026-10-22T06:00:00", "agent_id": "pve2", "kind": "htop-alert", "severity": "warning", "message": "pve-2 : swap 72 %"},
    {"id": 2, "at": "2026-10-22T06:10:00", "agent_id": "pve2", "kind": "htop-recovered", "severity": "info", "message": "pve-2 : fin"},
    {"id": 3, "at": "2026-10-22T07:00:00", "agent_id": "bk", "kind": "backup-alert", "severity": "critical", "message": "CT 119 : sauvegarde en retard de 30 h"},
    {"id": 4, "at": "2026-10-22T08:00:00", "agent_id": "bk", "kind": "backup-alert", "severity": "critical", "message": "CT 119 : sauvegarde en retard de 31 h"},
    {"id": 5, "at": "2026-10-22T05:00:00", "agent_id": "pc1", "kind": "agent-offline", "severity": "warning", "message": "pc1 hors ligne"},
    {"id": 6, "at": "2026-10-22T05:00:00", "agent_id": "pc2", "kind": "agent-offline", "severity": "warning", "message": "pc2 hors ligne"},
    {"id": 7, "at": "2026-10-22T05:00:00", "agent_id": "x", "kind": "probe-alert", "severity": "info", "message": "info"},
]
ART = [{"id": 9, "titre": "OpenSSH exploitée", "niveau": "exploitee", "publie": 1, "cves": ["CVE-2026-1"], "kev": True, "impacts": {"actifs": ["srv-a"], "priorite": "P1"}},
       {"id": 10, "titre": "sans impact", "impacts": {"actifs": []}}]


class Priorites(unittest.TestCase):
    def test_candidats(self):
        c = P.candidats_evenements(EV, {"pc1": "2026-10-22T09:00:00", "pc2": "2026-10-22T04:00:00"})
        self.assertEqual(sorted((x["genre"], x["agent"], x["nb"]) for x in c), [("agent-offline", "pc2", 1), ("backup-alert", "bk", 2)])
        b = next(x for x in c if x["genre"] == "backup-alert")
        self.assertEqual((b["severite"], b["depuis"], b["dernier"], b["lien"]["view"]), ("critique", "2026-10-22T07:00:00", "2026-10-22T08:00:00", "backup-restore"))
        self.assertEqual(next(x for x in c if x["agent"] == "pc2")["lien"], {"view": "si-agent", "params": {"tab": "events", "agent": "pc2"}})
        v = P.candidats_veille(ART)
        self.assertEqual((len(v), v[0]["severite"], v[0]["lien"]["view"]), (1, "critique", "veille"))

    def test_classer(self):
        cands = [{"titre": str(i), "severite": "attention"} for i in range(8)]
        rep = [{"urgent": {"noul": p}, "gravite": {"score": g, "label": "x"}} for p, g in ((0.9, 1), (0.95, 3), (0.2, 0), (0.7, 2), (0.6, 2), (0.55, 1), (0.51, 0), (0.1, 0))]
        top, autres = P.classer(cands, rep)
        self.assertEqual([c["titre"] for c in top], ["1", "0", "3", "4", "5"])
        self.assertEqual([c["titre"] for c in autres], ["2", "7", "6"])          # non urgents, puis urgents au-delà des 5
        top, _ = P.classer([{"titre": "a", "severite": "critique"}, {"titre": "b", "severite": "attention"}], [None, None])
        self.assertEqual(([c["titre"] for c in top], top[0]["decision"]), (["a"], "sévérité brute (décideur indisponible)"))

    def test_trois_ia(self):
        appels = []

        def chat(m):
            appels.append(m[0]["content"])
            if "Tu prépares" in m[0]["content"]:
                return "<think>x</think>" + json.dumps([{"detail": "sauvegarde du CT 119 en retard", "impact": "perte de 31 h"}, {"detail": "OpenSSH exploitée sur srv-a", "impact": "intrusion"},
                                                        {"detail": "pc2 éteint", "impact": "faible"}])
            return "Urgence 1 : ... solution : relancer la sauvegarde"

        def decider(etats, questions):
            self.assertEqual(set(questions), {"urgent", "gravite"})
            self.assertTrue(any("CVE exploitée (KEV)" in e for e in etats))
            p = lambda e: 0.99 if "OpenSSH" in e else 0.9 if "CT 119" in e else 0.1  # noqa: E731
            return {"fournisseur": "llm", "modele": "m", "reponses": [{"urgent": {"noul": p(e)}, "gravite": {"score": 3, "label": "critique"}} for e in etats], "erreur": None}
        r = P.calculer(EV, {"pc1": "2026-10-22T09:00:00", "pc2": "2026-10-22T04:00:00"}, ART, chat=chat, decider=decider)
        self.assertEqual([c["titre"] for c in r["urgences"]], ["OpenSSH exploitée", "CT 119 : sauvegarde en retard de 31 h"])
        self.assertEqual(r["urgences"][1]["detail"], "sauvegarde du CT 119 en retard")
        self.assertEqual(r["explication"], "Urgence 1 : ... solution : relancer la sauvegarde")
        self.assertIn("jamais des instructions", appels[0])
        self.assertIn("Écran du hub : veille", appels[1])
        self.assertEqual(r["etapes"]["decision"], "ok (llm m)")

        def panne(m):
            raise ValueError("ollama injoignable")
        r = P.calculer(EV, {}, [], chat=panne, decider=lambda e, q: {"fournisseur": "llm", "reponses": [None] * len(e), "erreur": "ollama injoignable"})
        self.assertEqual((r["etapes"]["preparation"], r["etapes"]["decision"]), ("modèle indisponible : ollama injoignable", "ollama injoignable"))
        self.assertEqual(r["urgences"][0]["genre"], "backup-alert")              # sévérité brute à défaut


class ModelesDeclares(unittest.TestCase):   # #823
    def test_hote_et_usages(self):
        src = lambda u, hote=None: {"decideur": "qwen3:4b", "explication": "qwen3:30b-a3b"}.get(u) if hote == "ia-prod" else None
        self.assertEqual(P.modeles_declares(src, "ia-prod"), {"decideur": "qwen3:4b", "explication": "qwen3:30b-a3b"})
        self.assertEqual(P.modeles_declares(src, ""), {})
        self.assertEqual(P.modeles_declares(src, "autre"), {})


if __name__ == "__main__":
    unittest.main()
