"""Tests #617 : sonde web-audit (parse, constats, collecte avec fetch simulé, serveur HTTP local)."""
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import web_audit as wa  # noqa: E402

HTML = """<html><head><title> Intranet </title><link rel="stylesheet" href="/s.css"><link rel="canonical" href="/x">
<script src="https://cdn.exemple/app.js"></script><script src="data:text/js,1"></script></head>
<body><img src="img/logo.png"><iframe src="http://insecure.exemple/frame"></iframe><img src="img/logo.png"></body></html>"""


def fake_fetch_factory(table):
    def fetch(url, timeout=10.0, method="GET", want_body=True, **kw):
        r = {"url": url, "dns_ms": 5.0, "connect_ms": 10.0, "tls_ms": None, "ttfb_ms": 100.0, "total_ms": 150.0, "status": 200, "bytes": 10,
             "content_type": "text/html", "server": "x", "location": None, "error": None, "tls": None, "addresses": ["192.0.2.1"]}
        body = b"<html></html>"
        spec = table.get(url, {})
        r.update({k: v for k, v in spec.items() if k != "body"})
        if "body" in spec:
            body = spec["body"]; r["bytes"] = len(body)
        return r, (body if not r["error"] else None)
    return fetch


class WebAuditTests(unittest.TestCase):
    def test_parse_subresources(self):
        subs, title = wa.parse_subresources(HTML, "https://intra.exemple/app/")
        self.assertEqual(title, "Intranet")
        self.assertEqual([u for _, u in subs], ["https://intra.exemple/s.css", "https://cdn.exemple/app.js", "https://intra.exemple/app/img/logo.png", "http://insecure.exemple/frame"])

    def test_collect_redirect_sous_ressources_constats(self):
        table = {
            "https://intra.exemple/": {"status": 302, "location": "/app/"},
            "https://intra.exemple/app/": {"status": 200, "body": HTML.encode(), "ttfb_ms": 2000.0, "total_ms": 2300.0, "tls": {"version": "TLSv1.3", "cert_days_left": 7}},
            "https://cdn.exemple/app.js": {"status": 503, "content_type": "text/plain"},
            "https://intra.exemple/app/img/logo.png": {"status": 200, "total_ms": 3000.0},
            "https://down.exemple/": {"error": "connect-failed: timeout", "status": None, "total_ms": None},
        }
        out = wa.collect(["https://intra.exemple/", "https://down.exemple/"], fetch=fake_fetch_factory(table))
        u0 = out["urls"][0]
        self.assertEqual(u0["final_url"], "https://intra.exemple/app/"); self.assertEqual(len(u0["chain"]), 2); self.assertEqual(u0["title"], "Intranet")
        codes = {f["code"] for f in u0["findings"]}
        self.assertEqual(codes, {"slow-ttfb", "cert-expiring", "sub-errors", "sub-slow", "mixed-content"})
        self.assertEqual(u0["state"], "warning")
        self.assertEqual(out["urls"][1]["state"], "critical"); self.assertEqual(out["urls"][1]["findings"][0]["code"], "connect-failed")
        self.assertEqual(out["summary"], {"total": 2, "ok": 0, "warning": 1, "critical": 1, "state": "critical"})

    def test_serveur_local_reel(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    body = b"<html><head><title>ok</title><script src='/a.js'></script></head><body>x</body></html>"
                    self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                elif self.path == "/a.js":
                    self.send_response(500); self.end_headers()
                else:
                    self.send_response(404); self.end_headers()
            def log_message(self, *a):  # silence
                pass
        srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
        try:
            out = wa.collect(["http://127.0.0.1:%d/" % port, "http://127.0.0.1:%d/absent" % port], timeout=5)
        finally:
            srv.shutdown()
        u0, u1 = out["urls"]
        self.assertEqual(u0["main"]["status"], 200); self.assertIsNotNone(u0["main"]["ttfb_ms"]); self.assertIsNone(u0["main"]["tls_ms"])
        self.assertEqual(u0["subresources"][0]["status"], 500); self.assertIn("sub-errors", {f["code"] for f in u0["findings"]})
        self.assertEqual(u1["main"]["status"], 404); self.assertEqual(u1["state"], "warning")
        # DNS en échec
        r, body = wa.fetch_one("http://nom-inexistant.invalid/", timeout=3)
        self.assertTrue(r["error"].startswith("dns-failed")); self.assertIsNone(body)

    def test_cli_sans_url(self):
        p = subprocess.run([sys.executable, os.path.join(HERE, "web_audit.py")], capture_output=True, text=True, timeout=30, env={**os.environ, "ProgramData": "/nonexistent"})
        self.assertEqual(p.returncode, 0); self.assertIn("aucune URL", json.loads(p.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
