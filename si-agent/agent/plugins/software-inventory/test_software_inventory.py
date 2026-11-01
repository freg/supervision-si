# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import software_inventory as si  # noqa: E402


class Parsers(unittest.TestCase):
    def test_dpkg_rpm(self):
        rows = si.parse_dpkg("vim\t2:9.0\tinstall ok installed\tDebian Vim <vim@x>\nfoo\t1\tdeinstall ok config-files\tx\n")
        self.assertEqual(rows, [{"name": "vim", "version": "2:9.0", "publisher": "Debian Vim", "source": "dpkg"}])
        rows = si.parse_rpm("bash\t5.2-1\tFedora Project\t1700000000\n")
        self.assertEqual((rows[0]["name"], rows[0]["publisher"]), ("bash", "Fedora Project"))
        self.assertIn("installed_at", rows[0])

    def test_flatpak_snap_brew(self):
        self.assertEqual(si.parse_flatpak("GIMP\torg.gimp.GIMP\t2.10\n")[0], {"name": "GIMP", "version": "2.10", "publisher": "gimp", "source": "flatpak", "id": "org.gimp.GIMP"})
        rows = si.parse_snap("Name  Version  Rev  Tracking  Publisher  Notes\ncore22  x  1  -  canonical✓  base\nfirefox  120.0  1  -  mozilla✓  -\n")
        self.assertEqual([r["name"] for r in rows], ["firefox"])
        self.assertEqual(si.parse_brew("wget 1.21.4\n")[0]["version"], "1.21.4")

    def test_windows_and_mac(self):
        rows = si.parse_windows('\ufeff[{"DisplayName":"Microsoft 365 Apps for business - fr-fr","DisplayVersion":"16.0.1","Publisher":"Microsoft Corporation","InstallDate":"20240102","Scope":"machine"},{"DisplayName":"","DisplayVersion":"1"},{"DisplayName":"Microsoft 365 Apps for business - fr-fr","DisplayVersion":"16.0.1"}]')
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["installed_at"], rows[0]["scope"]), ("2024-01-02", "machine"))
        self.assertEqual(si.parse_windows("pas du json"), [])
        self.assertEqual(si.parse_mac_apps([("DraftSight.app", "2024", "dassault")])[0]["name"], "DraftSight")

    def test_normalize(self):
        rows = si.normalize([{"name": "B", "version": "1"}, {"name": "a", "version": "2"}, {"name": "b", "version": "1"}, {"name": ""}])
        self.assertEqual([r["name"] for r in rows], ["a", "B"])


if __name__ == "__main__":
    unittest.main()
