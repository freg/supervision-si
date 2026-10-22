# -*- coding: utf-8 -*-
"""#824 installeur MSI : contrôles statiques (WiX, conditions, secret masqué) et install.ps1 (-Upgrade, -EnablePlugin)."""
import os
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
WIN = os.path.join(HERE, "..", "windows")
NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}


class Msi(unittest.TestCase):
    def setUp(self):
        self.t = ET.parse(os.path.join(WIN, "msi", "si-agent.wxs"))
        self.p = self.t.getroot().find("w:Package", NS)

    def test_proprietes_et_secret(self):
        props = {e.get("Id"): e for e in self.p.findall("w:Property", NS)}
        for k in ("CENTRAL", "TOKEN", "CAFINGERPRINT", "SITE", "PLUGINS", "KEEPDATA"):
            self.assertIn(k, props)
        self.assertEqual(props["TOKEN"].get("Hidden"), "yes")
        ca = {e.get("Id"): e for e in self.p.findall("w:CustomAction", NS)}
        self.assertEqual(ca["SiAgentInstall"].get("HideTarget"), "yes")
        self.assertTrue(all(c.get("Impersonate") == "no" and c.get("Execute") == "deferred" for c in ca.values()))
        self.assertIn("CENTRAL AND TOKEN", self.p.find("w:Launch", NS).get("Condition"))

    def test_sequences(self):
        cust = {e.get("Action"): e.get("Condition") for e in self.p.find("w:InstallExecuteSequence", NS)}
        self.assertIn("NOT UPGRADINGPRODUCTCODE", cust["SiAgentUninstall"])   # la mise à jour majeure ne vide pas ProgramData
        self.assertIn("WIX_UPGRADE_DETECTED", cust["SiAgentUpgrade"])
        sets = [e for e in self.p.findall("w:SetProperty", NS)]
        lignes = " ".join(e.get("Value") for e in sets)
        self.assertIn("-NoDownload", lignes)
        self.assertIn("-Upgrade -NoDownload", lignes)
        self.assertIn("-SystemCa", lignes)
        self.assertIn("-KeepData", lignes)

    def test_install_ps1(self):
        s = open(os.path.join(WIN, "install.ps1"), encoding="utf-8-sig").read()
        self.assertIn("if (-not $Upgrade -and -not $Ca -and -not $CaFingerprint", s)   # -Upgrade sans option de CA (MAJ automatique)
        self.assertIn('-split ","', s)
        self.assertTrue(open(os.path.join(WIN, "msi", "build-msi.ps1"), "rb").read().startswith(b"\xef\xbb\xbf"))   # PS 5.1 : UTF-8 avec BOM


if __name__ == "__main__":
    unittest.main()
