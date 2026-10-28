# -*- coding: utf-8 -*-
"""Tests #899 : fenêtre d'installation sans authentification (ouverture, échéance, fermeture au premier contact)."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accueil as ac  # noqa: E402

T = 1_800_000_000.0
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class Accueil(unittest.TestCase):
    def test_fenetre(self):
        e = ac.ouvrir({}, "pc-paul", 24, now=T)
        self.assertEqual(ac.statut(e, "pc-paul", {"last_seen_at": None}, now=T + 60), (True, None))
        self.assertFalse(ac.statut(e, "pc-autre", {"last_seen_at": None}, now=T)[0])               # non ouvert
        self.assertFalse(ac.statut(e, "pc-paul", None, now=T)[0])                                  # agent inconnu
        self.assertEqual(ac.statut(e, "pc-paul", {"last_seen_at": None}, now=T + 25 * 3600)[1], "fenêtre échue")
        self.assertTrue(ac.statut(e, "pc-paul", {"last_seen_at": iso(T - 3600)}, now=T + 60)[0])   # vu AVANT l'ouverture : réinstallation permise
        self.assertEqual(ac.statut(e, "pc-paul", {"last_seen_at": iso(T + 120)}, now=T + 180)[1], "agent déjà installé (contact reçu)")
        self.assertEqual(ac.ouvrir(e, "pc-paul", 0), {})
        self.assertEqual(ac.ouvrir({}, "x", 1000, now=T)["x"]["jusqua"], T + 72 * 3600)           # plafonné

    def test_nom_et_limiteur(self):
        self.assertTrue(ac.NOM.match("pc-paul.bureau_1"))
        self.assertFalse(ac.NOM.match("../etc") or ac.NOM.match("a b") or ac.NOM.match(""))
        l = ac.Limiteur(n=3, fenetre_s=60)
        self.assertEqual([l.accepte("192.0.2.1", now=T + i) for i in range(4)], [True, True, True, False])
        self.assertTrue(l.accepte("192.0.2.2", now=T))
        self.assertTrue(l.accepte("192.0.2.1", now=T + 61))


if __name__ == "__main__":
    unittest.main()
