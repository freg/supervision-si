"""Tests #624 : central local -- enrôlement, configuration et commandes signées, mesures, interface."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import local_central as lc  # noqa: E402
from si_agent import control, protocol  # noqa: E402


class Args:
    listen = "127.0.0.1"; port = 0; site = "test"; http = True; advertise_ip = "127.0.0.1"; interval = 30
    plugins = "web-audit"; plugin_arg = ["web-audit=--urls https://exemple.test"]; rebuild_archive = False; no_archive = True; verbose = False; commands_poll = 5

    def __init__(self, data):
        self.data = data


class LocalCentralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.central = lc.Central(Args(cls.tmp))
        lc.Handler.central = cls.central
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), lc.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def call(self, method, path, body=None, headers=None):
        raw = protocol.canonical_json(body) if body is not None else b""
        req = urllib.request.Request(self.base + path, data=raw if body is not None else None, method=method, headers=headers or {})
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def signed(self, method, path, aid, secret, body=None):
        raw = protocol.canonical_json(body) if body is not None else b""
        return self.call(method, path, body, protocol.auth_headers(aid, secret, method, path, raw))

    def test_chaine(self):
        c = self.central
        st, b, _ = self.call("POST", "/api/v1/enroll", {"token": "faux", "hostname": "PC", "platform": "windows"})
        self.assertEqual(st, 403)
        st, b, _ = self.call("POST", "/api/v1/enroll", {"token": c.state.data["token"], "hostname": "PC-PILOTE 01", "platform": "windows"})
        self.assertEqual(st, 201); e = json.loads(b); aid, sec = e["agent_id"], e["secret"]
        self.assertEqual(aid, "pc-pilote-01"); self.assertEqual(e["plugins"], ["web-audit"]); self.assertIsNone(e["ca_sha256"])
        # non signé / mal signé
        self.assertEqual(self.call("GET", "/api/v1/agents/%s/config" % aid)[0], 401)
        self.assertEqual(self.signed("GET", "/api/v1/agents/%s/config" % aid, aid, "mauvais")[0], 401)
        # configuration signée, plugin signé avec le secret de l'agent
        st, b, h = self.signed("GET", "/api/v1/agents/%s/config" % aid, aid, sec)
        self.assertEqual(st, 200); self.assertTrue(control.verify_response(sec, h, b)[0])
        cfg = json.loads(b); self.assertEqual(cfg["host_interval_seconds"], 30); self.assertEqual(cfg["commands_poll_seconds"], 5); man = cfg["plugins"][0]["manifest"]
        self.assertEqual(man["args"], ["--urls", "https://exemple.test"])
        import hmac, hashlib
        self.assertEqual(man["signature"], hmac.new(sec.encode(), control.plugin_signature_message("web-audit", man["version"], man["sha256"]).encode(), hashlib.sha256).hexdigest())
        # commande depuis l'interface, servie signée, acquittée
        st, b, _ = self.call("POST", "/ui/command", {"agent_id": aid, "type": "image_host", "params": {"target": "C:"}})
        self.assertEqual(st, 400)
        st, b, _ = self.call("POST", "/ui/command", {"agent_id": aid, "type": "image_host", "params": {"target": "\\\\nas\\p2v", "drives": "C:"}})
        self.assertEqual(st, 201); cid = json.loads(b)["id"]
        st, b, h = self.signed("GET", "/api/v1/agents/%s/commands" % aid, aid, sec)
        self.assertTrue(control.verify_response(sec, h, b)[0]); cmds = json.loads(b)["commands"]
        self.assertEqual([x["id"] for x in cmds], [cid]); self.assertEqual(cmds[0]["params"]["drives"], "C:")
        st, b, _ = self.signed("POST", "/api/v1/agents/%s/commands/%s/ack" % (aid, cid), aid, sec, {"ok": True, "result": {"started": True}})
        self.assertEqual(st, 200)
        self.assertEqual(self.signed("GET", "/api/v1/agents/%s/commands" % aid, aid, sec)[1], protocol.canonical_json({"commands": []}))
        # mesures + événements
        st, b, _ = self.signed("POST", "/api/v1/agents/%s/measurements" % aid, aid, sec, {"measurements": [
            {"task": "host", "at": "2026-09-26T10:00:00Z", "ok": True, "data": {"hostname": "PC"}, "error": None},
            control.make_event(aid, "image-started", "info", "image lancée", {"file": "x.vhdx"})]})
        self.assertEqual(st, 201); self.assertEqual(json.loads(b)["stored"], 2)
        ui = c.ui_state()
        self.assertEqual(ui["measurements"][aid]["host"]["data"]["hostname"], "PC")
        self.assertEqual(ui["events"][0]["kind"], "image-started"); self.assertEqual(ui["commands"][0]["status"], "done")
        self.assertNotIn("secret", ui["agents"][0])
        # face publique
        self.assertEqual(self.call("GET", "/deploy/windows?token=nope")[0], 403)
        st, b, _ = self.call("GET", "/deploy/windows?token=" + c.state.data["token"]); self.assertEqual(st, 200)
        self.assertIn("-EnrollToken", b.decode()); self.assertIn("-SystemCa", b.decode()); self.assertNotIn(sec, b.decode())
        self.assertIn("central local", self.call("GET", "/")[1].decode())
        self.assertEqual(self.call("GET", "/ca")[0], 404)

    def test_transfert_image(self):
        # #634 : morceaux signés avec reprise, clôture vérifiée (via l'agent réel : HttpClient.send_raw + fil de transfert)
        import hashlib, tempfile, time as _t
        from si_agent import agent as agent_mod, uploadctl
        c = self.central
        st, b, _ = self.call("POST", "/api/v1/enroll", {"token": c.state.data["token"], "hostname": "pc-img", "platform": "windows"})
        e = json.loads(b); aid, sec = e["agent_id"], e["secret"]
        tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "PC-IMG-20260926.vhdx")
        data = os.urandom(3_000_000); open(path, "wb").write(data)
        http = agent_mod.HttpClient(self.base, aid, sec)
        base = "/api/v1/agents/%s/images/%s" % (aid, "PC-IMG-20260926.vhdx")
        # 1er morceau puis « coupure »
        st, body = http.send_raw("PUT", base + "?offset=0", data[:1_000_000]); self.assertEqual(st, 201); self.assertEqual(body["size"], 1_000_000)
        st, body = http.send_raw("PUT", base + "?offset=0", data[:10]); self.assertEqual(st, 409)  # mauvais décalage
        self.assertEqual(self.call("PUT", base + "?offset=1000000")[0], 401)  # non signé
        # reprise par le fil de l'agent lui-même
        old_chunk = uploadctl.CHUNK; uploadctl.CHUNK = 700_000
        try:
            cfg = dict(agent_mod.DEFAULTS, agent_id=aid, secret=sec, central_url=self.base, site="test", queue_path=os.path.join(tmp, "q.db"), plugins_dir=tmp, state_path=os.path.join(tmp, "s.json"))
            ag = agent_mod.Agent(cfg, http=http)
            r = ag.start_upload(path, "c1", delete_after=True); self.assertTrue(r["ok"])
            for _ in range(200):
                if ag._upload_job["state"] != "running":
                    break
                _t.sleep(0.05)
            self.assertEqual(ag._upload_job["state"], "finished", ag._upload_job.get("error"))
            ag.follow_upload()
        finally:
            uploadctl.CHUNK = old_chunk
        final = os.path.join(c.images.root, aid, "PC-IMG-20260926.vhdx")
        self.assertTrue(os.path.exists(final)); self.assertEqual(hashlib.sha256(open(final, "rb").read()).hexdigest(), hashlib.sha256(data).hexdigest())
        self.assertFalse(os.path.exists(path))  # delete_after
        kinds = [m["data"]["kind"] for m in ag.queue.pending(limit=50) if m["task"] == "event"]
        self.assertIn("image-upload-started", kinds); self.assertIn("image-upload-finished", kinds); self.assertIn("image-deleted", kinds)
        self.assertEqual(c.ui_state()["images"][0]["name"], "PC-IMG-20260926.vhdx"); self.assertTrue(c.ui_state()["images"][0]["complete"])

    def test_bootstrap_tls(self):
        win, lin = lc.bootstrap_lines("https://192.0.2.10:6444", "tok", "s", "ab" * 32, ["web-audit"])
        self.assertIn("-CaFingerprint", win); self.assertIn("SiAgentTrustAll", win); self.assertIn("-EnablePlugin", win)
        self.assertIn("curl -fsSL -k", lin); self.assertIn("SI_AGENT_CA_SHA256=\"" + "ab" * 32, lin)


if __name__ == "__main__":
    unittest.main()
