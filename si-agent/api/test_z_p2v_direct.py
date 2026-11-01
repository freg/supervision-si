"""#748 : plan « direct » (préparations source / cible, VM réceptacle, lecture par relais, image, import, nettoyage) et
exécution : valeurs produites par les préparations reportées dans les étapes suivantes, attente de image-fetched."""
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


class Direct(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        for a in ("dir-srv", "dir-pve"): store.create_agent(cls.db, a, "siege", label=a)
        pra.FETCH_TIMEOUT = 20; pra.SLEEP = lambda n: time.sleep(min(n, 0.05))

    def test_plan(self):
        plan, err = migration.build({"method": "direct", "source_agent_id": "dir-srv", "pve_agent_id": "dir-pve", "vmid": 300, "storage": "local-lvm", "os": "windows", "bwlimit_mbps": 300})
        self.assertIsNone(err)
        self.assertEqual([s["action"] for s in plan["steps"]][:8], ["checkpoint", "p2v_prepare_source", "p2v_prepare_target", "create", "p2v_fetch", "image_host", "import_disk", "p2v_cleanup"])
        self.assertEqual(plan["steps"][2]["params"]["need_bytes"], "{{need_bytes}}"); self.assertEqual(plan["steps"][5]["params"]["target"], "{{src_target}}")
        self.assertEqual(plan["steps"][4]["params"]["bwlimit_mbps"], 300.0); self.assertEqual(plan["steps"][6]["params"]["attach"], "sata0")
        self.assertIn("p2v_cleanup", [s["action"] for s in plan["rollback_steps"]])
        steps, err = pra.validate_steps(plan["steps"]); self.assertIsNone(err)
        self.assertEqual(pra.command_type(steps[1]), "p2v"); self.assertEqual(pra.command_params(steps[2])["action"], "prepare_target")

    def test_execution(self):
        body = {"method": "direct", "source_agent_id": "dir-srv", "pve_agent_id": "dir-pve", "vmid": 301, "storage": "local-lvm", "os": "windows", "save": True}
        r = self.c.post("/pra/migrations/plan", json=body); self.assertEqual(r.status_code, 201, r.json); pid = r.json["plan"]["id"]
        seen = []

        def fake_agents():
            for _ in range(600):
                time.sleep(0.03)
                for aid in ("dir-srv", "dir-pve"):
                    for c in store.list_commands(self.db, aid, status="pending"):
                        p = c.get("params") or {}
                        seen.append((aid, c["type"], p))
                        res = {}
                        if c["type"] == "p2v" and p.get("action") == "prepare_source": res = {"ok": True, "target": "D:\\\\", "need_bytes": 70 * 2**30}
                        if c["type"] == "p2v" and p.get("action") == "prepare_target": res = {"ok": True, "import_dir": "/var/lib/vz/import/p2v-vm301", "vg": "pve"}
                        store.ack_command(self.db, aid, c["id"], {"ok": True, "error": None, "result": res})
                        if c["type"] == "image_host":
                            time.sleep(0.2)
                            appmod._event("image-fetched", "info", "image reçue par le relais", agent_id="dir-pve", details={"path": "/var/lib/vz/import/p2v-vm301/x.vhdx", "name": "x.vhdx", "sha256": "0", "bytes": 1})
        threading.Thread(target=fake_agents, daemon=True).start()
        rid = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute", "actor": "freg"}).json["run_id"]
        for _ in range(100):
            time.sleep(0.05)
            if self.c.get("/pra/runs/%d" % rid).json["run"]["status"] == "paused": break
        self.assertEqual(self.c.post("/pra/runs/%d/resume" % rid).status_code, 200)
        for _ in range(300):
            time.sleep(0.05)
            run = self.c.get("/pra/runs/%d" % rid).json["run"]
            if run["status"] == "paused" and run["steps"][9]["status"] == "waiting": break
        run = self.c.get("/pra/runs/%d" % rid).json["run"]
        self.assertEqual([s["status"] for s in run["steps"][:9]], ["done"] * 9, run["steps"])
        by = {(a, p.get("action") or t): p for a, t, p in seen}
        self.assertEqual(by[("dir-pve", "prepare_target")]["need_bytes"], 70 * 2**30)
        self.assertEqual(by[("dir-pve", "fetch")]["import_dir"], "/var/lib/vz/import/p2v-vm301")
        self.assertEqual(by[("dir-srv", "image_host")]["target"], "D:\\\\")
        imp = [p for a, t, p in seen if t == "vm_action" and p.get("action") == "import_disk"][0]
        self.assertEqual(imp["source"], "/var/lib/vz/import/p2v-vm301/x.vhdx")
        self.assertEqual(by[("dir-pve", "cleanup")]["vg"], "pve")
        self.c.post("/pra/runs/%d/abort" % rid, json={})


if __name__ == "__main__":
    unittest.main()
