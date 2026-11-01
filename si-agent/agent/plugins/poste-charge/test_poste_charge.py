# -*- coding: utf-8 -*-
"""Tests #896 : épreuves de charge en format réduit (quelques secondes, quelques Mo)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poste_charge as pc  # noqa: E402


class Charge(unittest.TestCase):
    def test_cpu(self):
        r = pc.epreuve_cpu(1, coeurs=2)
        self.assertEqual((r["coeurs"], r["erreurs_calcul"]), (2, 0))
        self.assertGreater(r["iterations"], 0)

    def test_cpu_detail_926(self):
        r = pc.epreuve_cpu(1, coeurs=2)
        self.assertEqual(r["coeurs_finis"], 2)
        self.assertLess(r["gel_max_s"], 5)
        self.assertIsNotNone(r["demarrage_max_s"])

    def test_cpu_cale_detail_926(self):
        r = pc.epreuve_cpu(30, coeurs=2, max_s=2)          # calcul plus long que le plafond -> calé, poste non figé
        self.assertEqual((r["statut"], r["coeurs_finis"]), ("calé", 0))
        sev, msg = pc.diagnostic_calage_cpu(r, 2)
        self.assertEqual(sev, "warning")
        self.assertIn("pas un signe matériel", msg)
        self.assertIn("19 cœur(s) sur 20", pc.diagnostic_calage_cpu({"coeurs": 20, "coeurs_finis": 1, "gel_max_s": 0}, 300)[1])
        self.assertEqual(pc.diagnostic_calage_cpu({"coeurs": 20, "coeurs_finis": 19, "gel_max_s": 42}, 300)[0], "critical")
        self.assertEqual(pc.diagnostic_calage_cpu({"coeurs": 20}, 300)[0], "critical", "ancien format : prudence")

    def test_memoire(self):
        r = pc.epreuve_memoire(50, 8, libre=16 * 2 ** 20)
        self.assertEqual((r["mo"], r["blocs_errones"]), (8, 0))

    def test_disque(self):
        with tempfile.TemporaryDirectory() as d:
            r = pc.epreuve_disque(4, d)
            self.assertTrue(r["identique"])
            self.assertEqual(os.listdir(d), [])                       # fichier effacé
            r = pc.epreuve_disque(4, os.path.join(d, "absent"))
            self.assertIsNotNone(r["erreur"])

    def test_main(self):
        with tempfile.TemporaryDirectory() as d:
            out = pc.main(["--cpu-s", "5", "--mem-pct", "5", "--mem-max-mo", "8", "--disque-mo", "16", "--dossier", d])
        self.assertEqual(out["verdict"], "aucun défaut reproduit")
        self.assertEqual(out["alerts"], [])


class ChargePilotage(unittest.TestCase):   # #913 : sélection d'épreuves, interruption, suivi direct
    def test_selection_epreuves(self):
        with tempfile.TemporaryDirectory() as d:
            out = pc.main(["--epreuves", "disque", "--disque-mo", "16", "--dossier", d])
        self.assertEqual(out["epreuves"], ["disque"])
        self.assertIsNone(out["processeur"])
        self.assertIsNone(out["memoire"])
        self.assertIsNotNone(out["disque"])
        self.assertEqual(out["verdict"], "aucun défaut reproduit")

    def test_stop_interrompt(self):
        with tempfile.TemporaryDirectory() as d:
            stop = os.path.join(d, "stop"); open(stop, "w").close()
            r = pc.epreuve_disque(4000, d, stop=stop)
            self.assertEqual(r["statut"], "interrompu")
            self.assertIsNone(r["identique"])
            out = pc.main(["--epreuves", "disque", "--disque-mo", "4000", "--stop", stop, "--dossier", d])
            self.assertEqual(out["verdict"], "interrompu")
            self.assertEqual(os.listdir(d), ["stop"])              # fichier de test effacé, sentinelle conservée

    def test_live_ndjson(self):
        with tempfile.TemporaryDirectory() as d:
            live = os.path.join(d, "live.json")
            pc.main(["--epreuves", "disque", "--disque-mo", "16", "--live", live, "--dossier", d])
            phases = {json.loads(l)["phase"] for l in open(live, encoding="utf-8") if l.strip()}
        self.assertTrue({"début", "disque", "fini"} <= phases)


if __name__ == "__main__":
    unittest.main()
