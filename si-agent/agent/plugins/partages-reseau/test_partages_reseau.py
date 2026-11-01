# -*- coding: utf-8 -*-
"""Tests #902 : inventaire des partages réseau (cibles, analyse smbclient, alertes) sans réseau réel."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import partages_reseau as pr  # noqa: E402

SMBCLIENT_G = """Disk|Commun|Dossier commun
Disk|Compta$|
IPC|IPC$|IPC Service
Printer|HP|Copieur du 2e
"""


class Partages(unittest.TestCase):
    def test_hotes(self):
        h = pr.hotes(["192.0.2.0/30", "192.0.2.50", "mauvais"], exclure=["192.0.2.1"])
        self.assertEqual(h, ["192.0.2.2", "192.0.2.50"])   # .1 exclu, .0/.3 hors hosts()
        self.assertEqual(len(pr.hotes(["10.0.0.0/8"], maxi=5)), 5)

    def test_parse_g(self):
        parts = []
        for l in SMBCLIENT_G.splitlines():
            f = l.split("|")
            if len(f) >= 2 and f[0] in ("Disk", "IPC", "Printer"):
                parts.append(f[1])
        self.assertEqual(parts, ["Commun", "Compta$", "IPC$", "HP"])

    def test_enumerer_et_invite(self):
        def runner(cmd, **k):
            return types.SimpleNamespace(stdout=SMBCLIENT_G, stderr="", returncode=0)
        parts, invite, err = pr.enumerer("192.0.2.5", 4, runner, "/usr/bin/smbclient")
        noms = {p["nom"]: p for p in parts}
        self.assertTrue(invite)
        self.assertFalse(noms["Commun"]["administratif"])
        self.assertTrue(noms["Compta$"]["administratif"])
        self.assertTrue(noms["IPC$"]["administratif"])
        self.assertEqual(noms["HP"]["type"], "imprimante")

    def test_enumerer_refuse(self):
        def runner(cmd, **k):
            return types.SimpleNamespace(stdout="", stderr="session setup failed: NT_STATUS_ACCESS_DENIED", returncode=1)
        parts, invite, err = pr.enumerer("192.0.2.6", 4, runner, "/usr/bin/smbclient")
        self.assertEqual((parts, invite, err), ([], False, "NT_STATUS_ACCESS_DENIED"))

    def test_main_alertes(self):
        def runner(cmd, **k):
            return types.SimpleNamespace(stdout=SMBCLIENT_G, stderr="", returncode=0)
        pr.presence_smb = lambda ip, t: {"smb": True, "dialecte": "SMB 3.1.1", "signature_exigee": False}
        out = pr.main(["--targets", "192.0.2.5"], runner=runner, which=lambda x: "/usr/bin/smbclient")
        codes = {a["code"]: a["severity"] for a in out["alerts"]}
        self.assertEqual(codes["partages-invite@192.0.2.5"], "warning")
        self.assertEqual(codes["partages-signature@192.0.2.5"], "info")
        self.assertEqual(out["serveurs"][0]["partages"][0]["nom"], "Commun")
        out = pr.main(["--targets", "192.0.2.5"], runner=runner, which=lambda x: None)
        self.assertEqual(out["alerts"][0]["code"], "partages-smbclient")
        self.assertEqual(out["serveurs"][0]["partages"], [])


if __name__ == "__main__":
    unittest.main()
