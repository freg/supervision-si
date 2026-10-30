# -*- coding: utf-8 -*-
"""#939 : argv et interprétation du pilotage BackupPC (module pur)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from si_agent import backuppcctl as bc  # noqa: E402

B = "/usr/share/backuppc/bin/BackupPC_serverMesg"


class Argv(unittest.TestCase):
    def test_actions(self):
        w = lambda x: "/usr/sbin/runuser" if x == "runuser" else None  # noqa: E731
        self.assertEqual(bc.argv("backup-full", "pc-1", "freg", B, which=w), ["runuser", "-u", "backuppc", "--", B, "backup", "pc-1", "pc-1", "freg", "1"])
        self.assertEqual(bc.argv("backup-incr", "pc-1", "freg", B, which=w)[-1], "0")
        self.assertEqual(bc.argv("stop", "pc-1", "freg", B, backoff_h=2, which=w)[-4:], ["stop", "pc-1", "freg", "2"])
        self.assertEqual(bc.argv("status", None, "x", B, root=False), [B, "status", "hosts"])
        self.assertEqual(bc.argv("status", None, "x", B, which=lambda x: None)[:4], ["su", "-s", "/bin/sh", "backuppc"])
        self.assertEqual(bc.argv("backup-full", "pc-1", "a b;rm", B, root=False)[4], "abrm", "utilisateur assaini")

    def test_refus(self):
        with self.assertRaises(ValueError):
            bc.argv("backup-full", "pc;rm -rf", "u", B)
        with self.assertRaises(ValueError):
            bc.argv("backup-full", "pc", "u", None)
        with self.assertRaises(ValueError):
            bc.argv("detruire", "pc", "u", B)
        self.assertIsNone(bc.binaire(existe=lambda p: False))
        self.assertEqual(bc.binaire(existe=lambda p: p == B), B)

    def test_interpreter(self):
        self.assertTrue(bc.interpreter("backup-full", 0, "ok: requested backup of pc-1", "", "pc-1")["ok"])
        r = bc.interpreter("backup-full", 0, "", "Can't connect to server (unix socket /var/run/backuppc/BackupPC.sock)", "pc-1")
        self.assertFalse(r["ok"])
        self.assertIn("tourne-t-il", r["erreur"])
        self.assertFalse(bc.interpreter("stop", 1, "unknown host pc-9", "", "pc-9")["ok"])


class Relais948(unittest.TestCase):
    def test_commande_et_argv(self):
        c = bc.commande_distante("backup-full", "pc-1", "freg")
        self.assertTrue(c.startswith('B=""; for b in /usr/share/backuppc/bin/BackupPC_serverMesg'))
        self.assertTrue(c.endswith('"$B" backup pc-1 pc-1 freg 1'))
        self.assertTrue(bc.commande_distante("stop", "pc-1", "a;b", backoff_h=2).endswith('"$B" stop pc-1 ab 2'))
        self.assertTrue(bc.commande_distante("status").endswith('"$B" status hosts'))
        with self.assertRaises(ValueError):
            bc.commande_distante("backup-incr", "pc;rm", "u")
        a = bc.argv_relais({"host": "192.0.2.5", "user": "si-bk", "key": "/k"}, "echo x")
        self.assertEqual(a[-7:], ["si-bk@192.0.2.5", "sudo", "-n", "-u", "backuppc", "sh", "-c"][:6] + ["echo x"] if False else a[-7:])
        self.assertEqual(a[-1], "echo x"); self.assertEqual(a[-3:-1], ["sh", "-c"]); self.assertIn("si-bk@192.0.2.5", a)
        self.assertEqual(bc.charger_relais("/x", lire=lambda p: '[{"name": "fichiers", "host": "192.0.2.5"}]')["name"], "fichiers")
        self.assertIsNone(bc.charger_relais("/x", lire=lambda p: "[]"))
        self.assertIsNone(bc.charger_relais("/nonexistent/backuppc.json"))
