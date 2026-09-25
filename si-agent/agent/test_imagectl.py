"""Tests #621 : image P2V à chaud (validation, BitLocker, espace, ligne de commande, suivi)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import imagectl  # noqa: E402

BDE_FR = """Chiffrement de lecteur BitLocker : outil de configuration version 10.0
Volume C: [Windows]
[Volume du système d'exploitation]
    Taille :                     475,73 Go
    Statut de la protection :    Protection activée
Volume D: [Data]
    Statut de la protection :    Protection désactivée
"""
BDE_EN = """Volume C: [OS]
    Protection Status:    Protection Off
Volume E: []
    Protection Status:    Protection On (suspended)
"""
FSUTIL_EN = """Total free bytes                : 120 000 000 000 (111,8 GB)
Total bytes                     : 512 000 000 000 (476,8 GB)
Total quota free bytes          : 120 000 000 000 (111,8 GB)
"""
FSUTIL_FR = """Total d'octets libres           : 300 000 000 000 (279,4 Go)
Total d'octets                  : 1 000 000 000 000 (931,3 Go)
Total d'octets libres de quota  : 300 000 000 000
"""


class ImageTests(unittest.TestCase):
    def test_validate(self):
        plan, err = imagectl.validate({"target": "\\\\nas\\images\\p2v\\", "drives": "C: d:", "tool_sha256": "SHA256:" + "a" * 64})
        self.assertIsNone(err); self.assertEqual(plan["drives"], ["C:", "D:"]); self.assertEqual(plan["tool_sha256"], "a" * 64)
        self.assertEqual(plan["target_dir"], "\\\\nas\\images\\p2v"); self.assertEqual(plan["tool_url"], imagectl.DEFAULT_TOOL_URL)
        plan, _ = imagectl.validate({"target": "D:\\images"}); self.assertEqual(plan["drives"], ["*"])
        for bad in ({}, {"target": "C:"}, {"target": "/mnt/x"}, {"target": "D:\\x", "drives": "C"}, {"target": "D:\\x", "tool_url": "ftp://x"}, {"target": "D:\\x", "tool_sha256": "zz"}):
            self.assertIsNotNone(imagectl.validate(bad)[1], bad)
        f = imagectl.target_file(plan, "PC-PILOTE 01", now=0)
        self.assertTrue(f.startswith("D:\\images" + os.sep + "PC-PILOTE-01-")); self.assertTrue(f.endswith(".vhdx"))

    def test_bitlocker(self):
        self.assertEqual(imagectl.parse_bitlocker(BDE_FR), {"C:": "on", "D:": "off"})
        self.assertEqual(imagectl.parse_bitlocker(BDE_EN), {"C:": "off", "E:": "suspended"})
        self.assertEqual(imagectl.bitlocker_blocks({"C:": "on", "D:": "off"}, ["*"]), ["C:"])
        self.assertEqual(imagectl.bitlocker_blocks({"C:": "on", "D:": "off"}, ["D:"]), [])
        self.assertEqual(imagectl.parse_bitlocker(""), {})

    def test_espace(self):
        self.assertEqual(imagectl.parse_used_bytes(FSUTIL_EN), (512_000_000_000, 120_000_000_000))
        self.assertEqual(imagectl.parse_used_bytes(FSUTIL_FR), (1_000_000_000_000, 300_000_000_000))
        self.assertEqual(imagectl.parse_used_bytes("rien"), (None, None))
        self.assertTrue(imagectl.enough_space(100, 111)); self.assertFalse(imagectl.enough_space(100, 109)); self.assertTrue(imagectl.enough_space(None, 5))

    def test_argv_et_suivi(self):
        plan, _ = imagectl.validate({"target": "\\\\nas\\p2v", "drives": "C:"})
        argv = imagectl.build_argv("C:\\ProgramData\\si-agent\\tools\\disk2vhd64.exe", plan, "\\\\nas\\p2v\\x.vhdx")
        self.assertEqual(argv[1:], ["C:", "\\\\nas\\p2v\\x.vhdx", "-c", "-v", "-accepteula"])
        job = {"started": 1000, "target_file": "t", "pid": 5, "last_report": 1000}
        self.assertEqual(imagectl.follow(job, lambda p: True, lambda p: 10, lambda pid: True, 1100)[0], "running")
        st, d = imagectl.follow(job, lambda p: True, lambda p: 10, lambda pid: True, 1400); self.assertEqual(st, "progress"); self.assertEqual(d["bytes"], 10)
        st, d = imagectl.follow(job, lambda p: True, lambda p: 5000, lambda pid: False, 4600); self.assertEqual((st, d["bytes"], d["seconds"]), ("finished", 5000, 3600))
        self.assertEqual(imagectl.follow(job, lambda p: False, lambda p: 0, lambda pid: False, 1200)[0], "failed")


if __name__ == "__main__":
    unittest.main()
