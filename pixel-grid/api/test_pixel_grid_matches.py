"""Tests des routes de correspondance nom -> localisation (livraison #426),
sur une base SQLite temporaire : python3 -m unittest test_pixel_grid_matches
depuis pixel-grid/api/ (rights-api non configuré -> écritures autorisées)."""
import os
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["PIXEL_GRID_DB_PATH"] = _tmp.name
os.environ["DB_BACKEND"] = "sqlite"
os.environ.pop("RIGHTS_API_URL", None)
_conn = sqlite3.connect(_tmp.name)
_conn.execute("CREATE TABLE geolocations (localisation TEXT PRIMARY KEY, latitude REAL, longitude REAL, parent_localisation TEXT, location_type TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
for loc, lat, lon in [("@5", 45.76, 4.83), ("Arobase 3", 46.59, 4.84), ("Agence Nantes", 47.2, -1.55), ("Sans coordonnées", None, None), ("__default__", 45.77, 2.4)]:
    _conn.execute("INSERT INTO geolocations VALUES (?, ?, ?, NULL, NULL, 'now', 'now')", (loc, lat, lon))
_conn.commit(); _conn.close()

import app as pixel_app  # noqa: E402

client = pixel_app.app.test_client()


class MatchesTest(unittest.TestCase):
    def test_tables_creees(self):
        self.assertIsInstance(client.get("/geolocations/matches").get_json()["matches"], list)
        self.assertIsInstance(client.get("/geolocations/aliases").get_json()["aliases"], list)

    def test_resolve_get_sans_persistance(self):
        d = client.get("/geolocations/resolve?name=UPS-Arobase-5").get_json()
        self.assertEqual(d["match"]["localisation"], "@5")
        self.assertEqual(d["match"]["latitude"], 45.76)
        self.assertTrue(d["match"]["mapped"])
        self.assertFalse(any(m["name"] == "UPS-Arobase-5" and m["subject"] == "UPS-Arobase-5" for m in client.get("/geolocations/matches").get_json()["matches"]))
        self.assertEqual(client.get("/geolocations/resolve").status_code, 400)

    def test_resolve_post_persiste_puis_decision(self):
        subs = [{"subject": "ip:10.0.0.1", "name": "UPS-Arobase-5"}, {"subject": "ip:10.0.0.2", "name": "pc-compta"},
                {"subject": "ip:10.0.0.3", "name": "sw-arobase"}, {"subject": "name:nas", "name": "nas", "site": "Arobase-3"}]
        d = client.post("/geolocations/resolve", json={"subjects": subs}).get_json()
        by = {m["subject"]: m for m in d["matches"]}
        self.assertEqual((by["ip:10.0.0.1"]["localisation"], by["ip:10.0.0.1"]["status"]), ("@5", "auto"))
        self.assertEqual(by["ip:10.0.0.1"]["method"], "exact/nom")
        self.assertIsNone(by["ip:10.0.0.2"]["status"])
        self.assertEqual(by["ip:10.0.0.3"]["status"], "suggested", "ambigu (@5 / Arobase 3) : proposé, pas appliqué")
        self.assertEqual((by["name:nas"]["localisation"], by["name:nas"]["method"]), ("Arobase 3", "exact/site"))
        stored = {m["subject"]: m for m in client.get("/geolocations/matches").get_json()["matches"]}
        self.assertEqual(set(stored), {"ip:10.0.0.1", "ip:10.0.0.3", "name:nas"}, "rien de crédible -> rien de stocké")
        # rejet, puis un nouveau resolve ne le recalcule pas
        r = client.put("/geolocations/matches/ip:10.0.0.1", json={"status": "rejected"})
        self.assertEqual(r.status_code, 200, r.get_json())
        d = client.post("/geolocations/resolve", json={"subjects": subs[:1]}).get_json()
        self.assertEqual(d["matches"][0]["status"], "rejected")
        self.assertEqual(d["matches"][0]["localisation"], "@5", "la localisation calculée reste visible")
        # choix manuel : localisation obligatoire et connue
        self.assertEqual(client.put("/geolocations/matches/ip:10.0.0.3", json={"status": "manual"}).status_code, 400)
        self.assertEqual(client.put("/geolocations/matches/ip:10.0.0.3", json={"status": "manual", "localisation": "Nulle part"}).status_code, 400)
        m = client.put("/geolocations/matches/ip:10.0.0.3", json={"status": "manual", "localisation": "Agence Nantes"}).get_json()["match"]
        self.assertEqual((m["status"], m["latitude"]), ("manual", 47.2))
        # validation d'une correspondance calculée
        m = client.put("/geolocations/matches/name:nas", json={"status": "validated"}).get_json()["match"]
        self.assertEqual((m["status"], m["localisation"], m["score"]), ("validated", "Arobase 3", 1.0))
        # retour à l'automatique
        self.assertEqual(client.delete("/geolocations/matches/ip:10.0.0.1").status_code, 200)
        d = client.post("/geolocations/resolve", json={"subjects": subs[:1]}).get_json()
        self.assertEqual(d["matches"][0]["status"], "auto")
        self.assertEqual(client.put("/geolocations/matches/x", json={"status": "bizarre"}).status_code, 400)

    def test_alias(self):
        self.assertEqual(client.post("/geolocations/aliases", json={"alias": "annexe", "localisation": "Inconnue"}).status_code, 400)
        self.assertEqual(client.post("/geolocations/aliases", json={"alias": "annexe nord", "localisation": "Agence Nantes"}).status_code, 200)
        d = client.get("/geolocations/resolve?name=srv-annexe-nord").get_json()
        self.assertEqual((d["match"]["localisation"], d["match"]["method"]), ("Agence Nantes", "alias"))
        self.assertEqual(client.delete("/geolocations/aliases?alias=annexe nord").status_code, 200)
        self.assertEqual(client.get("/geolocations/aliases").get_json()["aliases"], [])

    def test_sans_coordonnees_non_mappe(self):
        d = client.get("/geolocations/resolve?name=ups-sans-coordonnees").get_json()
        self.assertEqual(d["match"]["localisation"], "Sans coordonnées")
        self.assertFalse(d["match"]["mapped"])


if __name__ == "__main__":
    unittest.main()
