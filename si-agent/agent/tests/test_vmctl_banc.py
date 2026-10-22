# -*- coding: utf-8 -*-
"""#825 banc d'installation : agent invité QEMU (ping, IP, exec) ; exec réservé aux VM « banc-… », vérifié sur l'hôte."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import vmctl  # noqa: E402


class R(object):
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


class Banc(unittest.TestCase):
    def test_argv(self):
        self.assertEqual(vmctl.build_argv({"vmid": 9501, "action": "guest_ping"})[0], ["qm", "guest", "cmd", "9501", "ping"])
        self.assertEqual(vmctl.build_argv({"vmid": 9501, "action": "guest_ip"})[0][-1], "network-get-interfaces")
        a, e = vmctl.build_argv({"vmid": 9501, "action": "guest_exec", "argv": ["sh", "-c", "echo ok"], "timeout": 99999})
        self.assertEqual(a, ["qm", "guest", "exec", "9501", "--timeout", "1800", "--", "sh", "-c", "echo ok"])
        self.assertIn("QEMU", vmctl.build_argv({"vmid": 9501, "action": "guest_exec", "kind": "lxc", "argv": ["x"]})[1])
        self.assertIn("argv", vmctl.build_argv({"vmid": 9501, "action": "guest_exec", "argv": "sh -c x"})[1])
        self.assertIn("argv", vmctl.build_argv({"vmid": 9501, "action": "guest_exec", "argv": []})[1])

    def test_nom_et_lecture(self):
        self.assertEqual(vmctl.nom_banc("boot: order=scsi0\nname: banc-debian13-7\nmemory: 2048\n"), "banc-debian13-7")
        self.assertIsNone(vmctl.nom_banc("name: prod-mail\n"))
        self.assertEqual(vmctl.lire_exec('{"exitcode":0,"exited":1,"out-data":"ok\\n"}')["out"], "ok\n")
        self.assertIsNone(vmctl.lire_exec("pas du json"))

    def test_exec_refuse_hors_banc_et_code_retour(self):
        vus = []

        def cmd(conf_nom, retour):
            def f(argv, timeout):
                vus.append(argv)
                if argv[:2] == ["qm", "config"]:
                    return R(0, "name: %s\n" % conf_nom)
                return R(0, json.dumps(retour))
            return f
        r = vmctl.run(cmd("prod-mail", {}), {"vmid": 120, "action": "guest_exec", "argv": ["sh", "-c", "rm -rf /"]})
        self.assertFalse(r["ok"]); self.assertIn("pas une VM de banc", r["error"])
        self.assertEqual(len(vus), 1)   # rien exécuté dans l'invité
        r = vmctl.run(cmd("banc-w11-3", {"exitcode": 0, "exited": 1, "out-data": "Running"}), {"vmid": 9503, "action": "guest_exec", "argv": ["powershell.exe", "-Command", "x"]})
        self.assertTrue(r["ok"]); self.assertEqual(r["result"]["exec"]["out"], "Running")
        r = vmctl.run(cmd("banc-w11-3", {"exitcode": 1, "exited": 1, "err-data": "introuvable"}), {"vmid": 9503, "action": "guest_exec", "argv": ["x"]})
        self.assertFalse(r["ok"]); self.assertIn("introuvable", r["error"])


if __name__ == "__main__":
    unittest.main()
