# -*- coding: utf-8 -*-
"""#774 : étapes de migration exécutées par l'agent (migctl) et sonde « migration » (état, débit, fin du journal)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import re
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

    def test_zfs_modele_basevol(self):   # CT converti en modèle : rpool/basevol-104-disk-0 (vu sur pve-3, B8 « VOLUME MANQUANT »)
        import subprocess
        st, _e = migctl.validate({"id": "b8", "kind": "zfs_pull", "params": {"host": "h", "pool": "rpool", "ids": [101, 104], "snapshot": "mig1", "dest": "d"}})
        sh = migctl.script(st)
        rx = re.search(r"grep -E '([^']+)'", sh).group(1).replace("\\$", "$")
        vols = "rpool/subvol-101-disk-0\nrpool/basevol-104-disk-0\nrpool/base-104-disk-1\nrpool/vm-1040-disk-0\nrpool/subvol-102-disk-0\n"
        out = subprocess.run(["grep", "-E", rx], input=vols, capture_output=True, text=True).stdout.split()
        self.assertEqual(out, ["rpool/subvol-101-disk-0", "rpool/basevol-104-disk-0", "rpool/base-104-disk-1"])


class Conteneur(unittest.TestCase):
    def test_ct_en_service(self):   # /var/lib/lxc/<id>/rootfs est vide vu de l'hôte : racine du CT par /proc/<pid>/root
        for k in ("rsync_pull", "verify_rsync"):
            st, e = migctl.validate({"id": "b2", "kind": k, "params": {"host": "198.51.100.10", "ct": 103, "dest": "/data/ct103"}})
            self.assertIsNone(e)
            sh = migctl.script(st)
            self.assertEqual(subprocess.run(["bash", "-n"], input=sh, text=True).returncode, 0)
            self.assertIn("lxc-info -n $ct -p -H", sh); self.assertIn("/proc/$pid/root/", sh); self.assertIn("pct unmount", sh)
            self.assertIn("'--exclude=/proc/*'", sh)
        self.assertIn("SOURCE VIDE", migctl.script(migctl.validate({"id": "b", "kind": "rsync_pull", "params": {"host": "h", "src": "/x", "dest": "/y"}})[0]))
        self.assertIsNotNone(migctl.validate({"id": "b", "kind": "rsync_pull", "params": {"host": "h", "dest": "/y"}})[1])
        self.assertIsNotNone(migctl.validate({"id": "b", "kind": "rsync_pull", "params": {"host": "h", "ct": "103; rm", "dest": "/y"}})[1])

    def test_source_vide(self):   # rsync réussi mais rien copié -> échec 12
        d = tempfile.mkdtemp()
        src, dst = os.path.join(d, "vide"), os.path.join(d, "dst")
        os.makedirs(src)
        st, _e = migctl.validate({"id": "bv", "kind": "rsync_pull", "params": {"host": "h", "src": src, "dest": dst}})
        sh = migctl.script(st).replace("-e 'ssh", "-e 'false").replace("root@h:", "")
        r = subprocess.run(["bash", "-c", sh], capture_output=True, text=True)
        self.assertEqual(r.returncode, 12, r.stdout + r.stderr)
        self.assertIn("SOURCE VIDE", r.stdout)


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
        self.assertEqual((s["state"], s["rc"], s["size"], s["pct"], s["remaining"]), ("failed", 255, 500, 50.0, 500))
        self.assertNotIn("vieux", s["log_tail"])
        self.assertIn("Permission denied (publickey).", s["log_tail"])

    def test_total_source(self):   # restant / transféré / total : total d'après `zfs list` du nœud source
        z = ("rpool\t/rpool\t9000\t9000\nrpool/subvol-101-disk-0\t/rpool/subvol-101-disk-0\t100\t250\n"
             "rpool/subvol-101-disk-1\t/rpool/subvol-101-disk-1\t50\t60\nrpool/vm-104-disk-0\t-\t400\t800\n"
             "rpool/subvol-1010-disk-0\t/rpool/subvol-1010-disk-0\t7\t7\nautre/vm-104-disk-0\t-\t5\t5\nmal\tformé\n")
        rows = mr.parse_zfs_list(z)
        self.assertEqual(len(rows), 6)
        rows_m = rows + mr.parse_zfs_list("rpool/basevol-107-disk-0\t/rpool/basevol-107-disk-0\t30\t90\n")
        self.assertEqual(mr.pick_total("zfs_pull", {"pool": "rpool", "ids": [101, 107]}, rows_m, False), 180)   # modèle compté
        self.assertEqual(mr.pick_total("zfs_pull", {"pool": "rpool", "ids": [101, 104]}, rows, False), 550)   # send -c : compressé
        self.assertEqual(mr.pick_total("rsync_pull_all", {"src_dir": "/rpool/", "pattern": "subvol-*"}, rows, True), 157)
        self.assertEqual(mr.pick_total("rsync_pull_all", {"src_dir": "/rpool", "pattern": "subvol-*"}, rows, False), 317)
        self.assertEqual(mr.pick_total("rsync_pull", {"ct": 101}, rows, False), 310)
        self.assertEqual(mr.pick_total("rsync_pull", {"src": "/rpool/subvol-101-disk-1/"}, rows, True), 50)
        self.assertIsNone(mr.pick_total("rsync_pull", {"ct": 999}, rows, True))
        self.assertIsNone(mr.pick_total("check_ssh", {}, rows, True))
        self.assertEqual(mr.parse_df_used("Filesystem 1-blocks Used Available Capacity Mounted\n/dev/a 100 40 60 40% /\n/dev/b 10 2 8 20% /b\n"), 42)
        calls = []

        def sh(argv, timeout=30):
            calls.append(argv)
            if argv[0] == "stat":
                return 0, "ext2/ext3\n"
            if "zfs list" in argv[-1]:
                return 0, z
            return 0, "Filesystem 1-blocks Used Available Capacity Mounted\n/dev/loop0 100 33 67 33% /\n"
        m = {"kind": "rsync_pull", "params": {"host": "pve-a", "ct": 102}, "measure": {"type": "path", "target": "/nulle/part"}, "started_at": 5}
        self.assertEqual(mr.source_total(m, sh), 33)   # pas de sous-volume ZFS : df dans le CT
        self.assertIn("pct exec 102 -- df -B1 -l -P -x tmpfs -x devtmpfs", calls[-1][-1])
        d = tempfile.mkdtemp()
        base = os.path.join(d, "b6")
        self.assertEqual(mr.cached_total(base, m, 100.0, sh=sh), 33)
        n = len(calls)
        self.assertEqual(mr.cached_total(base, m, 200.0, sh=sh), 33)   # gardé : pas de nouvel appel
        self.assertEqual(len(calls), n)
        self.assertEqual(mr.cached_total(base, dict(m, started_at=6), 300.0, compute=False, sh=sh), None)   # autre lancement

    def test_measure_dossier(self):
        d = tempfile.mkdtemp()
        tgt = os.path.join(d, "dest")
        os.makedirs(tgt)
        used = mr._df_used(tgt)
        self.assertEqual(mr.measure({"type": "path", "target": tgt}, {}), (used, "volume"))
        sz, scope = mr.measure({"type": "path", "target": tgt}, {"base_used": used - 10, "carry": 1000})
        self.assertEqual(scope, "depuis")
        self.assertGreaterEqual(sz, 1010)
        self.assertEqual(mr.measure({"type": "path", "target": "/"}, {})[1], "dest")   # volume dédié (point de montage)
        # migctl : ligne de base au lancement + ce qu'un passage précédent avait copié
        json.dump({"target": tgt, "size": 777}, open(os.path.join(d, "x.done"), "w"))
        bl = migctl.baseline({"type": "path", "target": tgt}, os.path.join(d, "x"), lambda a: (0, "Used\n12345\n", ""))
        self.assertEqual(bl, {"base_used": 12345, "carry": 777})
        bl = migctl.baseline({"type": "path", "target": tgt + "2"}, os.path.join(d, "x"), lambda a: (0, "Used\n5\n", ""))
        self.assertEqual(bl, {"base_used": 5, "carry": 0})   # autre destination : rien repris
        self.assertEqual(migctl.baseline({"type": "zfs", "target": "a/b"}, os.path.join(d, "x"), None), {})


if __name__ == "__main__":
    unittest.main()
