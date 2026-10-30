# -*- coding: utf-8 -*-
"""#928 : intégration de la commande « acces-services » à l'agent (tâche de fond, mesure poussée, pas de secret)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tests.test_si_agent as _base  # noqa: E402


class AccesServicesAgent(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def test_commande_en_fond_et_mesure(self):
        from si_agent import accesservices
        vus = {}

        def faux_mesurer(cibles, timeout=10.0, **kw):
            vus["cibles"] = cibles
            vus["timeout"] = timeout
            return {"at": "2026-10-30T10:00:00Z", "sites": [{"nom": "GED", "brut": {"total_ms": 120, "status": 200, "erreur": None},
                    "authentifie": {"total_ms": 400, "status": 200, "connecte": True, "erreur": None}, "constats": []}],
                    "alerts": []}

        accesservices.mesurer = faux_mesurer                 # la vraie mesure est testée ailleurs
        r = self.agent.execute_command({"id": "c-as", "type": "acces-services", "params": {
            "cibles": [{"nom": "GED", "url": "https://ged.exemple/", "auth": {"type": "basic", "user": "francois", "secret": "S3"}}],
            "timeout": 7}})
        self.assertTrue(r["ok"] and r["result"]["started"] and r["result"]["sites"] == 1)
        self.agent._acces.join(5)
        self.assertEqual(vus["timeout"], 7)
        self.assertEqual(vus["cibles"][0]["auth"]["secret"], "S3", "le secret est bien passé en mémoire à la mesure")
        m = self.agent.queue.latest(task="acces-services", limit=1)[0]
        self.assertTrue(m["data"]["sites"][0]["authentifie"]["connecte"])
        # un second lancement pendant que le premier tourne serait refusé (ici le 1er est fini)
        self.assertFalse(self.agent.execute_command({"id": "c-x", "type": "acces-services", "params": {"cibles": []}})["ok"])

    def test_refus_concurrent(self):
        import threading
        from si_agent import accesservices
        barriere = threading.Event()
        accesservices.mesurer = lambda cibles, timeout=10.0, **kw: (barriere.wait(5), {"at": "t", "sites": [], "alerts": []})[1]
        r1 = self.agent.execute_command({"id": "c1", "type": "acces-services", "params": {"cibles": [{"url": "https://a/"}]}})
        self.assertTrue(r1["ok"])
        r2 = self.agent.execute_command({"id": "c2", "type": "acces-services", "params": {"cibles": [{"url": "https://b/"}]}})
        self.assertFalse(r2["ok"])
        self.assertIn("déjà en cours", r2["error"])
        barriere.set()
        self.agent._acces.join(5)


if __name__ == "__main__":
    unittest.main()
