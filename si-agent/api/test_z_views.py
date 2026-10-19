"""#753 : vues de parc paramétrables (groupes d'agents, en-tête htop par agent, Ollama)."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import store  # noqa: E402
import views  # noqa: E402

HOST = {"system": {"hostname": "srv-a", "os": "Debian GNU/Linux 12", "cpus": 8, "cpu_model": "Xeon", "uptime_seconds": 86400},
        "cpu": {"percent": 42.5, "load1": 1.5, "load5": 1.2, "load15": 1.0},
        "memory": {"total_bytes": 16 * 2**30, "used_percent": 61.0, "swap_total_bytes": 2**30, "swap_used_percent": 5.0},
        "disks": [{"mountpoint": "/", "used_percent": 40.0, "total_bytes": 100}, {"mountpoint": "/data", "used_percent": 91.0, "total_bytes": 900},
                  {"mountpoint": "/net", "used_percent": None}], "services": {"available": True, "failed": ["x.service"]}}
OLLAMA = {"up": True, "version": "0.12", "models": [{"name": "qwen3:14b", "loaded": True, "gpu_pct": 100, "vram": 9e9}, {"name": "phi4", "loaded": False}], "alerts": []}


class Views(unittest.TestCase):
    def test_normalize(self):
        v, err = views.normalize([{"id": "serveurs", "label": "Serveurs", "groups": [{"name": "Proxmox", "agents": ["pve10", "pve10", "bad id!"]}]}])
        self.assertIsNone(err); self.assertEqual(v[0]["groups"][0]["agents"], ["pve10"])
        self.assertIn("identifiant", views.normalize([{"id": "A B"}])[1])
        self.assertIn("unique", views.normalize([{"id": "a"}, {"id": "a"}])[1])
        self.assertIn("nom", views.normalize([{"id": "a", "groups": [{"agents": []}]}])[1])
        self.assertIn("1 à 20", views.normalize([])[1])

    def test_row_and_overview(self):
        latest = {"host": {"at": "2026-10-14T10:00:00Z", "data": HOST}, "plugin:ollama": {"data": OLLAMA},
                  "plugin:node-activity": {"data": {"nodes": [{"zone": "local", "cores_pct": [10.0, None, 30.0], "net": [{"iface": "lo", "rx_bps": 9}, {"iface": "eth0", "rx_bps": 800, "tx_bps": 200}]}]}}}
        r = views.row({"agent_id": "srv-a", "online": "online", "agent_version": "0.5.60", "risks": {"state": "warning", "counts": {"warning": 2}}}, latest)
        self.assertEqual((r["cpu_pct"], r["mem_pct"], r["disk_max_pct"], r["failed_services"]), (42.5, 61.0, 91.0, 1))
        self.assertEqual([d["mount"] for d in r["disks"]], ["/data", "/"]); self.assertEqual(r["cores_pct"], [10.0, 30.0])
        self.assertEqual((r["net_rx_bps"], r["net_tx_bps"]), (800, 200))
        self.assertEqual(r["ollama"]["models"], 2); self.assertEqual(r["ollama"]["loaded"][0]["name"], "qwen3:14b")
        g = views.row({"agent_id": "g"}, {"plugin:gpu": {"at": "2026-10-19T09:00:00Z", "data": {"gpus": [
            {"name": "NVIDIA RTX A4500", "vendor": "NVIDIA", "driver": "nvidia", "vram_total": 20 << 30, "vram_used": 10 << 30, "vram_pct": 50.0,
             "util_pct": 87.0, "temp_c": 64.0, "power_w": 150.2, "processes": [{"pid": 1}]}],
            "alerts": [{"code": "gpu-no-driver@x", "severity": "warning", "message": "Intel : aucun pilote"}]}}})
        self.assertEqual((g["gpus"][0]["name"], g["gpus"][0]["vram_pct"], g["gpu_alerts"]), ("NVIDIA RTX A4500", 50.0, ["Intel : aucun pilote"]))
        self.assertNotIn("processes", g["gpus"][0])
        empty = views.row({"agent_id": "w"}, {})
        self.assertIsNone(empty["cpu_pct"]); self.assertNotIn("ollama", empty); self.assertNotIn("gpus", empty)
        view = {"id": "ia", "label": "IA", "groups": [{"name": "GPU", "agents": ["srv-a", "absent"]}]}
        o = views.overview(view, {"srv-a": r, "w": dict(empty, online="offline")})
        self.assertEqual(o["groups"][0]["missing"], ["absent"]); self.assertEqual(o["unassigned"], ["w"])
        self.assertEqual(o["groups"][0]["totals"]["online"], 1); self.assertEqual(o["totals"]["disk_max"], 91.0)

    def test_routes(self):
        c = appmod.app.test_client()
        r = c.get("/views"); self.assertEqual([v["id"] for v in r.json["views"]], ["serveurs", "postes", "ia", "perso"])
        store.create_agent(appmod.DB_PATH, "vw-srv", "siege", label="vw-srv")
        body = {"views": [{"id": "serveurs", "label": "Serveurs", "groups": [{"name": "Linux", "agents": ["vw-srv"]}]}, {"id": "perso", "label": "Postes personnels"}]}
        self.assertEqual(c.put("/views", json=body).status_code, 200)
        self.assertEqual(len(c.get("/views").json["views"]), 2)
        o = c.get("/views/serveurs/overview").json
        self.assertEqual(o["groups"][0]["rows"][0]["agent_id"], "vw-srv")
        self.assertEqual(c.get("/views/absente/overview").status_code, 404)
        self.assertEqual(c.put("/views", json={"views": [{"id": "x y"}]}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
