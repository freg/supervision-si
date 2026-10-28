# -*- coding: utf-8 -*-
"""Tests #885 : sonde softether sur un journal de sécurité de même format qu'un serveur réel (valeurs fictives)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import softether as se  # noqa: E402

J1 = '''2026-10-28 09:11:20.266 The connection "CID-100" (IP address: 198.51.100.7, Host name: client.exemple.net, Port number: 1701, Client name: "L2TP VPN Client", Version: 4.38, Build: 9760) is attempting to connect to the Virtual Hub. The auth type provided is "External server authentication" and the user name is "alice".
2026-10-28 09:11:20.266 Connection "CID-100": Successfully authenticated as user "alice".
2026-10-28 09:11:20.266 Connection "CID-100": The new session "SID-ALICE-[L2TP]-5" has been created. (IP address: 198.51.100.7, Port number: 1701, Physical underlying protocol: "Legacy VPN - L2TP")
2026-10-28 09:11:20.297 Session "SID-ALICE-[L2TP]-5": VPN Client details: (Client product name: "L2TP VPN Client", Client host name: "MacBook-Exemple.local", Client IP address: "198.51.100.7", Virtual Hub name: "Bureau")
2026-10-28 09:11:20.804 Session "SID-SECURENAT-1": The DHCP server of host "00-AC-00-00-00-01" (192.168.30.1) on this session allocated, for host "SID-ALICE-[L2TP]-5" on another session "CA-00-00-00-00-01", the new IP address 192.168.30.10.
2026-10-28 09:20:00.000 SecureNAT: The TCP session 205659 has been created. Connection source 192.168.30.10:51823, Connection destination 192.0.2.1:443
2026-10-28 10:18:57.260 Session "SID-ALICE-[L2TP]-5": The session has been terminated. The statistical information is as follows: Total outgoing data size: 170535183 bytes, Total incoming data size: 1193375014 bytes.
'''
J2 = '''2026-10-28 10:19:01.929 The connection "CID-101" (IP address: 198.51.100.7, Host name: client.exemple.net, Port number: 1701, Client name: "L2TP VPN Client", Version: 4.38, Build: 9760) is attempting to connect to the Virtual Hub. The auth type provided is "External server authentication" and the user name is "alice".
2026-10-28 10:19:01.939 Connection "CID-101": The new session "SID-ALICE-[L2TP]-6" has been created. (IP address: 198.51.100.7, Port number: 1701, Physical underlying protocol: "Legacy VPN - L2TP")
'''
ECHECS = "".join('''2026-10-28 10:3%d:00.000 The connection "CID-2%d" (IP address: 203.0.113.66, Host name: , Port number: 443, Client name: "SoftEther VPN Client", Version: 4.38, Build: 9760) is attempting to connect to the Virtual Hub. The auth type provided is "Password authentication" and the user name is "admin".
2026-10-28 10:3%d:00.100 Connection "CID-2%d": User authentication failed. The user name that has been provided was "admin".
''' % (i, i, i, i) for i in range(6))
NOW = datetime(2026, 10, 28, 10, 40, 0)


class Softether(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.base = self.d.name
        os.makedirs(os.path.join(self.base, "security_log", "Bureau"))
        os.makedirs(os.path.join(self.base, "security_log", "Prestataire"))
        self.f = os.path.join(self.base, "security_log", "Bureau", "sec_20261028.log")
        with open(self.f, "w") as fh:
            fh.write(J1)
        with open(os.path.join(self.base, "security_log", "Prestataire", "sec_20200101.log"), "w") as fh:
            fh.write(J1.replace("alice", "trop-vieux"))
        self.st = os.path.join(self.base, "etat.json")

    def tearDown(self):
        self.d.cleanup()

    def run_(self):
        return se.main(["--dir", self.base, "--state", self.st], now=NOW)

    def test_session_close(self):
        out = self.run_()
        self.assertEqual(len(out["sessions"]), 1)          # le fichier de 2020 est hors conservation
        s = out["sessions"][0]
        self.assertEqual((s["hub"], s["utilisateur"], s["origine"], s["nom_origine"], s["protocole"], s["poste"], s["adresse_vpn"]),
                         ("Bureau", "alice", "198.51.100.7", "client.exemple.net", "Legacy VPN - L2TP", "MacBook-Exemple.local", "192.168.30.10"))
        self.assertEqual((s["debut"], s["fin"], s["emis"], s["recu"], s["en_cours"], s["duree_s"]),
                         ("2026-10-28T09:11:20", "2026-10-28T10:18:57", 170535183, 1193375014, False, 4057))

    def test_incremental_et_session_en_cours(self):
        self.run_()
        with open(self.f, "a") as fh:
            fh.write(J2)
        out = self.run_()
        self.assertEqual(len(out["sessions"]), 2)           # la 1re n'est pas relue en double
        recente = out["sessions"][0]
        self.assertTrue(recente["en_cours"])
        self.assertEqual((recente["sid"], recente["duree_s"]), ("SID-ALICE-[L2TP]-6", 1259))
        with open(self.st) as fh:
            self.assertIn("positions", json.load(fh))

    def test_echecs(self):
        with open(self.f, "a") as fh:
            fh.write(ECHECS)
        out = self.run_()
        self.assertEqual(len(out["echecs"]), 6)
        self.assertEqual(out["echecs"][0]["utilisateur"], "admin")
        self.assertIn("vpn-echecs@203.0.113.66", [a["code"] for a in out["alerts"]])

    def test_absent(self):
        out = se.main(["--dir", os.path.join(self.base, "rien"), "--state", self.st], now=NOW)
        self.assertEqual(out["alerts"][0]["code"], "vpn-softether-journaux")


if __name__ == "__main__":
    unittest.main()
