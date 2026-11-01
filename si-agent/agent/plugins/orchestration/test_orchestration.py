# -*- coding: utf-8 -*-
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestration as P  # noqa: E402


class Collecte(unittest.TestCase):
    def test_collecte(self):
        noeuds = {"items": [{"kind": "Node", "metadata": {"name": "n1", "labels": {}}, "status": {"conditions": [{"type": "Ready", "status": "False"}]}}]}
        out = "@@K3S\n%s\n@@NOMAD\n" % json.dumps(noeuds)
        d = P.collecter(lambda a, timeout=0: types.SimpleNamespace(returncode=0, stdout=out, stderr=""))
        self.assertEqual((d["moteurs"]["k3s"]["noeuds"][0]["nom"], d["moteurs"]["nomad"]["installe"]), ("n1", False))
        self.assertEqual([a["code"] for a in d["alerts"]], ["orchestration-noeud"])
        d = P.collecter(lambda a, timeout=0: types.SimpleNamespace(returncode=2, stdout="", stderr="bash: x"))
        self.assertEqual(d["alerts"][0]["code"], "orchestration-etat")


if __name__ == "__main__":
    unittest.main()
