# -*- coding: utf-8 -*-
"""#930 : intégration de la commande « sauvegarde-poste » à l'agent (tâche de fond, secret via env, mesure poussée)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tests.test_si_agent as _base  # noqa: E402


class FakeRun:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


class SauvegardeAgent(unittest.TestCase):
    setUp = _base.AgentTests.setUp

    def test_commande_en_fond_capture_et_mesure(self):
        vus = {}
        sortie = ("SI-BK-DEBUT\n" + '{"confs":[{"app":"Thunderbird","cle":"HKCU\\\\Software\\\\Mozilla","fichier":"confs/Thunderbird-1.reg","octets":1200}],'
                  '"dossiers":[{"app":"Thunderbird","source":"%APPDATA%\\\\Thunderbird","octets":500000}],'
                  '"destinations":[{"type":"usb","cible":"E:\\\\sauvegardes","ok":true},{"type":"unc","cible":"\\\\\\\\nas\\\\backup","ok":true}],'
                  '"archive":{"nom":"bk.zip","octets":501200,"sha256":"ABC"},"erreurs":[]}\n' + "SI-BK-FIN\n")

        def faux_cmd(argv, timeout=None, env=None, confined=None):
            vus["argv"] = argv
            vus["env"] = (confined or {}).get("env") if confined else env
            # vérifie que le script de capture a bien été écrit et contient reg export
            sp = argv[-1]
            vus["script"] = open(sp, encoding="utf-8-sig").read()
            vus["remonter"] = open(os.path.join(os.path.dirname(sp), "remonter.cmd"), encoding="utf-8").read()
            return FakeRun(sortie)

        self.agent.cmd = faux_cmd
        params = {"confs": [{"app": "Thunderbird", "cles": ["HKCU\\Software\\Mozilla"], "dossiers": ["%APPDATA%\\Thunderbird"]}],
                  "montages": {"lecteurs": [{"lettre": "Z:", "chemin": "\\\\srv\\part"}], "partages": [], "imprimantes": []},
                  "destinations": {"usb": "E:\\sauvegardes", "unc": {"chemin": "\\\\nas\\backup", "user": "superv", "secret": "TOP"}}}
        r = self.agent.execute_command({"id": "c-bk", "type": "sauvegarde-poste", "params": params})
        self.assertTrue(r["ok"] and r["result"]["started"] and r["result"]["confs"] == 1)
        self.agent._sauvegarde.join(5)
        self.assertIn("reg export", vus["script"])
        self.assertIn("net use Z:", vus["remonter"])
        self.assertEqual(vus["env"].get("SI_BK_UNC_USER"), "superv")
        self.assertEqual(vus["env"].get("SI_BK_UNC_PASS"), "TOP")
        m = self.agent.queue.latest(task="sauvegarde-poste", limit=1)[0]
        self.assertEqual(m["data"]["archive"]["nom"], "bk.zip")
        self.assertTrue(m["ok"])
        # le secret ne doit apparaître ni dans la mesure ni dans le script de capture
        import json as _j
        self.assertNotIn("TOP", _j.dumps(m))
        self.assertNotIn("TOP", vus["script"])

    def test_refus_sans_confs_et_concurrent(self):
        import threading
        self.assertFalse(self.agent.execute_command({"id": "c0", "type": "sauvegarde-poste", "params": {"confs": []}})["ok"])
        barriere = threading.Event()

        def lent(argv, timeout=None, env=None, confined=None):
            barriere.wait(5)
            return FakeRun("SI-BK-DEBUT\n{}\nSI-BK-FIN\n")
        self.agent.cmd = lent
        p = {"confs": [{"app": "A", "cles": ["HKCU\\Software\\A"], "dossiers": []}], "destinations": {}}
        self.assertTrue(self.agent.execute_command({"id": "c1", "type": "sauvegarde-poste", "params": p})["ok"])
        r2 = self.agent.execute_command({"id": "c2", "type": "sauvegarde-poste", "params": p})
        self.assertFalse(r2["ok"])
        self.assertIn("déjà en cours", r2["error"])
        barriere.set()
        self.agent._sauvegarde.join(5)


if __name__ == "__main__":
    unittest.main()
