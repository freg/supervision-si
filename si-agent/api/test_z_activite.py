# -*- coding: utf-8 -*-
"""#830 activité de si-agent-api (pied de page du hub) : en cours, récentes, priorités instrumentées."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activite as AC  # noqa: E402
import app as appmod  # noqa: E402
import priorites as P  # noqa: E402


class Activite(unittest.TestCase):
    def test_resume(self):
        r = AC.resume([{"id": 2, "debut": 990.0, "fin": None}, {"id": 1, "debut": 900.0, "fin": 910.0, "ok": 1}], 1000.0)
        self.assertEqual((r["en_cours"][0]["depuis_s"], r["recentes"][0]["duree_s"]), (10, 10.0))

    def test_api_et_priorites(self):
        c = appmod.app.test_client()
        with AC.suivre("ia", "travail de test"):
            self.assertIn("travail de test", [x["detail"] for x in c.get("/etat-hub").json["en_cours"]])
        P.calculer([{"id": 1, "kind": "disk-full", "severity": "critical", "message": "disque plein", "agent_id": "a", "at": "2026-10-22T10:00:00Z"}], {}, [],
                   chat=lambda m: "[]", decider=lambda e, q: {"fournisseur": "t", "modele": "m", "erreur": None,
                                                             "reponses": [{"urgent": {"noul": 0.9}, "gravite": {"score": 0.9, "label": "haute"}}] * len(e)},
                   modeles={}, consignes={})
        faits = [x["detail"] for x in c.get("/etat-hub").json["recentes"]]
        self.assertTrue(any(f.startswith("Priorités · préparation") for f in faits), faits)
        self.assertIn("Priorités · décideur", faits)



class CommandesSuivies(unittest.TestCase):
    """#837 : commandes Émulation / Orchestration dans le pied de page, avec la vue à ouvrir."""
    def test_commandes(self):
        import activite as A2
        rows = [{"id": "c1", "agent_id": "pcia", "type": "orchestration", "params": '{"action": "installer", "moteur": "nomad"}',
                 "created_at": "2026-10-22T10:00:00+00:00", "status": "pending", "result": None, "acked_at": None},
                {"id": "c2", "agent_id": "pcia", "type": "emulation", "params": '{"action": "lancer", "instance": "emu-rpi0w-1"}',
                 "created_at": "2026-10-22T09:00:00Z", "status": "failed", "result": '{"ok": false, "error": "QEMU absent"}', "acked_at": "2026-10-22T09:01:00Z"}]
        t = A2._ts("2026-10-22T10:05:00Z")
        ec, rc = A2.commandes_suivies(rows, t)
        self.assertEqual((ec[0]["vue"], ec[0]["depuis_s"], ec[0]["detail"]), ("orchestration", 300, "orchestration : installer nomad · pcia"))
        self.assertEqual((rc[0]["vue"], rc[0]["ok"], rc[0]["erreur"], rc[0]["duree_s"]), ("emulation", False, "QEMU absent", 60.0))
        self.assertEqual(A2.commandes_suivies(rows[:1], t + 7 * 3600), ([], []))   # en attente depuis plus de 6 h : abandonnée


if __name__ == "__main__":
    unittest.main()
