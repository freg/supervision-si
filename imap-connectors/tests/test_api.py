# -*- coding: utf-8 -*-
"""Tests de chaîne imap-connectors (#489) : API Flask + poller contre
un FAUX IMAP et de FAUX HTTP — vraie base SQLite temporaire, aucun
réseau, aucune boîte réelle."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP = tempfile.mkdtemp(prefix="imap-connectors-test-")
os.environ["IMAP_CONNECTORS_DB_PATH"] = os.path.join(TMP, "test.db")

import app as app_mod  # noqa: E402
import store  # noqa: E402

store.ensure_schema(app_mod.DB_PATH)

ZENOSS_BODY = """Alert generated at 2026/08/11 10:30:12.000 Equipement : sw-coeur
Message : Ping degrade Localisation : /Parc Composants : 
Severite : Warning"""

FAKE_MESSAGES = [
    {"uid": "101", "message_id": "<a@b>", "from_addr": "zenoss@exemple.fr",
     "subject": "[Site A] sw-coeur Ping degrade", "date": "Tue, 11 Aug 2026 12:31:00 +0200",
     "body": ZENOSS_BODY, "_num": b"1"},
    {"uid": "102", "message_id": "<c@d>", "from_addr": "user@exemple.fr",
     "subject": "format bizarre", "date": "Tue, 11 Aug 2026 12:40:00 +0200",
     "body": "rien de reconnaissable", "_num": b"2"},
]


class FakeResp:
    status_code = 201
    text = '{"id": 42}'

    def json(self):
        return {"id": 42}


class ChainTests(unittest.TestCase):
    def setUp(self):
        for t in ("connectors", "messages", "deliveries"):
            conn = store.connect(app_mod.DB_PATH)
            conn.execute("DELETE FROM %s" % t)
            conn.commit()
            conn.close()
        self.c = app_mod.app.test_client()

    def _create(self, **kw):
        body = dict(name="zenoss-in", host="imap.lan", username="zenoss@lan", password="x",
                    target="zenoss", enabled=True, interval_seconds=60)
        body.update(kw)
        r = self.c.post("/connectors", json=body)
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def test_crud_et_secret_jamais_expose(self):
        c = self._create()
        self.assertNotIn("password", c, "le mot de passe ne sort jamais par l'API")
        listed = self.c.get("/connectors").get_json()["connectors"]
        self.assertEqual(len(listed), 1)
        self.assertNotIn("password", listed[0])
        r = self.c.put("/connectors/%d" % c["id"], json={"notes": "boîte principale"})
        self.assertEqual(r.get_json()["notes"], "boîte principale")
        r = self.c.post("/connectors", json={"name": "zenoss-in", "host": "h", "username": "u", "password": "p", "target": "sms"})
        self.assertEqual(r.status_code, 409, "nom unique")
        r = self.c.post("/connectors", json={"name": "incomplet"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.c.delete("/connectors/%d" % c["id"]).status_code, 200)
        self.assertEqual(self.c.get("/connectors").get_json()["connectors"], [])

    def test_chaine_releve_complet(self):
        c = self._create()
        pixel_db = os.path.join(TMP, "timeseries.db")
        seen = {"marked": []}

        def fake_fetch(cfg, limit=50):
            return list(FAKE_MESSAGES), None

        def fake_mark(cfg, nums):
            seen["marked"] += nums
            return None

        app_mod.imap_fetch.fetch_unseen = fake_fetch
        app_mod.imap_fetch.mark_seen = fake_mark
        try:
            handled, error = app_mod.poll_connector(
                store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
                fetch=fake_fetch, deliver_kw={"db_path": pixel_db, "backend": "sqlite"})
        finally:
            app_mod.imap_fetch.fetch_unseen = app_mod.imap_fetch.__dict__.get("_orig", app_mod.imap_fetch.fetch_unseen)
        self.assertIsNone(error)
        self.assertEqual(handled, 2)

        msgs = self.c.get("/messages").get_json()["messages"]
        self.assertEqual(len(msgs), 2)
        parsed = [m for m in msgs if m["parsed"]]
        self.assertEqual(len(parsed), 1, "le message au format bizarre reste non interprété")
        ok_msg = parsed[0]
        self.assertEqual(ok_msg["kind"], "zenoss-active")
        self.assertEqual(ok_msg["deliveries"][0]["ok"], 1)
        self.assertIn("pixel-grid", ok_msg["deliveries"][0]["detail"])
        # l'événement est bien dans la base pixel-grid
        import sqlite3
        conn = sqlite3.connect(pixel_db)
        rows = conn.execute("SELECT nom, valeur, type FROM events").fetchall()
        meta = conn.execute("SELECT kind FROM type_meta WHERE type = 'alerte_zenoss_email'").fetchone()
        conn.close()
        self.assertEqual(rows, [("sw-coeur", 1.0, "alerte_zenoss_email")])
        self.assertEqual(meta[0], "integer_enum")
        # marquage lu : SEUL le message interprété+routé est marqué —
        # le non interprété reste non lu (file de secours).
        self.assertEqual(seen["marked"], [b"1"])
        # second relevé : déduplication, rien de nouveau
        handled2, _ = app_mod.poll_connector(
            store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
            fetch=fake_fetch, deliver_kw={"db_path": pixel_db, "backend": "sqlite"})
        self.assertEqual(handled2, 0, "déjà journalisé : pas de doublon")
        # stats + grille
        st = self.c.get("/stats").get_json()
        self.assertEqual(st["per_connector"][str(c["id"])]["messages"], 2)
        self.assertEqual(st["per_connector"][str(c["id"])]["non_interpretes"], 1)
        self.assertTrue(st["grid"])
        # état du connecteur
        updated = [x for x in self.c.get("/connectors").get_json()["connectors"] if x["id"] == c["id"]][0]
        self.assertTrue(updated["last_ok"])

    def test_releve_boite_injoignable(self):
        c = self._create(name="boite-morte")
        handled, error = app_mod.poll_connector(
            store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
            fetch=lambda cfg, limit=50: ([], "connexion refusée"))
        self.assertEqual(handled, 0)
        self.assertEqual(error, "connexion refusée")
        updated = [x for x in self.c.get("/connectors").get_json()["connectors"] if x["id"] == c["id"]][0]
        self.assertFalse(updated["last_ok"])
        self.assertEqual(updated["last_error"], "connexion refusée")

    def test_routage_tickets(self):
        c = self._create(name="sav-in", target="tickets")
        posts = []

        def fake_post(url, json=None, timeout=None):
            posts.append((url, json))
            return FakeResp()

        msg = {"uid": "201", "message_id": "<t@t>", "from_addr": "user@exemple.fr",
               "subject": "Panne imprimante", "date": "Tue, 11 Aug 2026 12:40:00 +0200",
               "body": "plus de toner", "_num": b"5"}
        app_mod.imap_fetch.mark_seen = lambda cfg, nums: None
        handled, _ = app_mod.poll_connector(
            store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
            fetch=lambda cfg, limit=50: ([msg], None), deliver_kw={"post": fake_post})
        self.assertEqual(handled, 1)
        self.assertEqual(len(posts), 1)
        url, payload = posts[0]
        self.assertIn("/tickets", url)
        self.assertEqual(payload["source_type"], "imap")
        self.assertEqual(payload["source_nom"], "sav-in")
        self.assertEqual(payload["subject"], "[IMAP] Panne imprimante")


if __name__ == "__main__":
    unittest.main()
