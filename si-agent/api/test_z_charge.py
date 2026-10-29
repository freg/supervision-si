# -*- coding: utf-8 -*-
"""#913 : pilotage des tests de charge (poste-charge) -- lancer (épreuves + paramètres), arrêt, suivi direct.
`cd si-agent/api && python3 -m unittest test_z_charge`."""
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


class Charge(unittest.TestCase):
    def test_lancer_construit_la_commande(self):
        c = A.app.test_client()
        r = c.post("/postes/charge/lancer", json={"agent": "pc-x", "epreuves": ["disque"], "disque_mo": 64, "max_s": 30})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["epreuves"], ["disque"])
        self.assertIn("--epreuves", d["args"])
        self.assertIn("disque", d["args"])
        self.assertIn("--max-s", d["args"])
        cmds = store.list_commands(A.DB_PATH, "pc-x", limit=10)
        self.assertTrue(any(x["type"] == "run_plugin" and (x.get("params") or {}).get("id") == "poste-charge" for x in cmds))

    def test_stop_et_live(self):
        c = A.app.test_client()
        self.assertEqual(c.post("/postes/charge/stop", json={"agent": "pc-y"}).status_code, 200)
        cmds = store.list_commands(A.DB_PATH, "pc-y", limit=10)
        self.assertTrue(any(x["type"] == "stop_plugin" for x in cmds))
        live = c.get("/postes/charge/live?agent=pc-y").get_json()
        self.assertIn("live", live)
        self.assertIn("resultat", live)

    def test_validation(self):
        c = A.app.test_client()
        self.assertEqual(c.post("/postes/charge/lancer", json={}).status_code, 400)
        self.assertEqual(c.post("/postes/charge/lancer", json={"agent": "x", "epreuves": ["bidon"]}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
