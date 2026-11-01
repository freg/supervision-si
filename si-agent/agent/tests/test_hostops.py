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


class ActionsDepuisOs(unittest.TestCase):
    """#880 : ping vers une adresse tierce, processus, réseau, journal du système ; dans un conteneur (pct exec)."""
    W = staticmethod(lambda x: "/usr/sbin/" + x if x in ("pct", "journalctl", "iftop") else None)

    def test_ping(self):
        argvs, err = hostops.plan({"action": "ping", "target": "192.0.2.10", "count": 99}, {})
        self.assertIsNone(err)
        self.assertEqual(argvs, [["ping", "-n", "-c", "20", "-W", "2", "192.0.2.10"]])
        for bad in ("-c 9 x", "a;id", "$(id)", "", "x y"):
            self.assertEqual(hostops.plan({"action": "ping", "target": bad}, {})[1], "adresse invalide (IPv4, IPv6 ou nom)")
        self.assertIsNone(hostops.plan({"action": "ping", "target": "2001:db8::1"}, {})[1])

    def test_top_net_syslog(self):
        self.assertIn("top -b -n 1", hostops.plan({"action": "top"}, {})[0][0][2])
        net = hostops.plan({"action": "net"}, {}, which=self.W)[0]
        self.assertEqual(len(net), 3)                                   # débits, iftop présent, connexions
        self.assertEqual(net[1][0], "iftop")
        self.assertEqual(len(hostops.plan({"action": "net"}, {}, which=lambda x: None)[0]), 2)
        self.assertEqual(hostops.plan({"action": "syslog", "lines": 5, "priority": "err"}, {}, which=self.W)[0][0],
                         ["journalctl", "-n", "10", "--no-pager", "-o", "short-iso", "-p", "err"])
        self.assertIn("tail -n 200", hostops.plan({"action": "syslog"}, {}, which=lambda x: None)[0][0][2])

    def test_conteneur(self):
        argvs, err = hostops.plan({"action": "top", "ct": "108"}, {}, which=self.W)
        self.assertIsNone(err)
        self.assertEqual(argvs[0][:4], ["pct", "exec", "108", "--"])
        net = hostops.plan({"action": "net", "ct": 108}, {}, which=self.W)[0]
        self.assertTrue(all(v[:4] == ["pct", "exec", "108", "--"] for v in net))
        self.assertFalse(any("iftop" in v for v in net))               # iftop de l'hôte, pas forcément dans le CT
        self.assertEqual(hostops.plan({"action": "top", "ct": "1;x"}, {}, which=self.W)[1], "numéro de conteneur invalide")
        self.assertIn("pct absent", hostops.plan({"action": "top", "ct": "108"}, {}, which=lambda x: None)[1])
        self.assertEqual(hostops.plan({"action": "ping", "target": "192.0.2.1", "ct": "108"}, {})[0][0][0], "ping")   # ping : depuis le nœud

    def test_execution_et_audit(self):
        with tempfile.TemporaryDirectory() as d:
            r = hostops.run({"action": "ping", "target": "192.0.2.10"}, {}, lambda argv, t: (0, "4 packets transmitted, 4 received", ""),
                            audit_path=os.path.join(d, "a.log"))
            self.assertTrue(r["ok"])
            self.assertIn("4 received", r["output"])
            with open(os.path.join(d, "a.log"), encoding="utf-8") as fh:
                self.assertEqual(json.loads(fh.readline())["action"], "ping")


if __name__ == "__main__":
    unittest.main()
