# -*- coding: utf-8 -*-
"""#743 : tournées de mesures réparties -- créneaux (rotate / spread), suppléance, heures calmes, plafond par site,
couverture, validation ; passage complet du tick sur la base (commande run_plugin, acquittement, créneau fait)."""
import os, sys, tempfile, unittest
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
sys.path.insert(0, os.path.dirname(__file__))
import app as appmod, store, rotation  # noqa: E402

PLAN = {"id": 7, "name": "nmap", "plugin_id": "network-neighbors", "mode": "rotate", "period_seconds": 3600,
        "agents": ["a1", "a2", "a3"], "quiet_hours": [], "max_concurrent_per_site": 1}


class Pure(unittest.TestCase):
    def test_slots_rotate_regular(self):
        s = rotation.slots(PLAN, 0, 4 * 3600)
        self.assertEqual(len(s), 4)
        self.assertEqual({b - a for (a, _), (b, _) in zip(s, s[1:])}, {3600})          # régularité
        self.assertEqual(s[0][0] % 3600, rotation.phase(7, 3600))

    def test_slots_spread_offsets(self):
        p = dict(PLAN, mode="spread")
        s = rotation.slots(p, 0, 3600)
        self.assertEqual(sorted(a for _, a in s), ["a1", "a2", "a3"])
        starts = sorted(t for t, _ in s)
        gaps = {b - a for a, b in zip(starts, starts[1:])}
        self.assertTrue(all(1199 <= g <= 1201 for g in gaps))                         # un tiers de période entre agents

    def test_rotation_and_substitution(self):
        ph = rotation.phase(7, 3600)
        agents = [rotation.choose_agent(PLAN, ph + k * 3600, {"a1", "a2", "a3"})[0] for k in range(3)]
        self.assertEqual(sorted(agents), ["a1", "a2", "a3"])                           # chacun son tour
        titular = rotation.choose_agent(PLAN, ph, {"a1", "a2", "a3"})[0]
        others = {"a1", "a2", "a3"} - {titular}
        agent, sub = rotation.choose_agent(PLAN, ph, others)
        self.assertIn(agent, others); self.assertEqual(sub, titular)                   # suppléance
        self.assertEqual(rotation.choose_agent(PLAN, ph, set()), (None, titular))

    def test_due_quiet_and_cap(self):
        ph = rotation.phase(7, 3600)
        p = dict(PLAN, quiet_hours=[[22, 6]])
        night = 2 * 86400 + 23 * 3600 + ph % 3600 - 3600 * ((ph // 3600) % 24)
        d = rotation.due(p, night - 1, night + 7200, {"a1", "a2", "a3"}, {}, {}, 0)
        self.assertTrue(all(x["status"] == "skipped" and x["detail"] == "heure calme" for x in d if rotation.in_quiet(p["quiet_hours"], x["slot"])))
        self.assertTrue(rotation.in_quiet([[22, 6]], 23 * 3600) and rotation.in_quiet([[22, 6]], 3 * 3600) and not rotation.in_quiet([[22, 6]], 12 * 3600))
        busy = {"siege": 1}
        d = rotation.due(PLAN, 0, 3600, {"a1", "a2", "a3"}, busy, {"a1": "siege", "a2": "siege", "a3": "siege"}, 0)
        self.assertEqual([x["status"] for x in d], ["wait"])

    def test_coverage_and_validate(self):
        runs = [{"slot_start": 100, "status": "done", "substitute_for": None}, {"slot_start": 200, "status": "done", "substitute_for": "a1"},
                {"slot_start": 300, "status": "skipped", "substitute_for": None}]
        p = dict(PLAN, period_seconds=100, id=0)
        c = rotation.coverage(runs, p, 0, 400)
        self.assertEqual((c["done"], c["substituted"], c["skipped"]), (2, 1, 1))
        self.assertEqual(rotation.validate({"name": "x", "plugin_id": "p", "period_seconds": 60, "agents": ["a"]})[1], "période minimale : 300 s")
        self.assertIn("spread", rotation.validate({"name": "x", "plugin_id": "p", "period_seconds": 300, "mode": "spread", "agents": list("abcdef")})[1])
        self.assertEqual(rotation.validate({"name": "x", "plugin_id": "p", "period_seconds": 600, "agents": ["z"]}, {"p"}, {"a"})[1], "agents inconnus : z")


class Tick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        for a in ("rot-a", "rot-b"):
            store.create_agent(cls.db, a, "siege", label=a)
        store.upsert_plugin(cls.db, {"id": "rot-probe", "version": "1", "runner": "python", "entry": "x.py", "interval_seconds": 3600,
                                     "timeout_seconds": 60, "args": [], "enabled": False, "description": "test"}, "print('{}')")

    @classmethod
    def tearDownClass(cls):
        conn = store._connect(cls.db)
        try:
            for t in ("rotation_runs", "rotation_plans"):
                conn.execute("DELETE FROM %s" % t)
            conn.execute("DELETE FROM commands WHERE agent_id LIKE 'rot-%'"); conn.execute("DELETE FROM agents WHERE agent_id LIKE 'rot-%'")
            conn.commit()
        finally:
            conn.close()

    def test_routes_and_tick(self):
        r = self.c.post("/rotations", json={"name": "balayage", "plugin_id": "rot-probe", "period_seconds": 600, "agents": ["rot-a", "rot-b"]})
        self.assertEqual(r.status_code, 201, r.get_json()); pid = r.get_json()["id"]
        self.assertEqual(self.c.post("/rotations", json={"name": "x", "plugin_id": "inconnue", "period_seconds": 600, "agents": ["rot-a"]}).status_code, 400)
        ph = rotation.phase(pid, 600)
        slot = 10 * 600 + ph
        store.set_setting(self.db, "rotation_last_tick", slot - 10)
        done = rotation.tick(self.db, now=slot + 5, online={"rot-b"}, site_of={"rot-a": "siege", "rot-b": "siege"}, tz_offset=0)
        self.assertEqual(len(done), 1); d = done[0]
        self.assertEqual((d["agent"], d["status"]), ("rot-b", "queued"))
        cmd = store.get_command(self.db, d["command_id"])
        self.assertEqual((cmd["type"], cmd["params"]["id"]), ("run_plugin", "rot-probe"))
        store.ack_command(self.db, "rot-b", d["command_id"], {"ok": True, "result": {}})
        rotation.tick(self.db, now=slot + 40, online={"rot-b"}, site_of={"rot-a": "siege", "rot-b": "siege"}, tz_offset=0)
        runs = self.c.get("/rotations/%d/runs" % pid).get_json()["runs"]
        self.assertEqual(runs[0]["status"], "done")
        lst = self.c.get("/rotations").get_json()["rotations"]
        self.assertEqual(lst[0]["name"], "balayage"); self.assertTrue(lst[0]["next"])
        self.assertEqual(self.c.delete("/rotations/%d" % pid).status_code, 200)


if __name__ == "__main__":
    unittest.main()
