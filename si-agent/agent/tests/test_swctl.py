# -*- coding: utf-8 -*-
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from si_agent import swctl  # noqa: E402


class Build(unittest.TestCase):
    def test_managers(self):
        which = lambda n: n in ("apt-get", "brew", "winget")  # noqa: E731
        self.assertEqual(swctl.build_argv({"action": "install", "package": "vim"}, "Linux", which)[0], ["apt-get", "-y", "-q", "install", "vim"])
        self.assertEqual(swctl.build_argv({"action": "uninstall", "package": "wget"}, "Darwin", which)[0], ["brew", "uninstall", "wget"])
        argv, _, _ = swctl.build_argv({"action": "install", "package": "Mozilla.Firefox"}, "Windows", which)
        self.assertEqual(argv[:4], ["winget", "install", "--id", "Mozilla.Firefox"])
        self.assertIn("--silent", argv)
        self.assertEqual(swctl.build_argv({"action": "install", "package": "x", "manager": "dnf"}, "Linux", which)[0][0], "dnf")

    def test_refusals(self):
        for bad in ({"action": "purge", "package": "vim"}, {"action": "install", "package": "vim; rm -rf /"}, {"action": "install", "package": "--force"},
                    {"action": "install", "package": "vim", "manager": "pip"}, {"action": "install", "package": ""}):
            self.assertIsNotNone(swctl.build_argv(bad, "Linux", lambda n: True)[2], bad)
        self.assertIn("absent", swctl.build_argv({"action": "install", "package": "vim"}, "Linux", lambda n: False)[2])

    def test_run(self):
        calls = []
        def cmd(argv, timeout=None, env=None):
            calls.append((argv, env))
            return types.SimpleNamespace(returncode=0, stdout="Setting up vim\n", stderr="")
        r = swctl.run(cmd, {"action": "install", "package": "vim"}, system="Linux", which=lambda n: n == "apt-get")
        self.assertTrue(r["ok"])
        self.assertEqual(calls[0][1], {"DEBIAN_FRONTEND": "noninteractive"})
        r = swctl.run(lambda a, timeout=None, env=None: types.SimpleNamespace(returncode=100, stdout="", stderr="E: Unable to locate package foo"),
                      {"action": "install", "package": "foo"}, system="Linux", which=lambda n: n == "apt-get")
        self.assertEqual((r["ok"], r["error"]), (False, "E: Unable to locate package foo"))


if __name__ == "__main__":
    unittest.main()
