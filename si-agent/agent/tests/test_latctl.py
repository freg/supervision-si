# -*- coding: utf-8 -*-
"""#775 : mesures de latence (latctl) -- validation, script (bash -n, lecture seule), SSH, lecture des mesures."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import latctl  # noqa: E402

T = [{"id": "fa", "ip": "198.51.100.7", "ports": [443, 22], "names": ["www.example.org"]}]
OUT = """@@L|-|host|pve-a
@@L|-|missing|ping
@@L|fa|ping_loss|25
@@L|fa|ping_ms|12.345
@@L|fa|tcp_443|13100
@@L|fa|tcp_22|ERR
@@L|fa|https_ip:www.example.org|0.000010 0.012500 7.912500 7.970000 8.000000 200
@@L|fa|https_name:www.example.org|0.003000 0.000000 0.000000 0.000000 10.001000 000
@@L|fa|dns:www.example.org|203.0.113.9 
"""


class Latctl(unittest.TestCase):
    def test_validate(self):
        self.assertIsNone(latctl.validate({"targets": T})[1])
        bad = [{"targets": []}, {"targets": [{"id": "a b", "ip": "1.2.3.4"}]}, {"targets": [{"id": "a", "ip": "$(id)"}]},
               {"targets": [{"id": "a", "ip": "1.2.3.4", "ports": ["22"]}]}, {"targets": [{"id": "a", "ip": "1.2.3.4", "names": ["x;y"]}]},
               {"targets": T, "via": {"login": "root;x", "host": "h"}}, {"targets": T, "via": {"login": "francois", "host": "h", "jump": "a b"}},
               {"targets": T, "via": {"login": "francois", "host": "h", "key": "../k"}}, {"targets": [dict(T[0], id="x%d" % i) for i in range(41)]}]
        for b in bad:
            self.assertIsNotNone(latctl.validate(b)[1], b)

    def test_script(self):
        plan, _e = latctl.validate({"targets": T})
        sh = latctl.script(plan)
        self.assertEqual(subprocess.run(["bash", "-n"], input=sh, text=True).returncode, 0)
        self.assertIn("--resolve www.example.org:443:198.51.100.7", sh)
        self.assertIn("--noproxy '*'", sh)
        for w in ("rm ", "> /", "sudo"):
            self.assertNotIn(w, sh)

    def test_ssh(self):
        plan, _e = latctl.validate({"targets": T, "via": {"login": "francois", "host": "r2d2.example.org", "port": 2222, "jump": "freg@gw.example.org:9922", "sudo": True}})
        a = latctl.ssh_argv(plan["via"])
        self.assertEqual(a[-2:], ["francois@r2d2.example.org", "sudo -n bash -s"])
        self.assertIn("BatchMode=yes", a); self.assertEqual(a[a.index("-J") + 1], "freg@gw.example.org:9922"); self.assertEqual(a[a.index("-p") + 1], "2222")

    def test_parse(self):
        r = latctl.parse(OUT)
        self.assertEqual((r["host"], r["missing"]), ("pve-a", ["ping"]))
        t = r["targets"]["fa"]
        self.assertEqual((t["ping_ms"], t["ping_loss"], t["tcp"]), (12.345, 25.0, {"443": 13.1, "22": None}))
        h = t["https"]["www.example.org"]
        self.assertEqual((h["ip"]["connect_ms"], h["ip"]["tls_ms"], h["ip"]["ttfb_ms"], h["ip"]["code"], h["ip"]["ok"]), (12.5, 7900.0, 57.5, 200, True))
        self.assertFalse(h["name"]["ok"]); self.assertIsNone(h["name"]["connect_ms"])
        self.assertEqual(h["resolved"], ["203.0.113.9"])

    def test_run(self):
        calls = []

        def runner(argv, inp, timeout):
            calls.append(argv)
            return (255, "", "francois@h: Permission denied (publickey).") if argv[0] == "ssh" else (0, OUT, "")
        self.assertTrue(latctl.run({"targets": T}, runner)["ok"])
        r = latctl.run({"targets": T, "via": {"login": "francois", "host": "h"}}, runner)
        self.assertFalse(r["ok"]); self.assertIn("Permission denied (publickey)", r["error"])

    def test_reel_local(self):   # le script tourne vraiment (cible locale, sans réseau extérieur)
        plan, _e = latctl.validate({"targets": [{"id": "lo", "ip": "127.0.0.1", "ports": [1], "names": []}]})
        r = subprocess.run(["bash", "-s"], input=latctl.script(plan), capture_output=True, text=True, timeout=60)
        res = latctl.parse(r.stdout)
        self.assertIn("lo", res["targets"]); self.assertIsNone(res["targets"]["lo"]["tcp"]["1"])


if __name__ == "__main__":
    unittest.main()
