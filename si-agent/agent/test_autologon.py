"""Tests #628 : réouverture de session une fois (validation, valeurs Winlogon, nettoyage, masquage)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import autologon  # noqa: E402


class AutologonTests(unittest.TestCase):
    def test_validate(self):
        plan, err = autologon.validate({"user": "pilote", "password": "s3cret"})
        self.assertIsNone(err); self.assertEqual((plan["domain"], plan["count"]), (".", 1))
        plan, _ = autologon.validate({"user": "pilote", "password": "x", "domain": "EXEMPLE", "count": 99})
        self.assertEqual((plan["domain"], plan["count"]), ("EXEMPLE", autologon.MAX_COUNT))
        for bad in ({}, {"user": "pilote"}, {"user": "a\"b", "password": "x"}, {"user": "pilote", "password": ""}, {"user": "pilote", "password": "x", "domain": "a;b"}, {"user": "pilote", "password": "x", "count": "z"}):
            self.assertIsNotNone(autologon.validate(bad)[1], bad)

    def test_apply_sans_mot_de_passe_dans_le_resume(self):
        plan, _ = autologon.validate({"user": "pilote", "password": "s3cret"})
        written = {}
        res = autologon.apply(plan, lambda n, k, v: written.__setitem__(n, (k, v)))
        self.assertEqual(written["AutoAdminLogon"], ("sz", "1")); self.assertEqual(written["AutoLogonCount"], ("dword", 1))
        self.assertEqual(written["DefaultPassword"], ("sz", "s3cret")); self.assertEqual(written["DefaultUserName"], ("sz", "pilote"))
        self.assertNotIn("password", res); self.assertNotIn("s3cret", str(res))

    def test_cleanup(self):
        reg = {"AutoAdminLogon": "1", "DefaultPassword": "s3cret", "AutoLogonCount": 0, "DefaultUserName": "pilote"}
        r = autologon.cleanup(reg.get, lambda n: reg.pop(n, None), lambda n, k, v: reg.__setitem__(n, v))
        self.assertTrue(r["cleaned"]); self.assertNotIn("DefaultPassword", reg); self.assertEqual(reg["AutoAdminLogon"], "0"); self.assertNotIn("AutoLogonCount", reg)
        self.assertEqual(reg["DefaultUserName"], "pilote")  # le nom reste, comme Winlogon le laisse
        reg = {"AutoAdminLogon": "1", "DefaultPassword": "s3cret", "AutoLogonCount": 2}
        self.assertEqual(autologon.cleanup(reg.get, lambda n: reg.pop(n, None), lambda n, k, v: None), {"cleaned": False, "remaining": 2})
        reg = {"AutoAdminLogon": "0"}  # Winlogon a déjà tout nettoyé
        self.assertEqual(autologon.cleanup(reg.get, lambda n: reg.pop(n, None), lambda n, k, v: None), {"cleaned": False, "remaining": 0})

    def test_redact(self):
        p = {"action": "reboot", "autologon": {"user": "pilote", "password": "s3cret"}}
        r = autologon.redact(p)
        self.assertEqual(r["autologon"]["password"], "***"); self.assertEqual(p["autologon"]["password"], "s3cret")
        self.assertEqual(autologon.redact({"action": "reboot"}), {"action": "reboot"})


if __name__ == "__main__":
    unittest.main()
