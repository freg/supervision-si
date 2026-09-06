"""Collecteur : logique (sans socket) puis chaîne RÉELLE sonde -> collecteur
en HTTP sur 127.0.0.1 (port libre), avec le vrai client signé de la sonde
et la vraie file locale des deux côtés."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from netprobe_agent import protocol
from netprobe_agent.agent import Agent, HttpClient
from netprobe_agent.collector import CollectorCore, Fleet, serve
from netprobe_agent.tasks import CmdResult
from tests.test_parsers import IW_LINK_CONNECTED, PING_OK
from tests.test_tasks_agent import FakeCmd, fake_files


def make_core(tmp, agents=None, central_url=""):
    fleet_path = os.path.join(tmp, "fleet.json")
    with open(fleet_path, "w") as fh:
        json.dump({"agents": agents if agents is not None else {
            "s1": {"secret": "k1", "tasks": [{"type": "sys", "every": 60}], "tasks_version": "v1"},
        }, "version": "f1"}, fh)
    cfg = {"collector_id": "c1", "secret": "kc", "site": "alpha", "central_url": central_url,
           "fleet_path": fleet_path, "queue_path": os.path.join(tmp, "cq.db"), "db_path": os.path.join(tmp, "c.db"),
           "forward_seconds": 60, "fleet_sync_seconds": 300, "batch_size": 3}
    return CollectorCore(cfg)


def signed(agent_id, secret, method, path, body=None):
    raw = protocol.canonical_json(body) if body is not None else b""
    return protocol.auth_headers(agent_id, secret, method, path, raw), raw


class Core(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.core = make_core(self.tmp)

    def test_tasks_requires_valid_signature(self):
        path = "/api/v1/agents/s1/tasks"
        h, _ = signed("s1", "k1", "GET", path)
        status, body = self.core.handle_tasks("s1", h, "10.0.0.5")
        self.assertEqual(status, 200)
        self.assertEqual(body["tasks"], [{"type": "sys", "every": 60}])
        self.assertEqual(body["version"], "v1")
        h, _ = signed("s1", "MAUVAIS", "GET", path)
        self.assertEqual(self.core.handle_tasks("s1", h, None)[0], 401)
        h, _ = signed("inconnu", "k1", "GET", "/api/v1/agents/inconnu/tasks")
        status, body = self.core.handle_tasks("inconnu", h, None)
        self.assertEqual(status, 401)
        self.assertIn("inconnue", body["error"])

    def test_measurements_identity_comes_from_signature(self):
        path = "/api/v1/agents/s1/measurements"
        payload = {"measurements": [
            {"task": "ping:x", "at": "2026-09-06T10:00:00Z", "ok": True, "data": {"rtt_avg_ms": 1.2}, "agent_id": "USURPE"},
            {"task": "ping:x", "at": "2026-09-06T10:00:00Z", "ok": True},           # doublon
            {"task": "", "at": "x"},                                                # invalide
        ]}
        h, raw = signed("s1", "k1", "POST", path, payload)
        status, body = self.core.handle_measurements("s1", h, raw, "10.0.0.5")
        self.assertEqual(status, 200)
        self.assertEqual((body["accepted"], body["duplicates"], len(body["rejected"])), (1, 1, 1))
        stored = self.core.queue.pending()
        self.assertEqual(stored[0]["agent_id"], "s1", "l'identité vient de la signature, jamais du corps")
        st = self.core.handle_status()[1]
        self.assertEqual(st["agents"][0]["agent_id"], "s1")
        self.assertEqual(st["agents"][0]["measurements"], 1)
        self.assertEqual(st["agents"][0]["last_ip"], "10.0.0.5")
        self.assertEqual(st["queue"]["pending"], 1)

    def test_measurements_bad_bodies(self):
        path = "/api/v1/agents/s1/measurements"
        h, raw = signed("s1", "k1", "POST", path, {"measurements": [{"task": "", "at": ""}]})
        self.assertEqual(self.core.handle_measurements("s1", h, raw)[0], 400)
        h, raw = signed("s1", "k1", "POST", path, {"nope": 1})
        self.assertEqual(self.core.handle_measurements("s1", h, raw)[0], 400)
        # Corps modifié après signature
        h, raw = signed("s1", "k1", "POST", path, {"measurements": []})
        self.assertEqual(self.core.handle_measurements("s1", h, raw + b" ")[0], 401)

    def test_forward_store_and_forward_to_central(self):
        path = "/api/v1/agents/s1/measurements"
        ms = [{"task": "sys", "at": "2026-09-06T10:%02d:00Z" % i} for i in range(7)]
        h, raw = signed("s1", "k1", "POST", path, {"measurements": ms})
        self.core.handle_measurements("s1", h, raw)
        self.core.cfg["central_url"] = "http://central"
        calls = []
        def central_down(method, path, body):
            calls.append((method, path)); return 0, None
        self.assertEqual(self.core.forward(central_down), 0)
        self.assertEqual(self.core.queue.pending_count(), 7)
        self.assertEqual(self.core.last_forward_error, "HTTP 0")
        def central_up(method, path, body):
            calls.append((method, path, len(body["measurements"]), body["site"], body["collector_id"])); return 200, {"accepted": 3}
        self.assertEqual(self.core.forward(central_up), 7)
        self.assertEqual(self.core.queue.pending_count(), 0)
        self.assertEqual([c[2] for c in calls[1:]], [3, 3, 1], "lots de batch_size")
        self.assertEqual(calls[1][1], "/agents/measurements/bulk")
        self.assertEqual(calls[1][3:], ("alpha", "c1"))
        self.assertIsNone(self.core.last_forward_error)

    def test_forward_without_central_is_noop(self):
        self.assertEqual(self.core.forward(lambda *a: (200, {})), 0)

    def test_sync_fleet_replaces_and_persists(self):
        self.core.cfg["central_url"] = "http://central"
        new_fleet = {"agents": {"s1": {"secret": "k1b", "tasks": [], "tasks_version": "v2"}, "s2": {"secret": "k2", "tasks": []}}, "version": "f2"}
        self.assertTrue(self.core.sync_fleet(lambda m, p, b: (200, new_fleet)))
        self.assertEqual(self.core.fleet.version, "f2")
        self.assertIsNotNone(self.core.fleet.get("s2"))
        reloaded = Fleet(self.core.cfg["fleet_path"])
        self.assertEqual(reloaded.version, "f2", "persistée pour survivre à un redémarrage sans central")
        self.assertFalse(self.core.sync_fleet(lambda m, p, b: (200, new_fleet)), "identique : pas de mise à jour")
        self.assertFalse(self.core.sync_fleet(lambda m, p, b: (401, {"error": "x"})))
        self.assertEqual(self.core.fleet.version, "f2")
        # Un agent sans secret dans la flotte est ignoré (jamais authentifiable)
        self.core.sync_fleet(lambda m, p, b: (200, {"agents": {"s3": {"tasks": []}}, "version": "f3"}))
        self.assertIsNone(self.core.fleet.get("s3"))


class EndToEndHttp(unittest.TestCase):
    """Sonde réelle (HttpClient urllib + LocalQueue) -> collecteur réel
    (ThreadingHTTPServer) sur 127.0.0.1."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.core = make_core(self.tmp, agents={
            "s1": {"secret": "k1", "tasks": [{"type": "wifi_link", "every": 30}, {"type": "ping", "every": 60, "params": {"host": "192.168.10.1"}}], "tasks_version": "v9"},
        })
        self.server = serve(self.core, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_probe_pulls_tasks_and_pushes_measurements(self):
        cfg = {"agent_id": "s1", "secret": "k1", "collector_url": "http://127.0.0.1:%d" % self.port, "site": "alpha",
               "poll_config_seconds": 300, "flush_seconds": 30, "batch_size": 100,
               "queue_path": os.path.join(self.tmp, "aq.db"), "default_tasks": [{"type": "sys", "every": 60}]}
        cmd = FakeCmd({"iw link": CmdResult(0, IW_LINK_CONNECTED), "ping": CmdResult(0, PING_OK)})
        agent = Agent(cfg, cmd=cmd, files=fake_files({}))
        self.assertTrue(agent.refresh_tasks(force=True))
        self.assertEqual(agent.tasks_source, "collector")
        self.assertEqual(agent.tasks_version, "v9")
        self.assertEqual([t["type"] for t in agent.tasks], ["wifi_link", "ping"])
        produced = agent.tick()
        self.assertEqual(len(produced), 2)
        self.assertEqual(agent.flush(force=True), 2)
        self.assertEqual(agent.queue.pending_count(), 0)
        # Côté collecteur : reçues, dédupliquées au second envoi, visibles localement
        self.assertEqual(self.core.queue.pending_count(), 2)
        latest = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/v1/latest?task=wifi_link" % self.port).read())
        self.assertEqual(latest["measurements"][0]["data"]["bssid"], "9c:8e:cd:12:34:56")
        status = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/v1/status" % self.port).read())
        self.assertEqual(status["agents"][0]["agent_id"], "s1")
        self.assertEqual(status["agents"][0]["measurements"], 2)
        health = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/health" % self.port).read())
        self.assertEqual(health["site"], "alpha")

    def test_wrong_secret_is_rejected_over_http(self):
        cfg = {"agent_id": "s1", "secret": "faux", "collector_url": "http://127.0.0.1:%d" % self.port, "site": "alpha",
               "poll_config_seconds": 300, "flush_seconds": 30, "batch_size": 100,
               "queue_path": os.path.join(self.tmp, "aq2.db"), "default_tasks": [{"type": "sys", "every": 60}]}
        agent = Agent(cfg, cmd=FakeCmd({}), files=fake_files({}))
        self.assertFalse(agent.refresh_tasks(force=True))
        self.assertEqual(agent.tasks_source, "local", "reste sur ses tâches locales")
        agent.tick()
        self.assertEqual(agent.flush(force=True), 0)
        self.assertEqual(agent.queue.pending_count(), 1, "conservée localement, jamais perdue")
        self.assertEqual(self.core.queue.pending_count(), 0, "rien n'est entré côté collecteur")

    def test_unknown_routes(self):
        for path in ("/nope", "/api/v1/agents/s1/autre"):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path))
                self.fail("404 attendu")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 404)


if __name__ == "__main__":
    unittest.main()
