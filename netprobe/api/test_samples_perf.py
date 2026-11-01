"""#740 : dernier échantillon par cible par index, purge par plage, analyseurs non relancés à chaque tick,
plan de requête sans parcours de table. Lancer depuis netprobe/api : python3 -m unittest test_samples_perf"""
import os
import sqlite3
import tempfile
import time
import unittest

import scheduler
import store


class SamplesPerf(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "np.db")
        store.ensure_schema(self.db)
        self.t1, _ = store.add_target(self.db, "192.0.2.1")
        self.t2, _ = store.add_target(self.db, "192.0.2.2")
        for i in range(30):
            store.record_sample(self.db, self.t1, True, latency_ms=float(i))
            store.record_sample(self.db, self.t2, i % 2 == 0, latency_ms=float(100 + i))

    def test_latest_per_target(self):
        rows = store.latest_sample_per_target(self.db)
        self.assertEqual([(r["target_id"], r["latency_ms"]) for r in rows], [(self.t1, 29.0), (self.t2, 129.0)])

    def test_query_plan_uses_index(self):
        conn = sqlite3.connect(self.db)
        plan = " ".join(str(r) for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT s2.id FROM smokeping_samples s2 WHERE s2.target_id = 1 ORDER BY s2.id DESC LIMIT 1"))
        self.assertIn("idx_smokeping_target_id", plan)
        self.assertNotIn("TEMP B-TREE", plan)

    def test_prune_keeps_most_recent(self):
        n = store.prune_old_samples(self.db, keep_count_per_target=10)
        self.assertEqual(n, 40)
        left = store.list_samples(self.db, self.t1, limit=100)
        self.assertEqual([s["latency_ms"] for s in left], [float(i) for i in range(29, 19, -1)])
        self.assertEqual(store.prune_old_samples(self.db, keep_count_per_target=10), 0)

    def test_analyzers_not_rerun_every_tick(self):
        store.set_probe_config(self.db, "analyzer", True, frequency_seconds=600)
        scheduler._last_analyzer_run.clear()
        t0 = time.time()
        self.assertTrue(scheduler.run_analyzer_tick(self.db, now_ts=t0, now_hour=12)["ran"])
        self.assertFalse(scheduler.run_analyzer_tick(self.db, now_ts=t0 + 15, now_hour=12)["ran"])   # pas relancé au tick suivant
        self.assertTrue(scheduler.run_analyzer_tick(self.db, now_ts=t0 + 700, now_hour=12)["ran"])


if __name__ == "__main__":
    unittest.main()
