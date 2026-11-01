"""#750 : plan de rapatriement d'un CT / d'une VM depuis un nœud Proxmox distant (export + restauration, vérification,
transition, destruction par tranches) et exécution : attente de xfer-done / xfer-failed portant l'id de la commande."""
import os
import sys
import tempfile
import threading
import time
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import migration  # noqa: E402
import pra  # noqa: E402
import store  # noqa: E402


class Repatriate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        store.create_agent(cls.db, "rep-pve", "siege", label="rep-pve")
        pra.XFER_TIMEOUT = 20; pra.SLEEP = lambda n: time.sleep(min(n, 0.05))

    def test_plan(self):
        plan, err = migration.build({"method": "repatriate", "pve_agent_id": "rep-pve", "remote": "pve-a", "vmid": 109, "newid": 9109, "storage": "local-zfs", "bwlimit_mbps": 400})
        self.assertIsNone(err)
        self.assertEqual([s["action"] for s in plan["steps"]], ["checkpoint", "xfer_export", "xfer_verify", "checkpoint", "xfer_destroy"])
        self.assertEqual(plan["steps"][4]["params"]["confirm"], "109"); self.assertEqual(plan["steps"][4]["params"]["window"], "20:00-07:00")
        self.assertEqual(plan["rollback_steps"], [])
        steps, err = pra.validate_steps(plan["steps"]); self.assertIsNone(err)
        self.assertEqual(pra.command_type(steps[1]), "xfer"); self.assertEqual(pra.command_params(steps[4])["action"], "destroy")
        for bad, msg in (({"remote": "a b"}, "remote"), ({"vmid": 50}, "≥ 100"), ({"window": "20h"}, "window"), ({"storage": ""}, "storage")):
            b = {"method": "repatriate", "pve_agent_id": "rep-pve", "remote": "pve-a", "vmid": 109, "storage": "local-zfs"}; b.update(bad)
            self.assertIn(msg, migration.build(b)[1])
        _, err = pra.validate_steps([{"agent_id": "rep-pve", "action": "xfer_destroy", "params": {"remote": "a", "vmid": 109, "copy": 9109, "confirm": "108"}}])
        self.assertIn("confirm", err)

    def test_execution(self):
        r = self.c.post("/pra/migrations/plan", json={"method": "repatriate", "pve_agent_id": "rep-pve", "remote": "pve-a", "vmid": 102, "newid": 9102, "storage": "local-zfs", "window": "", "save": True})
        self.assertEqual(r.status_code, 201, r.json); pid = r.json["plan"]["id"]
        seen = []

        def fake_agent():
            for _ in range(900):
                time.sleep(0.03)
                for c in store.list_commands(self.db, "rep-pve", status="pending"):
                    p = c.get("params") or {}; seen.append(p.get("action"))
                    store.ack_command(self.db, "rep-pve", c["id"], {"ok": True, "error": None, "result": {"ok": True}})
                    time.sleep(1.1)                 # UNIQUE(agent, source, at, kind) : un xfer-done par seconde
                    ok = p.get("action") != "verify" or len(seen) > 0
                    appmod._event("xfer-done" if ok else "xfer-failed", "info", "%s fini" % p.get("action"), agent_id="rep-pve",
                                  details={"command": c["id"], "action": p.get("action"), "result": {"identical": True} if p.get("action") == "verify" else {}})
        threading.Thread(target=fake_agent, daemon=True).start()
        rid = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute", "actor": "freg"}).json["run_id"]

        def wait(status):
            for _ in range(300):
                time.sleep(0.05)
                run = self.c.get("/pra/runs/%d" % rid).json["run"]
                if run["status"] == status: return run
            self.fail("statut %s jamais atteint (%s) %s" % (status, run["status"], run["steps"]))
        wait("paused"); self.assertEqual(self.c.post("/pra/runs/%d/resume" % rid).status_code, 200)
        run = wait("paused")                        # transition 2 : après export + vérification
        self.assertEqual(seen, ["export", "verify"])
        self.assertEqual(run["steps"][2]["result"]["outcome"], {"identical": True})
        self.assertEqual(self.c.post("/pra/runs/%d/resume" % rid).status_code, 200)
        run = wait("done")
        self.assertEqual(seen, ["export", "verify", "destroy"])

    def test_failure_stops_plan(self):
        plan, _ = migration.build({"method": "repatriate", "pve_agent_id": "rep-pve", "remote": "pve-a", "vmid": 110, "storage": "local-zfs"})
        steps, _ = pra.validate_steps(plan["steps"][1:3])          # export puis vérification, sans transition

        def fake():
            for _ in range(300):
                time.sleep(0.03)
                for c in store.list_commands(self.db, "rep-pve", status="pending"):
                    store.ack_command(self.db, "rep-pve", c["id"], {"ok": True, "error": None, "result": {}})
                    appmod._event("xfer-failed", "warning", "vzdump distant : code 255", agent_id="rep-pve", details={"command": c["id"]})
        threading.Thread(target=fake, daemon=True).start()
        conn = store._connect(self.db)
        try:
            cur = conn.execute("INSERT INTO pra_runs (plan_id, mode, status, started_at, steps) VALUES (0, 'execute', 'running', ?, '[]')", (store.now_iso(),)); conn.commit(); rid = cur.lastrowid
        finally:
            conn.close()
        self.assertEqual(pra.execute(self.db, {"name": "t", "steps": steps}, rid, False), "failed")


if __name__ == "__main__":
    unittest.main()
