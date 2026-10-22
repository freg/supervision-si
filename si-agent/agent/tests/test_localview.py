# -*- coding: utf-8 -*-
"""Vue locale de transparence (livraison #819) : masquage, filtre d'adresses, enregistreur, page, cycle de l'agent."""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from si_agent import localview  # noqa: E402
from tests.test_si_agent import FakeHttp  # noqa: E402
from si_agent import agent as agent_mod  # noqa: E402


class Pure(unittest.TestCase):
    def test_sanitize_masque_les_secrets_recursivement(self):
        cfg = {"agent_id": "a", "secret": "s3cr3t", "central_url": "https://c", "nested": {"api_key": "k", "Password": "p", "port": 1},
               "token": "", "ca_fingerprint": "ab:cd", "liste": [{"private_key": "x"}]}
        out = localview.sanitize(cfg)
        txt = json.dumps(out)
        for v in ("s3cr3t", '"k"', '"p"', '"x"'):
            self.assertNotIn(v, txt)
        self.assertEqual((out["agent_id"], out["nested"]["port"], out["ca_fingerprint"], out["token"]), ("a", 1, "ab:cd", ""))
        self.assertEqual(out["secret"], localview.MASK)

    def test_allowed(self):
        self.assertTrue(localview.allowed("127.0.0.1", []))
        self.assertTrue(localview.allowed("::1", []))
        self.assertTrue(localview.allowed("::ffff:127.0.0.1", []))
        self.assertFalse(localview.allowed("172.16.51.20", []))
        self.assertTrue(localview.allowed("172.16.51.20", ["172.16.51.0/24"]))
        self.assertTrue(localview.allowed("::ffff:172.16.51.20", ["172.16.51.20"]))
        self.assertFalse(localview.allowed("172.16.52.20", ["172.16.51.0/24", "pas-une-ip"]))
        self.assertFalse(localview.allowed("n'importe", ["0.0.0.0/0"]))

    def test_merged(self):
        self.assertEqual(localview.merged(None), localview.DEFAULT)
        m = localview.merged({"enabled": 1, "port": "8091", "bind": "", "allow": ["10.0.0.0/8", ""], "inconnu": 1})
        self.assertEqual(m, {"enabled": True, "port": 8091, "bind": "127.0.0.1", "allow": ["10.0.0.0/8"]})
        self.assertEqual(localview.merged({"port": "x"})["port"], 8090)

    def test_recorder_et_sondes(self):
        r = localview.Recorder()
        r.record({"task": "host", "at": "t1", "ok": True, "data": {"cpu": 1}})
        r.record({"task": "host", "at": "t2", "ok": True, "data": {"cpu": 2}})
        r.record({"task": "plugin:p1", "at": "t3", "ok": False, "error": "boum", "data": None})
        r.record({"task": "event", "at": "t4", "ok": True, "data": {"kind": "k", "severity": "info", "message": "m"}})
        r.record("pas une mesure")
        tasks, events = r.snapshot()
        by = {t["task"]: t for t in tasks}
        self.assertEqual((by["host"]["count"], by["host"]["at"], by["host"]["data"]), (2, "t2", {"cpu": 2}))
        self.assertIsNone(by["event"]["data"])
        self.assertEqual(events, [{"at": "t4", "kind": "k", "severity": "info", "message": "m"}])
        self.assertTrue(by["host"]["label"].startswith("État du système"))
        self.assertEqual(localview.task_label("plugin:x"), "Sonde « x »")
        rows = localview.plugin_rows([{"id": "p2", "enabled": False}, {"id": "p1", "enabled": True, "interval_seconds": 60}, {"id": "p3", "blocked": True}],
                                     lambda m: m.get("enabled"), lambda m: m.get("blocked"), {"p1": 99}, by)
        self.assertEqual([(x["id"], x["state"]) for x in rows], [("p1", "active"), ("p2", "inactive"), ("p3", "bloquée")])
        self.assertEqual((rows[0]["last_ok"], rows[0]["last_error"], rows[0]["next_run"]), (False, "boum", 99))
        v = localview.build_view({"agent_id": "a"}, {"secret": "s"}, rows, r, now=5)
        self.assertEqual(v["tasks"][-1]["task"], "event")
        self.assertEqual(v["config"]["secret"], localview.MASK)

    def test_page_autonome_et_sombre(self):
        head = localview.PAGE.split("<script>")[0]
        self.assertNotIn("http://", head); self.assertNotIn("https://", head)
        self.assertIn("--bg:#0f1115", head)
        self.assertIn("lecture seule", localview.PAGE)


class Server(unittest.TestCase):
    def test_sert_page_et_json_et_filtre(self):
        srv = localview.LocalViewServer(0, lambda: {"agent": {"host": "h"}, "secret_visible": False}, bind="127.0.0.1")
        port = srv.start()
        try:
            html = urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5).read().decode("utf-8")
            self.assertIn("Agent de supervision", html)
            v = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/view.json" % port, timeout=5).read())
            self.assertEqual(v["agent"]["host"], "h")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen("http://127.0.0.1:%d/../../etc/passwd" % port, timeout=5)
        finally:
            srv.stop()
        def boom():
            raise RuntimeError("panne")
        srv = localview.LocalViewServer(0, boom, bind="127.0.0.1")
        port = srv.start()
        try:
            self.assertEqual(json.loads(urllib.request.urlopen("http://127.0.0.1:%d/view.json" % port, timeout=5).read()), {"error": "panne"})
        finally:
            srv.stop()


class AgentCycle(unittest.TestCase):
    def _agent(self, local_view=None):
        d = tempfile.mkdtemp()
        cfg = dict(agent_mod.DEFAULTS)
        cfg.update({"agent_id": "srv-01", "secret": "s3cr3t", "central_url": "http://central", "site": "siege",
                    "queue_path": os.path.join(d, "q.db"), "plugins_dir": os.path.join(d, "plugins"),
                    "state_path": os.path.join(d, "state.json"), "block_file": os.path.join(d, "BLOCKED"),
                    "require_signed_responses": False})
        if local_view is not None:
            cfg["local_view"] = local_view
        http = FakeHttp("s3cr3t")
        return agent_mod.Agent(cfg, http=http), http

    def test_fermee_par_defaut(self):
        a, _ = self._agent()
        a.local_view_tick()
        self.assertIsNone(a._local_view)

    def test_ouverte_par_le_central_puis_fermee(self):
        a, http = self._agent()
        http.config["local_view"] = {"enabled": True, "port": 0}
        a.refresh_config(force=True)
        a.event("essai", "warning", "message de test")
        a.local_view_tick()
        srv = a._local_view
        self.assertIsNotNone(srv)
        try:
            v = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/view.json" % srv.port, timeout=5).read())
            txt = json.dumps(v)
            self.assertNotIn("s3cr3t", txt)
            self.assertEqual((v["agent"]["agent_id"], v["agent"]["site"]), ("srv-01", "siege"))
            self.assertIn("essai", [e["kind"] for e in v["events"]])
            self.assertIn("event", [t["task"] for t in v["tasks"]])
            self.assertTrue(v["agent"]["block_file"].endswith("BLOCKED"))
            # la mesure est bien partie dans la vraie file (la vue ne détourne rien)
            self.assertGreaterEqual(a.queue.pending_count(), 1)
            http.config = dict(http.config, version="v2", local_view={"enabled": False})
            a.refresh_config(force=True); a.local_view_tick()
            self.assertIsNone(a._local_view)
        finally:
            if a._local_view:
                a._local_view.stop()

    def test_agent_json_seul(self):
        a, _ = self._agent({"enabled": True, "port": 0})
        a.local_view_tick()
        try:
            self.assertIsNotNone(a._local_view)
        finally:
            a._local_view.stop()


if __name__ == "__main__":
    unittest.main()
