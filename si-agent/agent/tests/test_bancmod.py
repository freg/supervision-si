# -*- coding: utf-8 -*-
"""#826 modèles de VM du banc : validation, script (empreinte, snippets, agent invité, template), exécution."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import bancmod as M  # noqa: E402


class R(object):
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


class Bancmod(unittest.TestCase):
    def test_valider(self):
        v, e = M.valider({"recette": "debian13", "vmid": 9000})
        self.assertEqual((v["stockage"], v["pont"], v["disque_go"], v["autoriser_snippets"]), ("local-lvm", "vmbr0", 12, False))
        self.assertIn("recette", M.valider({"recette": "windows11", "vmid": 9000})[1])
        self.assertIn("pont", M.valider({"recette": "debian13", "vmid": 9000, "pont": "eth0; rm -rf /"})[1])
        self.assertIn("stockage", M.valider({"recette": "debian13", "vmid": 9000, "stockage": "a b"})[1])
        self.assertEqual(M.valider({"recette": "rocky9", "vmid": 9000, "disque_go": 999})[0]["disque_go"], 200)

    def test_script(self):
        for rec in M.RECETTES:
            s = M.script(M.valider({"recette": rec, "vmid": 9001, "stockage": "data-zfs", "pont": "vmbr1"})[0])
            self.assertIn("sum \"$F.part\"", s)                       # empreinte vérifiée avant usage
            self.assertIn("--agent enabled=1", s)
            self.assertIn("import-from=", s)
            self.assertIn("cicustom vendor=local:snippets/banc-vendor.yaml", s)
            self.assertIn("qemu-guest-agent", s)
            self.assertIn("qm template $V", s)
            self.assertIn("banc-modele-%s" % rec, s)
            self.assertIn("bridge=vmbr1", s)
            r = subprocess.run(["bash", "-n", "-c", s], capture_output=True, text=True)   # syntaxe bash
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('[ "1" = "1" ]', M.script(M.valider({"recette": "debian12", "vmid": 9002, "autoriser_snippets": True})[0]))

    def test_run(self):
        r = M.run(lambda argv, timeout: R(1, "", "téléchargement\nERREUR : empreinte sha512 différente : image refusée\n"), {"recette": "debian13", "vmid": 9000})
        self.assertFalse(r["ok"]); self.assertEqual(r["error"], "ERREUR : empreinte sha512 différente : image refusée")
        r = M.run(lambda argv, timeout: R(0, "modèle 9000 prêt"), {"recette": "ubuntu2404", "vmid": 9000})
        self.assertTrue(r["ok"]); self.assertEqual((r["result"]["os"], r["result"]["vmid"]), ("linux", 9000))
        self.assertFalse(M.run(None, {"recette": "x"})["ok"])


if __name__ == "__main__":
    unittest.main()
