# -*- coding: utf-8 -*-
"""Tests #894 : conservation, liste d'autorisés, analyse et recherche des messages syslog reçus."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal as j  # noqa: E402

T = time.mktime((2026, 10, 28, 11, 0, 0, 0, 0, -1))


class Journal(unittest.TestCase):
    def test_analyse(self):
        e = j.analyser("<134>Oct 28 11:00:00 MikroTik wireguard,info: wg-bureau: peer abc= handshake")
        self.assertEqual((e["sev"], e["niveau"], e["fac"], e["hote"], e["app"]), (6, "info", 16, "MikroTik", "wireguard,info"))
        self.assertEqual(e["msg"], "wg-bureau: peer abc= handshake")
        e = j.analyser("<11>1 2026-10-28T11:00:00Z routeur sshd 42 - - login failed for admin")
        self.assertEqual((e["sev"], e["hote"], e["app"], e["msg"]), (3, "routeur", "sshd", "login failed for admin"))
        self.assertEqual(j.analyser("texte sans en-tête")["msg"], "texte sans en-tête")
        self.assertEqual(j.decoder("été".encode("cp1252")), "été")

    def test_autorisation(self):
        nets = j.reseaux("192.0.2.182, 10.0.0.0/8")
        self.assertTrue(j.autorise("192.0.2.182", nets))
        self.assertTrue(j.autorise("10.1.2.3", nets))
        self.assertFalse(j.autorise("192.0.2.183", nets))
        self.assertTrue(j.autorise("203.0.113.1", []))

    def test_ecriture_recherche_purge(self):
        with tempfile.TemporaryDirectory() as d:
            jr = j.Journal(d, retention_jours=30)
            jr._purge = T
            jr.ecrire("192.0.2.182", "<134>Oct 28 11:00:00 MikroTik system,info: user admin logged in", t=T)
            jr.ecrire("192.0.2.182", "<131>Oct 28 11:01:00 MikroTik system,error: login failure for user x", t=T + 60)
            jr.ecrire("192.0.2.182", "<134>Sep 01 11:00:00 MikroTik system,info: ancien", t=T - 50 * 86400)
            self.assertIsNone(jr.ecrire("../etc", "x", t=T))                    # adresse non conforme : rien d'écrit
            r = jr.chercher(q="user")
            self.assertEqual([x["msg"] for x in r], ["login failure for user x", "user admin logged in"])
            self.assertEqual(len(jr.chercher(sev_max=3)), 1)
            self.assertEqual(len(jr.chercher(emetteur="192.0.2.182", depuis=T - 86400)), 2)
            em = jr.emetteurs()[0]
            self.assertEqual((em["ip"], em["hote"], em["jours"], em["messages_dernier_jour"]), ("192.0.2.182", "MikroTik", 2, 2))
            self.assertEqual(jr.purger(T), 1)
            self.assertEqual(jr.emetteurs()[0]["jours"], 1)


if __name__ == "__main__":
    unittest.main()
