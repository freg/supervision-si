# -*- coding: utf-8 -*-
"""#920 : environnement et sortie des sondes sous Windows.
`cd si-agent/agent && python3 -m unittest tests.test_windows_env`"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from si_agent import control, host, plugins  # noqa: E402

# os.environ sous Windows : clés EN MAJUSCULES (c'est ce qui faisait perdre SystemRoot aux sondes)
ENV_WINDOWS = {"SYSTEMROOT": r"C:\WINDOWS", "WINDIR": r"C:\WINDOWS", "PSMODULEPATH": r"C:\Program Files\WindowsPowerShell\Modules",
               "PROGRAMFILES": r"C:\Program Files", "PROGRAMFILES(X86)": r"C:\Program Files (x86)", "PROGRAMDATA": r"C:\ProgramData",
               "PATH": r"C:\WINDOWS\system32", "COMSPEC": r"C:\WINDOWS\system32\cmd.exe", "TEMP": r"C:\WINDOWS\TEMP",
               "SI_AGENT_SECRET_TEST": "ne-doit-pas-passer", "HTTPS_PROXY": "http://interne:3128"}


class EnvironnementSondes(unittest.TestCase):
    def test_variables_systeme_gardees_malgre_les_majuscules(self):
        env = control.plugin_env("pc-alpha", "siege", "poste-windows", base_env=ENV_WINDOWS)
        for k in ("SYSTEMROOT", "WINDIR", "PSMODULEPATH", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "PATH", "COMSPEC", "TEMP"):
            self.assertIn(k, env, k)
        self.assertNotIn("SI_AGENT_SECRET_TEST", env)
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["SI_PLUGIN_ID"], "poste-windows")

    def test_casse_mixte_aussi(self):
        env = control.plugin_env("a", "s", "p", base_env={"SystemRoot": r"C:\Windows", "Path": r"C:\x"})
        self.assertEqual(env["SystemRoot"], r"C:\Windows")


class DecodageSortie(unittest.TestCase):
    def test_utf8_oem_bom(self):
        self.assertEqual(host.decode_sortie("relevé → ok".encode("utf-8")), "relevé → ok")
        self.assertEqual(host.decode_sortie("\ufeff{\"a\": 1}".encode("utf-8")), "{\"a\": 1}")
        self.assertEqual(host.decode_sortie("Windows a analysé le système".encode("cp850")), "Windows a analysé le système")
        self.assertEqual(host.decode_sortie(b""), "")
        self.assertEqual(host.decode_sortie("déjà décodé"), "déjà décodé")

    def test_run_cmd_confine_decode_les_octets(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = host.run_cmd([sys.executable, "-c", "print('relevé → fini')"], timeout=30, confined={"env": env, "encoding": "auto"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "relevé → fini")


class ErreurDeSonde(unittest.TestCase):
    def test_la_fin_de_la_trace_est_gardee_923(self):
        trace = "Traceback (most recent call last):\n" + "  File \"C:\\x\\poste_windows.py\", line 1, in main\n    x()\n" * 30 + "TypeError: '>' not supported"
        cmd = lambda argv, **k: host.CmdResult(1, "", trace)
        m = plugins.run_plugin({"id": "p", "runner": "python", "entry": "p.py", "path": "/x/p.py", "present": True, "timeout_seconds": 5}, cmd, now=0)
        self.assertFalse(m["ok"])
        self.assertTrue(m["error"].endswith("TypeError: '>' not supported"), m["error"][-80:])
        self.assertLessEqual(len(m["error"]), 620)


if __name__ == "__main__":
    unittest.main()
