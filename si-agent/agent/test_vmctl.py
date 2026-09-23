"""Tests du contrôle des VM Proxmox par l'agent (#572)."""
import unittest
from types import SimpleNamespace

from si_agent import vmctl


class Vmctl(unittest.TestCase):
    def test_build_argv(self):
        self.assertEqual(vmctl.build_argv({"vmid": 103, "action": "start"}), (["qm", "start", "103"], None))
        self.assertEqual(vmctl.build_argv({"vmid": "101", "action": "shutdown"}), (["qm", "shutdown", "101", "--timeout", "120"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 200, "action": "stop", "kind": "lxc"}), (["pct", "stop", "200"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 100, "action": "snapshot", "snapname": "avant-maj", "description": "x"}), (["qm", "snapshot", "100", "avant-maj", "--description", "x"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 100, "action": "rollback", "snapname": "avant-maj"}), (["qm", "rollback", "100", "avant-maj"], None))
        for bad in ({"vmid": "x", "action": "start"}, {"vmid": 0, "action": "start"}, {"vmid": 1, "action": "delete"}, {"vmid": 1, "action": "snapshot", "snapname": "1 rm -rf"},
                    {"vmid": 1, "action": "reset", "kind": "lxc"}, {"vmid": 1, "action": "start", "kind": "docker"}):
            argv, err = vmctl.build_argv(bad)
            self.assertIsNone(argv); self.assertTrue(err)

    def test_run(self):
        calls = []
        def cmd(argv, timeout=0):
            calls.append(argv); return SimpleNamespace(returncode=0, stdout="", stderr="")
        r = vmctl.run(cmd, {"vmid": 103, "action": "start"})
        self.assertTrue(r["ok"]); self.assertEqual(calls[0], ["qm", "start", "103"])
        r = vmctl.run(lambda a, timeout=0: SimpleNamespace(returncode=2, stdout="", stderr="VM is locked (backup)"), {"vmid": 103, "action": "stop"})
        self.assertFalse(r["ok"]); self.assertIn("locked", r["error"])
        r = vmctl.run(lambda a, timeout=0: SimpleNamespace(returncode=-127, stdout="", stderr=""), {"vmid": 1, "action": "start"})
        self.assertIn("Proxmox", r["error"])
        self.assertFalse(vmctl.run(cmd, {"vmid": 1, "action": "boum"})["ok"])


if __name__ == "__main__":
    unittest.main()
