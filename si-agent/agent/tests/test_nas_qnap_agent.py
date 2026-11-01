# -*- coding: utf-8 -*-
"""#940 : commande nas-qnap-ctl côté agent -- essai en lecture, executer gardé par intervention."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tests.test_si_agent as _base  # noqa: E402


class FakeRun:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


class NasQnapAgent(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def _conf(self):
        p = os.path.join(tempfile.mkdtemp(), "nas-qnap.json")
        with open(p, "w") as fh:
            json.dump([{"name": "nas-1", "host": "192.0.2.9", "user": "admin", "key": "/k",
                        "actions": {"snapshot": {"commande": "qcli_snapshot -c -v {volume}", "lecture": False}, "liste": {"commande": "qcli_snapshot -l", "lecture": True}}}], fh)
        return p

    def test_essai_lecture_et_executer_intervention(self):
        conf = self._conf()
        vus = {}
        import itertools
        t = itertools.count(1_700_000_000)
        self.agent.clock = lambda: next(t)     # horodatages distincts : la file locale ignore les doublons (task, at)
        self.agent.cmd = lambda argv, timeout=None, env=None, confined=None: (vus.__setitem__("argv", argv), FakeRun("snap1\nsnap2"))[1]
        self.agent.cfg["remote_shell"] = "off"
        self.assertFalse(self.agent.execute_command({"id": "c0", "type": "nas-qnap-ctl", "params": {"nas": "nas-1", "mode": "essai", "action": "liste", "config": conf}})["ok"])
        self.agent.cfg["remote_shell"] = "lecture"
        r = self.agent.execute_command({"id": "c1", "type": "nas-qnap-ctl", "params": {"nas": "nas-1", "mode": "essai", "action": "liste", "config": conf}})
        self.assertTrue(r["ok"], r)
        self.assertEqual(vus["argv"][-2:], ["admin@192.0.2.9", "qcli_snapshot -l"])
        self.assertEqual(r["result"]["sortie"], "snap1\nsnap2")
        r = self.agent.execute_command({"id": "c2", "type": "nas-qnap-ctl", "params": {"nas": "nas-1", "mode": "executer", "action": "snapshot", "args": {"volume": "DataVol1"}, "config": conf}})
        self.assertFalse(r["ok"]); self.assertIn("intervention", r["error"])
        self.agent.cfg["remote_shell"] = "intervention"
        r = self.agent.execute_command({"id": "c3", "type": "nas-qnap-ctl", "params": {"nas": "nas-1", "mode": "executer", "action": "snapshot", "args": {"volume": "DataVol1"}, "config": conf}})
        self.assertTrue(r["ok"], r)
        self.assertEqual(vus["argv"][-1], "qcli_snapshot -c -v DataVol1")
        self.assertIn("executer", [m["data"]["mode"] for m in self.agent.queue.latest(task="nas-qnap-ctl", limit=5)])
        # commande libre : lecture seulement, jamais en executer
        r = self.agent.execute_command({"id": "c4", "type": "nas-qnap-ctl", "params": {"nas": "nas-1", "mode": "essai", "commande": "ls -1 /share", "config": conf}})
        self.assertTrue(r["ok"]) 
        r = self.agent.execute_command({"id": "c5", "type": "nas-qnap-ctl", "params": {"nas": "nas-1", "mode": "executer", "commande": "ls -1 /share", "config": conf}})
        self.assertFalse(r["ok"])

    def test_nas_inconnu(self):
        self.agent.cfg["remote_shell"] = "intervention"
        r = self.agent.execute_command({"id": "c6", "type": "nas-qnap-ctl", "params": {"nas": "zz", "mode": "essai", "action": "liste", "config": self._conf()}})
        self.assertFalse(r["ok"]); self.assertIn("absent", r["error"])
