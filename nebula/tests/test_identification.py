# -*- coding: utf-8 -*-
"""Tests #1004 : catégories par client (filtres par catégorie et certitude), confirmation humaine, apprentissage qui modifie
les certitudes des clients partageant les mêmes traits, annulation. Données inventées."""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

os.environ["NEBULA_POLL_DISABLED"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
from flask import Flask  # noqa: E402

import categorie as cg  # noqa: E402
import client_history as ch  # noqa: E402
import client_history_routes as chr_  # noqa: E402
import identification as idf  # noqa: E402


class Identification(unittest.TestCase):
    def setUp(self):
        idf._cache.clear(); idf.invalider()
        self.db = os.path.join(tempfile.mkdtemp(), "n.db")
        now = int(time.time())
        conn = sqlite3.connect(self.db)
        cl = [{"mac": "84:9e:56:00:00:%02x" % i, "name": "mini-%d" % i, "manufacturer": "Cloud Network Technology Singapore", "lastSeen": now} for i in range(3)]
        cl += [{"mac": "6e:00:00:00:00:01", "name": "Galaxy-Tab-A11", "os": "Android", "lastSeen": now}]
        ch.ingest(conn, "s1", ch.merge(cl, now=now), now=now)
        conn.close()
        self.droit = [True]
        app = Flask(__name__)
        chr_.register(app, {"conn": lambda: sqlite3.connect(self.db), "client": None, "sites": lambda: [], "db_path": self.db,
                            "configured": lambda: False, "manage": lambda b: (self.droit[0], None if self.droit[0] else "droit 'manage' requis")})
        self.c = app.test_client()

    def test_filtres_et_menus(self):
        m = self.c.get("/client-history/categories?site=s1").get_json()
        self.assertIn({"categorie": "mobile Android", "n": 1}, m["categories"])
        self.assertEqual([n["niveau"] for n in m["niveaux"]], ["confirmée", "forte", "moyenne", "faible", "aucune"])
        r = self.c.get("/client-history?site=s1&categorie=mobile%20Android").get_json()
        self.assertEqual([x["mac"] for x in r["rows"]], ["6e:00:00:00:00:01"])
        self.assertIn(r["rows"][0]["niveau"], ("forte", "moyenne", "faible"))
        self.assertEqual(self.c.get("/client-history?site=s1&certitude=confirm%C3%A9e").get_json()["total"], 0)

    def test_confirmation_et_apprentissage(self):
        conn = sqlite3.connect(self.db)
        avant = idf.categorie_client(conn, "s1", idf.fiche(conn, "s1", "84:9e:56:00:00:02"))
        conn.close()
        self.droit[0] = False
        r = self.c.post("/client-history/categorie/decision", json={"site": "s1", "mac": "84:9e:56:00:00:00", "categorie": "machine Linux / sans écran"})
        self.assertEqual((r.status_code, r.get_json()["reglage"]["view"]), (403, "rights"))
        self.droit[0] = True
        self.assertEqual(self.c.post("/client-history/categorie/decision", json={"site": "s1", "mac": "84:9e:56:00:00:00", "categorie": "grille-pain"}).status_code, 400)
        for i in (0, 1):
            d = self.c.post("/client-history/categorie/decision", json={"site": "s1", "mac": "84:9e:56:00:00:%02x" % i, "categorie": "machine Linux / sans écran", "user": "freg"}).get_json()
            self.assertEqual(d["categorie"], "machine Linux / sans écran")
        self.assertEqual(self.c.get("/client-history?site=s1&certitude=confirm%C3%A9e").get_json()["total"], 2)
        conn = sqlite3.connect(self.db)
        apres = idf.categorie_client(conn, "s1", idf.fiche(conn, "s1", "84:9e:56:00:00:02"))
        conn.close()
        self.assertEqual(apres["categorie"], "machine Linux / sans écran")
        self.assertGreater(apres["confiance"], avant["confiance"] if avant["categorie"] == apres["categorie"] else 0)
        self.assertTrue(any(p["texte"].startswith("appris : 2 confirmation(s)") for p in apres["hypotheses"][0]["preuves"]))
        self.assertEqual(self.c.delete("/client-history/categorie/decision", json={"site": "s1", "mac": "84:9e:56:00:00:00"}).get_json()["annule"], 1)
        self.assertEqual(self.c.get("/client-history?site=s1&certitude=confirm%C3%A9e").get_json()["total"], 1)

    def test_correction_affaiblit_la_proposition(self):
        st = cg.apprentissage([{"categorie": "machine Linux / sans écran", "proposee": "mobile Android", "traits": {"fabricant": "x", "SSID": "wifi"}}] * 3)
        self.assertEqual(st[("fabricant", "x")]["neg"], {"mobile Android": 3})
        self.assertNotIn(("SSID", "wifi"), st)
        f = {"mac": "6e:00:00:00:00:09", "manufacturer": "X", "os": "Android"}
        sans, avec = cg.categoriser(f, None), cg.categoriser(f, None, appris={("fabricant", "x"): st[("fabricant", "x")]})
        self.assertEqual(sans["hypotheses"][0]["score"] - avec["hypotheses"][0]["score"], 15)   # le système annoncé garde la parole
        self.assertEqual(cg.categoriser({"mac": "00:aa:00:00:00:09", "manufacturer": "X"}, None, appris={("fabricant", "x"): st[("fabricant", "x")]})["categorie"],
                         "machine Linux / sans écran")
        r2 = cg.categoriser({"mac": "6e:00:00:00:00:09", "manufacturer": "X"}, None, decision={"categorie": "imprimante", "par": "freg"})
        self.assertEqual((r2["categorie"], r2["confiance"], r2["niveau"]), ("imprimante", 100, "confirmée"))


if __name__ == "__main__":
    unittest.main()
