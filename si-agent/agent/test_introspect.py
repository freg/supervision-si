"""Tests #616 : introspection (empreinte de l'agent) et banc de charge."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import introspect  # noqa: E402


class FakeTimes:
    def __init__(self):
        self.cpu = 0.0
    def __call__(self):
        return NS(user=self.cpu * 0.6, system=self.cpu * 0.2, children_user=self.cpu * 0.2, children_system=0.0, elapsed=0)


class IntrospectTests(unittest.TestCase):
    def test_tracker_cpu_et_taches(self):
        clock = [1000.0]; times = FakeTimes()
        tr = introspect.Tracker(clock=lambda: clock[0], cpu_times=times, cores=4)
        tr.record("plugin:wifi-probe", 2.5); tr.record("plugin:wifi-probe", 1.5, ok=False); tr.record("host", 0.4)
        clock[0] += 60; times.cpu += 6.0  # 6 s CPU sur 60 s = 10 % d'un cœur, 2,5 % machine
        p = tr.snapshot(rss_bytes=50_000_000, queue_size=3, host_load1=1.2)
        self.assertEqual(p["cpu_core_percent"], 10.0); self.assertEqual(p["cpu_machine_percent"], 2.5)
        self.assertEqual(p["tasks"]["plugin:wifi-probe"], {"runs": 2, "min": 1.5, "avg": 2.0, "max": 2.5, "total": 4.0, "failed": 1})
        self.assertEqual(tr.durations, {})  # fenêtre remise à zéro
        clock[0] += 60; times.cpu += 0.6
        p2 = tr.snapshot(bench=True)
        self.assertEqual(p2["cpu_core_percent"], 1.0); self.assertTrue(p2["bench"])
        s = introspect.summarize(tr.points)
        self.assertEqual(s["points"], 2); self.assertEqual(s["all"]["cpu_core_max"], 10.0)
        self.assertEqual(s["bench"]["points"], 1); self.assertEqual(s["normal"]["points"], 1)
        self.assertEqual(s["costly"][0]["name"], "plugin:wifi-probe"); self.assertEqual(s["costly"][0]["failed"], 1)
        self.assertEqual(introspect.summarize([]), {"points": 0})

    def test_fenetre_bornee(self):
        clock = [0.0]; times = FakeTimes()
        tr = introspect.Tracker(clock=lambda: clock[0], cpu_times=times, cores=1)
        for _ in range(introspect.WINDOW_MAX + 20):
            clock[0] += 30; tr.snapshot()
        self.assertEqual(len(tr.points), introspect.WINDOW_MAX)

    def test_plan_bench(self):
        until, factor, err = introspect.plan_bench({"minutes": 5, "factor": 4}, 100)
        self.assertEqual((until, factor, err), (400, 4, None))
        until, factor, _ = introspect.plan_bench({"minutes": 999, "factor": 1}, 0)
        self.assertEqual((until, factor), (3600, 2))
        self.assertIsNotNone(introspect.plan_bench({"minutes": "x"}, 0)[2])
        self.assertEqual(introspect.forced_interval(300, 6), 50.0); self.assertEqual(introspect.forced_interval(60, 10), 15)

    def test_read_rss_ne_leve_jamais(self):
        v = introspect.read_rss()
        self.assertTrue(v is None or v > 0)


if __name__ == "__main__":
    unittest.main()
