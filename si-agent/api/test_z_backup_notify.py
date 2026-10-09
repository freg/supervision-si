# -*- coding: utf-8 -*-
"""#716 : sauvegardes (sonde pulled-backups) -> événements backup-* -> relais notify-api (groupes de la tuile Notifications)."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ["SI_AGENT_PURGE_THREAD"] = "0"
os.environ.setdefault("SI_AGENT_PUBLIC_URL", "https://vm:6443/api/si-agent")
os.environ.setdefault("SI_AGENT_CA_FILE", os.path.join(tempfile.mkdtemp(), "ca.crt"))
os.environ["SI_AGENT_NOTIFY_SYNC"] = "1"
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "agent"))
import app as _app  # noqa: E402,F401  (alias des modules partagés, comme test_si_agent_api)
import notify  # noqa: E402
import store  # noqa: E402


def mesure(at, backups, alerts=()):
    return {"task": "plugin:pulled-backups", "at": at, "data": {"backups": backups, "alerts": list(alerts), "summary": {}}}


JOB = {"host": "appli", "job": "base+site", "ok": True, "at": 1_800_000_000, "size": 25_000_000, "notify_ok": True}


class BackupEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")
        store.ensure_schema(self.db)
        store.create_agent(self.db, "pbs", "alpha")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def kinds(self, ev):
        return [(e["kind"], e["severity"]) for e in ev]

    def test_cycle(self):
        _, _, _, ev = store.ingest_measurements(self.db, "pbs", [mesure("2026-10-09T15:00:00Z", [JOB])])
        self.assertEqual(ev, [])                                        # première mesure : pas d'avalanche
        _, _, _, ev = store.ingest_measurements(self.db, "pbs", [mesure("2026-10-09T15:15:00Z", [JOB])])
        self.assertEqual(ev, [])                                        # même réussite : rien
        j2 = dict(JOB, at=JOB["at"] + 86400)
        _, _, _, ev = store.ingest_measurements(self.db, "pbs", [mesure("2026-10-10T00:45:00Z", [j2])])
        self.assertEqual(self.kinds(ev), [("backup-done", "info")])
        self.assertIn("25.0 Mo", ev[0]["message"])
        fail = {"code": "pull-failed:appli / base+site", "severity": "warning", "message": "appli / base+site : dernière sauvegarde en échec (ssh)"}
        _, _, _, ev = store.ingest_measurements(self.db, "pbs", [mesure("2026-10-11T00:45:00Z", [dict(j2, ok=False)], [fail])])
        self.assertEqual(self.kinds(ev), [("backup-alert", "warning")])
        _, _, _, ev = store.ingest_measurements(self.db, "pbs", [mesure("2026-10-12T00:45:00Z", [dict(j2, at=j2["at"] + 2 * 86400)])])
        self.assertEqual(sorted(self.kinds(ev)), [("backup-done", "info"), ("backup-recovered", "info")])

    def test_sonde_pbs(self):
        al = {"code": "pbs-old:backup:optick/host/app", "severity": "warning", "message": "PBS : backup:optick/host/app sans sauvegarde depuis 40 h"}
        m = {"task": "plugin:pbs", "at": "2026-10-11T00:00:00Z", "data": {"alerts": [al], "summary": {}}}
        _, _, _, ev = store.ingest_measurements(self.db, "pbs", [m])
        self.assertEqual(self.kinds(ev), [("backup-alert", "warning")])
        self.assertTrue(ev[0]["message"].startswith("PBS : "))

    def test_sans_notify_ok_et_regroupement(self):
        prev = {"backups": [dict(JOB, notify_ok=False), dict(JOB, job="b"), dict(JOB, job="c")]}
        cur = {"backups": [dict(JOB, notify_ok=False, at=2), dict(JOB, job="b", at=2), dict(JOB, job="c", at=2)]}
        ev = store.backup_done_events(prev, cur)
        self.assertEqual(len(ev), 1)                                    # b et c regroupés, la tâche sans notify_ok ignorée
        self.assertEqual([i["job"] for i in ev[0]["details"]["items"]], ["b", "c"])


class Relay(unittest.TestCase):
    class Client:
        def __init__(self):
            self.sent = []

        def notify(self, action, subject, body="", context=None, severity=None, **k):
            self.sent.append((action, subject, severity))

    def test_hub_action(self):
        self.assertEqual(notify.hub_action({"kind": "backup-done", "severity": "info"}), "si-agent.backup-done")
        self.assertEqual(notify.hub_action({"kind": "probe-alert", "severity": "warning"}), "si-agent.probe-alert")
        self.assertIsNone(notify.hub_action({"kind": "agent-online", "severity": "info"}))
        self.assertIsNone(notify.hub_action({"kind": "x y", "severity": "critical"}))     # genre non conforme

    def test_relay(self):
        c = self.Client()
        os.environ.pop("NOTIFY_API_URL", None)
        self.assertIsNone(notify.relay_to_hub({"kind": "backup-alert", "severity": "warning", "message": "m"}, client=c))   # non configuré
        os.environ["NOTIFY_API_URL"] = "http://notify-api:5000"
        try:
            self.assertEqual(notify.relay_to_hub({"kind": "backup-alert", "severity": "warning", "message": "appli : échec"}, client=c), "si-agent.backup-alert")
            self.assertEqual(c.sent, [("si-agent.backup-alert", "[supervision-si] appli : échec", "warning")])
        finally:
            os.environ.pop("NOTIFY_API_URL", None)


if __name__ == "__main__":
    unittest.main()
