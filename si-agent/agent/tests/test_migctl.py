# -*- coding: utf-8 -*-
"""#774 : étapes de migration exécutées par l'agent (migctl) et sonde « migration » (état, débit, fin du journal)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from si_agent import migctl  # noqa: E402

_spec = importlib.util.spec_from_file_location("migration_report", os.path.join(HERE, "..", "plugins", "migration", "migration_report.py"))
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)

STEPS = [
    {"id": "a1", "kind": "check_ssh", "params": {"host": "pve-a.exemple"}},
    {"id": "a2", "kind": "check_space", "params": {"path": "data", "min_gb": 500}},
    {"id": "a3", "kind": "check_space", "params": {"path": "/opt/ext", "min_gb": 1}},
    {"id": "b1", "kind": "check_file", "params": {"path": "/opt/ext/pbs.zfs", "dataset": "rpool/data/vm-1-disk-0", "snapshot": "mig1"}},
    {"id": "b2", "kind": "zfs_create", "params": {"dataset": "data/ovh/pve-a"}},
    {"id": "b3", "kind": "rsync_pull", "params": {"host": "198.51.100.10", "src": "/var/lib/lxc/103/rootfs", "dest": "/data/ovh/pve-a/ct103", "conf": "/etc/pve/lxc/103.conf", "bwlimit_mb": 50}},
    {"id": "b4", "kind": "rsync_pull_all", "params": {"host": "198.51.100.11", "src_dir": "/rpool/data", "pattern": "subvol-*", "dest_dir": "/opt/ext/ovh/pve-b"}},
    {"id": "b5", "kind": "zfs_pull", "params": {"host": "198.51.100.12", "pool": "rpool/data", "ids": [102, 119], "snapshot": "mig1", "dest": "data/ovh/pve-c", "bwlimit_mb": 40}},
    {"id": "b6", "kind": "zfs_send_file", "params": {"dataset": "backup/pbs", "snapshot": "mig1", "file": "/opt/ext/pbs.zfs"}},
    {"id": "c1", "kind": "verify_rsync", "params": {"host": "198.51.100.10", "src": "/var/lib/lxc/103/rootfs", "dest": "/data/ovh/pve-a/ct103"}},
    {"id": "c2", "kind": "verify_zfs", "params": {"dest": "data/ovh/pve-c", "snapshot": "mig1"}},
]


class Validate(unittest.TestCase):
    def test_all_kinds_valid_and_bash_ok(self):
        for s in STEPS:
            st, err = migctl.validate(s)
            self.assertIsNone(err, s)
            sh = migctl.script(st)
            r = subprocess.run(["bash", "-n"], input=sh, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, "%s : %s" % (s["id"], r.stderr))
        self.assertEqual(sorted({s["kind"] for s in STEPS}), sorted(migctl.KINDS))

    def test_refus(self):
        bad = [
            {"id": "x", "kind": "rm_rf", "params": {}},
            {"id": "x y", "kind": "check_ssh", "params": {"host": "h"}},
            {"id": "x", "kind": "check_ssh", "params": {}},
            {"id": "x", "kind": "check_ssh", "params": {"host": "h; rm -rf /"}},
            {"id": "x", "kind": "rsync_pull", "params": {"host": "h", "src": "/a/../etc", "dest": "/b"}},
            {"id": "x", "kind": "rsync_pull", "params": {"host": "h", "src": "/a", "dest": "/b$(id)"}},
            {"id": "x", "kind": "rsync_pull_all", "params": {"host": "h", "src_dir": "/a", "pattern": "x;y", "dest_dir": "/b"}},
            {"id": "x", "kind": "zfs_pull", "params": {"host": "h", "pool": "rpool", "ids": ["1;x"], "snapshot": "s", "dest": "d"}},
            {"id": "x", "kind": "zfs_pull", "params": {"host": "h", "pool": "rpool", "ids": [1], "snapshot": "s`id`", "dest": "d"}},
            {"id": "x", "kind": "check_space", "params": {"path": "/a", "min_gb": "beaucoup"}},
        ]
        for s in bad:
            self.assertIsNotNone(migctl.validate(s)[1], s)

    def test_script_contenu(self):
        st, _e = migctl.validate(STEPS[5])
        sh = migctl.script(st)
        self.assertIn("--bwlimit=51200", sh)
        self.assertIn("UN AUTRE RSYNC ÉCRIT DÉJÀ", sh)
        self.assertIn("/data/ovh/pve-a/ct103.conf", sh)
        st, _e = migctl.validate(STEPS[7])
        sh = migctl.script(st)
        self.assertIn("receive_resume_token", sh); self.assertIn("zfs recv -s -u", sh); self.assertIn("102|119", sh)
        self.assertEqual(migctl.measure(st), {"type": "zfs", "target": "data/ovh/pve-c"})


class Run(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.calls = []
        self.active = 3

    def runner(self, argv):
        self.calls.append(argv)
        if argv[:2] == ["systemctl", "is-active"]:
            return (0 if self.active == 0 else 3), ("active" if self.active == 0 else "inactive"), ""
        if argv[0] == "zfs":
            return 0, "1000\n", ""
        return 0, "", ""

    def test_start_pause_resume_stop(self):
        r = migctl.run({"action": "start", "step": STEPS[8]}, self.runner, self.d, now=100.0)
        self.assertTrue(r["ok"], r)
        meta = json.load(open(os.path.join(self.d, "b6.json")))
        self.assertEqual((meta["total"], meta["measure"]["type"], meta["started_at"], meta["unit"]), (1000, "file", 100.0, "si-mig-b6"))
        self.assertTrue(os.path.exists(os.path.join(self.d, "b6.sh")))
        sr = next(c for c in self.calls if c[0] == "systemd-run")
        self.assertIn("si-mig-b6", sr); self.assertIn("b6.rc", sr[-1])
        self.active = 0
        self.assertFalse(migctl.run({"action": "start", "step": STEPS[8]}, self.runner, self.d)["ok"])   # tourne déjà
        self.assertTrue(migctl.run({"action": "pause", "id": "b6"}, self.runner, self.d)["ok"])
        self.assertTrue(os.path.exists(os.path.join(self.d, "b6.paused")))
        self.assertTrue(migctl.run({"action": "resume", "id": "b6"}, self.runner, self.d)["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.d, "b6.paused")))
        self.assertTrue(migctl.run({"action": "stop", "id": "b6"}, self.runner, self.d)["ok"])
        self.assertEqual(open(os.path.join(self.d, "b6.rc")).read().strip(), "143")
        self.assertFalse(migctl.run({"action": "x"}, self.runner, self.d)["ok"])
        self.assertFalse(migctl.run({"action": "stop", "id": "../x"}, self.runner, self.d)["ok"])


class Sonde(unittest.TestCase):
    def test_step_state(self):
        self.assertEqual(mr.step_state("active", None, False), "running")
        self.assertEqual(mr.step_state("active", None, True), "paused")
        self.assertEqual(mr.step_state("inactive", 0, False), "done")
        self.assertEqual(mr.step_state("inactive", 7, False), "failed")
        self.assertEqual(mr.step_state("inactive", 143, False), "stopped")
        self.assertEqual(mr.step_state("inactive", None, False), "unknown")

    def test_rate(self):
        self.assertEqual(mr.rate(2000, {"size": 1000, "at": 10.0}, 20.0), 100)
        self.assertIsNone(mr.rate(2000, None, 20.0))
        self.assertIsNone(mr.rate(500, {"size": 1000, "at": 10.0}, 20.0))

    def test_main(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "data.bin")
        open(f, "wb").write(b"x" * 500)
        json.dump({"id": "b6", "kind": "zfs_send_file", "title": "copie", "unit": "si-mig-b6", "started_at": 1e12, "measure": {"type": "file", "target": f}, "total": 1000},
                  open(os.path.join(d, "b6.json"), "w"))
        open(os.path.join(d, "b6.log"), "w").write("vieux\n@@START x\nligne 1\nPermission denied (publickey).\n")
        open(os.path.join(d, "b6.rc"), "w").write("255\n")
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            mr.main(["--dir", d, "--state", os.path.join(d, "st.json")])
        out = json.loads(buf.getvalue())
        s = out["steps"][0]
        self.assertEqual((s["state"], s["rc"], s["size"], s["pct"]), ("failed", 255, 500, 50.0))
        self.assertNotIn("vieux", s["log_tail"])
        self.assertIn("Permission denied (publickey).", s["log_tail"])


if __name__ == "__main__":
    unittest.main()
