# -*- coding: utf-8 -*-
"""#765 : restes du rapatriement sur le nœud local (liste, contrôles de purge)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import leftovers as lo  # noqa: E402

D = "/var/lib/vz/dump"
FILES = {D: [(D + "/vzdump-lxc-102-2026_10_13-17_00_55.tar.gz", 374 << 30, 1791997860), (D + "/vzdump-lxc-108-2026_10_13-09_08_54.tar.gz", 124 << 30, 1791970860),
             (D + "/vzdump-qemu-205-2026_10_14-01_00_00.vma.zst.part", 3 << 30, 1792000000), (D + "/export-109.log", 1100, 1792000000),
             (D + "/petit.raw", 1 << 20, 1792000000)]}
LOS = json.dumps({"loopdevices": [{"name": "/dev/loop0", "back-file": "/rpool/data/PVE-1/102/disk.raw"}]})
MOUNTS = "rpool/ROOT/pve-1 / zfs rw 0 0\n/dev/loop0 /rpool/data/PVE-1/102/mount ext4 ro 0 0\n"


class Leftovers(unittest.TestCase):
    def scan(self, confs=None, busy=()):
        return lo.scan([D, "/data/dump"], lambda d: FILES.get(d, []), LOS, MOUNTS, lambda p: (394 << 30, 1791990000), confs, busy)

    def test_scan(self):
        it = self.scan()
        self.assertEqual([(x["kind"], x["vmid"]) for x in it], [("image", 102), ("archive", 102), ("archive", 108), ("part", 205)])
        self.assertEqual(it[0]["loop"], {"dev": "/dev/loop0", "mount": "/rpool/data/PVE-1/102/mount"})
        self.assertEqual(lo.purge_steps(it[0]), [["umount", "/rpool/data/PVE-1/102/mount"], ["losetup", "-d", "/dev/loop0"]])
        self.assertEqual(lo.purge_steps(it[1]), [])

    def test_purge_checks(self):
        it = self.scan(confs={"205.conf": "scsi0: local:vzdump-qemu-205-2026_10_14-01_00_00.vma.zst.part"})
        p = D + "/vzdump-lxc-108-2026_10_13-09_08_54.tar.gz"
        self.assertIn("ne fait pas partie", lo.check_purge({"path": "/etc/passwd", "confirm": "passwd", "reason": "x" * 10}, it)[1])
        self.assertIn("confirm", lo.check_purge({"path": p, "confirm": "autre", "reason": "x" * 10}, it)[1])
        self.assertIn("motif", lo.check_purge({"path": p, "confirm": os.path.basename(p), "reason": "court"}, it)[1])
        self.assertEqual(lo.check_purge({"path": p, "confirm": os.path.basename(p), "reason": "copie validée"}, it)[0]["vmid"], 108)
        q = D + "/vzdump-qemu-205-2026_10_14-01_00_00.vma.zst.part"
        self.assertIn("référencé", lo.check_purge({"path": q, "confirm": os.path.basename(q), "reason": "x" * 10}, it)[1])
        self.assertEqual(self.scan(busy={q})[3]["in_use"], "export en cours")


if __name__ == "__main__":
    unittest.main()
