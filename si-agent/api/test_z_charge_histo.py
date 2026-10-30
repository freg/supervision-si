# -*- coding: utf-8 -*-
"""#932 : historique des tests de charge -- route de consultation (relevés successifs, exclut -live)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
os.environ.setdefault("SI_AGENT_CA_FILE", os.path.join(tempfile.mkdtemp(), "ca.crt"))
sys.path.insert(0, HERE)
import app as A  # noqa: E402
import store  # noqa: E402


class ChargeHisto(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        try:
            store.create_agent(A.DB_PATH, "pc-h", "siege")
        except ValueError:
            pass

    def test_historique_date_et_exclut_live(self):
        for i, (at, verdict) in enumerate([("2026-10-30T09:00:00Z", "défaut reproduit"), ("2026-10-30T10:00:00Z", "aucun défaut reproduit")]):
            store.ingest_measurements(A.DB_PATH, "pc-h", [{"task": "plugin:poste-charge", "at": at, "agent_id": "pc-h",
                "data": {"verdict": verdict, "epreuves": ["cpu", "disque"], "processeur": {"coeurs": 20, "coeurs_finis": 20}}}])
            store.ingest_measurements(A.DB_PATH, "pc-h", [{"task": "plugin:poste-charge-live", "at": at, "agent_id": "pc-h",
                "data": {"echantillons": [1, 2]}}])
        r = self.c.get("/postes/charge/historique?agent=pc-h")
        self.assertEqual(r.status_code, 200)
        h = r.get_json()["historique"]
        self.assertEqual(len(h), 2, "deux runs, le -live exclu")
        self.assertEqual(h[0]["data"]["verdict"], "aucun défaut reproduit", "le plus récent d'abord")
        self.assertEqual(h[1]["data"]["verdict"], "défaut reproduit")
        self.assertEqual(self.c.get("/postes/charge/historique").status_code, 400)

    def test_limit(self):
        for i in range(5):
            store.ingest_measurements(A.DB_PATH, "pc-h", [{"task": "plugin:poste-charge", "at": "2026-10-29T0%d:00:00Z" % i,
                "agent_id": "pc-h", "data": {"verdict": "aucun défaut reproduit"}}])
        self.assertEqual(len(self.c.get("/postes/charge/historique?agent=pc-h&limit=2").get_json()["historique"]), 2)


if __name__ == "__main__":
    unittest.main()
