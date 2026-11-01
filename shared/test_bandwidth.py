"""Tests #641 : bande passante (débits, fenêtre unitaire estimée, tranches)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bandwidth as bw  # noqa: E402


class RateTests(unittest.TestCase):
    def test_rates_et_reset(self):
        # 1 Mo en 10 s = 800 000 bits/s ; puis reset (compteur qui redescend) ignoré
        s = [(0, 0), (10, 1_000_000), (20, 2_000_000), (30, 100)]
        r = bw.rates(s)
        self.assertEqual(len(r), 2)  # 3e intervalle (reset) ignoré
        self.assertAlmostEqual(r[0][2], 800_000.0)
        self.assertEqual(bw.rates([(5, 500), (5, 900)]), [])  # dt=0 ignoré


class WindowTests(unittest.TestCase):
    def test_estimation_fenetre(self):
        # activité par rafales : 3 intervalles actifs (30 s), repos, 1 actif (10 s), repos, 2 actifs (20 s)
        hi, lo = 5_000_000.0, 100.0
        series = [(0, 10, hi), (10, 20, hi), (20, 30, hi), (30, 40, lo),
                  (40, 50, hi), (50, 60, lo),
                  (60, 70, hi), (70, 80, hi)]
        w = bw.estimate_unit_window(series)
        self.assertEqual(w["runs"], 3)
        self.assertEqual(w["min_run_seconds"], 10.0)   # la rafale la plus courte
        self.assertEqual(w["max_run_seconds"], 30.0)
        self.assertEqual(w["suggested_slot_seconds"], 10)  # arrondi lisible
        self.assertGreater(w["idle_bps"], bw.IDLE_FLOOR_BPS - 1)
        self.assertEqual(bw.estimate_unit_window([])["unit_seconds"], None)

    def test_per_slot(self):
        series = [(0, 10, 800_000.0), (10, 20, 1_600_000.0), (3600, 3610, 400_000.0)]
        slots = bw.per_slot(series, 3600, origin=0)
        self.assertEqual(len(slots), 2)
        # tranche 1 : moyenne pondérée (800k*10 + 1600k*10)/20 = 1 200 000 bps, pic 1 600 000
        self.assertAlmostEqual(slots[0]["avg_bps"], 1_200_000.0); self.assertEqual(slots[0]["peak_bps"], 1_600_000.0)
        self.assertEqual(slots[0]["active_fraction"], 1.0)

    def test_analyze(self):
        # compteur cumulé toutes les 10 s pendant 2 min, débit ~800 kbps
        samples = [(t, 1_000_000 * (t // 10)) for t in range(0, 130, 10)]
        a = bw.analyze(samples)
        self.assertEqual(a["intervals"], 12)
        self.assertTrue(a["window"]["unit_seconds"] >= 10)
        self.assertEqual(len(a["hourly"]), 1)  # tout dans la même heure
        self.assertGreater(a["summary"]["total_bytes"], 0)
        self.assertEqual(a["summary"]["suggested_slot_seconds"], a["window"]["suggested_slot_seconds"])


if __name__ == "__main__":
    unittest.main()
