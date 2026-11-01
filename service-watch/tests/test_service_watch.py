# -*- coding: utf-8 -*-
"""Tests service-watch (#531) : zone DNS, classement, empreinte/diff,
scénario, en-têtes canari, constats, base et API (réseau simulé)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ["SERVICE_WATCH_SCHEDULER"] = "0"
os.environ["SERVICE_WATCH_DATA_DIR"] = tempfile.mkdtemp()
import checks  # noqa: E402
import store  # noqa: E402
import app as app_mod  # noqa: E402

ZONE = """$ORIGIN exemple.test.
$TTL 3600
@       IN SOA ns1.exemple.test. admin.exemple.test. (1 2 3 4 5)
@       IN NS  ns1.exemple.test.
@       IN A   203.0.113.10
www     IN A   203.0.113.10
ged     3600 IN CNAME www.exemple.test.
@       IN MX  10 mail.exemple.test.
_sip._tcp IN SRV 10 5 5060 sip.exemple.test.
*       IN A   203.0.113.11
@       IN TXT "v=spf1 -all"
; commentaire
autre.exemple.net.  IN A 198.51.100.5
"""


class Zone(unittest.TestCase):
    def test_parse_zone(self):
        c = checks.parse_zone(ZONE)
        names = [x["name"] for x in c]
        self.assertEqual(names, ["exemple.test", "www.exemple.test", "ged.exemple.test", "mail.exemple.test", "sip.exemple.test", "autre.exemple.net"])
        self.assertEqual(next(x for x in c if x["name"] == "mail.exemple.test")["hint"], "mail")
        self.assertEqual(next(x for x in c if x["name"] == "ged.exemple.test")["target"], "www.exemple.test")

    def test_parse_name_list(self):
        c = checks.parse_zone("www.exemple.test\nmail.exemple.test 203.0.113.5\npas un nom\n")
        self.assertEqual([x["name"] for x in c], ["www.exemple.test", "mail.exemple.test"])
        self.assertEqual(c[1]["target"], "203.0.113.5")
        self.assertEqual(checks.parse_zone(""), [])


class Classify(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(checks.classify({"resolved": False, "ips": [], "open_ports": []}), "silencieux")
        self.assertEqual(checks.classify({"ips": ["203.0.113.1"], "open_ports": []}), "silencieux")
        self.assertEqual(checks.classify({"ips": ["x"], "open_ports": [443], "http": {"status": 200, "title": "Accueil"}}), "web")
        self.assertEqual(checks.classify({"ips": ["x"], "open_ports": [443], "http": {"status": 200, "title": "ownCloud"}}), "ged")
        self.assertEqual(checks.classify({"ips": ["x"], "open_ports": [25, 993]}), "mail")
        self.assertEqual(checks.classify({"ips": ["x"], "open_ports": [22]}), "ssh")
        self.assertEqual(checks.classify({"ips": ["x"], "open_ports": [8443]}), "autre")


class Content(unittest.TestCase):
    def test_normalize_masks_volatile(self):
        a = checks.normalize_html("<html><script>x()</script><h1>Accueil</h1><p>Le 17/09/2026 à 14:22, 1 234 visiteurs</p><!-- c --></html>")
        b = checks.normalize_html("<html><h1>Accueil</h1><p>Le 18/09/2026 à 09:05, 987 visiteurs</p></html>")
        self.assertEqual(a, b)
        self.assertEqual(checks.fingerprint(a), checks.fingerprint(b))
        m = checks.normalize_html("<p>Météo : soleil</p>", masks=[r"Météo : \w+"])
        self.assertIn("<masque>", m)

    def test_diff(self):
        d = checks.content_diff("Bienvenue sur notre site institutionnel", "Bienvenue sur notre site hacked by")
        self.assertGreater(d["change_pct"], 20)
        self.assertTrue(any(l.startswith("+") for l in d["lines"]))
        self.assertEqual(checks.content_diff("a b c", "a b c")["change_pct"], 0.0)


class Scenario(unittest.TestCase):
    def test_evaluate_step(self):
        r = {"status": 200, "text": "Bienvenue chez nous", "headers": {"Content-Type": "text/html"}, "url": "https://www.exemple.test/", "elapsed_ms": 120}
        self.assertTrue(checks.evaluate_step({"expect": {"status": 200, "text": "bienvenue", "headers": {"content-type": "html"}, "url": "exemple.test", "max_ms": 1000}}, r)["ok"])
        e = checks.evaluate_step({"expect": {"status": [301, 302], "not_text": "Bienvenue", "max_ms": 50}}, r)
        self.assertFalse(e["ok"]); self.assertEqual(len(e["reasons"]), 3)

    def test_run_scenario_with_fake_session(self):
        import probe

        class FakeResp:
            def __init__(self, status, text, url):
                self.status_code, self.text, self.url, self.headers = status, text, url, {}

        class FakeSession:
            def __init__(self):
                self.headers, self.calls = {}, []

            def request(self, method, url, data=None, json=None, timeout=None, allow_redirects=True):
                self.calls.append((method, url, dict(data or {})))
                if url.endswith("/login"):
                    return FakeResp(302 if data.get("password") == "s3cret" else 200, "" if data.get("password") == "s3cret" else "identifiants incorrects", url)
                return FakeResp(200, "<h1>Bienvenue</h1>", url)

        fs = FakeSession()
        probe.requests.Session = lambda: fs
        steps = [{"name": "accueil", "path": "/", "expect": {"status": 200, "text": "Bienvenue"}},
                 {"name": "connexion", "path": "/login", "login": {"credential": "test-web"}, "expect": {"status": 302, "not_text": "identifiants incorrects"}}]
        out = probe.run_scenario({"name": "www.exemple.test"}, steps, {"test-web": ("alice", "s3cret")})
        self.assertTrue(out["ok"]); self.assertEqual(len(out["steps"]), 2)
        self.assertEqual(fs.calls[1][2]["username"], "alice")
        self.assertNotIn("s3cret", json.dumps(out))  # jamais de secret dans le résultat
        out = probe.run_scenario({"name": "www.exemple.test"}, steps, {"test-web": ("alice", "faux")})
        self.assertFalse(out["ok"]); self.assertEqual(out["failed_step"], "connexion")
        out = probe.run_scenario({"name": "www.exemple.test"}, steps, {})
        self.assertIn("absent du coffre", out["reasons"][0])


class Canary(unittest.TestCase):
    def test_auth_results(self):
        h = "Received: from a\nReceived: from b\nAuthentication-Results: mx.exemple.test; spf=pass smtp.mailfrom=x; dkim=fail header.d=y; dmarc=pass\n"
        self.assertEqual(checks.parse_auth_results(h), {"spf": "pass", "dkim": "fail", "dmarc": "pass"})
        self.assertEqual(checks.received_hops(h), 2)
        self.assertEqual(checks.parse_auth_results("Received-SPF: softfail (x)\n")["spf"], "softfail")

    def test_evaluate_canary(self):
        c = {"name": "mail entrant", "max_delay_s": 120}
        self.assertEqual([a["code"] for a in checks.evaluate_canary(c, {"received": True, "delay_s": 30, "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}})], [])
        self.assertEqual([a["code"] for a in checks.evaluate_canary(c, {"received": False, "waited_s": 300})], ["canary-lost"])
        codes = [a["code"] for a in checks.evaluate_canary(c, {"received": True, "delay_s": 200, "auth": {"spf": "fail", "dkim": None, "dmarc": None}, "altered": True})]
        self.assertEqual(codes, ["canary-late", "canary-auth", "canary-altered"])
        self.assertEqual([a["code"] for a in checks.evaluate_canary(c, {"send_error": "refus"})], ["canary-send-failed"])


class Evaluate(unittest.TestCase):
    def test_entry_alerts(self):
        e = {"name": "www.exemple.test", "ports": [80, 443], "expect_url": "www.exemple.test"}
        base = {"resolved": True, "ips": ["203.0.113.1"], "open_ports": [80, 443], "ports_tested": [80, 443], "kind": "web",
                "http": {"status": 200, "final_url": "https://www.exemple.test/", "elapsed_ms": 200}, "tls": {"days_left": 60, "names": ["www.exemple.test"]}}
        self.assertEqual(checks.evaluate_entry(e, base), [])
        self.assertEqual([a["code"] for a in checks.evaluate_entry(e, {"resolved": False})], ["dns-unresolved"])
        self.assertEqual([a["code"] for a in checks.evaluate_entry(e, dict(base, open_ports=[]))], ["silent"])
        r = dict(base, open_ports=[80], http=dict(base["http"], status=503, final_url="https://parking.exemple/", hosting_page="parking", elapsed_ms=9000), tls={"days_left": -3, "names": ["autre.test"]})
        codes = [a["code"] for a in checks.evaluate_entry(e, r)]
        for c in ("port-closed", "http-5xx", "http-slow", "http-redirect", "hosting-page", "cert-expired", "cert-name"):
            self.assertIn(c, codes)
        r = dict(base, tls={"days_left": 10, "names": ["*.exemple.test"]}, scenario={"ok": False, "failed_step": "connexion", "reasons": ["statut 200"]}, content_diff={"change_pct": 45.0, "reference_at": "2026-09-01"})
        codes = [a["code"] for a in checks.evaluate_entry(e, r, prev={"kind": "ged"})]
        self.assertEqual(sorted(codes), ["cert-expiring", "content-changed", "kind-changed", "scenario-failed"])
        self.assertEqual(checks.summarize(checks.evaluate_entry(e, r))["state"], "critical")


class StoreAndApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        app_mod.DB_PATH = os.path.join(self.tmp, "t.db")
        self.c = app_mod.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_import_and_gone(self):
        r = self.c.post("/service-watch/import", json={"text": ZONE, "replace": True})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.get_json()["created"], 6)
        r = self.c.post("/service-watch/import", json={"text": "www.exemple.test\n", "replace": True})
        self.assertEqual(len(r.get_json()["gone"]), 5)
        es = self.c.get("/service-watch/entries").get_json()["entries"]
        self.assertEqual(len([e for e in es if e["gone_at"]]), 5)
        self.assertEqual([e["kind"] for e in self.c.get("/service-watch/events").get_json()["events"]][:1], ["entry-gone"])

    def test_check_entry_with_fake_probe(self):
        import probe
        calls = {"n": 0}

        def fake_qualify(entry, timeout=5):
            calls["n"] += 1
            bad = calls["n"] >= 2
            return {"name": entry["name"], "resolved": True, "ips": ["203.0.113.1"], "open_ports": [443], "ports_tested": [443], "kind": "web",
                    "http": {"status": 503 if bad else 200, "final_url": "https://%s/" % entry["name"], "elapsed_ms": 100}, "tls": {"days_left": 90, "names": [entry["name"]]},
                    "_text": "<h1>Accueil</h1><p>Site %s</p>" % ("piraté" if bad else "officiel")}
        probe.qualify = fake_qualify
        sent = []
        app_mod.secrets_alert = type("S", (), {"send_email_alert": staticmethod(lambda s, b: sent.append(s) or True), "send_sms_alert": staticmethod(lambda m: False)})
        self.c.post("/service-watch/entries", json={"name": "www.exemple.test", "ports": [443], "diff_threshold_pct": 10})
        r = self.c.post("/service-watch/entries/www.exemple.test/check")
        self.assertEqual(r.get_json()["state"], "ok"); self.assertTrue(r.get_json()["result"]["content_diff"]["new_reference"])
        r = self.c.post("/service-watch/entries/www.exemple.test/check").get_json()
        self.assertEqual(r["state"], "critical")
        self.assertEqual(sorted(a["code"] for a in r["alerts"]), ["content-changed", "http-5xx"])
        self.assertEqual(len(sent), 1)  # une notification pour les deux constats
        r = self.c.post("/service-watch/entries/www.exemple.test/check").get_json()
        self.assertEqual(len(sent), 1)  # constats persistants : pas de répétition
        runs = self.c.get("/service-watch/entries/www.exemple.test/runs").get_json()
        self.assertEqual(len(runs["runs"]), 3); self.assertEqual(runs["reference"]["validated_by"], "auto")
        ev = self.c.get("/service-watch/events").get_json()["events"]
        self.assertEqual(ev[0]["kind"], "entry-alert"); self.assertEqual(ev[0]["notified"], "email")
        st = self.c.get("/service-watch/status").get_json()
        self.assertEqual(st["counts"]["critical"], 1)

    def test_canary_config_and_registry(self):
        r = self.c.post("/service-watch/canaries", json={"name": "mail entrant", "to": "c@exemple.test", "smtp_host": "smtp.exemple", "imap_host": "imap.exemple"})
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/service-watch/canaries", json={"name": "mail entrant", "to": "c@exemple.test", "smtp_host": "smtp.exemple", "imap_host": "imap.exemple", "imap_credential": "canari-imap"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.c.get("/service-watch/canaries").get_json()["canaries"][0]["config"]["imap_credential"], "canari-imap")
        conn = store.connect(app_mod.DB_PATH)
        self.assertEqual(app_mod.load_registry(conn), 3); conn.commit(); conn.close()
        es = self.c.get("/service-watch/entries").get_json()["entries"]
        self.assertEqual(len([e for e in es if e["source"] == "registry"]), 3)


if __name__ == "__main__":
    unittest.main()
