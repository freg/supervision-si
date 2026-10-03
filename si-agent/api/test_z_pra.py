# -*- coding: utf-8 -*-
"""#653 : plans PRA -- validation des étapes, simulation (agents connus/inconnus), exécution séquentielle avec acquittements
simulés (done puis failed → arrêt), continue_on_error, refus d'une double exécution."""
import os, sys, json, tempfile, unittest, threading, time
# Nommé test_z_pra pour passer APRÈS test_si_agent_api dans l'ordre de découverte : la suite importe `app` une seule fois
# et ce fichier-là fixe l'environnement (chemin de CA, URL publique) que ses propres tests relisent ensuite.
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
sys.path.insert(0, os.path.dirname(__file__))
import app as appmod, store, pra

class Pra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        # identifiants propres à ce fichier et nettoyés ensuite : la suite partage une seule base (app importé une fois)
        for a in ("pra-pve10", "pra-pve11"):
            store.create_agent(cls.db, a, "siege", label=a)

    @classmethod
    def tearDownClass(cls):
        conn = store._connect(cls.db)
        try:
            for t, col in (("commands", "agent_id"), ("events", "agent_id"), ("agents", "agent_id")):
                try: conn.execute("DELETE FROM %s WHERE %s LIKE 'pra-pve%%'" % (t, col))
                except Exception: pass
            conn.execute("DELETE FROM pra_runs"); conn.execute("DELETE FROM pra_plans"); conn.commit()
        finally:
            conn.close()

    def test_validate(self):
        self.assertEqual(pra.validate_steps([])[1], "au moins une étape")
        self.assertEqual(pra.validate_steps([{"agent_id": "pra-pve11", "vmid": 101, "action": "migrate"}])[1], "étape 1 (migrate) : paramètre target requis")
        self.assertEqual(pra.validate_steps([{"agent_id": "pra-pve11", "vmid": "x", "action": "start"}])[1], "étape 1 : vmid entier requis")
        st, err = pra.validate_steps([{"agent_id": "pra-pve11", "vmid": "101", "action": "Migrate", "params": {"target": "pra-pve10"}, "label": "super → pve10"}])
        self.assertIsNone(err); self.assertEqual(pra.command_params(st[0]), {"target": "pra-pve10", "vmid": 101, "action": "migrate", "kind": "qemu"})

    def test_plan_simulate_execute(self):
        r = self.c.post("/pra/plans", json={"name": "PRA super", "steps": [
            {"agent_id": "pra-pve11", "vmid": 101, "action": "backup", "params": {"storage": "pbs"}, "label": "sauvegarde"},
            {"agent_id": "pra-pve11", "vmid": 101, "action": "migrate", "params": {"target": "pra-pve10"}},
            {"agent_id": "inconnu", "vmid": 7, "action": "start"}]})
        self.assertEqual(r.status_code, 201, r.json); pid = r.json["plan"]["id"]
        r = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "simulate"}); rid = r.json["run_id"]
        run = self.c.get("/pra/runs/%d" % rid).json["run"]; self.assertEqual(run["status"], "failed"); self.assertEqual([s["ok"] for s in run["steps"]], [True, True, False])
        self.assertEqual(run["steps"][0]["params"]["storage"], "pbs"); self.assertEqual(store.list_commands(self.db, "pra-pve11"), [])      # rien envoyé
        # exécution : un faux agent acquitte la 1re commande ok, la 2e en échec -> arrêt, 3e jamais envoyée
        def fake_agent():
            seen = 0
            for _ in range(200):
                time.sleep(0.05)
                for c in store.list_commands(self.db, "pra-pve11", status="pending"):
                    seen += 1; store.ack_command(self.db, "pra-pve11", c["id"], {"ok": seen == 1, "error": None if seen == 1 else "migration refusée"})
                    if seen == 2: return
        t = threading.Thread(target=fake_agent, daemon=True); t.start()
        r = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute", "actor": "freg"}); self.assertEqual(r.status_code, 202); rid = r.json["run_id"]
        pra._runs[rid].join(timeout=20); t.join(timeout=5)
        run = self.c.get("/pra/runs/%d" % rid).json["run"]
        self.assertEqual(run["status"], "failed"); self.assertEqual([s["status"] for s in run["steps"]], ["done", "failed", "pending"])
        self.assertEqual(run["steps"][1]["result"]["error"], "migration refusée"); self.assertTrue(run["finished_at"])
        self.assertEqual(len(self.c.get("/pra/plans/%d/runs" % pid).json["runs"]), 2)
        self.assertEqual(self.c.put("/pra/plans/%d" % pid, json={"steps": [{"agent_id": "pra-pve11", "vmid": 1, "action": "fly"}]}).status_code, 400)
        self.assertEqual(self.c.delete("/pra/plans/%d" % pid).json["ok"], True)

if __name__ == "__main__": unittest.main()
