# -*- coding: utf-8 -*-
"""#800 : relais si-htop vu du central -- transitions des constats, routes /htop (relais simulé)."""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import htoprelay  # noqa: E402


class Transitions(unittest.TestCase):
    def test_apparition_aggravation_fin(self):
        evs, a = htoprelay.transitions({}, [{"code": "htop-cpu:pve-a", "severity": "warning", "message": "pve-a : CPU à 93 %"}, {"code": "x", "severity": "info"}])
        self.assertEqual([(e[0], e[1]) for e in evs], [("htop-alert", "warning")])
        self.assertEqual(evs[0][3]["hote"], "pve-a")
        evs, a = htoprelay.transitions(a, [{"code": "htop-cpu:pve-a", "severity": "warning", "message": "pve-a : CPU à 95 %"}])
        self.assertEqual(evs, [])                                          # persiste : rien
        evs, a = htoprelay.transitions(a, [{"code": "htop-cpu:pve-a", "severity": "critical", "message": "pve-a : CPU à 99 %"}])
        self.assertEqual([(e[1], e[3]["aggravation"]) for e in evs], [("critical", True)])
        evs, a = htoprelay.transitions(a, [])
        self.assertEqual([(e[0], e[1]) for e in evs], [("htop-recovered", "info")])
        self.assertEqual(a, {})

    def test_lecture(self):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):   # noqa: N802
                ok = self.headers.get("X-Htop-Token") == "j"
                b = json.dumps({"chemin": self.path} if ok else {"error": "jeton"}).encode()
                self.send_response(200 if ok else 401)
                self.end_headers()
                self.wfile.write(b)
        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = "http://127.0.0.1:%d" % srv.server_address[1]
            self.assertEqual(htoprelay.lire(base, "j", htoprelay.chemin_hote("pve 2/x")), (200, {"chemin": "/hote/pve%202%2Fx"}))
            self.assertEqual(htoprelay.lire(base, "mauvais", "/etat")[0], 401)
            self.assertEqual(htoprelay.lire("", "j", "/etat")[0], 503)
            self.assertEqual(htoprelay.lire("http://127.0.0.1:1", "j", "/etat", timeout=1)[0], 502)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
