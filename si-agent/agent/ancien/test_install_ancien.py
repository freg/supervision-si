# -*- coding: utf-8 -*-
"""Tests #867 : installeur des hôtes anciens -- généré à jour, syntaxe sh/dash, choix du mode, relevé embarqué."""
import os
import re
import subprocess
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, "..", "plugins", "systemes"))
import importlib.util  # noqa: E402
import systemes  # noqa: E402

spec = importlib.util.spec_from_file_location("mk", os.path.join(ICI, "make-installer.py"))
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
SCRIPT = os.path.join(ICI, "install-ancien.sh")


def lancer(faux, *args):
    env = dict(os.environ, SI_ANCIEN_FAUX=faux)
    env.pop("SSH_CLIENT", None)
    p = subprocess.run(["sh", SCRIPT] + list(args), capture_output=True, text=True, env=env, timeout=30)
    return p.returncode, p.stdout + p.stderr


class InstallAncien(unittest.TestCase):
    def test_genere_a_jour(self):
        with open(SCRIPT, encoding="utf-8") as f:
            self.assertEqual(f.read(), mk.generer(), "relancer make-installer.py")

    def test_syntaxe(self):
        for sh in ("sh", "dash", "bash"):
            if subprocess.run(["which", sh], capture_output=True).returncode == 0:
                self.assertEqual(subprocess.run([sh, "-n", SCRIPT]).returncode, 0, sh)

    def test_debian4_et_5_releve(self):
        for faux in ("4.0|i686|2.3.6||0.9.8c|4.3p2", "5.0.10|i686|2.7||0.9.8g|5.1p1", "5.0.10|x86_64|2.7||0.9.8g|5.1p1"):
            code, out = lancer(faux)
            self.assertEqual(code, 0, out)
            self.assertIn("mode retenu : releve", out)
            self.assertIn("fin de support", out)
            self.assertIn("rien n'a été modifié", out)
            self.assertIn('command="/usr/local/sbin/si-agent-releve",no-pty', out)

    def test_recent_agent(self):
        code, out = lancer("12.7|x86_64|2.36|3.11|3.0.15|9.2p1")
        self.assertIn("mode retenu : agent", out)
        self.assertIn("install.sh", out)
        self.assertNotIn("fin de support", out)
        code, out = lancer("9.13|i686|2.24|3.5|1.1.0l|7.4p1")  # r2d2 : i686 + Python 3.5 -> relevé
        self.assertIn("mode retenu : releve", out)
        code, out = lancer("12.7|x86_64|2.36|3.11|3.0.15|9.2p1", "--force-releve")
        self.assertIn("mode retenu : releve", out)

    def test_installer_refuse_sans_root_ou_cle(self):
        code, out = lancer("4.0|i686|2.3.6||0.9.8c|4.3p2", "--installer")
        self.assertNotEqual(code, 0)
        self.assertRegex(out, r"root|--cle")

    def test_option_inconnue(self):
        self.assertEqual(lancer("4.0|i686|2.3.6||||", "--bidon")[0], 2)

    def test_releve_embarque_identique_et_lisible(self):
        with open(SCRIPT, encoding="utf-8") as f:
            s = f.read()
        inv = re.search(r"<<'SI_INVENTAIRE_FIN'\n(.*?)\nSI_INVENTAIRE_FIN\n", s, re.S).group(1)
        self.assertEqual(inv, systemes.INVENTAIRE_SH.strip("\n"))
        p = subprocess.run(["sh", "-s"], input=inv, capture_output=True, text=True, timeout=120)
        r = systemes.parse_systeme(p.stdout)
        self.assertTrue(r and r.get("noyau") and r.get("os"))


if __name__ == "__main__":
    unittest.main()
