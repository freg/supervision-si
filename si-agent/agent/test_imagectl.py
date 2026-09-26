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
FSUTIL_FR_REEL = """Nombre total d'octets libres                : 116 819 386 368 (108,8 Go)
Nombre total d'octets                     : 195 149 426 688 (181,7 Go)
Nombre total d'octets libres dans le quota          : 116 819 386 368 (108,8 Go)
Octets de pool non disponibles          :               0 (  0,0 Ko)
Octets de pool non disponibles dans le quota    :               0 (  0,0 Ko)
Octets utilisés                      :  72 338 055 168 ( 67,4 Go)
Nombre total d'octets réservés            :   5 991 985 152 (  5,6 Go)
Volume de stockage des octets réservés   :   5 946 667 008 (  5,5 Go)
Octets validés disponibles       :               0 (  0,0 Ko)
Octets disponibles dans le pool            :               0 (  0,0 Ko)
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

    def test_partage(self):
        # #635 : partage monté par l'agent ; la cible doit être sous le partage ; mot de passe masqué
        plan, err = imagectl.validate({"target": "\\\\srv\\p2v\\pc1", "share": {"unc": "\\\\srv\\p2v\\", "user": "img", "password": "s", "domain": "EX"}, "transfer": True})
        self.assertIsNone(err); self.assertEqual(plan["share"], {"unc": "\\\\srv\\p2v", "user": "EX\\img", "password": "s"}); self.assertFalse(plan["transfer"])
        self.assertIsNotNone(imagectl.validate({"target": "D:\\x", "share": {"unc": "\\\\srv\\p2v", "user": "u", "password": "p"}})[1])
        self.assertIsNotNone(imagectl.validate({"target": "\\\\srv\\p2v", "share": {"unc": "\\\\srv", "user": "u", "password": "p"}})[1])
        self.assertIsNotNone(imagectl.validate({"target": "\\\\srv\\p2v", "share": {"unc": "\\\\srv\\p2v", "user": "u"}})[1])
        self.assertEqual(imagectl.redact({"share": {"unc": "x", "user": "u", "password": "p"}})["share"]["password"], "***")
        self.assertIsNone(imagectl.validate({"target": "D:\\x"})[0]["share"])

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
        # #629 : sortie réelle Windows 11 fr -- « réservés » ne doit pas écraser le total, « Octets utilisés » prime
        self.assertEqual(imagectl.parse_used_bytes(FSUTIL_FR_REEL), (195_149_426_688, 116_819_386_368))
        self.assertEqual(imagectl.used_bytes(FSUTIL_FR_REEL), 72_338_055_168)
        self.assertEqual(imagectl.used_bytes(FSUTIL_EN), 392_000_000_000); self.assertIsNone(imagectl.used_bytes("rien"))
        self.assertTrue(imagectl.enough_space(100, 111)); self.assertFalse(imagectl.enough_space(100, 109)); self.assertTrue(imagectl.enough_space(None, 5))

    def test_argv_et_suivi(self):
        plan, _ = imagectl.validate({"target": "\\\\nas\\p2v", "drives": "C:"})
        argv = imagectl.build_argv("C:\\ProgramData\\si-agent\\tools\\disk2vhd64.exe", plan, "\\\\nas\\p2v\\x.vhdx")
        self.assertEqual(argv[1:], ["-accepteula", "-h", "-c", "C:", "\\\\nas\\p2v\\x.vhdx"])
        plan2, _ = imagectl.validate({"target": "\\\\nas\\p2v", "tool_args": "-accepteula -c"})
        self.assertEqual(imagectl.build_argv("d.exe", plan2, "o")[1:], ["-accepteula", "-c", "*", "o"])
        self.assertIsNotNone(imagectl.validate({"target": "\\\\nas\\p2v", "tool_args": ["-c", "rm -rf"]})[1])
        # #630 : vivant sans fichier après 3 min -> bloqué
        job2 = {"started": 1000, "target_file": "t", "pid": 5, "last_report": 1000}
        self.assertEqual(imagectl.follow(job2, lambda p: False, lambda p: 0, lambda pid: True, 1100)[0], "running")
        self.assertEqual(imagectl.follow(job2, lambda p: False, lambda p: 0, lambda pid: True, 1200)[0], "stalled")
        self.assertEqual(imagectl.follow(job2, lambda p: True, lambda p: 10, lambda pid: True, 1200)[0], "running")
        job = {"started": 1000, "target_file": "t", "pid": 5, "last_report": 1000}
        self.assertEqual(imagectl.follow(job, lambda p: True, lambda p: 10, lambda pid: True, 1100)[0], "running")
        st, d = imagectl.follow(job, lambda p: True, lambda p: 10, lambda pid: True, 1400); self.assertEqual(st, "progress"); self.assertEqual(d["bytes"], 10)
        st, d = imagectl.follow(job, lambda p: True, lambda p: 5000, lambda pid: False, 4600); self.assertEqual((st, d["bytes"], d["seconds"]), ("finished", 5000, 3600))
        self.assertEqual(imagectl.follow(job, lambda p: False, lambda p: 0, lambda pid: False, 1200)[0], "failed")


if __name__ == "__main__":
    unittest.main()
