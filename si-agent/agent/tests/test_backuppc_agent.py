# -*- coding: utf-8 -*-
"""#939 : commande backuppc-ctl côté agent -- lecture libre, intervention gardée, mesure et évènement."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tests.test_si_agent as _base  # noqa: E402
from si_agent import backuppcctl as bc  # noqa: E402


class FakeRun:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


class BackuppcAgent(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def _cmd(self, vus, stdout="ok: requested backup of pc-1"):
        def faux(argv, timeout=None, env=None, confined=None):
            vus["argv"] = argv
            return FakeRun(stdout)
        return faux

    def test_status_sans_autorisation(self):
        vus = {}
        self.agent.cmd = self._cmd(vus, "%Status = ( 'pc-1' => { 'state' => 'Status_idle' } );")
        self.agent.cfg["remote_shell"] = "off"
        with mock.patch.object(bc, "binaire", return_value="/usr/share/backuppc/bin/BackupPC_serverMesg"):
            r = self.agent.execute_command({"id": "c0", "type": "backuppc-ctl", "params": {"action": "status"}})
        self.assertTrue(r["ok"], r)
        self.assertEqual(vus["argv"][-2:], ["status", "hosts"])
        self.assertEqual(self.agent.queue.latest(task="backuppc-ctl", limit=1)[0]["data"]["action"], "status")

    def test_backup_garde_par_intervention(self):
        vus = {}
        self.agent.cmd = self._cmd(vus)
        with mock.patch.object(bc, "binaire", return_value="/usr/share/backuppc/bin/BackupPC_serverMesg"):
            self.agent.cfg["remote_shell"] = "off"
            self.assertFalse(self.agent.execute_command({"id": "c1", "type": "backuppc-ctl", "params": {"action": "backup-full", "host": "pc-1"}})["ok"])
            self.agent.cfg["remote_shell"] = "lecture"
            r = self.agent.execute_command({"id": "c2", "type": "backuppc-ctl", "params": {"action": "backup-full", "host": "pc-1"}})
            self.assertFalse(r["ok"]); self.assertIn("intervention", r["error"]); self.assertNotIn("argv", vus)
            self.agent.cfg["remote_shell"] = "intervention"
            r = self.agent.execute_command({"id": "c3", "type": "backuppc-ctl", "params": {"action": "backup-full", "host": "pc-1", "actor": "freg"}})
        self.assertTrue(r["ok"], r)
        self.assertEqual(vus["argv"][-5:], ["backup", "pc-1", "pc-1", "freg", "1"])
        ev = [e for e in self.agent.queue.latest(task="event", limit=5) if e["data"].get("kind") == "backuppc"]
        self.assertTrue(ev and "demandé" in ev[0]["data"]["message"])

    def test_binaire_absent_et_hote_invalide(self):
        self.agent.cfg["remote_shell"] = "intervention"
        with mock.patch.object(bc, "binaire", return_value=None):
            r = self.agent.execute_command({"id": "c4", "type": "backuppc-ctl", "params": {"action": "stop", "host": "pc-1"}})
        self.assertFalse(r["ok"]); self.assertIn("introuvable", r["error"])
        with mock.patch.object(bc, "binaire", return_value="/x/BackupPC_serverMesg"):
            r = self.agent.execute_command({"id": "c5", "type": "backuppc-ctl", "params": {"action": "stop", "host": "pc;rm"}})
        self.assertFalse(r["ok"]); self.assertIn("invalide", r["error"])


if __name__ == "__main__":
    unittest.main()


class BackuppcRelais948(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def test_relais_ssh(self):
        import json
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "backuppc.json")
        with open(p, "w") as fh:
            json.dump([{"name": "fichiers", "host": "192.0.2.5", "user": "si-bk", "key": "/k"}], fh)
        vus = {}
        self.agent.cmd = lambda argv, timeout=None, env=None, confined=None: (vus.__setitem__("argv", argv), FakeRun("ok: requested backup of pc-1"))[1]
        self.agent.cfg["remote_shell"] = "intervention"
        r = self.agent.execute_command({"id": "r1", "type": "backuppc-ctl", "params": {"action": "backup-incr", "host": "pc-1", "actor": "freg", "config": p}})
        self.assertTrue(r["ok"], r)
        self.assertIn("si-bk@192.0.2.5", vus["argv"]); self.assertEqual(vus["argv"][-3:-1], ["sh", "-c"])
        self.assertTrue(vus["argv"][-1].endswith('"$B" backup pc-1 pc-1 freg 0'))
        self.assertEqual(r["result"]["relais"], "fichiers")
