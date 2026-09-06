import os
import sqlite3
import tempfile
import unittest

from netprobe_agent import protocol
from netprobe_agent.localqueue import LocalQueue


class Protocol(unittest.TestCase):
    def test_canonical_json_is_deterministic(self):
        a = protocol.canonical_json({"b": 1, "a": [1, 2], "é": "ü"})
        b = protocol.canonical_json({"a": [1, 2], "é": "ü", "b": 1})
        self.assertEqual(a, b)
        self.assertEqual(a, '{"a":[1,2],"b":1,"é":"ü"}'.encode("utf-8"))

    def test_sign_verify_roundtrip(self):
        body = protocol.canonical_json({"measurements": []})
        h = protocol.auth_headers("sonde-01", "s3cret", "POST", "/api/v1/agents/sonde-01/measurements", body, timestamp=1700000000)
        self.assertEqual(h[protocol.HEADER_ID], "sonde-01")
        self.assertEqual(h[protocol.HEADER_TS], "1700000000")
        ok, why = protocol.verify("s3cret", "POST", "/api/v1/agents/sonde-01/measurements", h, body)
        self.assertTrue(ok, why)

    def test_verify_rejects_tampering(self):
        body = protocol.canonical_json({"x": 1})
        h = protocol.auth_headers("s", "k", "POST", "/p", body)
        self.assertFalse(protocol.verify("k", "POST", "/p", h, b'{"x":2}')[0], "corps modifié")
        self.assertFalse(protocol.verify("k", "POST", "/autre", h, body)[0], "chemin modifié")
        self.assertFalse(protocol.verify("k", "GET", "/p", h, body)[0], "méthode modifiée")
        self.assertFalse(protocol.verify("autre", "POST", "/p", h, body)[0], "mauvais secret")
        bad = dict(h); bad[protocol.HEADER_TS] = "1"
        self.assertFalse(protocol.verify("k", "POST", "/p", bad, body)[0], "timestamp modifié")
        self.assertEqual(protocol.verify("", "POST", "/p", h, body), (False, "appareil inconnu"))
        self.assertEqual(protocol.verify("k", "POST", "/p", {}, body)[1], "en-têtes de signature absents")

    def test_headers_case_insensitive_lookup(self):
        body = b""
        h = protocol.auth_headers("s", "k", "GET", "/p", body)
        lower = {k.lower(): v for k, v in h.items()}
        self.assertTrue(protocol.verify("k", "GET", "/p", lower, body)[0])

    def test_sign_refuses_empty_secret(self):
        with self.assertRaises(ValueError):
            protocol.sign("", "GET", "/", 0, b"")

    def test_validate_measurement(self):
        self.assertTrue(protocol.validate_measurement({"task": "ping:x", "at": "2026-09-06T00:00:00Z"})[0])
        self.assertFalse(protocol.validate_measurement({"task": "", "at": "x"})[0])
        self.assertFalse(protocol.validate_measurement({"task": "t", "at": "x", "ok": "oui"})[0])
        self.assertFalse(protocol.validate_measurement({"task": "t", "at": "x", "data": []})[0])
        self.assertFalse(protocol.validate_measurement("pas un objet")[0])
        self.assertEqual(protocol.measurement_key("a", "t", "at"), "a|t|at")


class Queue(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "queue.db")
        self.q = LocalQueue(self.path)

    def tearDown(self):
        self.q.close()

    def m(self, task="ping:h", at="2026-09-06T10:00:00Z", **kw):
        d = {"agent_id": "s1", "task": task, "at": at, "ok": True, "data": {"v": 1}, "error": None}
        d.update(kw)
        return d

    def test_put_dedupe_pending_mark_sent(self):
        self.assertTrue(self.q.put(self.m()))
        self.assertFalse(self.q.put(self.m()), "même agent/tâche/instant : doublon ignoré")
        self.assertTrue(self.q.put(self.m(at="2026-09-06T10:01:00Z")))
        self.assertEqual(self.q.pending_count(), 2)
        batch = self.q.pending(limit=1)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]["data"], {"v": 1})
        self.q.mark_sent([batch[0]["_id"]])
        self.assertEqual(self.q.pending_count(), 1)
        self.assertEqual(self.q.stats()["total"], 2)

    def test_put_many_and_latest(self):
        n = self.q.put_many([self.m(at="t%d" % i) for i in range(5)] + [self.m(at="t0")])
        self.assertEqual(n, 5)
        latest = self.q.latest(limit=2)
        self.assertEqual([x["at"] for x in latest], ["t4", "t3"])
        self.assertFalse(latest[0]["sent"])
        self.assertEqual(len(self.q.latest(task="autre")), 0)

    def test_purge_keeps_pending_and_recent(self):
        for i in range(10):
            self.q.put(self.m(at="t%02d" % i))
        ids = [x["_id"] for x in self.q.pending(limit=8)]
        self.q.mark_sent(ids)
        # Tout est "récent" (sent_at = maintenant) : rien à purger avec 7 jours.
        self.assertEqual(self.q.purge_sent(older_than_seconds=7 * 86400, keep_min=2), 0)
        # older_than=0 mais keep_min=5 : garde les 5 plus récentes (dont les 2
        # non envoyées), ne touche JAMAIS aux non envoyées.
        removed = self.q.purge_sent(older_than_seconds=0, keep_min=5)
        self.assertEqual(removed, 5)
        self.assertEqual(self.q.pending_count(), 2)
        self.assertEqual(self.q.stats()["total"], 5)

    def test_corrupt_db_is_set_aside(self):
        self.q.close()
        with open(self.path, "wb") as fh:
            fh.write(b"ceci n'est pas une base sqlite" * 100)
        q2 = LocalQueue(self.path)
        self.assertEqual(q2.pending_count(), 0)
        self.assertTrue(any(f.startswith("queue.db.corrupt.") for f in os.listdir(os.path.dirname(self.path))))
        q2.close()

    def test_wal_mode(self):
        self.assertEqual(self.q.conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")


if __name__ == "__main__":
    unittest.main()
