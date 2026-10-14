# -*- coding: utf-8 -*-
"""#756 : gestes encadrés (liste fermée, listes blanches, motif, audit)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import hostops  # noqa: E402


class Runner:
    def __init__(self, code=0, out=""):
        self.calls, self.code, self.out = [], code, out

    def __call__(self, argv, timeout=120):
        self.calls.append(argv)
        return self.code, self.out, ""


class HostOpsTest(unittest.TestCase):
    def setUp(self):
        self.audit = os.path.join(tempfile.mkdtemp(), "a.log")

    def run_(self, params, cfg=None, runner=None, which=None):
        return hostops.run(params, cfg or {}, runner or Runner(), which=which, audit_path=self.audit, now=1)

    def test_read_actions(self):
        r = Runner()
        self.assertTrue(self.run_({"action": "journal", "unit": "ollama", "lines": 5000}, runner=r)["ok"])
        self.assertEqual(r.calls[0], ["journalctl", "-u", "ollama", "-n", "1000", "--no-pager", "-o", "short-iso"])
        self.assertIn("non autorisé", self.run_({"action": "journal", "unit": "ssh"})["error"])
        self.assertIn("non autorisé", self.run_({"action": "journal", "unit": "ollama; rm -rf /"})["error"])
        st = self.run_({"action": "service_status", "unit": "ollama"}, runner=Runner(code=3, out="inactive"))
        self.assertTrue(st["ok"]); self.assertEqual(st["code"], 3)
        self.assertIn("action", self.run_({"action": "shell", "cmd": "id"})["error"])

    def test_write_needs_reason_and_audit(self):
        self.assertIn("motif", self.run_({"action": "service_restart", "unit": "ollama"})["error"])
        r = Runner(out="active")
        res = self.run_({"action": "service_restart", "unit": "ollama", "reason": "modèle bloqué", "actor": "freg"}, runner=r)
        self.assertTrue(res["ok"]); self.assertEqual(r.calls, [["systemctl", "restart", "ollama"], ["systemctl", "is-active", "ollama"]])
        with open(self.audit) as fh:
            lines = [json.loads(l) for l in fh]
        self.assertEqual(lines[0]["refused"], "motif obligatoire pour une action qui modifie l'hôte")
        self.assertEqual((lines[1]["actor"], lines[1]["reason"], lines[1]["refused"]), ("freg", "modèle bloqué", None))

    def test_docker_and_compose(self):
        out = '{"Names": "open-webui", "Image": "ghcr.io/x/open-webui:main", "State": "running", "Status": "Up 2 h", "Ports": ""}\n'
        res = self.run_({"action": "docker_ps"}, runner=Runner(out=out))
        self.assertEqual(res["containers"][0]["name"], "open-webui")
        cfg = {"hostops": {"containers": ["open-*"], "compose_dirs": ["/opt/ia"]}}
        self.assertIn("non autorisé", self.run_({"action": "docker_restart", "container": "postgres", "reason": "test"}, cfg)["error"])
        self.assertTrue(self.run_({"action": "docker_restart", "container": "open-webui", "reason": "mise à jour"}, cfg)["ok"])
        self.assertIn("aucun", self.run_({"action": "compose_update", "dir": "/opt/ia", "reason": "mise à jour"})["error"])
        self.assertIn("non autorisé", self.run_({"action": "compose_update", "dir": "/opt/ia/../etc", "reason": "mise à jour"}, cfg)["error"])
        r = Runner()
        self.assertTrue(self.run_({"action": "compose_update", "dir": "/opt/ia/", "reason": "nouvelle image"}, cfg, runner=r)["ok"])
        self.assertEqual(r.calls[1], ["docker", "compose", "--project-directory", "/opt/ia/", "up", "-d"])
        failing = Runner(code=1)
        self.assertFalse(self.run_({"action": "compose_update", "dir": "/opt/ia", "reason": "x" * 5}, cfg, runner=failing)["ok"])
        self.assertEqual(len(failing.calls), 1)                         # up -d non tenté après un pull en échec

    def test_gpu_disabled_catalogue(self):
        r = Runner()
        self.run_({"action": "gpu"}, runner=r, which=lambda x: "/usr/bin/xpu-smi" if x == "xpu-smi" else None)
        self.assertEqual(r.calls[0], ["xpu-smi", "discovery"])
        self.assertIn("désactivés", self.run_({"action": "disk"}, {"hostops": {"enabled": False}})["error"])
        cat = hostops.catalogue({"hostops": {"units": ["ollama"]}})
        self.assertEqual(cat["units"], ["ollama"]); self.assertIn("compose_update", cat["write"])
        big = self.run_({"action": "disk"}, runner=Runner(out="x" * 50000))
        self.assertTrue(big["truncated"]); self.assertEqual(len(big["output"]), hostops.MAX_OUT)


if __name__ == "__main__":
    unittest.main()
