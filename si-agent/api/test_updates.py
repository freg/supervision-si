# -*- coding: utf-8 -*-
import time
import unittest

import updates

PKG = {"name": "si-agent-agent-0.5.3.tar.gz", "version": "0.5.3", "sha256": "ab" * 32, "size": 100}
NOW = time.time()


def iso(seconds_ago):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - seconds_ago))


class Updates(unittest.TestCase):
    def test_settings_et_versions(self):
        s = updates.normalize_settings({"beta_agents": ["b", "a", "a", ""], "general_enabled": 1, "retry_after_s": "x"})
        self.assertEqual(s["beta_agents"], ["a", "b"])
        self.assertTrue(s["general_enabled"] and s["auto"])
        self.assertEqual(s["retry_after_s"], 21600)
        self.assertEqual(updates.version_tuple("0.5.10"), (0, 5, 10))
        self.assertGreater(updates.version_tuple("0.5.10"), updates.version_tuple("0.5.3"))
        self.assertEqual(updates.version_tuple("v0.5"), (0, 5))

    def test_statuts(self):
        s = updates.normalize_settings({"beta_agents": ["beta1"]})
        st = lambda a, c=None: updates.agent_status(a, "0.5.3", s, c, NOW)  # noqa: E731
        self.assertEqual(st({"agent_id": "x", "agent_version": "0.5.3"}), "up-to-date")
        self.assertEqual(st({"agent_id": "x", "agent_version": "0.6.0"}), "newer")
        self.assertEqual(st({"agent_id": "x", "agent_version": None}), "unknown")
        self.assertEqual(st({"agent_id": "x", "agent_version": "0.5.2"}), "not-eligible")
        self.assertEqual(st({"agent_id": "beta1", "agent_version": "0.5.2"}), "eligible")
        pend = {"status": "pending", "params": {"version": "0.5.3"}, "created_at": iso(60)}
        self.assertEqual(st({"agent_id": "beta1", "agent_version": "0.5.2"}, pend), "pending")
        started = {"status": "acked", "params": {"version": "0.5.3"}, "acked_at": iso(120), "result": {"ok": True, "result": {"started": True}}}
        self.assertEqual(st({"agent_id": "beta1", "agent_version": "0.5.2"}, started), "started")
        failed = {"status": "acked", "params": {"version": "0.5.3"}, "acked_at": iso(120), "result": {"ok": False, "error": "sha"}}
        self.assertEqual(st({"agent_id": "beta1", "agent_version": "0.5.2"}, failed), "failed")
        old_fail = dict(failed, acked_at=iso(7 * 3600))
        self.assertEqual(st({"agent_id": "beta1", "agent_version": "0.5.2"}, old_fail), "eligible", "réessai après le délai")
        other = {"status": "acked", "params": {"version": "0.5.1"}, "acked_at": iso(60), "result": {"ok": True, "result": {"started": True}}}
        self.assertEqual(st({"agent_id": "beta1", "agent_version": "0.5.2"}, other), "eligible", "commande d'une autre version ignorée")
        self.assertEqual(updates.agent_status({"agent_id": "x", "agent_version": "0.5.2"}, None, s, None, NOW), "no-package")

    def test_plan_et_planification(self):
        s = updates.normalize_settings({"beta_agents": ["beta1"], "general_enabled": False})
        agents = [{"agent_id": "beta1", "agent_version": "0.5.2", "hostname": "h1"}, {"agent_id": "srv", "agent_version": "0.5.2"}, {"agent_id": "ok", "agent_version": "0.5.3"}]
        planned = updates.plan(agents, PKG, s, {}, NOW)
        self.assertEqual([p["status"] for p in planned], ["eligible", "not-eligible", "up-to-date"])
        self.assertEqual([p["channel"] for p in planned], ["beta", "off", "off"])
        self.assertEqual(updates.to_schedule(planned), ["beta1"])
        s2 = updates.normalize_settings({"beta_agents": ["beta1"], "general_enabled": True})
        self.assertEqual(updates.to_schedule(updates.plan(agents, PKG, s2, {}, NOW)), ["beta1", "srv"])
        p = updates.command_params(PKG, "c1")
        self.assertEqual((p["version"], p["url"], p["command_id"]), ("0.5.3", "/package", "c1"))
        self.assertEqual(updates.summary(planned, PKG, s)["counts"], {"eligible": 1, "not-eligible": 1, "up-to-date": 1})


if __name__ == "__main__":
    unittest.main()
