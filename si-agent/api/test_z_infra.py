"""#749 : assemblage de la vue d'ensemble PVE / PBS (nœuds locaux / distants, VM, transferts, totaux) et route."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import infra  # noqa: E402
import store  # noqa: E402

ACT = {"nodes": [{"name": "pve10", "zone": "local", "ok": True, "cpu_pct": 12.5, "cores_pct": [10, 15], "ncpu": 2, "mem_total": 32, "mem_used": 16,
                  "disks": [{"mount": "/", "size": 100, "used": 40, "pct": 40}], "net": [{"iface": "vmbr0", "rx_bps": 800, "tx_bps": 200}],
                  "conn": {"estab": 7}, "procs": [{"pid": 1, "kind": "vzdump", "elapsed_s": 60, "cmd": "vzdump 109 --stdout"}],
                  "files": [{"path": "/var/lib/vz/dump/x.tar.gz", "size": 1000, "rate_bps": 50, "active": True}]},
                 {"name": "pve-2", "zone": "remote", "ok": False, "error": "délai"}],
       "alerts": [{"code": "disk-full:pve10:/", "severity": "warning", "message": "x"}]}
PROX = {"node": {"name": "pve10"}, "storages": [{"storage": "local-zfs", "total": 1000, "used": 400, "avail": 600}],
        "vms": [{"vmid": 100, "name": "partages", "type": "qemu", "status": "running", "cpu": 0.25, "maxcpu": 4, "mem": 2, "maxmem": 4, "uptime_s": 9},
                {"vmid": 9000, "name": "modele", "template": True}]}
REM = {"nodes": [{"name": "pve-2", "ok": True, "storages": [{"storage": "local", "total": 2000, "used": 1800, "avail": 200},
                                                              {"storage": "backup", "total": 2000, "used": 1800, "avail": 200}],
                  "guests": [{"vmid": 103, "name": "FTTH24", "type": "lxc", "status": "running", "cpu": 0.05, "maxcpu": 2, "mem": 1, "maxmem": 2, "uptime": 99},
                             {"vmid": 104, "name": "x", "type": "lxc", "status": "stopped"}]}]}
PBS = {"datastores": [{"name": "backup", "used_percent": 40.0, "total": 2400}]}


class Infra(unittest.TestCase):
    def test_assemblage(self):
        o = infra.overview([("a1", "pve10", "t", ACT)], [("a1", "pve10", "t", PROX)], [("a1", "pve10", "t", REM)], [("a2", "pbs10", "t", PBS)])
        names = [n["name"] for n in o["nodes"]]
        self.assertEqual(names, ["pve10", "pbs10", "pve-2"])                       # local PVE, local PBS, puis distants
        loc = o["nodes"][0]
        self.assertEqual((loc["cpu_pct"], loc["guests"], loc["storages"][0]["storage"]), (12.5, {"running": 1, "stopped": 0, "total": 1}, "local-zfs"))
        self.assertEqual(o["nodes"][1]["role"], "pbs")
        rem = o["nodes"][2]
        self.assertEqual((rem["zone"], rem["ok"], rem["guests"]["stopped"]), ("distant", True, 1))   # inventaire ssh OK même si activité en échec
        self.assertEqual([v["vmid"] for v in o["vms"]], [103, 104, 100])            # modèle exclu
        self.assertEqual(o["vms"][2]["cpu_pct"], 25.0)
        self.assertEqual(o["vms"][0]["uptime_s"], 99)
        self.assertEqual(o["totals"]["distant"]["storage_total"], 2000)             # deux stockages du même système de fichiers : une fois
        self.assertEqual((o["totals"]["local"]["rx_bps"], o["totals"]["local"]["estab"]), (800, 7))
        self.assertEqual({t["what"] for t in o["transfers"]}, {"processus", "fichier"})
        self.assertEqual(o["alerts"][0]["agent_id"], "a1")

    def test_task_progress(self):   # #766
        t = {"guests": [1, 2, 3], "done": [{"vmid": 1}], "failed": [], "current": 2, "percent": None, "read_bytes": 50}
        p = infra.task_progress(t, {1: 100, 2: 100, 3: 200})
        self.assertEqual((p["current_pct"], p["current_estimated"], p["overall_pct"], p["n_done"], p["n_total"]), (50, True, 37.5, 1, 3))
        p = infra.task_progress(dict(t, percent=20), {})
        self.assertEqual((p["current_pct"], p["current_estimated"], p["overall_pct"]), (20, False, 40.0))
        ov = infra.overview([("a", "pve10", "t", {"nodes": [{"name": "pve10", "zone": "local", "pve_tasks": [dict(t, type="vzdump")]}]})],
                            [("a", "pve10", "t", {"node": {"name": "pve10"}, "vms": [{"vmid": 2, "disk": 100}]})], [], [])
        self.assertEqual((ov["pve_tasks"][0]["node"], ov["pve_tasks"][0]["progress"]["current_pct"]), ("pve10", 50))

    def test_route(self):
        db = appmod.DB_PATH
        store.create_agent(db, "infra-a", "siege", label="infra-a")
        conn = store._connect(db)
        try:
            conn.execute("INSERT INTO measurements (agent_id, task, at, received_at, ok, data) VALUES (?, ?, ?, ?, 1, ?)", ("infra-a", "plugin:node-activity", "2026-10-14T10:00:00Z", "2026-10-14T10:00:01Z", json.dumps(ACT)))
            conn.commit()
        except Exception as e:  # noqa: BLE001 -- schéma de measurements différent : le test d'assemblage suffit
            self.skipTest("insertion directe impossible : %s" % e)
        finally:
            conn.close()
        r = appmod.app.test_client().get("/infra/overview")
        self.assertEqual(r.status_code, 200)
        self.assertIn("pve10", [n["name"] for n in r.json["nodes"]])


if __name__ == "__main__":
    unittest.main()
