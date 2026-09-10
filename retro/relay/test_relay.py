# -*- coding: utf-8 -*-
"""#441 : agent relais -- file locale, envoi par lots au central (faux
central HTTP en fil), rejeu après une panne, création/fin de parcours,
API locale de l'extension. `cd retro/relay && python3 -m unittest test_relay`."""
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import relay as R


class FakeCentral(BaseHTTPRequestHandler):
    """retro-api simulé : exige le jeton ; `down` simule une panne (503)."""
    received = []
    down = False
    journeys = 0

    def log_message(self, *a):
        pass

    def _json(self, code, body):
        b = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.headers.get("X-Relay-Token") != "tok":
            return self._json(401, {"error": "jeton"})
        return self._json(200, {"apps": [{"label": "gestion"}], "relay_token_configured": True})

    def do_POST(self):
        if self.headers.get("X-Relay-Token") != "tok":
            return self._json(401, {"error": "jeton"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if FakeCentral.down:
            return self._json(503, {"error": "panne"})
        if self.path == "/journeys":
            FakeCentral.journeys += 1
            return self._json(201, {"id": "j%d" % FakeCentral.journeys, "app": body.get("app"), "name": body.get("name"), "started_at": "2026-09-08T10:00:00Z"})
        if self.path.endswith("/events"):
            FakeCentral.received.extend([(self.path.split("/")[2], e["seq"], e["kind"]) for e in body["events"]])
            return self._json(200, {"added": len(body["events"])})
        if self.path.endswith("/end"):
            return self._json(200, {"id": self.path.split("/")[2], "status": "done"})
        return self._json(404, {"error": "?"})


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class RelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.central_srv = HTTPServer(("127.0.0.1", 0), FakeCentral)
        threading.Thread(target=cls.central_srv.serve_forever, daemon=True).start()
        cls.tmp = tempfile.mkdtemp()
        cls.relay = R.Relay(R.Central("http://127.0.0.1:%d" % cls.central_srv.server_port, "tok"), R.Queue(os.path.join(cls.tmp, "q.db")), flush_seconds=0.2)
        cls.srv = R.serve(cls.relay, port=0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_port

    @classmethod
    def tearDownClass(cls):
        cls.relay.stop(); cls.srv.shutdown(); cls.central_srv.shutdown()

    def _wait_empty(self, timeout=3.0):
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.relay.queue.pending_count() == 0:
                return True
            time.sleep(0.05)
        return False

    def test_chain_with_outage(self):
        FakeCentral.received = []
        code, d = _post(self.base + "/events", {"events": [{"kind": "click"}]})
        self.assertEqual(code, 409)  # pas de parcours
        code, j = _post(self.base + "/journeys", {"app": "gestion", "name": "test", "tester": "freg"})
        self.assertEqual(code, 201)
        jid = j["id"]
        code, d = _post(self.base + "/events", {"events": [{"kind": "navigation", "data": {"url": "http://a/"}}, {"kind": "dom"}]})
        self.assertEqual((code, d["queued"], d["last_seq"]), (200, 2, 2))
        self.assertTrue(self._wait_empty())
        self.assertEqual(FakeCentral.received, [(jid, 1, "navigation"), (jid, 2, "dom")])
        # panne du central : la file garde tout, dans l'ordre, puis rejoue
        FakeCentral.down = True
        _post(self.base + "/events", {"events": [{"kind": "click"}, {"kind": "submit"}]})
        _post(self.base + "/mark", {"label": "après"})
        self.assertFalse(self.relay.flush_once())
        self.assertIn("panne", self.relay.last_error)
        self.assertEqual(self.relay.queue.pending_count(), 3)
        FakeCentral.down = False
        self.assertTrue(self._wait_empty())
        self.assertEqual([x[1:] for x in FakeCentral.received[2:]], [(3, "click"), (4, "submit"), (5, "mark")])
        # statut, fin (vide la file d'abord), apps transmises
        with urllib.request.urlopen(self.base + "/status") as r:
            st = json.loads(r.read())
        self.assertEqual((st["current"]["id"], st["sent"], st["pending"]), (jid, 5, 0))
        _post(self.base + "/events", {"events": [{"kind": "click"}]})
        code, d = _post(self.base + "/journeys/%s/end" % jid, {})
        self.assertEqual((code, d["status"]), (200, "done"))
        self.assertEqual(self.relay.queue.pending_count(), 0)
        self.assertIsNone(self.relay.current)
        with urllib.request.urlopen(self.base + "/apps") as r:
            self.assertEqual(json.loads(r.read())["apps"][0]["label"], "gestion")

    def test_bad_token_and_unknown_journey(self):
        FakeCentral.received = []
        bad = R.Relay(R.Central("http://127.0.0.1:%d" % self.central_srv.server_port, "mauvais"), R.Queue(os.path.join(self.tmp, "q2.db")))
        code, d = bad.create_journey({"app": "x"})
        self.assertEqual(code, 401)
        # un lot pour un parcours que le central refuse (404/409) est abandonné, la file ne se bloque pas
        q = R.Queue(os.path.join(self.tmp, "q3.db"))
        rl = R.Relay(R.Central("http://127.0.0.1:%d" % self.central_srv.server_port, "tok"), q)
        q.put("inconnu", [{"kind": "click"}])
        FakeCentral.down = False
        self.assertTrue(rl.flush_once())  # 200 chez le faux central (il accepte tout) -> acquitté
        self.assertEqual(q.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
