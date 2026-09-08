# -*- coding: utf-8 -*-
"""Tests de si-proxy-admin-api (#454) : vérification réelle du jeton
Keycloak (paire RSA jetable, JWKS injecté), liste blanche d'utilisateurs,
pont vers l'interface de contrôle (simulée), synthèse supervision."""
import datetime as dt
import json
import os
import sys
import time
import unittest

os.environ["SI_PROXY_ADMIN_TOKEN"] = "ADMIN-test"
os.environ["SI_PROXY_ADMIN_USERS"] = "freg, francois"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jwt.algorithms import RSAAlgorithm  # noqa: E402

import app as appmod  # noqa: E402
import auth  # noqa: E402
import summary  # noqa: E402

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY2 = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_for(*keys_with_kid):
    ks = []
    for k, kid in keys_with_kid:
        j = json.loads(RSAAlgorithm.to_jwk(k.public_key()))
        j.update({"kid": kid, "use": "sig", "alg": "RS256"})
        ks.append(j)
    return {"keys": ks}


def make_token(username="freg", key=KEY, kid="k1", exp_delta=300, **extra):
    claims = {"preferred_username": username, "name": username.title(), "exp": int(time.time()) + exp_delta,
              "iat": int(time.time()), "typ": "Bearer", "azp": "supervision-hub"}
    claims.update(extra)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


class TestVerifier(unittest.TestCase):
    def setUp(self):
        self.fetches = []

        def fetch(url):
            self.fetches.append(url)
            return jwks_for((KEY, "k1"))
        self.v = auth.KeycloakVerifier("http://kc/certs", ["freg"], fetch=fetch)

    def test_valid_token(self):
        u = self.v.verify(make_token())
        self.assertEqual(u["username"], "freg")
        self.assertEqual(len(self.fetches), 1)
        self.v.verify(make_token())
        self.assertEqual(len(self.fetches), 1, "clés en cache")

    def test_wrong_key_rejected(self):
        with self.assertRaises(auth.AuthError) as cm:
            self.v.verify(make_token(key=KEY2, kid="k1"))
        self.assertEqual(cm.exception.status, 401)

    def test_unknown_kid_refetches_then_rejects(self):
        with self.assertRaises(auth.AuthError):
            self.v.verify(make_token(key=KEY2, kid="k9"))
        self.assertEqual(len(self.fetches), 2)

    def test_expired(self):
        with self.assertRaises(auth.AuthError) as cm:
            self.v.verify(make_token(exp_delta=-120))
        self.assertIn("expiré", str(cm.exception))

    def test_user_not_allowed_is_403(self):
        with self.assertRaises(auth.AuthError) as cm:
            self.v.verify(make_token(username="eve"))
        self.assertEqual(cm.exception.status, 403)

    def test_case_insensitive_user(self):
        self.assertEqual(self.v.verify(make_token(username="FREG"))["username"], "freg")

    def test_azp_check(self):
        v = auth.KeycloakVerifier("u", ["freg"], fetch=lambda _u: jwks_for((KEY, "k1")), expected_azp="supervision-hub")
        v.verify(make_token())
        with self.assertRaises(auth.AuthError):
            v.verify(make_token(azp="autre-client"))

    def test_jwks_unreachable_503(self):
        def boom(_u):
            raise OSError("down")
        v = auth.KeycloakVerifier("u", ["freg"], fetch=boom)
        with self.assertRaises(auth.AuthError) as cm:
            v.verify(make_token())
        self.assertEqual(cm.exception.status, 503)

    def test_bearer_parse(self):
        self.assertEqual(auth.bearer_from_header("Bearer abc"), "abc")
        self.assertEqual(auth.bearer_from_header("bearer abc"), "abc")
        self.assertIsNone(auth.bearer_from_header("Basic abc"))
        self.assertIsNone(auth.bearer_from_header(None))


class TestApi(unittest.TestCase):
    def setUp(self):
        appmod.verifier = auth.KeycloakVerifier("u", ["freg"], fetch=lambda _u: jwks_for((KEY, "k1")))
        self.calls = []
        self.relay = {"enabled": True, "host_connected": True, "sessions": [{"session": 3, "kind": "shell", "target": None, "client": "cn:freg"}],
                      "counters": {"opened": 5, "closed": 4, "refused": 2, "active": 1}, "banned": [{"ip": "203.0.113.9", "seconds_left": 100}]}
        now = dt.datetime.now(dt.timezone.utc)
        old = (now - dt.timedelta(hours=30)).isoformat()
        recent = (now - dt.timedelta(minutes=5)).isoformat()
        self.audit = [
            {"event": "refused", "at": old, "peer": "203.0.113.9", "reason": "jeton refusé", "client": "token:client"},
            {"event": "session-start", "at": old, "session": 1, "client": "cn:freg", "kind": "connect", "target": "192.168.1.10:443"},
            {"event": "session-end", "at": old, "session": 1, "target": "192.168.1.10:443", "bytes_up": 100, "bytes_down": 900},
            {"event": "session-start", "at": recent, "session": 2, "client": "cn:freg", "kind": "http", "target": "192.168.1.10:443"},
            {"event": "session-end", "at": recent, "session": 2, "target": "192.168.1.10:443", "bytes_up": 10, "bytes_down": 90},
            {"event": "session-start", "at": recent, "session": 3, "client": "cn:freg", "kind": "shell", "target": None},
            {"event": "refused", "at": recent, "peer": "198.51.100.4", "reason": "CN non autorisé", "client": "cn:bob"},
        ]

        def fake_control(method, path, timeout=8):
            self.calls.append((method, path))
            if path == "/status":
                return 200, dict(self.relay)
            if path.startswith("/audit"):
                return 200, {"audit": self.audit}
            if path == "/sessions/3/kill":
                return 200, {"killed": True, "session": "3"}
            if path == "/sessions/7/kill":
                return 404, {"killed": False, "session": "7"}
            if path in ("/disable", "/enable"):
                return 200, {"enabled": path == "/enable"}
            if path.startswith("/unban/"):
                return 200, {"unbanned": True, "ip": path[7:]}
            return 404, {"error": "route inconnue"}
        appmod.app.control_call = fake_control
        self.c = appmod.app.test_client()

    def h(self, **kw):
        return {"Authorization": "Bearer " + make_token(**kw)}

    def test_health_public_status_guarded(self):
        self.assertEqual(self.c.get("/health").status_code, 200)
        self.assertEqual(self.c.get("/status").status_code, 401)
        self.assertEqual(self.c.get("/status", headers={"Authorization": "Bearer nimp"}).status_code, 401)
        self.assertEqual(self.c.get("/status", headers=self.h(username="eve")).status_code, 403)
        r = self.c.get("/status", headers=self.h())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["counters"]["active"], 1)

    def test_whoami(self):
        r = self.c.get("/whoami", headers=self.h())
        self.assertEqual(r.get_json(), {"username": "freg", "name": "Freg"})

    def test_actions_forwarded(self):
        self.assertEqual(self.c.post("/sessions/3/kill", headers=self.h()).status_code, 200)
        self.assertEqual(self.c.post("/sessions/7/kill", headers=self.h()).status_code, 404)
        self.assertEqual(self.c.post("/sessions/abc/kill", headers=self.h()).status_code, 400)
        self.assertEqual(self.c.post("/disable", headers=self.h()).get_json(), {"enabled": False})
        self.assertEqual(self.c.post("/enable", headers=self.h()).get_json(), {"enabled": True})
        self.assertEqual(self.c.post("/unban/203.0.113.9", headers=self.h()).get_json()["unbanned"], True)
        self.assertEqual(self.c.post("/unban/evil;rm", headers=self.h()).status_code, 400)
        # sans jeton, aucune action ne part vers le relais
        n = len(self.calls)
        self.assertEqual(self.c.post("/disable").status_code, 401)
        self.assertEqual(len(self.calls), n)

    def test_audit_limit_clamped(self):
        self.c.get("/audit?limit=99999", headers=self.h())
        self.assertIn(("GET", "/audit?limit=1000"), self.calls)

    def test_summary(self):
        r = self.c.get("/summary?hours=24", headers=self.h())
        self.assertEqual(r.status_code, 200)
        s = r.get_json()
        self.assertEqual((s["state"], s["sessions_active"], s["host_connected"]), ("ok", 1, True))
        self.assertEqual(s["refused_window"], 1)         # un refus dans les 24 h, l'ancien exclu
        self.assertEqual(s["sessions_window"], 2)
        self.assertEqual(s["last_refused"]["peer"], "198.51.100.4")
        self.assertEqual(s["last_session"]["kind"], "shell")
        self.assertEqual(len(s["targets"]), 1)
        t = s["targets"][0]
        self.assertEqual((t["host"], t["count"], t["kinds"], t["bytes"]), ("192.168.1.10", 2, ["connect", "http"], 1100))
        self.assertEqual(s["banned"][0]["ip"], "203.0.113.9")

    def test_summary_relay_down(self):
        appmod.app.control_call = lambda m, p, timeout=8: (503, {"error": "relais injoignable : refus"})
        s = self.c.get("/summary", headers=self.h()).get_json()
        self.assertEqual((s["state"], s["relay"]), ("critical", "down"))
        self.assertIn("injoignable", s["error"])


class TestSummaryPure(unittest.TestCase):
    def test_states(self):
        self.assertEqual(summary.build_summary({"host_connected": False, "enabled": True}, [])["state"], "warning")
        self.assertEqual(summary.build_summary({"host_connected": True, "enabled": False}, [])["state_text"], "bastion en pause")
        self.assertEqual(summary.build_summary({"host_connected": True, "enabled": True}, [])["state_text"], "prêt, aucune session")

    def test_target_host(self):
        self.assertEqual(summary.target_host("10.0.0.1:22"), "10.0.0.1")
        self.assertEqual(summary.target_host("[fe80::1]:22"), "fe80::1")
        self.assertEqual(summary.target_host("super"), "super")
        self.assertIsNone(summary.target_host(None))


if __name__ == "__main__":
    unittest.main()
