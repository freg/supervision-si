# -*- coding: utf-8 -*-
"""Tests #869 : purge des mesures par petits lots (rétention globale, rétention par tâche, dernière mesure gardée)."""
import os
import sqlite3
import tempfile
import time
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import si_agent_plugins  # noqa: F401  (image Docker)
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    import si_agent.plugins as _plugins
    from si_agent import control as _control
    sys.modules.setdefault("si_agent_plugins", _plugins)
    sys.modules.setdefault("si_agent_control", _control)
import store  # noqa: E402

DAY = 86400


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class PurgeLots(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "t.db")
        store.ensure_schema(self.db)
        self.now = 1_800_000_000
        c = sqlite3.connect(self.db)
        rows = [("vieux", "host", iso(self.now - 400 * DAY), "{}", iso(self.now - 400 * DAY))]  # n'a plus jamais parlé
        for d in range(120, -1, -1):          # 121 jours, 3 tâches, 2 agents, ordre d'arrivée = ordre des ids
            t = self.now - d * DAY
            for a in ("a1", "a2"):
                for task in ("host", "plugin:guest-usage", "plugin:systemes"):
                    rows.append((a, task, iso(t), "{}", iso(t)))
        c.executemany("INSERT INTO measurements (agent_id, task, at, data, received_at) VALUES (?, ?, ?, ?, ?)", rows)
        c.commit(); c.close()

    def count(self, where="1=1", args=()):
        c = sqlite3.connect(self.db)
        try:
            return c.execute("SELECT COUNT(*) FROM measurements WHERE " + where, args).fetchone()[0]
        finally:
            c.close()

    def test_retention_et_derniere_gardee(self):
        n = store.purge_measurements(self.db, 90, batch=7, pause=0, now=self.now)
        self.assertGreater(n, 0)
        cutoff = iso(self.now - 90 * DAY)
        self.assertEqual(self.count("received_at < ? AND agent_id != 'vieux'", (cutoff,)), 0)
        self.assertEqual(self.count("agent_id = 'vieux'"), 1)          # dernière mesure de l'agent muet conservée
        self.assertEqual(self.count("agent_id = 'a1' AND task = 'host'"), 91)

    def test_retention_par_tache(self):
        store.purge_measurements(self.db, 90, batch=50, pause=0, now=self.now, task_retention={"plugin:guest-usage": 3})
        self.assertEqual(self.count("agent_id = 'a1' AND task = 'plugin:guest-usage'"), 4)
        self.assertEqual(self.count("agent_id = 'a1' AND task = 'plugin:systemes'"), 91)

    def test_id_before_dichotomie(self):
        c = sqlite3.connect(self.db)
        try:
            i = store._id_before(c, iso(self.now - 90 * DAY))
            self.assertEqual(c.execute("SELECT MAX(id) FROM measurements WHERE received_at < ?", (iso(self.now - 90 * DAY),)).fetchone()[0], i)
            self.assertIsNone(store._id_before(c, "1970-01-01T00:00:00Z"))
        finally:
            c.close()

    def test_repetee_sans_effet(self):
        store.purge_measurements(self.db, 90, batch=13, pause=0, now=self.now)
        self.assertEqual(store.purge_measurements(self.db, 90, batch=13, pause=0, now=self.now), 0)

    def test_index_par_sonde_utilise(self):
        self.assertTrue(store.ensure_task_index(self.db))
        self.assertFalse(store.ensure_task_index(self.db))
        c = sqlite3.connect(self.db)
        try:
            plan = " ".join(str(r) for r in c.execute("EXPLAIN QUERY PLAN SELECT agent_id, MAX(at) FROM measurements WHERE task = ? GROUP BY agent_id", ("host",)))
        finally:
            c.close()
        self.assertIn(store.TASK_INDEX, plan)


class ReceptionGuestUsage(unittest.TestCase):
    """#869 : la fusion guest-usage se fait après la validation de la réception, résultat identique à #771."""

    def test_fusion_apres_validation(self):
        import guestusage as gu
        db = os.path.join(tempfile.mkdtemp(), "g.db")
        store.ensure_schema(db)
        store.create_agent(db, "gu-b", "siege", label="gu-b")

        def gd(web, rrd):
            return {"nodes": [{"name": "pve-h", "ok": True, "guests": [{"vmid": 201, "name": "site", "status": "running",
                    "days": {"web": web, "login": [], "mysql": [], "rrd": rrd, "rrd_weeks": [], "deep": False}}]}]}
        jours = [{"day": "2025-%02d-%02d" % (1 + i // 28, 1 + i % 28), "req": i} for i in range(300)]   # > un lot de 200
        m1 = {"task": "plugin:guest-usage", "at": "2026-10-15T10:00:00Z", "data": gd([{"day": "2026-10-15", "req": 3, "visitors": 1}] + jours, [{"day": "2026-10-15", "cpu": 9.0}])}
        m2 = {"task": "plugin:guest-usage", "at": "2026-10-15T18:00:00Z", "data": gd([{"day": "2026-10-15", "req": 2, "visitors": 1, "bytes": 50}], [{"day": "2026-10-15", "cpu": 2.0}])}
        bad = {"task": "plugin:guest-usage", "at": "2026-10-15T19:00:00Z", "data": {"nodes": "pas une liste"}}
        acc = store.ingest_measurements(db, "gu-b", [m1, m2, bad])
        self.assertEqual(acc[0], 3)
        conn = store._connect(db)
        try:
            h = gu.history(conn, "pve-h", 201, "2020-01-01")
            nb = conn.execute("SELECT COUNT(*) FROM guest_daily").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual([x for x in h["web"] if x["day"] == "2026-10-15"], [{"day": "2026-10-15", "req": 3, "visitors": 1, "bytes": 50}])
        self.assertEqual(h["rrd"], [{"day": "2026-10-15", "cpu": 2.0}])
        self.assertEqual(len(h["web"]), 301)
        self.assertEqual(nb, 302)


if __name__ == "__main__":
    unittest.main()
