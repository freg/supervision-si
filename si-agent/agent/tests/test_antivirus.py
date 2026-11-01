# -*- coding: utf-8 -*-
"""Tests antivirus (#520) : décodage du Centre de sécurité Windows, produits
macOS, statut et risques."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from si_agent import antivirus  # noqa: E402


class Windows(unittest.TestCase):
    def test_decode_product_state(self):
        self.assertEqual(antivirus.decode_security_center_state(397568), (True, True))    # 0x061100 : actif, à jour
        self.assertEqual(antivirus.decode_security_center_state(393472), (False, True))   # 0x060100 : inactif
        self.assertEqual(antivirus.decode_security_center_state(397584), (True, False))   # 0x061110 : actif, périmé
        self.assertEqual(antivirus.decode_security_center_state("abc"), (None, None))

    def test_map_windows_tiers_et_defender(self):
        av = antivirus.map_windows([{"displayName": "Bitdefender Endpoint Security Tools", "productState": 397568},
                                    {"displayName": "Windows Defender", "productState": 393472}],
                                   defender={"enabled": False, "realtime": False, "signatures_age_days": 3})
        self.assertEqual([p["name"] for p in av["products"]], ["Bitdefender Endpoint Security Tools", "Windows Defender"], "Defender du Centre de sécurité, pas doublé")
        self.assertEqual(av["primary"], "Bitdefender Endpoint Security Tools")
        self.assertEqual(av["status"], "ok")
        self.assertEqual(antivirus.evaluate(av), [])

    def test_map_windows_defender_seul_et_aucun(self):
        av = antivirus.map_windows([], defender={"enabled": True, "realtime": True, "signatures_age_days": 12})
        self.assertEqual(av["products"][0]["source"], "defender")
        self.assertEqual(av["status"], "outdated")
        self.assertEqual(antivirus.evaluate(av), [], "Defender seul : risques détaillés déjà produits par risks.evaluate (#440)")
        none = antivirus.map_windows([], defender=None)
        self.assertEqual(none["status"], "none")
        self.assertEqual([r["id"] for r in antivirus.evaluate(none)], ["antivirus-none"])
        off = antivirus.map_windows([{"displayName": "ESET Security", "productState": 393472}])
        self.assertEqual(off["status"], "disabled")
        self.assertEqual(antivirus.evaluate(off)[0]["severity"], "critical")
        unk = antivirus.map_windows([{"displayName": "Mystère AV", "productState": 0x062200}])
        self.assertEqual(unk["status"], "unknown")
        self.assertEqual([r["id"] for r in antivirus.evaluate(unk)], ["antivirus-state-unknown"])


class MacOS(unittest.TestCase):
    def test_produits_et_protections(self):
        exists = lambda p: p in ("/Library/Bitdefender/AVP", "/Applications/Malwarebytes.app")  # noqa: E731
        ps = "launchd\n/Library/Bitdefender/AVP/BDLDaemon.app/Contents/MacOS/BDLDaemon\nbdmd\nFinder\n"
        av = antivirus.map_macos(exists, ps, xprotect_version="5286", xprotect_age_days=12,
                                 spctl="assessments enabled", csrutil="System Integrity Protection status: enabled.")
        names = {p["name"]: p for p in av["products"]}
        self.assertTrue(names["Bitdefender"]["enabled"] and names["Bitdefender"]["installed"])
        self.assertFalse(names["Malwarebytes"]["enabled"], "installé mais démon absent")
        self.assertEqual(av["primary"], "Bitdefender")
        self.assertEqual(av["status"], "ok")
        self.assertEqual(av["platform"]["gatekeeper"], True)
        self.assertEqual(av["platform"]["sip"], True)
        self.assertEqual(antivirus.evaluate(av), [])

    def test_sans_produit_gatekeeper_off(self):
        av = antivirus.map_macos(lambda p: False, "launchd\nFinder\n", xprotect_version="5200", xprotect_age_days=90,
                                 spctl="assessments disabled", csrutil="System Integrity Protection status: disabled.")
        self.assertEqual(av["status"], "none")
        ids = [r["id"] for r in antivirus.evaluate(av)]
        self.assertEqual(ids, ["antivirus-none", "gatekeeper-off", "sip-off", "xprotect-old"])
        self.assertEqual(antivirus.summary_line(av), "aucun antivirus détecté")

    def test_summary_line(self):
        av = antivirus.map_windows([{"displayName": "ESET", "productState": 397584}])
        self.assertEqual(antivirus.summary_line(av), "ESET (actif, définitions périmées)")
        self.assertIsNone(antivirus.summary_line(None))


if __name__ == "__main__":
    unittest.main()
