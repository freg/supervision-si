# -*- coding: utf-8 -*-
"""Tests purs de l'audit, du garde-fou anti-force-brute (fail2ban maison)
et du parseur HTTP de l'interface de contrôle (livraison #453)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from siproxy import audit, guard, proto  # noqa: E402


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
        self.tmp.close()
        self.a = audit.Audit(path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_session_lifecycle_and_journal(self):
        self.a.start(1, "cn:freg", "connect", "192.168.1.10:443", peer="10.0.0.5")
        self.assertEqual(self.a.counters()["active"], 1)
        act = self.a.active()
        self.assertEqual(act[0]["client"], "cn:freg")
        self.assertEqual(act[0]["target"], "192.168.1.10:443")
        self.a.finish(1, bytes_up=1234, bytes_down=56789, outcome="closed")
        self.assertEqual(self.a.counters(), {"opened": 1, "closed": 1, "refused": 0, "active": 0})
        with open(self.tmp.name, encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh]
        self.assertEqual([l["event"] for l in lines], ["session-start", "session-end"])
        end = lines[1]
        self.assertEqual((end["bytes_up"], end["bytes_down"], end["outcome"]), (1234, 56789, "closed"))
        self.assertIsNotNone(end["duration_s"])
        self.assertEqual(end["peer"] if "peer" in end else lines[0]["peer"], "10.0.0.5")

    def test_refused_and_recent_never_contain_tokens(self):
        self.a.refused("token:client", "jeton refusé", kind="shell", peer="203.0.113.7")
        rec = self.a.recent(10)
        self.assertEqual(rec[-1]["event"], "refused")
        self.assertEqual(rec[-1]["reason"], "jeton refusé")
        self.assertEqual(rec[-1]["peer"], "203.0.113.7")
        with open(self.tmp.name, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertNotIn("CTOKEN", raw)
        self.assertEqual(self.a.counters()["refused"], 1)

    def test_recent_tail_and_limit(self):
        for i in range(30):
            self.a.refused("token:client", "r%d" % i)
        rec = self.a.recent(5)
        self.assertEqual(len(rec), 5)
        self.assertEqual(rec[-1]["reason"], "r29")

    def test_no_path_is_silent(self):
        a = audit.Audit(path=None)
        a.start(1, "cn:x", "shell")
        a.finish(1)
        self.assertEqual(a.recent(), [])
        self.assertEqual(a.counters()["closed"], 1)

    def test_client_label(self):
        self.assertEqual(audit.client_label("freg"), "cn:freg")
        self.assertEqual(audit.client_label(None), "token:client")
        self.assertEqual(audit.client_label(None, "host"), "token:host")


class TestGuard(unittest.TestCase):
    def test_ban_after_threshold_and_expiry(self):
        t = [1000.0]
        g = guard.Guard(threshold=3, window_s=60, ban_s=120, clock=lambda: t[0])
        self.assertFalse(g.record_failure("1.2.3.4"))
        self.assertFalse(g.record_failure("1.2.3.4"))
        self.assertTrue(g.record_failure("1.2.3.4"))      # 3e échec -> banni
        self.assertTrue(g.is_banned("1.2.3.4"))
        self.assertEqual(g.banned()[0]["ip"], "1.2.3.4")
        self.assertTrue(100 < g.banned()[0]["seconds_left"] <= 120)
        t[0] += 121
        self.assertFalse(g.is_banned("1.2.3.4"))           # expiré
        self.assertEqual(g.banned(), [])

    def test_window_slides(self):
        t = [0.0]
        g = guard.Guard(threshold=3, window_s=60, ban_s=100, clock=lambda: t[0])
        g.record_failure("a"); t[0] += 30; g.record_failure("a")
        t[0] += 40                                            # le 1er échec sort de la fenêtre
        self.assertFalse(g.record_failure("a"))              # 2 échecs dans la fenêtre seulement
        self.assertFalse(g.is_banned("a"))

    def test_success_clears_and_unban(self):
        g = guard.Guard(threshold=2, window_s=60, ban_s=100)
        g.record_failure("b")
        g.record_success("b")
        self.assertFalse(g.record_failure("b"))              # compteur remis à zéro
        self.assertTrue(g.record_failure("b"))
        self.assertTrue(g.unban("b"))
        self.assertFalse(g.is_banned("b"))
        self.assertFalse(g.unban("b"))

    def test_none_ip_ignored(self):
        g = guard.Guard(threshold=1)
        self.assertFalse(g.record_failure(None))
        self.assertFalse(g.is_banned(None))


class TestHttpParse(unittest.TestCase):
    def test_parse(self):
        m, p, h = proto.parse_http_request(b"GET /status HTTP/1.1\r\nHost: x\r\nX-Si-Proxy-Admin: abc\r\n\r\n")
        self.assertEqual((m, p), ("GET", "/status"))
        self.assertEqual(h["x-si-proxy-admin"], "abc")
        self.assertEqual(proto.parse_http_request(b"\r\n\r\n")[0], None)
        m, p, _ = proto.parse_http_request(b"post /sessions/3/kill HTTP/1.1\r\n\r\n")
        self.assertEqual((m, p), ("POST", "/sessions/3/kill"))


if __name__ == "__main__":
    unittest.main()
