# -*- coding: utf-8 -*-
"""Tests d'intégration du catalogue (livraison #429) contre un VRAI
PostGIS (GEO_CATALOG_TEST_DB_URL, ex. postgresql://geocat:geocat@localhost:5432/geocat)
et un faux pixel-grid + faux géocodeur (réponses BAN/communes simulées, jamais
le réseau). Sautés si la base n'est pas configurée."""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DB_URL = os.environ.get("GEO_CATALOG_TEST_DB_URL")
if DB_URL:
    os.environ["GEO_CATALOG_DB_URL"] = DB_URL
    os.environ["PIXEL_GRID_API_INTERNAL_URL"] = "http://pixel-grid.test"
    os.environ.pop("RIGHTS_API_URL", None)
    import app as api  # noqa: E402
    import refs  # noqa: E402
    import store  # noqa: E402

GEOS = [
    {"localisation": "Parc/Batiment 5", "latitude": 45.7640, "longitude": 4.8357, "parent_localisation": "Parc", "location_type": "site", "mapped": True},
    {"localisation": "Parc", "latitude": None, "longitude": None, "parent_localisation": None, "location_type": "zone", "mapped": False},
    {"localisation": "Agence 17300", "latitude": 45.9, "longitude": -1.0, "mapped": True},
    {"localisation": "__default__", "latitude": 45.77, "longitude": 2.4, "mapped": True},
]
MATCHES = [{"subject": "ip:10.0.0.7", "name": "UPS-Batiment-5", "site": None, "localisation": "Parc/Batiment 5", "status": "auto", "score": 1.0, "method": "exact/nom"}]


class FakeResp(object):
    def __init__(self, status, data):
        self.status_code, self._data = status, data
        self.content = b"x"

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)


def fake_get(url, **kw):
    if url.endswith("/geolocations"):
        return FakeResp(200, {"geolocations": GEOS})
    if url.endswith("/geolocations/matches"):
        return FakeResp(200, {"matches": MATCHES})
    if "geocodage/search" in url:
        if "Batiment" in url and "index=poi" in url:
            return FakeResp(200, {"features": [{"properties": {"id": "poi1", "toponym": "Batiment 5", "type": "poi", "score": 0.88}, "geometry": {"coordinates": [4.8360, 45.7645]}}]})
        if "Batiment" in url:
            return FakeResp(200, {"features": [{"properties": {"id": "a1", "label": "Avenue du Batiment 75000 Villexemple", "type": "street", "score": 0.7, "city": "Villexemple", "postcode": "75000"}, "geometry": {"coordinates": [0.3660, 46.6600]}}]})
        return FakeResp(200, {"features": []})
    if "communes?codePostal=17300" in url:
        return FakeResp(200, [{"code": "17300", "nom": "Rochefort", "codesPostaux": ["17300"], "centre": {"coordinates": [-0.96, 45.94]}, "population": 24000}])
    if "communes?fields" in url:
        return FakeResp(200, [{"code": "75056", "nom": "Villexemple", "codesPostaux": ["75000"], "centre": {"coordinates": [4.86, 45.79]}, "population": 4800},
                              {"code": "17299", "nom": "Rochefort", "codesPostaux": ["17300"], "centre": {"coordinates": [-0.96, 45.94]}, "population": 24000}])
    return FakeResp(404, {})


@unittest.skipUnless(DB_URL, "GEO_CATALOG_TEST_DB_URL non défini")
class CatalogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = store.connect(DB_URL)
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS catalog_links, catalog_refs, catalog_positions, ref_communes, ref_geocode_cache, catalog_sync_log CASCADE")
        conn.commit()
        store.ensure_schema(conn)
        conn.close()
        cls.c = api.app.test_client()

    def test_01_status_vide(self):
        s = self.c.get("/status").get_json()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["communes"]["count"], 0)
        self.assertEqual(s["osm_tables"], [])

    def test_02_sync_interpretation_liens(self):
        with mock.patch("refs.requests.get", side_effect=fake_get):
            r = self.c.post("/sync", json={})
        self.assertEqual(r.status_code, 200, r.get_json())
        d = r.get_json()
        self.assertEqual((d["positions"], d["errors"]), (3, []), "__default__ exclu")
        rows = {p["label"]: p for p in self.c.get("/positions").get_json()["positions"]}
        tp = rows["Parc/Batiment 5"]
        self.assertEqual(tp["precision"], "poi", "le POI Géoplateforme est la référence la plus précise")
        self.assertGreaterEqual(tp["confidence"], 80, tp["interpretation"]["reasons"])
        self.assertEqual({r["source"] for r in tp["refs"]}, {"geolocations", "ban"})
        self.assertEqual({(l["object_type"], l["object_id"]) for l in tp["links"]}, {("supervised", "ip:10.0.0.7"), ("geolocation", "Parc")})
        zone = rows["Parc"]
        self.assertEqual(zone["confidence"], 0, "aucune référence pour un nom générique")
        self.assertEqual({l["object_id"] for l in zone["links"]}, {"Parc/Batiment 5"})
        ag = rows["Agence 17300"]
        self.assertEqual({r["source"] for r in ag["refs"]}, {"geolocations", "commune"}, "code postal -> commune via geo.api.gouv.fr (cache)")
        self.assertEqual(ag["precision"], "commune")
        self.assertLess(ag["confidence"], 70, "commune seule : incertain")

    def test_03_decisions(self):
        rows = {p["label"]: p for p in self.c.get("/positions").get_json()["positions"]}
        pid = rows["Agence 17300"]["id"]
        self.assertEqual(self.c.put("/positions/%d/correct" % pid, json={"lat": 200, "lon": 0}).status_code, 400)
        self.assertEqual(self.c.put("/positions/%d/correct" % pid, json={}).status_code, 400)
        p = self.c.put("/positions/%d/correct" % pid, json={"lat": 45.95, "lon": -0.97, "note": "vu sur place"}).get_json()["position"]
        self.assertEqual((p["status"], p["confidence"], p["lat"]), ("corrected", 100, 45.95))
        self.assertIn("human", {r["source"] for r in p["refs"]})
        # une resynchronisation ne touche pas à la décision
        with mock.patch("refs.requests.get", side_effect=fake_get):
            self.c.post("/sync", json={"only": ["Agence 17300"]})
        p = self.c.get("/positions/%d" % pid).get_json()
        self.assertEqual((p["status"], p["lat"], p["confidence"]), ("corrected", 45.95, 100))
        self.assertEqual(p["interpretation"]["reasons"], ["décision humaine (corrected)"])
        # validation puis retour à l'automatique
        zid = rows["Parc"]["id"]
        self.assertEqual(self.c.put("/positions/%d/validate" % zid, json={}).status_code, 400, "rien à valider sans position")
        tid = rows["Parc/Batiment 5"]["id"]
        v = self.c.put("/positions/%d/validate" % tid, json={}).get_json()["position"]
        self.assertEqual((v["status"], v["confidence"]), ("validated", 95))
        r = self.c.put("/positions/%d/reset" % tid, json={}).get_json()["position"]
        self.assertEqual(r["status"], "auto")
        self.assertNotIn("human", {x["source"] for x in r["refs"]})
        # reprise d'une référence
        ban = next(x for x in r["refs"] if x["source"] == "ban" and x["precision"] == "street")
        u = self.c.put("/positions/%d/refs/%d/use" % (tid, ban["id"]), json={}).get_json()["position"]
        self.assertEqual((u["status"], u["lat"]), ("corrected", 45.80))
        self.assertEqual(self.c.put("/positions/%d/reset" % tid, json={}).status_code, 200)

    def test_04_push_vers_pixel_grid(self):
        rows = {p["label"]: p for p in self.c.get("/positions").get_json()["positions"]}
        pid = rows["Agence 17300"]["id"]
        with mock.patch("refs.requests.post", return_value=FakeResp(200, {"status": "ok"})) as p:
            r = self.c.post("/positions/%d/push" % pid, json={"groups": ["admin_hub"]})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(p.call_args.kwargs["json"]["localisation"], "Agence 17300")
            self.assertEqual(p.call_args.kwargs["json"]["latitude"], 45.95)
        zid = rows["Parc"]["id"]
        self.assertEqual(self.c.post("/positions/%d/push" % zid, json={}).status_code, 400, "sans position")

    def test_05_communes_et_lookup(self):
        with mock.patch("refs.requests.get", side_effect=fake_get):
            r = self.c.post("/referentials/communes/load", json={})
            self.assertEqual(r.get_json()["communes"], 2)
            d = self.c.get("/referentials/lookup?label=Site%20Villexemple").get_json()
        self.assertIn("commune", {x["source"] for x in d["refs"]}, "nom de commune proche (pg_trgm) sans code postal")
        self.assertEqual(d["interpretation"]["precision"], "municipality")
        s = self.c.get("/status").get_json()
        self.assertEqual(s["communes"]["count"], 2)
        self.assertGreaterEqual(s["geocode_cache"], 3)
        self.assertEqual(s["last_sync"]["positions"], 1)

    def test_06_nearby(self):
        rows = {p["label"]: p for p in self.c.get("/positions").get_json()["positions"]}
        p = self.c.get("/positions/%d" % rows["Parc/Batiment 5"]["id"]).get_json()
        self.assertIn("nearby", p)
        self.assertEqual(self.c.get("/positions/999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
