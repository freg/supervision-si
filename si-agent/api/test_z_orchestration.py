# -*- coding: utf-8 -*-
"""#832 tuile Orchestration : clusters (sonde orchestration), placement automatique, commandes, masquage du jeton."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import orchestration as OR  # noqa: E402
import store  # noqa: E402

PRET = {"nom": "n", "pret": True}


class Pur(unittest.TestCase):
    def test_placer(self):
        cl = [{"agent_id": "a", "online": True, "k3s": {"installe": True, "noeuds": [PRET], "charges": [1, 2]}, "nomad": {"installe": False}},
              {"agent_id": "b", "online": True, "k3s": {"installe": True, "noeuds": [PRET, PRET], "charges": [1, 2]}, "nomad": {"installe": True, "noeuds": [], "charges": []}},
              {"agent_id": "c", "online": False, "k3s": {"installe": True, "noeuds": [PRET], "charges": []}}]
        self.assertEqual(OR.placer(cl, "k3s"), "b")
        self.assertEqual(OR.placer(cl, "nomad"), "b")
        self.assertIsNone(OR.placer(cl[:1], "nomad"))


class Api(unittest.TestCase):
    def test_parcours(self):
        db, c = appmod.DB_PATH, appmod.app.test_client()
        store.create_agent(db, "orch-hote", "siege")
        self.assertIn("activer la sonde", c.post("/orchestration/commande", json={"agent": "orch-hote", "action": "etat"}).json["error"])
        store.ingest_measurements(db, "orch-hote", [{"task": "plugin:orchestration", "at": "2026-10-22T12:00:00Z", "ok": True,
            "data": {"moteurs": {"k3s": {"installe": True, "noeuds": [PRET], "charges": [{"moteur": "k3s", "nom": "web", "espace": "si"}]}}, "expirees": []}}])
        e = c.get("/orchestration").json
        cl = next(x for x in e["clusters"] if x["agent_id"] == "orch-hote")
        self.assertEqual((cl["k3s"]["charges"][0]["nom"], cl["nomad"]["installe"]), ("web", False))
        self.assertIn("vms", e["machines"])
        r = c.post("/orchestration/commande", json={"agent": "orch-hote", "action": "deployer", "moteur": "k3s", "nom": "web2", "image": "nginx:1.27-alpine", "port": 80, "ttl_h": 4})
        self.assertEqual((r.status_code, r.json["agent"]), (201, "orch-hote"))
        self.assertIn("image", c.post("/orchestration/commande", json={"agent": "orch-hote", "action": "deployer", "moteur": "k3s", "nom": "x", "image": "a b"}).json["error"])
        c.post("/orchestration/commande", json={"agent": "orch-hote", "action": "rejoindre", "moteur": "k3s", "serveur": "https://srv:6443", "jeton": "K10SECRETSECRETSECRET::server:x"})
        cmds = c.get("/orchestration").json["commandes"]
        self.assertTrue(any(x["params"].get("jeton") == "(masqué)" for x in cmds))
        self.assertNotIn("K10SECRET", str(cmds))
        self.assertNotIn("K10SECRET", str(c.get("/events?limit=50").json))


if __name__ == "__main__":
    unittest.main()
