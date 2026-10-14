# -*- coding: utf-8 -*-
"""#756 : synthèses Parc IA (rapports d'évaluation, activité du journal par jour)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stats  # noqa: E402


class StatsTest(unittest.TestCase):
    def test_eval_summary(self):
        rep = {"at": "2026-10-14T12:00:00Z", "model": "qwen3:14b", "score": 0.8, "tok_s_avg": 16.2, "cases": 2,
               "by_kind": {"ask": {"n": 1, "score": 0.9, "errors": 0, "scored": 1}},
               "results": [{"checks": [{"ok": True}, {"ok": False}]}, {"error": "délai", "checks": [{"ok": True}]}]}
        s = stats.eval_summary(rep, "eval-x.json")
        self.assertEqual((s["criteria_ok"], s["criteria"], s["errors"]), (2, 3, 1)); self.assertEqual(s["by_kind"]["ask"], {"n": 1, "score": 0.9, "errors": 0})
        self.assertIsNone(stats.eval_summary({"results": [{}]})["criteria"])

    def test_journal_stats(self):
        L = [json.dumps(x) for x in [{"at": "2026-10-13T10:00:00Z", "kind": "ask", "ms": 1000, "tok_s": 10},
                                     {"at": "2026-10-14T10:00:00Z", "kind": "ask", "ms": 3000, "tok_s": 20},
                                     {"at": "2026-10-14T11:00:00Z", "kind": "eval", "error": "x"},
                                     {"at": "2026-09-01T00:00:00Z", "kind": "ask"}]] + ["pas du json"]
        d = stats.journal_stats(L, "2026-10-01")
        self.assertEqual([x["day"] for x in d], ["2026-10-13", "2026-10-14"])
        self.assertEqual((d[1]["n"], d[1]["errors"], d[1]["ms_avg"], d[1]["tok_s_avg"], d[1]["by_kind"]), (2, 1, 3000, 20.0, {"ask": 1, "eval": 1}))


if __name__ == "__main__":
    unittest.main()
