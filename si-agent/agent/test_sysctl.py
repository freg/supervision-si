"""Tests #633 : différé `at`, Windows Update, protection (validation, lignes de commande, résumés)."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import sysctl  # noqa: E402


class AtTests(unittest.TestCase):
    def test_parse_at(self):
        now = 1_800_000_000
        self.assertEqual(sysctl.parse_at(None, now), (None, None)); self.assertEqual(sysctl.parse_at("", now), (None, None))
        self.assertEqual(sysctl.parse_at(now + 3600, now), (now + 3600.0, None))
        mk = lambda t: 1_800_010_000  # mktime simulé -> futur
        self.assertEqual(sysctl.parse_at("2026-09-28T02:00", now, mktime=mk), (1_800_010_000, None))
        self.assertEqual(sysctl.parse_at("2026-09-28 02:00:30", now, mktime=mk)[1], None)
        self.assertIsNotNone(sysctl.parse_at("demain", now)[1]); self.assertIsNotNone(sysctl.parse_at(now - 3600, now)[1])
        self.assertIsNotNone(sysctl.parse_at(now + 400 * 86400, now)[1])


class UpdateTests(unittest.TestCase):
    def test_validate_et_argv(self):
        plan, err = sysctl.validate_update({"action": "install", "kbs": "KB5049624, 5050000", "reboot": True})
        self.assertIsNone(err); self.assertEqual(plan["kbs"], ["KB5049624", "KB5050000"]); self.assertTrue(plan["reboot"])
        self.assertEqual(sysctl.validate_update({})[0]["action"], "status")
        self.assertIsNotNone(sysctl.validate_update({"action": "remove"})[1]); self.assertIsNotNone(sysctl.validate_update({"kbs": ["x"]})[1])
        argv = sysctl.update_argv("powershell.exe", "C:\\s\\winupdate.ps1", plan, "C:\\out.json")
        self.assertEqual(argv[-6:], ["-Action", "install", "-Kb", "KB5049624,KB5050000", "-Out", "C:\\out.json"])
        self.assertNotIn("-Kb", sysctl.update_argv("p", "s", sysctl.validate_update({})[0]))

    def test_resume(self):
        self.assertEqual(sysctl.summarize_update({"pending": [1, 2], "reboot_required": True}), "2 mise(s) à jour en attente, redémarrage requis")
        self.assertIn("réussi", sysctl.summarize_update({"pending": [], "install": {"count": 3, "result": 2, "reboot_required": True}}))
        self.assertIn("rien à installer", sysctl.summarize_update({"pending": [], "install": {"count": 0}}))
        self.assertIn("erreur", sysctl.summarize_update({"error": "COM"})); self.assertEqual(sysctl.summarize_update(None), "sans résultat")


class ProtectionTests(unittest.TestCase):
    def test_validate_et_argv(self):
        plan, err = sysctl.validate_protection({"firewall": "off", "profiles": "public,private"})
        self.assertIsNone(err); self.assertEqual(plan["profiles"], ["Public", "Private"]); self.assertFalse(plan["status_only"])
        self.assertTrue(sysctl.validate_protection({})[0]["status_only"])
        self.assertIsNotNone(sysctl.validate_protection({"firewall": "maybe"})[1]); self.assertIsNotNone(sysctl.validate_protection({"profiles": "Work"})[1])
        argv = sysctl.protection_argv("p", "s", plan)
        self.assertEqual(argv[-4:], ["-Firewall", "off", "-Profiles", "Public,Private"])
        argv = sysctl.protection_argv("p", "s", sysctl.validate_protection({"defender": "on"})[0])
        self.assertEqual(argv[-2:], ["-Defender", "on"]); self.assertNotIn("-Firewall", argv)

    def test_resume(self):
        s = sysctl.summarize_protection({"firewall": [{"profile": "Public", "enabled": False}], "defender": {"realtime": True, "tamper_protected": True}, "third_party": [{"name": "AVG Antivirus"}], "errors": ["Defender : refusé"]})
        self.assertIn("Public INACTIF", s); self.assertIn("falsification", s); self.assertIn("AVG", s); self.assertIn("refusé", s)


if __name__ == "__main__":
    unittest.main()
