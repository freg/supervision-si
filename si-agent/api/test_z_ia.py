"""#756 : tuile Parc IA -- hôtes Ollama (sonde) ou déclarés, modèles, conteneurs ; relais en lecture vers l'assistant."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import store  # noqa: E402


class Ia(unittest.TestCase):
    def test_overview_hosts_and_relay(self):
        c = appmod.app.test_client(); db = appmod.DB_PATH
        store.create_agent(db, "ia-host", "siege"); store.create_agent(db, "ia-vm", "siege"); store.create_agent(db, "autre", "siege")
        store.ingest_measurements(db, "ia-host", [{"task": "plugin:ollama", "at": "2026-10-14T12:00:00Z", "data": {"up": True, "models": [{"name": "qwen3:14b", "loaded": True, "gpu_pct": 100}]}},
                                                  {"task": "plugin:docker-containers", "at": "2026-10-14T12:00:00Z", "data": {"containers": [{"name": "open-webui", "state": "running"}]}}])
        conn = store._connect(db)
        try:
            conn.execute("INSERT OR IGNORE INTO agent_plugins (agent_id, plugin_id, enabled) VALUES ('ia-host', 'ollama', 1)"); conn.commit()
        except Exception:  # noqa: BLE001 -- schéma différent : l'hôte sera déclaré à la main
            pass
        finally:
            conn.close()
        self.assertEqual(c.put("/ia/hosts", json={"agents": ["ia-vm", "ia-host", "bad id!"]}).json["declared"], ["ia-vm", "ia-host"])
        o = c.get("/ia/overview").json
        ids = [h["agent_id"] for h in o["hosts"]]
        self.assertEqual(ids, ["ia-host", "ia-vm"])
        h = o["hosts"][0]
        self.assertEqual(h["models"][0]["name"], "qwen3:14b"); self.assertEqual(h["containers"][0]["name"], "open-webui")
        self.assertEqual(c.get("/ia/assistant/index/rebuild").status_code, 404)
        r = c.get("/ia/assistant/status"); self.assertEqual(r.status_code, 502); self.assertIn("injoignable", r.json["error"])


if __name__ == "__main__":
    unittest.main()
