"""#755 : la version de l'agent est mise à jour dès son événement de démarrage (agent-started / agent-updated),
sans attendre l'inventaire -- sinon la tuile Mises à jour affiche « installeur lancé, sans effet » à tort."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402,F401
import store  # noqa: E402


class AgentVersion(unittest.TestCase):
    def test_started_event_sets_version(self):
        db = appmod.DB_PATH
        store.create_agent(db, "av1", "siege")
        ev = lambda at, kind, det: {"task": "event", "at": at, "data": {"kind": kind, "severity": "info", "message": kind, "details": det}}  # noqa: E731
        store.ingest_measurements(db, "av1", [ev("2026-10-14T12:10:47Z", "agent-started", {"version": "0.5.60"})])
        self.assertEqual(store.get_agent(db, "av1")["agent_version"], "0.5.60")
        store.ingest_measurements(db, "av1", [ev("2026-10-14T12:20:00Z", "agent-updated", {"from": "0.5.60", "to": "0.5.61"})])
        self.assertEqual(store.get_agent(db, "av1")["agent_version"], "0.5.61")
        store.ingest_measurements(db, "av1", [ev("2026-10-14T12:30:00Z", "agent-started", {"version": "; DROP"})])
        self.assertEqual(store.get_agent(db, "av1")["agent_version"], "0.5.61")


if __name__ == "__main__":
    unittest.main()
