# -*- coding: utf-8 -*-
"""Publication locale (livraison #547) : JSON avec âge, page, serveur, cycle de l'agent."""
import json
import os
import sys
import tempfile
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from si_agent import publish  # noqa: E402
from tests.test_si_agent import FakeHttp  # noqa: E402
from si_agent import agent as agent_mod  # noqa: E402


class Pure(unittest.TestCase):
    def test_with_age_and_page(self):
        self.assertEqual(publish.with_age(None), {"at": None, "stale": True, "sites": []})
        p = {"at": 1000, "received_at": 1000, "sites": [{"name": "S"}]}
        out = publish.with_age(p, now=1100)
        self.assertEqual((out["age_seconds"], out["stale"]), (100, False))
        self.assertTrue(publish.with_age(p, now=1000 + publish.STALE_AFTER + 1)["stale"])
        page = publish.render_page("Réseau <campus>")
        self.assertIn("<title>Réseau &lt;campus&gt;</title>", page)
        self.assertNotIn("http://", page.split("<script>")[0].split("<style>")[0])  # aucune dépendance externe


class Server(unittest.TestCase):
    def test_serves_page_and_board(self):
        srv = publish.PublishServer(0, "Titre", bind="127.0.0.1", clock=lambda: 2000)
        port = srv.start()
        try:
            html = urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5).read().decode("utf-8")
            self.assertIn("<h1>Titre</h1>", html)
            b = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/board.json" % port, timeout=5).read())
            self.assertTrue(b["stale"])
            srv.set_payload({"at": 1900, "received_at": 1900, "title": "Titre", "sites": [{"name": "S", "resume": "ok", "phrases": [], "devices": []}]})
            b = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/board.json" % port, timeout=5).read())
            self.assertEqual((b["age_seconds"], b["stale"], b["sites"][0]["name"]), (100, False, "S"))
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen("http://127.0.0.1:%d/etc/passwd" % port, timeout=5)
        finally:
            srv.stop()


class AgentCycle(unittest.TestCase):
    def test_publish_tick(self):
        d = tempfile.mkdtemp()
        cfg = dict(agent_mod.DEFAULTS)
        cfg.update({"agent_id": "srv-01", "secret": "s3cr3t", "central_url": "http://central", "site": "siege",
                    "queue_path": os.path.join(d, "q.db"), "plugins_dir": os.path.join(d, "plugins"),
                    "state_path": os.path.join(d, "state.json"), "block_file": os.path.join(d, "BLOCKED"),
                    "require_signed_responses": False})
        http = FakeHttp("s3cr3t")
        http.config["publish"] = {"enabled": True, "port": 0, "title": "T", "interval_seconds": 60}
        orig = http.request
        def request(method, path, body=None):
            if path.endswith("/publish"):
                return 200, {"enabled": True, "at": 5, "title": "T", "sites": [{"name": "S", "resume": "ok", "phrases": [], "devices": []}]}
            return orig(method, path, body)
        http.request = request
        a = agent_mod.Agent(cfg, http=http)
        a.refresh_config(force=True)
        self.assertEqual(a.cfg["publish"]["title"], "T")
        a.publish_tick()
        srv = a._publish_server
        self.assertIsNotNone(srv)
        try:
            b = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/board.json" % srv.port, timeout=5).read())
            self.assertEqual(b["sites"][0]["name"], "S")
            self.assertFalse(b["stale"])
            # désactivation par le central : serveur arrêté
            http.config = dict(http.config, version="v2", publish={"enabled": False})
            a.refresh_config(force=True); a.publish_tick()
            self.assertIsNone(a._publish_server)
        finally:
            if a._publish_server:
                a._publish_server.stop()


if __name__ == "__main__":
    unittest.main()
