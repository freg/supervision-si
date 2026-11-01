# -*- coding: utf-8 -*-
"""#653 : opérations d'exploitation / PRA de vmctl -- argv construits et validés, délai long, refus explicites."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import vmctl

class Ops(unittest.TestCase):
    def test_migrate(self):
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "migrate", "target": "pve10"}), (["qm", "migrate", "101", "pve10", "--online"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "migrate", "target": "pve10", "online": False, "with_local_disks": True}), (["qm", "migrate", "101", "pve10", "--with-local-disks"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 203, "action": "migrate", "kind": "lxc", "target": "pve11"}), (["pct", "migrate", "203", "pve11", "--restart"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "migrate", "target": "pve10; rm -rf /"})[1], "target (nœud cible) requis")

    def test_backup_move_clone(self):
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "backup", "storage": "pbs-ovh"}), (["vzdump", "101", "--storage", "pbs-ovh", "--mode", "snapshot", "--compress", "zstd"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "backup", "storage": "x", "mode": "live"})[1], "mode : snapshot, suspend ou stop")
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "move_disk", "disk": "scsi0", "storage": "zfs-fast"}), (["qm", "disk", "move", "101", "scsi0", "zfs-fast", "--delete", "1"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 203, "action": "move_disk", "kind": "lxc", "disk": "rootfs", "storage": "zfs-fast"}), (["pct", "move-volume", "203", "rootfs", "zfs-fast", "--delete", "1"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "move_disk", "disk": "sda", "storage": "x"})[1], "disk (scsi0, virtio0, rootfs, mp0…) requis")
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "clone", "newid": 9101, "name": "super-pra", "target": "pve10"}), (["qm", "clone", "101", "9101", "--name", "super-pra", "--full", "--target", "pve10"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "clone", "newid": 101})[1], "newid invalide")

    def test_replication(self):
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "replicate", "target": "pve10", "schedule": "*/15"}), (["pvesr", "create-local-job", "101-0", "pve10", "--schedule", "*/15"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "unreplicate", "job": 2}), (["pvesr", "delete", "101-2", "--force", "1"], None))
        self.assertEqual(vmctl.build_argv({"vmid": 101, "action": "replicate", "target": "pve10", "schedule": "`id`"})[1][:17], "schedule invalide")

    def test_run_long_timeout(self):
        seen = {}
        class R: returncode = 0; stdout = "ok"; stderr = ""
        def cmd(argv, timeout): seen["t"] = timeout; return R()
        r = vmctl.run(cmd, {"vmid": 101, "action": "migrate", "target": "pve10"}); self.assertTrue(r["ok"]); self.assertEqual(seen["t"], vmctl.LONG_TIMEOUT)
        vmctl.run(cmd, {"vmid": 101, "action": "start"}); self.assertEqual(seen["t"], 180)

if __name__ == "__main__": unittest.main()
