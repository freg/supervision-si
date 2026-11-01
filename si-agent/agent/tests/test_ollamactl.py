"""#746 : pilotage d'Ollama (si_agent.ollamactl) et sonde ollama, contre un faux serveur Ollama local."""
import importlib.util
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from si_agent import ollamactl

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = {"models": {"qwen3:14b": 9_300_000_000}, "loaded": {}, "calls": []}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/api/version":
            return self._send({"version": "0.40.3"})
        if self.path == "/api/tags":
            return self._send({"models": [{"name": n, "size": s, "modified_at": "2026-10-13T20:00:00Z",
                                           "details": {"family": "qwen3", "parameter_size": "14.8B", "quantization_level": "Q4_K_M"}}
                                          for n, s in STATE["models"].items()]})
        if self.path == "/api/ps":
            return self._send({"models": [{"name": n, "size": 10_000, "size_vram": v, "expires_at": "x", "context_length": 32768}
                                          for n, v in STATE["loaded"].items()]})
        self._send({"error": "?"}, 404)

    def do_DELETE(self):
        b = self._body(); STATE["calls"].append(("delete", b["model"]))
        if b["model"] not in STATE["models"]:
            return self._send({"error": "model not found"}, 404)
        del STATE["models"][b["model"]]; self._send({})

    def do_POST(self):
        b = self._body(); STATE["calls"].append((self.path, b))
        if self.path == "/api/generate":
            if b.get("keep_alive") == 0:
                STATE["loaded"].pop(b["model"], None)
            else:
                STATE["loaded"][b["model"]] = 7_000 if b["model"].startswith("big") else 10_000
            if "prompt" in b:
                return self._send({"response": "Elle mesure.", "eval_count": 64, "eval_duration": 4_000_000_000, "load_duration": 2_000_000_000})
            return self._send({"done": True})
        if self.path == "/api/pull":
            self.send_response(200); self.send_header("Content-Type", "application/x-ndjson"); self.end_headers()
            if b["model"] == "absent:1b":
                self.wfile.write(b'{"error":"pull model manifest: file does not exist"}\n'); return
            STATE["models"][b["model"]] = 100
            for ev in ({"status": "pulling manifest"}, {"status": "pulling abc", "completed": 50, "total": 100},
                       {"status": "pulling abc", "completed": 100, "total": 100}, {"status": "success"}):
                self.wfile.write((json.dumps(ev) + "\n").encode())
            return
        self._send({"error": "?"}, 404)


class OllamaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d" % cls.srv.server_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_status_and_names(self):
        r = ollamactl.run_action({"action": "status"}, self.url)
        self.assertTrue(r["ok"]); self.assertEqual(r["status"]["version"], "0.40.3")
        self.assertIn("qwen3:14b", [m["name"] for m in r["status"]["models"]])
        for bad in ("", "../x", "a b", "-x", "x;rm"):
            self.assertFalse(ollamactl.valid_model(bad), bad)
        self.assertTrue(ollamactl.valid_model("hf.co/org/model:Q4_K_M"))
        self.assertFalse(ollamactl.run_action({"action": "delete", "model": "../etc"}, self.url)["ok"])
        self.assertFalse(ollamactl.run_action({"action": "rm", "model": "x"}, self.url)["ok"])

    def test_load_test_unload_delete(self):
        STATE["models"]["big:70b"] = 40_000
        r = ollamactl.run_action({"action": "load", "model": "big:70b"}, self.url)
        self.assertTrue(r["ok"]); self.assertEqual(r["model"]["gpu_pct"], 70)
        r = ollamactl.run_action({"action": "test", "model": "qwen3:14b"}, self.url)
        self.assertTrue(r["ok"]); self.assertEqual(r["rate"], 16.0); self.assertEqual(r["gpu_pct"], 100)
        self.assertTrue(ollamactl.run_action({"action": "unload", "model": "qwen3:14b"}, self.url)["ok"])
        self.assertNotIn("qwen3:14b", STATE["loaded"])
        self.assertTrue(ollamactl.run_action({"action": "delete", "model": "big:70b"}, self.url)["ok"])
        r = ollamactl.run_action({"action": "delete", "model": "nothere:1b"}, self.url)
        self.assertFalse(r["ok"]); self.assertIn("404", r["error"])

    def test_pull_stream_and_errors(self):
        seen = []
        ok, err = ollamactl.pull(self.url, "gemma3:4b", progress=seen.append)
        self.assertTrue(ok, err); self.assertEqual(seen[-1]["status"], "success"); self.assertIn("gemma3:4b", STATE["models"])
        ok, err = ollamactl.pull(self.url, "absent:1b")
        self.assertFalse(ok); self.assertIn("does not exist", err)
        started = []
        r = ollamactl.run_action({"action": "pull", "model": "x:1b"}, self.url, pull_state=None, start_pull=started.append)
        self.assertTrue(r["ok"]); self.assertEqual(started, ["x:1b"])
        r = ollamactl.run_action({"action": "pull", "model": "y:1b"}, self.url, pull_state={"running": True, "model": "x:1b"}, start_pull=started.append)
        self.assertFalse(r["ok"]); self.assertEqual(started, ["x:1b"])

    def test_down(self):
        r = ollamactl.run_action({"action": "status"}, "http://127.0.0.1:9")
        self.assertFalse(r["ok"]); self.assertIn("injoignable", r["error"])

    def test_probe_plugin(self):
        spec = importlib.util.spec_from_file_location("ollama_probe", os.path.join(HERE, "..", "plugins", "ollama", "ollama_probe.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        STATE["loaded"] = {"qwen3:14b": 10_000, "big:70b": 7_000}; STATE["models"]["big:70b"] = 40_000
        out = mod.collect(self.url, min_free_gb=1e9, models_dir=HERE)
        self.assertTrue(out["up"]); self.assertEqual(out["loaded"], 2)
        codes = [a["code"] for a in out["alerts"]]
        self.assertIn("model-off-gpu@big:70b", codes); self.assertIn("models-dir-full", codes)
        self.assertNotIn("model-off-gpu@qwen3:14b", codes)
        down = mod.collect("http://127.0.0.1:9")
        self.assertEqual(down["alerts"][0]["code"], "ollama-down")
        with open(os.path.join(HERE, "..", "plugins", "ollama", "manifest.json")) as fh:
            m = json.load(fh)
        self.assertFalse(m["enabled"]); self.assertFalse(m["privileged"])


if __name__ == "__main__":
    unittest.main()
