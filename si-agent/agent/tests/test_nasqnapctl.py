# -*- coding: utf-8 -*-
"""#940 : gestion à distance QNAP -- composition des commandes (liste blanche, actions déclarées, arguments)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from si_agent import nasqnapctl as nc  # noqa: E402

CIBLE = {"name": "nas-1", "host": "192.0.2.9", "user": "admin", "key": "/k",
         "actions": {"snapshot": {"commande": "qcli_snapshot -c -v {volume}", "lecture": False},
                     "snapshots-liste": {"commande": "qcli_snapshot -l", "lecture": True},
                     "louche": {"commande": "rm -rf /share/{volume}", "lecture": True}}}


class Composer(unittest.TestCase):
    def test_actions_declarees(self):
        self.assertEqual(nc.composer(CIBLE, "essai", action="snapshots-liste"), ("qcli_snapshot -l", True))
        self.assertEqual(nc.composer(CIBLE, "executer", action="snapshot", args={"volume": "DataVol1"}), ("qcli_snapshot -c -v DataVol1", False))
        with self.assertRaises(ValueError):
            nc.composer(CIBLE, "essai", action="snapshot", args={"volume": "DataVol1"})     # modification en essai
        with self.assertRaises(ValueError):
            nc.composer(CIBLE, "executer", action="snapshot")                                 # argument manquant
        with self.assertRaises(ValueError):
            nc.composer(CIBLE, "executer", action="snapshot", args={"volume": "x; reboot"})
        with self.assertRaises(ValueError):
            nc.composer(CIBLE, "executer", action="inconnue")
        with self.assertRaises(ValueError):
            nc.composer(CIBLE, "essai", action="louche", args={"volume": "v"})               # rm déclaré « lecture » : refusé
        self.assertEqual(nc.composer(CIBLE, "executer", action="snapshots-liste")[1], True, "une action de lecture reste une lecture")

    def test_commande_libre(self):
        self.assertEqual(nc.composer(CIBLE, "essai", commande="ls -1 /share/CACHEDEV1_DATA/.snapshot")[0], "ls -1 /share/CACHEDEV1_DATA/.snapshot")
        for mauvaise in ("qcli_snapshot -c", "cat /etc/x; reboot", "setcfg a b", "echo hi", "ls | sh", "cat $(ls)"):
            with self.assertRaises(ValueError, msg=mauvaise):
                nc.composer(CIBLE, "essai", commande=mauvaise)

    def test_argv_et_charger(self):
        a = nc.argv_ssh(CIBLE, "ls")
        self.assertEqual(a[-2:], ["admin@192.0.2.9", "ls"])
        self.assertIn("-i", a)
        l = nc.charger("/x", lire=lambda p: json.dumps([CIBLE, {"pas": "d'hôte"}]))
        self.assertEqual(len(l), 1)
        self.assertEqual(nc.trouver(l, "nas-1")["host"], "192.0.2.9")
        self.assertEqual(nc.trouver(l, "192.0.2.9")["name"], "nas-1")
        self.assertIsNone(nc.trouver(l, "autre"))
        self.assertEqual(nc.charger("/x", lire=lambda p: "pas du json"), [])
        r = nc.interpreter("essai", "snapshots-liste", "qcli_snapshot -l", 0, "a\nb", "")
        self.assertTrue(r["ok"] and r["sortie"] == "a\nb")
