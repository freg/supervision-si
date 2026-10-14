"""#761 : assistant de rapatriement -- campagne, inventaire du nœud distant, préparation, lancement des plans repatriate,
phases et avancement, validation."""
import os
import sys
import tempfile
import threading
import time
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import pra  # noqa: E402
import repatriation as repa  # noqa: E402
import store  # noqa: E402


class Pure(unittest.TestCase):
    def test_phase_progress(self):
        run = lambda sts, status="running": {"status": status, "steps": [  # noqa: E731
            {"index": 1, "params": {"action": "checkpoint"}, "status": sts[0]}, {"index": 2, "params": {"action": "export"}, "status": sts[1]},
            {"index": 3, "params": {"action": "verify"}, "status": sts[2]}, {"index": 4, "params": {"action": "checkpoint"}, "status": sts[3]},
            {"index": 5, "params": {"action": "destroy"}, "status": sts[4]}]}
        self.assertEqual(repa.guest_phase(None)[0], "todo")
        self.assertEqual(repa.guest_phase(run(["done", "sent", "pending", "pending", "pending"]))[0], "export")
        self.assertEqual(repa.guest_phase(run(["done", "done", "sent", "pending", "pending"]))[0], "verify")
        self.assertEqual(repa.guest_phase(run(["done", "done", "done", "waiting", "pending"], "paused"))[0], "validate")
        self.assertEqual(repa.guest_phase(run(["done", "done", "failed", "pending", "pending"], "failed"))[0], "diff")
        self.assertEqual(repa.guest_phase(run(["done", "done", "done", "done", "done"], "done"))[0], "done")
        c = {"step": "rapatriement", "guests": [{"vmid": 1, "decision": "rapatrier"}, {"vmid": 2, "decision": "rapatrier"}, {"vmid": 3, "decision": "garder"}]}
        p = repa.progress(c, {1: "validate", 2: "export"})
        st = {s["id"]: s["done"] for s in p["steps"]}
        self.assertEqual((st["inventaire"], st["preparation"], st["rapatriement"], st["verification"]), (1.0, 1.0, 0.75, 0.5))
        self.assertEqual(p["percent"], round(10 + 10 + 40 * 0.75 + 15 * 0.5, 1))
        done = repa.progress(dict(c, step="bilan"), {1: "done", 2: "done"})
        self.assertEqual(done["percent"], 100.0)

    def test_inventory_and_checks(self):
        g = repa.merge_inventory([{"vmid": 102, "decision": "rapatrier", "newid": 9102}, {"vmid": 50, "decision": "garder"}],
                                 [{"vmid": 102, "name": "MED10", "type": "lxc", "status": "stopped", "maxdisk": 400e9}, {"vmid": 109, "name": "ns3", "type": "lxc", "maxdisk": 8e9}])
        self.assertEqual([(x["vmid"], x["decision"], x["present"]) for x in g], [(102, "rapatrier", True), (109, "", True), (50, "garder", False)])
        checks = repa.preparation({"storage": "local-zfs"}, {"name": "pve10", "storages": [{"storage": "local-zfs", "avail": 300e9}]}, {"name": "pve-a", "ok": True}, g)
        by = {c["label"]: c["ok"] for c in checks}
        self.assertFalse(by["place libre sur le stockage local"]); self.assertTrue(by["nœud distant joignable par l'agent du nœud local"])


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        for a in ("rp-pve", "rp-pbs"): store.create_agent(cls.db, a, "siege")
        store.ingest_measurements(cls.db, "rp-pve", [{"task": "plugin:proxmox", "at": "2026-10-14T12:00:00Z", "data": {"node": {"name": "pve10"}, "vms": [], "storages": [{"storage": "local-zfs", "used": 600e9, "total": 2400e9, "avail": 1800e9}]}}])
        store.ingest_measurements(cls.db, "rp-pbs", [{"task": "plugin:pve-remote", "at": "2026-10-14T12:00:00Z", "data": {"nodes": [{"name": "pve-a", "ok": True, "storages": [],
                                  "guests": [{"vmid": 102, "name": "MED10", "type": "lxc", "status": "stopped", "maxdisk": 400e9}, {"vmid": 109, "name": "ns3", "type": "lxc", "status": "stopped", "maxdisk": 8e9}]}]}}])
        pra.XFER_TIMEOUT = 20; pra.SLEEP = lambda n: time.sleep(min(n, 0.05))

    def test_campaign(self):
        r = self.c.post("/repatriation", json={"remote": "pve-a", "pve_agent_id": "rp-pve", "storage": "local-zfs"})
        self.assertEqual(r.status_code, 201, r.json); cid = r.json["id"]
        self.assertEqual([g["vmid"] for g in r.json["guests"]], [102, 109]); self.assertEqual(r.json["local_storages"], ["local-zfs"])
        r = self.c.put("/repatriation/%d" % cid, json={"decisions": {"102": "rapatrier", "109": "garder"}, "step": "preparation"})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertTrue(all(ch["ok"] for ch in r.json["checks"]), r.json["checks"])
        self.assertEqual(r.json["progress"]["percent"], 10.0)
        self.assertEqual(self.c.put("/repatriation/%d" % cid, json={"decisions": {"102": "détruire"}}).status_code, 400)

        def fake_agent():
            for _ in range(900):
                time.sleep(0.03)
                for cmd in store.list_commands(self.db, "rp-pve", status="pending"):
                    store.ack_command(self.db, "rp-pve", cmd["id"], {"ok": True, "error": None, "result": {"ok": True}})
                    time.sleep(1.1)
                    appmod._event("xfer-done", "info", "%s fini" % cmd["params"].get("action"), agent_id="rp-pve", details={"command": cmd["id"], "result": {"identical": True}})
        threading.Thread(target=fake_agent, daemon=True).start()
        r = self.c.post("/repatriation/%d/launch" % cid, json={"actor": "freg"})
        self.assertEqual(r.json["launched"], [102]); g = r.json["campaign"]["guests"][0]
        self.assertEqual(g["newid"], 9102)
        for _ in range(200):
            time.sleep(0.05)
            g = self.c.get("/repatriation/%d" % cid).json["guests"][0]
            if g["phase"] == "validate": break
        self.assertEqual(g["phase"], "validate", g)
        self.assertEqual(self.c.post("/repatriation/%d/guest/102/validate" % cid).status_code, 200)
        for _ in range(200):
            time.sleep(0.05)
            c = self.c.get("/repatriation/%d" % cid).json
            if c["guests"][0]["phase"] == "done": break
        self.assertEqual(c["guests"][0]["phase"], "done")
        self.c.put("/repatriation/%d" % cid, json={"step": "bilan"})
        self.assertEqual(self.c.get("/repatriation/%d" % cid).json["progress"]["percent"], 100.0)
        lst = self.c.get("/repatriation").json
        self.assertEqual(lst["campaigns"][0]["percent"], 100.0)
        self.assertEqual(lst["local_agents"], [{"agent_id": "rp-pve", "hostname": None, "node": "pve10"}])
        d = self.c.get("/diag/tasks?tasks=plugin:proxmox,plugin:ollama,bad task!").json["tasks"]   # #763
        self.assertEqual([t["task"] for t in d], ["plugin:proxmox", "plugin:ollama"])
        self.assertEqual(d[0]["agents"][0]["agent_id"], "rp-pve"); self.assertTrue(d[0]["agents"][0]["ok"]); self.assertEqual(d[1]["agents"], [])
        self.assertIn("ollama", d[1]["hint"])


if __name__ == "__main__":
    unittest.main()
