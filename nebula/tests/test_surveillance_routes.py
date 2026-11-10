# -*- coding: utf-8 -*-
"""Tests #1001 : routes de la liste de surveillance (aperçu, droit manage avec lien vers le réglage, dépôt, rapprochement,
décision) et alerte après relève. Données inventées."""
import os
import sqlite3
import sys
import tempfile
import unittest

from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import client_history as ch  # noqa: E402
import surveillance_routes as sr  # noqa: E402

TEXTE = "T01\tTablette\tTab A11+\tSM-X230\tR5XXA01AAAA\ta4:9f:00:00:00:01\nT02\tTablette\tTab A11+\tSM-X230\tR5XXA02BBBB\ta4:9f:00:00:00:02\n"


class Routes(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "n.db")
        self.alertes, self.droit = [], [True]
        app = Flask(__name__)
        self.apres = sr.register(app, {"conn": lambda: sqlite3.connect(self.db), "sites": lambda: [{"siteId": "s1"}],
                                       "manage": lambda b: (self.droit[0], None if self.droit[0] else "droit 'manage' requis"),
                                       "notify": lambda *a: self.alertes.append(a)})
        self.c = app.test_client()

    def test_parcours(self):
        r = self.c.post("/surveillance/importer", json={"liste": "tablettes", "texte": TEXTE, "apercu": True}).get_json()
        self.assertEqual(len(r["elements"]), 2)
        self.droit[0] = False
        r = self.c.post("/surveillance/importer", json={"liste": "tablettes", "texte": TEXTE})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["reglage"]["view"], "rights")
        self.droit[0] = True
        self.assertEqual(self.c.post("/surveillance/importer", json={"liste": "", "texte": TEXTE}).status_code, 400)
        self.assertEqual(self.c.post("/surveillance/importer", json={"liste": "tablettes", "texte": TEXTE}).get_json()["ajoutes"], 2)
        conn = sqlite3.connect(self.db)
        now = 1_791_000_000
        ch.ingest(conn, "s1", ch.merge([{"mac": "a4:9f:00:00:00:02", "name": "Galaxy-Tab-A11", "manufacturer": "Samsung Electronics", "lastSeen": now}], now=now), now=now)
        conn.close()
        evts = self.apres("s1", now)
        self.assertEqual([(e["element"], e["statut"]) for e in evts], [("T02", "reconnu")])
        self.assertEqual(self.alertes[0][2], "info")
        self.assertEqual(self.apres("s1", now), [])
        self.assertEqual(len(self.alertes), 1)
        d = self.c.get("/surveillance?jours=400").get_json()
        t2 = next(e for e in d["elements"] if e["libelle"] == "T02")
        self.assertEqual(t2["dernier_repere"]["statut"], "reconnu")
        rid = t2["dernier_repere"]["id"]
        self.assertEqual(self.c.post("/surveillance/reperes/%d/decision" % rid, json={"decision": "n'importe"}).status_code, 400)
        self.assertEqual(self.c.post("/surveillance/reperes/999/decision", json={"decision": "rejete"}).status_code, 404)
        self.assertEqual(self.c.post("/surveillance/reperes/%d/decision" % rid, json={"decision": "rejete"}).get_json()["decision"], "rejete")
        self.assertIsNone(next(e for e in self.c.get("/surveillance?jours=400").get_json()["elements"] if e["libelle"] == "T02")["dernier_repere"])
        self.assertEqual(self.c.delete("/surveillance/listes/tablettes", json={}).get_json()["supprimes"], 2)

    def test_resume_alerte(self):
        s = sr.resume_alerte([{"type": "discordance", "liste": "l", "element": "T01", "mac": "m", "statut": "discordant", "nom": "x",
                               "discordances": ["fabricant annoncé « Intel », attendu « Samsung »"]}])
        self.assertEqual(s[2], "warning")
        self.assertIn("usurpation", s[0])
        self.assertIsNone(sr.resume_alerte([]))


if __name__ == "__main__":
    unittest.main()
