# -*- coding: utf-8 -*-
"""Tests #902 : partages, sessions et verrous Samba (smb.conf, smbstatus json et texte)."""
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import partages_samba as ps  # noqa: E402

CONF = """[global]
   workgroup = BUREAU
   map to guest = Bad User
[Commun]
   path = /srv/commun
   comment = Dossier commun
   guest ok = yes
   read only = no
   browseable = yes
[Compta]
   path = /srv/compta
   valid users = @compta
   writable = yes
[Public]
   path = /srv/public
   public = yes
   read only = yes
[printers]
   path = /var/spool/samba
"""
SMBSTATUS_JSON = json.dumps({
    "sessions": {"1": {"username": "alice", "groupname": "compta", "remote_machine": "192.0.2.30:49512", "connected_at": "2026-10-28T09:00:00",
                       "encryption": {"cipher": "AES-128-GCM"}, "signing": {"cipher": "AES-128-GMAC"}}},
    "tcons": {"7": {"service": "Compta", "machine": "192.0.2.30", "ip_address": "192.0.2.30", "connected_at": "2026-10-28T09:00:05", "encryption": {"cipher": "AES-128-GCM"}}},
})


class Samba(unittest.TestCase):
    def test_partages(self):
        p = {x["nom"]: x for x in ps.partages(ps.analyser_conf(CONF))}
        self.assertNotIn("printers", p)
        self.assertEqual((p["Commun"]["invite"], p["Commun"]["lecture_seule"]), (True, False))
        self.assertEqual((p["Compta"]["invite"], p["Compta"]["lecture_seule"], p["Compta"]["utilisateurs_valides"]), (False, False, "@compta"))
        self.assertEqual((p["Public"]["invite"], p["Public"]["lecture_seule"]), (True, True))

    def test_smbstatus_json(self):
        sess, verr = ps.analyser_smbstatus_json(SMBSTATUS_JSON)
        self.assertEqual((sess[0]["utilisateur"], sess[0]["ip"], sess[0]["chiffrement"]), ("alice", "192.0.2.30", "AES-128-GCM"))
        self.assertEqual((verr[0]["partage"], verr[0]["ip"]), ("Compta", "192.0.2.30"))

    def test_main(self):
        appels = []

        def runner(cmd, **k):
            appels.append(cmd[1] if len(cmd) > 1 else cmd[0])
            if cmd[1:3] == ["conf", "list"]:
                return types.SimpleNamespace(stdout=CONF, stderr="", returncode=0)
            if "--json" in cmd:
                return types.SimpleNamespace(stdout=SMBSTATUS_JSON, stderr="", returncode=0)
            return types.SimpleNamespace(stdout="", stderr="", returncode=1)
        out = ps.main([], runner=runner, which=lambda x: "/usr/bin/" + x)
        codes = {a["code"]: a["severity"] for a in out["alerts"]}
        self.assertEqual(codes["samba-invite-ecriture@Commun"], "warning")
        self.assertEqual(codes["samba-invite@Public"], "info")
        self.assertEqual(out["sessions"][0]["utilisateur"], "alice")
        self.assertEqual(out["verrous"][0]["partage"], "Compta")

    def test_sans_smbstatus(self):
        def runner(cmd, **k):
            return types.SimpleNamespace(stdout=(CONF if cmd[1:3] == ["conf", "list"] else ""), stderr="", returncode=0)
        out = ps.main([], runner=runner, which=lambda x: "/usr/bin/net" if x == "net" else None)
        self.assertEqual(out["alerts"][-1]["code"] if out["alerts"][-1]["code"] == "samba-smbstatus" else "ok", "ok")
        self.assertTrue(any(a["code"] == "samba-smbstatus" for a in out["alerts"]))
        self.assertTrue(out["partages"])


if __name__ == "__main__":
    unittest.main()
