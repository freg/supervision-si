# -*- coding: utf-8 -*-
"""#444 : spécification d'interface générée -- rapprochement champs/colonnes,
genres d'écran, table principale, conservation des choix manuels, route
GET/PUT /apps/<label>/ui-spec avec un faux dba-api."""
import copy
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("RETRO_DATA_DIR", tempfile.mkdtemp(prefix="retro-ui-"))
os.environ.setdefault("RETRO_RELAY_TOKEN", "relais-secret")

import journeys as J  # noqa: E402
import ui_spec as U  # noqa: E402
import journeys_store as S  # noqa: E402
import app as retro_app  # noqa: E402
import test_journeys as T  # noqa: E402

COLS = {"clients": [{"name": "id", "type": "int", "primary_key": True}, {"name": "nom", "type": "varchar"}, {"name": "email", "type": "varchar"}, {"name": "tel", "type": "varchar"}, {"name": "ville_id", "type": "int"}],
        "journal": [{"name": "id", "primary_key": True}, {"name": "client_id"}, {"name": "action"}]}


class PureTests(unittest.TestCase):
    def test_match_column(self):
        self.assertEqual(U.match_column("Nom", ["nom", "prenom"]), ("nom", 1.0, "exact"))
        self.assertEqual(U.match_column("txtNom", ["nom"]), ("nom", 1.0, "exact"))
        self.assertEqual(U.match_column("date_naissance", ["DateNaissance"]), ("DateNaissance", 0.9, "sans-separateurs"))
        self.assertEqual(U.match_column("Téléphone", ["tel", "telephone_fixe"])[0], "telephone_fixe")
        self.assertEqual(U.match_column("csrf", ["nom"]), (None, 0.0, None))
        self.assertEqual(U.match_column("email[]", ["email"]), ("email", 1.0, "exact"))

    def _spec(self, existing=None):
        steps = J.build_steps(T.EVENTS, "https://gestion.exemple.fr"); J.attribute_queries(steps, T.QUERIES)
        fmap = J.functional_map(steps, T.SCAN, "https://gestion.exemple.fr")
        return U.build_ui_spec(steps, fmap, COLS, "gestion", existing=existing)

    def test_build_spec(self):
        spec = self._spec()
        by = {s["id"]: s for s in spec["screens"]}
        self.assertEqual(set(by), {"clients", "client-n", "client-n-save"})
        lst = by["clients"]
        self.assertEqual((lst["kind"], lst["table"], lst["table_source"]), ("list", "clients", "journal SQL de l'écran"))
        self.assertEqual([(c["label"], c["column"]) for c in lst["columns"]], [("Nom", "nom"), ("Ville", "ville_id")])
        self.assertEqual(lst["links"][0]["to"], "client-n")
        form = by["client-n"]
        self.assertEqual((form["kind"], form["table"], form["pk"]), ("form", "clients", "id"))
        self.assertEqual([(f["name"], f["column"]) for f in form["fields"]], [("nom", "nom"), ("email", "email"), ("telephone", "tel")])
        self.assertEqual(form["actions"][0]["writes"], ["clients", "journal"])
        self.assertEqual(by["client-n-save"]["kind"], "action")
        self.assertEqual(spec["counts"]["nav"], 2)
        # les choix manuels survivent à une régénération
        edited = copy.deepcopy(spec)
        for s in edited["screens"]:
            if s["id"] == "clients":
                s["table"] = "journal"; s["table_manual"] = True; s["title"] = "Mes clients"; s["title_manual"] = True; s["hidden"] = True
        spec2 = self._spec(existing=edited)
        lst2 = [s for s in spec2["screens"] if s["id"] == "clients"][0]
        self.assertEqual((lst2["table"], lst2["table_source"], lst2["title"], lst2["hidden"], lst2["nav"]), ("journal", "choisi à la main", "Mes clients", True, False))

    def test_spec_without_columns(self):
        steps = J.build_steps(T.EVENTS, "https://gestion.exemple.fr")
        spec = U.build_ui_spec(steps, J.functional_map(steps, None), {}, "x")
        self.assertTrue(all(s["table"] is None for s in spec["screens"]))
        self.assertIn("table à choisir", spec["screens"][0]["todo"])


class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d


def fake_dba_get(url, params=None, timeout=None):
    t = url.rsplit("/tables/", 1)[1].split("/")[0]
    return FakeResp(COLS.get(t, []), 200 if t in COLS else 404)


class RouteTests(unittest.TestCase):
    def setUp(self):
        retro_app.app.config["TESTING"] = True
        self.c = retro_app.app.test_client()

    def test_ui_spec_routes(self):
        self.c.post("/apps", json={"label": "ui", "base_url": "https://gestion.exemple.fr", "dba_connection_id": 3})
        S.save_scan(retro_app.DB_PATH, "ui", T.SCAN)
        j = self.c.post("/journeys", json={"app": "ui"}).get_json()
        self.c.post(f"/journeys/{j['id']}/events", json={"events": T.EVENTS}, headers={"X-Relay-Token": "relais-secret"})
        with mock.patch.object(retro_app._requests, "get", side_effect=fake_dba_get):
            r = self.c.get("/apps/ui/ui-spec")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["regenerated"]); self.assertEqual(d["counts"]["screens"], 3)
        self.assertEqual(sorted(d["tables"]), ["clients"])  # seules les tables connues du faux dba-api ont des colonnes (pas de SQL collecté ici)
        # enregistrée : relue sans recalcul
        d2 = self.c.get("/apps/ui/ui-spec").get_json()
        self.assertNotIn("regenerated", d2)
        # modification manuelle puis régénération : conservée
        for s in d2["screens"]:
            if s["id"] == "clients":
                s["title"] = "Clientèle"; s["title_manual"] = True
        self.assertEqual(self.c.put("/apps/ui/ui-spec", json={"spec": d2}).status_code, 200)
        with mock.patch.object(retro_app._requests, "get", side_effect=fake_dba_get):
            d3 = self.c.get("/apps/ui/ui-spec?regenerate=1").get_json()
        self.assertEqual([s["title"] for s in d3["screens"] if s["id"] == "clients"], ["Clientèle"])
        self.assertEqual(self.c.put("/apps/ui/ui-spec", json={"spec": {}}).status_code, 400)
        self.assertEqual(self.c.get("/apps/inconnue/ui-spec").status_code, 404)


if __name__ == "__main__":
    unittest.main()
