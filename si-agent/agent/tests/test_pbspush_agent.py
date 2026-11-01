# -*- coding: utf-8 -*-
"""#931 : commande « pbs-push » sur l'agent (préflight + push, extraction de l'archive, secret en env, mesure)."""
import os
import sys
import tempfile
import zipfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tests.test_si_agent as _base  # noqa: E402


class FakeRun:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


REPO = "postes-backup@pbs!sauvegarde@pbs10:backup"


class PbsPushAgent(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def test_push_extrait_et_pousse(self):
        d = tempfile.mkdtemp()
        zpath = os.path.join(d, "sauvegarde-pc-paul-20261030.zip")
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("manifeste.json", "{}")
            z.writestr("confs/x.reg", "REGEDIT4")
        vus = {}

        def faux_cmd(argv, timeout=None, env=None, confined=None):
            vus["argv"] = argv
            vus["env"] = (confined or {}).get("env") if confined else env
            vus["dossier"] = argv[2].split(":", 1)[1]
            vus["extrait"] = sorted(os.listdir(vus["dossier"]))
            return FakeRun(stdout="host/pc-paul/2026-10-30T10:00:00Z was backed up", returncode=0)

        self.agent.cmd = faux_cmd
        r = self.agent.execute_command({"id": "c-pbs", "type": "pbs-push", "params": {
            "action": "push", "fichier": zpath, "repository": REPO, "namespace": "postes",
            "backup_id": "pc-paul", "fingerprint": "AB:CD", "token_secret": "TOPSECRET"}})
        self.assertTrue(r["ok"] and r["result"]["started"])
        self.agent._pbs.join(5)
        self.assertEqual(vus["argv"][0:2], ["proxmox-backup-client", "backup"])
        self.assertIn("manifeste.json", vus["extrait"])
        self.assertEqual(vus["env"].get("PBS_PASSWORD"), "TOPSECRET")
        self.assertNotIn("TOPSECRET", " ".join(vus["argv"]), "secret jamais en argv")
        self.assertFalse(os.path.exists(vus["dossier"]), "dossier d'extraction nettoyé")
        m = self.agent.queue.latest(task="pbs-push", limit=1)[0]
        self.assertTrue(m["ok"] and m["data"]["snapshot"] == "host/pc-paul/2026-10-30T10:00:00Z")
        import json as _j
        self.assertNotIn("TOPSECRET", _j.dumps(m))

    def test_preflight_lecture(self):
        def faux_cmd(argv, timeout=None, env=None, confined=None):
            assert argv[1] == "snapshot", argv
            return FakeRun(stdout="[]", returncode=0)
        self.agent.cmd = faux_cmd
        r = self.agent.execute_command({"id": "c-pf", "type": "pbs-push", "params": {
            "action": "preflight", "repository": REPO, "namespace": "postes", "token_secret": "X"}})
        self.assertTrue(r["ok"] and r["result"]["action"] == "preflight")
        self.agent._pbs.join(5)
        m = self.agent.queue.latest(task="pbs-push", limit=1)[0]
        self.assertTrue(m["ok"] and m["data"]["action"] == "preflight")

    def test_archive_absente(self):
        self.agent.cmd = lambda *a, **k: FakeRun(returncode=0)
        r = self.agent.execute_command({"id": "c-x", "type": "pbs-push", "params": {
            "action": "push", "fichier": "/n/existe/pas.zip", "repository": REPO, "backup_id": "pc-x"}})
        self.assertTrue(r["ok"])
        self.agent._pbs.join(5)
        m = self.agent.queue.latest(task="pbs-push", limit=1)[0]
        self.assertFalse(m["ok"])
        self.assertIn("introuvable", m["data"]["erreur"])

    def test_requis(self):
        self.assertFalse(self.agent.execute_command({"id": "c1", "type": "pbs-push", "params": {"action": "push", "repository": REPO}})["ok"])
        self.assertFalse(self.agent.execute_command({"id": "c2", "type": "pbs-push", "params": {"action": "push", "fichier": "/x.zip", "backup_id": "a"}})["ok"])


if __name__ == "__main__":
    unittest.main()
