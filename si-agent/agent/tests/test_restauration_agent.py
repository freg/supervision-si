# -*- coding: utf-8 -*-
"""#934 : commande « restauration-poste » (simulation lecture / application intervention, gate, mesure)."""
import json
import os
import sys
import tempfile
import zipfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tests.test_si_agent as _base  # noqa: E402


class FakeRun:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _zip(manifeste=None):
    d = tempfile.mkdtemp()
    z = os.path.join(d, "sauvegarde-pc-paul.zip")
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("manifeste.json", json.dumps(manifeste or {"confs": [{"app": "Thunderbird", "cles": ["HKCU\\Software\\Mozilla"], "dossiers": []}]}))
        f.writestr("confs/Thunderbird-1.reg", "REGEDIT4")
    return z


class RestaurationAgent(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def test_gate_intervention(self):
        z = _zip()
        self.agent.cfg["remote_shell"] = "off"
        self.assertFalse(self.agent.execute_command({"id": "c0", "type": "restauration-poste", "params": {"mode": "simulation", "source": {"chemin": z}}})["ok"])
        self.agent.cfg["remote_shell"] = "lecture"
        r = self.agent.execute_command({"id": "c1", "type": "restauration-poste", "params": {"mode": "appliquer", "source": {"chemin": z}}})
        self.assertFalse(r["ok"])
        self.assertIn("intervention", r["error"])

    def test_simulation_lecture(self):
        z = _zip()
        self.agent.cfg["remote_shell"] = "lecture"
        vus = {}

        def faux_cmd(argv, timeout=None, env=None, confined=None):
            vus["script"] = open(argv[-1], encoding="utf-8-sig").read()
            return FakeRun("SI-RST-DEBUT\n" + json.dumps({"simulation": True, "confs": [{"fichier": "Thunderbird-1.reg", "octets": 10}], "dossiers": [], "erreurs": []}) + "\nSI-RST-FIN")
        self.agent.cmd = faux_cmd
        r = self.agent.execute_command({"id": "c2", "type": "restauration-poste", "params": {"mode": "simulation", "source": {"chemin": z}}})
        self.assertTrue(r["ok"] and r["result"]["mode"] == "simulation")
        self.agent._restaure.join(5)
        self.assertIn("simulation=$true", vus["script"])
        self.assertNotIn("reg import", vus["script"])
        m = self.agent.queue.latest(task="restauration-poste", limit=1)[0]
        self.assertTrue(m["data"]["simulation"])

    def test_appliquer_intervention_lit_le_manifeste(self):
        z = _zip({"confs": [{"app": "PuTTY", "cles": ["HKCU\\Software\\SimonTatham"], "dossiers": []}]})
        self.agent.cfg["remote_shell"] = "intervention"
        vus = {}

        def faux_cmd(argv, timeout=None, env=None, confined=None):
            vus["script"] = open(argv[-1], encoding="utf-8-sig").read()
            return FakeRun("SI-RST-DEBUT\n" + json.dumps({"simulation": False, "registre": [{"app": "PuTTY", "ok": True}], "dossiers": [], "montages": None, "erreurs": []}) + "\nSI-RST-FIN")
        self.agent.cmd = faux_cmd
        r = self.agent.execute_command({"id": "c3", "type": "restauration-poste", "params": {"mode": "appliquer", "source": {"chemin": z}, "options": {"registre": True, "appdata": False, "montages": False}}})
        self.assertTrue(r["ok"])
        self.agent._restaure.join(5)
        self.assertIn("reg import $f", vus["script"])
        self.assertIn("SimonTatham", vus["script"], "cibles lues depuis le manifeste de l'archive")
        m = self.agent.queue.latest(task="restauration-poste", limit=1)[0]
        self.assertTrue(m["ok"] and m["data"]["registre"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
