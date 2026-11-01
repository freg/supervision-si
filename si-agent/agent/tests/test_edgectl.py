# -*- coding: utf-8 -*-
"""#776 : proxy d'entrée (edgectl) -- routes validées, configuration HAProxy déterministe et VALIDE (haproxy -c si
présent), application avec retour arrière, état."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import edgectl  # noqa: E402

R = [{"id": "glpi", "mode": "sni", "name": "GLPI.example.org", "backend": "192.0.2.10:443"},
     {"id": "ged", "mode": "sni", "name": "ged.example.org", "backend": "192.0.2.11", "send_proxy": True},
     {"id": "ssh-gw", "mode": "tcp", "front_port": 9922, "backend": "192.0.2.12:22"},
     {"id": "off", "mode": "sni", "name": "vieux.example.org", "backend": "192.0.2.13:443", "enabled": False}]


class Edge(unittest.TestCase):
    def test_validate(self):
        rts, err = edgectl.validate(R)
        self.assertIsNone(err)
        g = rts[0]
        self.assertEqual((g["name"], g["backend"], g["http_backend"]), ("glpi.example.org", "192.0.2.10:443", "192.0.2.10:80"))
        self.assertEqual(rts[1]["backend"], "192.0.2.11:443")
        bad = [[{"id": "a", "mode": "sni", "name": "x", "backend": "192.0.2.1:443"}],
               [{"id": "a", "mode": "sni", "name": "a.example.org", "backend": "192.0.2.1:443; rm"}],
               [{"id": "a", "mode": "tcp", "front_port": 443, "backend": "192.0.2.1:22"}],
               [{"id": "a", "mode": "tcp", "front_port": 22, "backend": "192.0.2.1"}],
               [{"id": "A B", "mode": "sni", "name": "a.example.org", "backend": "192.0.2.1:443"}],
               [{"id": "a", "mode": "lua", "backend": "192.0.2.1:443"}],
               R[:1] + [dict(R[0], id="autre")]]
        for b in bad:
            self.assertIsNotNone(edgectl.validate(b)[1], b)

    def test_render(self):
        rts, _e = edgectl.validate(R)
        a, b = edgectl.render(rts, "couple"), edgectl.render(list(reversed(rts)), "couple")
        self.assertEqual(a, b)   # même routes -> même texte (les deux proxys identiques)
        self.assertIn("use_backend be_glpi if { req.ssl_sni -i glpi.example.org }", a)
        self.assertIn("server s1 192.0.2.11:443 check send-proxy-v2", a)
        self.assertIn("bind :9922", a)
        self.assertNotIn("vieux.example.org", a)
        for w in ("external-check", "lua", "program"):
            self.assertNotIn(w, a)
        if shutil.which("haproxy"):
            d = tempfile.mkdtemp()
            for name, txt in (("plein.cfg", a), ("vide.cfg", edgectl.render([], "couple"))):
                f = os.path.join(d, name)
                open(f, "w").write(txt.replace("stats socket /run/haproxy/admin.sock", "stats socket %s/s.sock" % d))
                r = subprocess.run(["haproxy", "-c", "-f", f], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_apply(self):
        d = tempfile.mkdtemp()
        cfg = os.path.join(d, "haproxy.cfg")
        open(cfg, "w").write("# configuration d'origine\n")
        calls, fail = [], {"reload": False}

        def runner(argv):
            calls.append(argv)
            if argv[:2] == ["systemctl", "is-active"]:
                return 0, "active\n", ""
            if argv[:2] == ["systemctl", "reload-or-restart"] and fail["reload"]:
                return 1, "", "Job failed"
            return 0, "", ""
        reach = lambda hp, timeout=3.0: 1.0 if hp.startswith("192.0.2.10") else None   # noqa: E731
        r = edgectl.apply(R, runner, "couple", cfg, reach)
        self.assertTrue(r["ok"], r); self.assertTrue(r["changed"])
        self.assertTrue(open(cfg).read().startswith("# Généré par si-agent"))
        self.assertEqual(open(cfg + ".avant-si").read(), "# configuration d'origine\n")
        self.assertEqual(r["status"]["backends"]["192.0.2.10:443"], 1.0); self.assertIsNone(r["status"]["backends"]["192.0.2.12:22"])
        self.assertIn(["haproxy", "-c", "-f", cfg + ".si-new"], calls)
        r2 = edgectl.apply(R, runner, "couple", cfg, reach)
        self.assertFalse(r2["changed"]); self.assertEqual(r2["digest"], r["digest"])
        fail["reload"] = True
        before = open(cfg).read()
        r3 = edgectl.apply(R[:1], runner, "couple", cfg, reach)
        self.assertFalse(r3["ok"]); self.assertIn("ancienne configuration remise", r3["error"])
        self.assertEqual(open(cfg).read(), before)
        st = edgectl.run({"action": "status", "label": "couple", "routes": R}, runner, cfg, reach)
        self.assertEqual(st["expected_digest"], st["status"]["digest"])


if __name__ == "__main__":
    unittest.main()
