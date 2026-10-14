# -*- coding: utf-8 -*-
"""#750 : rapatriement d'un CT / VM depuis un nœud Proxmox distant (xferctl, fonctions pures)."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import xferctl  # noqa: E402


class XferTest(unittest.TestCase):
    def test_remotes_and_ssh(self):
        r = xferctl.load_remotes('[{"name": "pve-a", "host": "203.0.113.5", "key": "/root/.ssh/k"}, {"host": "pve-b.exemple"}, "x"]')
        self.assertEqual(set(r), {"pve-a", "pve-b.exemple"})
        a = xferctl.ssh_argv(r["pve-a"])
        self.assertIn("BatchMode=yes", a); self.assertEqual(a[-1], "root@203.0.113.5"); self.assertIn("/root/.ssh/k", a)
        self.assertEqual(xferctl.load_remotes("pas du json"), {})

    def test_check(self):
        q, err = xferctl.check({"remote": "pve-a", "vmid": 102, "newid": "9102", "storage": "local-zfs", "bwlimit_mbps": 400}, ("vmid", "newid", "storage"))
        self.assertIsNone(err); self.assertEqual(q["newid"], 9102); self.assertEqual(q["mode"], "stop")
        self.assertIn("remote", xferctl.check({"remote": "a b", "vmid": 1}, ("vmid",))[1])
        self.assertIn("vmid", xferctl.check({"remote": "a", "vmid": 50}, ("vmid",))[1])
        self.assertIn("window", xferctl.check({"remote": "a", "vmid": 150, "window": "20h"}, ("vmid",))[1])
        self.assertIn("storage", xferctl.check({"remote": "a", "vmid": 150, "newid": 151, "storage": "../x"}, ("vmid", "newid", "storage"))[1])

    def test_export_restore(self):
        q, _ = xferctl.check({"remote": "a", "vmid": 109, "newid": 9109, "storage": "local-zfs", "bwlimit_mbps": 80}, ("vmid", "newid", "storage"))
        a = xferctl.export_argv({"host": "203.0.113.5"}, q)
        self.assertEqual(a[-1], "vzdump 109 --stdout --compress zstd --mode stop --bwlimit 10000")
        self.assertEqual(xferctl.archive_name("lxc", 109, "2026_10_14-10_11_35"), "vzdump-lxc-109-2026_10_14-10_11_35.tar.zst")
        self.assertEqual(xferctl.restore_argv(q, "/d/x.tar.zst")[:3], ["pct", "restore", "9109"])
        q["kind"] = "qemu"
        self.assertEqual(xferctl.restore_argv(q, "/d/x.vma.zst")[:3], ["qmrestore", "/d/x.vma.zst", "9109"])

    def test_window(self):
        self.assertTrue(xferctl.in_window("", "12:00"))
        self.assertTrue(xferctl.in_window("20:00-07:00", "23:10")); self.assertTrue(xferctl.in_window("20:00-07:00", "06:59"))
        self.assertFalse(xferctl.in_window("20:00-07:00", "12:00")); self.assertTrue(xferctl.in_window("12:00-14:00", "13:00"))

    def test_compare(self):
        o = {".": ("0", "1"), "./etc/a": ("10", "5"), "./tmp/x": ("3", "1"), "./var/run/a.pid": ("2", "1"), "./srv/b": ("7", "9"), "./srv/gone": ("1", "1")}
        c = {".": ("0", "2"), "./etc/a": ("10", "5"), "./srv/b": ("8", "9"), "./srv/new": ("1", "1")}
        r = xferctl.compare(o, c)
        self.assertFalse(r["identical"]); self.assertEqual((r["missing"], r["extra"], r["changed"], r["vzdump_excluded"]), (1, 1, 1, 2))
        self.assertEqual(r["samples"]["missing"], ["./srv/gone"])
        same = xferctl.compare({"./a": ("1", "1"), "./tmp/z": ("1", "1")}, {"./a": ("1", "1")})
        self.assertTrue(same["identical"])

    def test_list_script_runs(self):
        # le cœur du script de liste (find | sed | sort) sur une vraie arborescence
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "etc")); os.makedirs(os.path.join(d, "proc", "1"))
        with open(os.path.join(d, "etc", "f"), "w") as fh:
            fh.write("abc")
        out = subprocess.run(["bash", "-c", xferctl.LIST_SH % {"root": d}], capture_output=True, text=True).stdout
        rows = xferctl.parse_list(out)
        self.assertEqual(rows["./etc/f"][0], "3"); self.assertEqual(rows["./etc"][0], "0")
        self.assertNotIn("./proc/1", rows); self.assertTrue(all(v[1].isdigit() for v in rows.values()))
        self.assertIn("conteneurs seulement", xferctl.list_script("qemu", 100))
        self.assertIn("pct mount $ID", xferctl.list_script("lxc", 102))

    def test_destroy_script(self):
        q, _ = xferctl.check({"remote": "a", "vmid": 102, "slice_gb": 10, "pause_s": 20}, ("vmid",))
        s = xferctl.destroy_script(q)
        self.assertIn("grep -q stopped", s); self.assertIn("truncate -s -10G", s); self.assertIn("sleep 20", s)
        self.assertIn("pct destroy $ID --purge 1", s); self.assertIn("-gt 10737418240", s)
        self.assertEqual(subprocess.run(["bash", "-n", "-c", s]).returncode, 0)

    def test_agent_guards(self):
        from si_agent import agent as agent_mod
        d = tempfile.mkdtemp(); conf = os.path.join(d, "pve-remote.json")
        with open(conf, "w") as fh:
            fh.write('[{"name": "pve-a", "host": "203.0.113.5"}]')

        class Fake:
            cfg = {"pve_remote": conf}; state = {}; _xfer_job = None
            def clock(self): return 0
            def event(self, *a, **k): pass
            def _save_state(self): pass
        f = Fake()
        run = lambda p: agent_mod.Agent.xfer_action(f, p, "c-1")  # noqa: E731
        self.assertIn("absent", run({"action": "verify", "remote": "pve-z", "vmid": 102, "newid": 9102})["error"])
        self.assertIn("confirm", run({"action": "destroy", "remote": "pve-a", "vmid": 102, "copy": 9102, "confirm": "101"})["error"])
        self.assertIn("pas de vérification", run({"action": "destroy", "remote": "pve-a", "vmid": 102, "copy": 9102, "confirm": "102"})["error"])
        f.state["xfer_verified"] = {"pve-a:102": {"copy": 9103}}
        self.assertIn("pas de vérification", run({"action": "destroy", "remote": "pve-a", "vmid": 102, "copy": 9102, "confirm": "102"})["error"])
        self.assertIn("action", run({"action": "rm"})["error"])
        f._xfer_job = {"state": "running", "action": "export", "vmid": 109}
        self.assertIn("déjà en cours", run({"action": "verify", "remote": "pve-a", "vmid": 102, "newid": 9102})["error"])


if __name__ == "__main__":
    unittest.main()
