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

CLEARED_BODY = """Event Cleared At: 2026/08/11 11:05:00.000 Alert generated at
2026/08/11 10:30:12.000 Clear Message : retour a la normale Message : Ping degrade
Localisation : /Parc Composants : 
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

    def test_cloche_sms_non_lus_et_accuse(self):
        c = self._create(name="sms-gw", target="sms")
        msg = {"uid": "301", "message_id": "<s@s>", "from_addr": "gw@sms.lan",
               "subject": "SMS de +33612345678", "date": "Tue, 11 Aug 2026 14:00:00 +0200",
               "body": "reunion avancee a 15h", "_num": b"7"}
        app_mod.imap_fetch.mark_seen = lambda cfg, nums: None
        handled, _ = app_mod.poll_connector(
            store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
            fetch=lambda cfg, limit=50: ([msg], None))
        self.assertEqual(handled, 1)
        # la cloche voit 1 non lu, avec expéditeur et texte interprétés
        n = self.c.get("/notifications").get_json()
        self.assertEqual(n["unread"], 1)
        self.assertEqual(len(n["items"]), 1)
        item = n["items"][0]
        self.assertEqual(item["connector_name"], "sms-gw")
        self.assertEqual(item["fields"]["sender"], "+33612345678")
        self.assertIn("reunion", item["fields"]["text"])
        # filtre par cible : zenoss ne remonte pas ce SMS
        self.assertEqual(self.c.get("/notifications?targets=zenoss").get_json()["unread"], 0)
        # accusé par id, puis plus rien ; second accusé = 0 (idempotent)
        r = self.c.post("/notifications/ack", json={"ids": [item["id"]]})
        self.assertEqual(r.get_json()["acked"], 1)
        self.assertEqual(self.c.get("/notifications").get_json()["unread"], 0)
        self.assertEqual(self.c.post("/notifications/ack", json={"ids": [item["id"]]}).get_json()["acked"], 0)
        # nouveau SMS puis « tout marquer lu »
        msg2 = dict(msg, uid="302", _num=b"8", subject="SMS de +33699999999")
        app_mod.poll_connector(store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
                               fetch=lambda cfg, limit=50: ([msg2], None))
        self.assertEqual(self.c.get("/notifications").get_json()["unread"], 1)
        r = self.c.post("/notifications/ack", json={"all": True, "targets": ["sms"]})
        self.assertEqual(r.get_json()["acked"], 1)
        self.assertEqual(self.c.get("/notifications").get_json()["unread"], 0)
        # garde-fous
        self.assertEqual(self.c.post("/notifications/ack", json={}).status_code, 400)
        self.assertEqual(self.c.post("/notifications/ack", json={"ids": ["abc"]}).status_code, 400)

    def test_auto_ack_a_la_resolution(self):
        """#492 : une résolution acquitte les alertes actives non lues
        du même équipement (et elle-même) — paramétrable par auto_ack."""
        # base pixel-grid créée par le livreur lui-même (comme en
        # production) — ne PAS pré-créer les tables ici
        pixel_kw = {"db_path": os.path.join(TMP, "pixel-auto.db"), "backend": "sqlite"}
        active = {"uid": "401", "message_id": "<z1@z>", "from_addr": "zenoss@exemple.fr",
                  "subject": "[Site A] sw-coeur Ping degrade", "date": "Tue, 11 Aug 2026 12:31:00 +0200",
                  "body": ZENOSS_BODY, "_num": b"1"}
        clear = {"uid": "402", "message_id": "<z2@z>", "from_addr": "zenoss@exemple.fr",
                 "subject": "[Site A] clear: sw-coeur Ping degrade", "date": "Tue, 11 Aug 2026 13:05:00 +0200",
                 "body": CLEARED_BODY, "_num": b"2"}
        app_mod.imap_fetch.mark_seen = lambda cfg, nums: None

        # auto_ack ACTIVÉ (défaut) : la résolution vide la cloche
        c = self._create(name="zen-auto")
        poll = lambda m: app_mod.poll_connector(  # noqa: E731
            store.get_connector(app_mod.DB_PATH, c["id"], with_secret=True),
            fetch=lambda cfg, limit=50: ([m], None), deliver_kw=pixel_kw)
        poll(active)
        self.assertEqual(self.c.get("/notifications?targets=zenoss").get_json()["unread"], 1)
        poll(clear)
        n = self.c.get("/notifications?targets=zenoss").get_json()
        self.assertEqual(n["unread"], 0, "résolution : alerte active ET résolution acquittées")

        # auto_ack DÉSACTIVÉ : tout reste visible, acquittement manuel
        c2 = self._create(name="zen-manuel", auto_ack=False)
        self.assertFalse([x for x in self.c.get("/connectors").get_json()["connectors"]
                          if x["id"] == c2["id"]][0]["auto_ack"])
        poll2 = lambda m: app_mod.poll_connector(  # noqa: E731
            store.get_connector(app_mod.DB_PATH, c2["id"], with_secret=True),
            fetch=lambda cfg, limit=50: ([m], None), deliver_kw=pixel_kw)
        poll2(dict(active, uid="501", _num=b"3"))
        poll2(dict(clear, uid="502", _num=b"4"))
        n = self.c.get("/notifications?targets=zenoss").get_json()
        self.assertEqual(n["unread"], 2, "sans auto_ack : alerte et résolution restent à acquitter")

    def test_migration_schema_489_vers_492(self):
        """Une base créée en #489 (sans ack_at ni auto_ack) est migrée
        par ensure_schema, sans perte."""
        import sqlite3 as _s
        old_db = os.path.join(TMP, "old-489.db")
        conn = _s.connect(old_db)
        conn.execute("CREATE TABLE connectors (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, "
                     "host TEXT NOT NULL, port INTEGER NOT NULL DEFAULT 993, tls INTEGER NOT NULL DEFAULT 1, "
                     "username TEXT NOT NULL, password TEXT NOT NULL, folder TEXT NOT NULL DEFAULT 'INBOX', "
                     "target TEXT NOT NULL, interval_seconds INTEGER NOT NULL DEFAULT 300, "
                     "mark_seen INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 0, "
                     "default_type_id INTEGER, default_level_id INTEGER, notes TEXT, "
                     "last_poll_at TEXT, last_ok INTEGER, last_error TEXT, last_message_at TEXT, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO connectors (name, host, username, password, target, created_at) "
                     "VALUES ('vieux', 'h', 'u', 'p', 'zenoss', '2026-09-13T00:00:00+00:00')")
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "connector_id INTEGER NOT NULL, uid TEXT NOT NULL, message_id TEXT, from_addr TEXT, "
                     "subject TEXT, date TEXT, fetched_at TEXT NOT NULL, parsed INTEGER NOT NULL DEFAULT 0, "
                     "kind TEXT, summary TEXT, fields TEXT, UNIQUE(connector_id, uid))")
        conn.commit(); conn.close()
        store.ensure_schema(old_db)
        conn = _s.connect(old_db)
        msg_cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
        con_cols = {r[1] for r in conn.execute("PRAGMA table_info(connectors)")}
        auto = conn.execute("SELECT auto_ack FROM connectors WHERE name = 'vieux'").fetchone()[0]
        conn.close()
        self.assertIn("ack_at", msg_cols)
        self.assertIn("auto_ack", con_cols)
        self.assertEqual(auto, 1, "les connecteurs existants héritent de l'auto-acquittement activé")

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
