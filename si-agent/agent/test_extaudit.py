"""Tests #687 : audit extérieur non intrusif (point d'observation)."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import extaudit  # noqa: E402


class Findings(unittest.TestCase):
    def test_site_sain(self):
        r = {"host": "app.exemple.fr", "ports": {"80": "open", "443": "open", "22": "filtered"},
             "tls": {"verified": True, "hostname_ok": True, "days_left": 60, "legacy_accepted": []},
             "https": {"headers": {"strict-transport-security": "max-age=1", "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
                                   "x-content-type-options": "nosniff", "referrer-policy": "no-referrer", "server": "nginx"}},
             "http": {"status": 301, "location": "https://app.exemple.fr/"}}
        self.assertEqual(extaudit.findings(r), [])

    def test_site_fragile(self):
        r = {"host": "vieux.exemple.fr", "ports": {"443": "open", "3389": "open", "8081": "open", "80": "open"},
             "tls": {"verified": False, "verify_error": "certificate has expired", "days_left": -3, "legacy_accepted": ["TLS 1.0"]},
             "https": {"headers": {"Server": "Apache/2.4.10 (Debian)"}},
             "http": {"status": 200}}
        fs = extaudit.findings(r)
        msgs = " | ".join(f["message"] for f in fs)
        self.assertIn("port 3389 ouvert depuis Internet (RDP)", msgs)
        self.assertIn("port 8081 ouvert", msgs)
        self.assertIn("expiré depuis 3 jour(s)", msgs)
        self.assertIn("TLS 1.0 encore accepté", msgs)
        self.assertIn("Apache/2.4.10", msgs)
        self.assertIn("ne redirige pas vers https", msgs)
        sc = extaudit.score(fs)
        self.assertEqual(sc["critical"], 2); self.assertGreaterEqual(sc["warning"], 4)

    def test_dns(self):
        self.assertEqual(extaudit.findings({"error": "résolution DNS impossible"})[0]["check"], "dns")

    def test_audit_target_simule(self):
        seen = []
        r = extaudit.audit_target({"host": "App.Exemple.fr", "ports": [443, 22, 80]}, pause=0,
                                  resolve=lambda h, p: [(0, 0, 0, "", ("192.0.2.10", 0))],
                                  tcp=lambda h, p, t: seen.append(p) or ("open" if p == 443 else "closed"),
                                  tls=lambda h, p, t: {"verified": True, "hostname_ok": True, "days_left": 5, "legacy_accepted": []},
                                  http=lambda url, t: {"status": 200, "headers": {"strict-transport-security": "x", "content-security-policy": "frame-ancestors 'self'",
                                                                                    "x-content-type-options": "nosniff", "referrer-policy": "x"}},
                                  sleep=lambda s: None)
        self.assertEqual(seen, [443, 22, 80]); self.assertEqual(r["host"], "app.exemple.fr"); self.assertEqual(r["addresses"], ["192.0.2.10"])
        self.assertNotIn("http", r)
        self.assertEqual([f["message"] for f in r["findings"]], ["certificat expire dans 5 jour(s)"])

    def test_cert_dates(self):
        d = extaudit.cert_dates({"notAfter": "Oct 20 12:00:00 2026 GMT", "issuer": ((("commonName", "CA test"),),)}, now=dt.datetime(2026, 10, 6))
        self.assertEqual((d["not_after"], d["days_left"], d["issuer"]), ("2026-10-20", 14, "commonName=CA test"))


if __name__ == "__main__":
    unittest.main()
