"""#751 : plan « lan » (récepteur sur le nœud, le poste pousse son image) -- jeton et URL du récepteur reportés dans
l'étape image_host, attente de image-fetched émis par le nœud."""
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


class Lan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        for a in ("lan-srv", "lan-pve"): store.create_agent(cls.db, a, "siege", label=a)
        pra.FETCH_TIMEOUT = 20; pra.SLEEP = lambda n: time.sleep(min(n, 0.05))

    def test_plan(self):
        plan, err = migration.build({"method": "lan", "source_agent_id": "lan-srv", "pve_agent_id": "lan-pve", "vmid": 310, "storage": "local-lvm", "os": "windows", "source_ip": "192.0.2.20"})
        self.assertIsNone(err)
        acts = [s["action"] for s in plan["steps"]]
        self.assertEqual(acts[:8], ["checkpoint", "p2v_prepare_source", "p2v_prepare_target", "create", "p2v_receive", "image_host", "import_disk", "p2v_cleanup"])
        self.assertNotIn("p2v_fetch", acts)
        self.assertEqual(plan["steps"][4]["params"], {"import_dir": "{{import_dir}}", "source_ip": "192.0.2.20", "port": 6461})
        self.assertEqual(plan["steps"][5]["params"]["push_token"], "{{push_token}}")
        steps, err = pra.validate_steps(plan["steps"]); self.assertIsNone(err)
        self.assertEqual(pra.command_params(steps[4])["action"], "receive")

    def test_execution(self):
        r = self.c.post("/pra/migrations/plan", json={"method": "lan", "source_agent_id": "lan-srv", "pve_agent_id": "lan-pve", "vmid": 311, "storage": "local-lvm", "save": True})
        self.assertEqual(r.status_code, 201, r.json); pid = r.json["plan"]["id"]
        seen = []

        def fake_agents():
            for _ in range(600):
                time.sleep(0.03)
                for aid in ("lan-srv", "lan-pve"):
                    for c in store.list_commands(self.db, aid, status="pending"):
                        p = c.get("params") or {}; seen.append((aid, c["type"], p)); res = {}
                        if p.get("action") == "prepare_source": res = {"ok": True, "target": "D:\\\\", "need_bytes": 2**30}
                        if p.get("action") == "prepare_target": res = {"ok": True, "import_dir": "/var/lib/vz/import/p2v-vm311", "vg": "pve"}
                        if p.get("action") == "receive": res = {"ok": True, "url": "http://192.0.2.5:6461", "token": "t0k"}
                        store.ack_command(self.db, aid, c["id"], {"ok": True, "error": None, "result": res})
                        if c["type"] == "image_host":
                            time.sleep(0.2)
                            appmod._event("image-fetched", "info", "image reçue sur le LAN", agent_id="lan-pve", details={"path": "/var/lib/vz/import/p2v-vm311/x.vhdx", "name": "x.vhdx", "sha256": "0", "bytes": 1})
        threading.Thread(target=fake_agents, daemon=True).start()
        rid = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute", "actor": "freg"}).json["run_id"]
        for _ in range(100):
            time.sleep(0.05)
            if self.c.get("/pra/runs/%d" % rid).json["run"]["status"] == "paused": break
        self.c.post("/pra/runs/%d/resume" % rid)
        for _ in range(300):
            time.sleep(0.05)
            if [s for s in seen if s[1] == "vm_action" and s[2].get("action") == "import_disk"]: break
        img = [s for s in seen if s[1] == "image_host"][0][2]
        self.assertEqual((img["push_url"], img["push_token"], img["target"]), ("http://192.0.2.5:6461", "t0k", "D:\\\\"))
        imp = [s for s in seen if s[1] == "vm_action" and s[2].get("action") == "import_disk"][0][2]
        self.assertEqual(imp["source"], "/var/lib/vz/import/p2v-vm311/x.vhdx")
        self.c.post("/pra/runs/%d/abort" % rid, json={})


if __name__ == "__main__":
    unittest.main()
