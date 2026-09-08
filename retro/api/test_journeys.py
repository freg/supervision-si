# -*- coding: utf-8 -*-
"""#441 : parcours applicatifs -- logique pure (étapes, normalisation
d'URL, routes Fat-Free, tables des requêtes, carte fonctionnelle) et
routes de retro-api (relais avec jeton, scan conservé par application,
collecte du journal général via un faux dba-api).
`cd retro/api && python3 -m unittest test_journeys`."""
import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="retro-test-")
os.environ["RETRO_DATA_DIR"] = _TMP
os.environ["RETRO_RELAY_TOKEN"] = "relais-secret"

import journeys as J  # noqa: E402
import journeys_store as S  # noqa: E402
import app as retro_app  # noqa: E402

SCAN = {
    "routes": [
        {"methods": ["GET"], "path": "/clients", "alias": None, "url_tokens": [], "handler_type": "instance", "controller_class": "ClientController", "controller_method": "index", "source_file": "index.php", "source_line": 10},
        {"methods": ["GET"], "path": "/client/@id", "alias": None, "url_tokens": ["id"], "handler_type": "instance", "controller_class": "ClientController", "controller_method": "show", "source_file": "index.php", "source_line": 11},
        {"methods": ["POST"], "path": "/client/@id/save", "alias": None, "url_tokens": ["id"], "handler_type": "instance", "controller_class": "ClientController", "controller_method": "save", "source_file": "index.php", "source_line": 12},
        {"methods": ["GET"], "path": "/api/*", "alias": None, "url_tokens": [], "handler_type": "instance", "controller_class": "ApiController", "controller_method": "any", "source_file": "index.php", "source_line": 13},
    ],
    "classes": {"ClientController": "app/controllers/client.php", "ApiController": "app/controllers/api.php"},
    "join_candidates": [{"from_table": "clients", "from_column": "id", "to_table": "contrats", "to_column": "client_id", "source_file": "app/controllers/client.php", "source_line": 40}],
    "file_tables": {"app/controllers/client.php": ["clients", "adresses"], "app/controllers/api.php": ["produits"]},
    "template_fields": {"client": ["nom", "email", "telephone"]},
}
EVENTS = [
    {"seq": 1, "at": "2026-09-08T09:59:59.8Z", "kind": "request", "data": {"method": "GET", "url": "https://gestion.exemple.fr/clients", "type": "main_frame", "status": 200}},
    {"seq": 2, "at": "2026-09-08T10:00:00Z", "kind": "navigation", "data": {"url": "https://gestion.exemple.fr/clients", "title": "Clients"}},
    {"seq": 3, "at": "2026-09-08T10:00:01Z", "kind": "dom", "data": {"title": "Clients", "forms": [{"action": "/clients", "method": "get", "fields": [{"name": "q", "type": "text"}]}], "headings": ["Clients"], "tables": [{"headers": ["Nom", "Ville"]}], "links_count": 42}},
    {"seq": 4, "at": "2026-09-08T10:00:05Z", "kind": "click", "data": {"selector": "table tr:nth-child(2) a", "text": "Dupont", "tag": "A", "href": "/client/42"}},
    {"seq": 5, "at": "2026-09-08T10:00:05.9Z", "kind": "request", "data": {"method": "GET", "url": "https://gestion.exemple.fr/client/42?tab=infos", "type": "main_frame", "status": 200}},
    {"seq": 6, "at": "2026-09-08T10:00:06.3Z", "kind": "navigation", "data": {"url": "https://gestion.exemple.fr/client/42?tab=infos", "title": "Client Dupont"}},
    {"seq": 7, "at": "2026-09-08T10:00:07Z", "kind": "request", "data": {"method": "GET", "url": "https://gestion.exemple.fr/api/produits/7", "type": "xmlhttprequest", "status": 200}},
    {"seq": 8, "at": "2026-09-08T10:00:20Z", "kind": "input", "data": {"field": "email", "type": "email", "length": 14}},
    {"seq": 9, "at": "2026-09-08T10:00:25Z", "kind": "submit", "data": {"action": "/client/42/save", "method": "post", "fields": ["nom", "email", "telephone", "csrf"]}},
    {"seq": 10, "at": "2026-09-08T10:00:25.4Z", "kind": "request", "data": {"method": "POST", "url": "https://gestion.exemple.fr/client/42/save", "type": "main_frame", "status": 302, "form_keys": ["nom", "email", "telephone", "csrf"]}},
    {"seq": 11, "at": "2026-09-08T10:00:26Z", "kind": "request", "data": {"method": "GET", "url": "https://gestion.exemple.fr/client/42", "type": "main_frame", "status": 200}},
    {"seq": 12, "at": "2026-09-08T10:00:26.5Z", "kind": "navigation", "data": {"url": "https://gestion.exemple.fr/client/42", "title": "Client Dupont"}},
    {"seq": 13, "at": "2026-09-08T10:00:40Z", "kind": "mark", "data": {"label": "après enregistrement"}},
]
QUERIES = [
    {"at": "2026-09-08 10:00:00.5", "sql": "SELECT * FROM clients c LEFT JOIN adresses a ON a.client_id = c.id ORDER BY c.nom"},
    {"at": "2026-09-08 10:00:06.5", "sql": "SELECT * FROM `clients` WHERE id = 42"},
    {"at": "2026-09-08 10:00:07.1", "sql": "SELECT p.* FROM produits p WHERE p.id = 7"},
    {"at": "2026-09-08 10:00:25.6", "sql": "UPDATE clients SET email = 'x@y.fr' WHERE id = 42"},
    {"at": "2026-09-08 10:00:25.7", "sql": "INSERT INTO journal (client_id, action) VALUES (42, 'maj')"},
    {"at": "2026-09-08 10:00:25.8", "sql": "SET NAMES utf8"},
    {"at": "2026-09-08 09:59:00", "sql": "SELECT 1 FROM avant_le_parcours"},
]


class PureTests(unittest.TestCase):
    def test_normalize_and_routes(self):
        self.assertEqual(J.normalize_path("https://h/appli/client/42/edit?tab=infos&id=7", "https://h/appli"), "/client/{n}/edit?id&tab")
        self.assertEqual(J.normalize_path("/x/550e8400-e29b-41d4-a716-446655440000"), "/x/{n}")
        self.assertEqual(J.normalize_path("https://h/appli", "https://h/appli"), "/")
        r = J.match_route("/client/{n}", "GET", SCAN["routes"])
        self.assertEqual(r["controller_method"], "show")
        self.assertEqual(J.match_route("/client/42/save", "POST", SCAN["routes"])["controller_method"], "save")
        self.assertIsNone(J.match_route("/client/42/save", "GET", SCAN["routes"]))
        self.assertEqual(J.match_route("/api/produits/{n}", "GET", SCAN["routes"])["controller_class"], "ApiController")
        self.assertIsNone(J.match_route("/inconnu", "GET", SCAN["routes"]))

    def test_tables_in_sql(self):
        self.assertEqual(J.tables_in_sql("SELECT * FROM clients c LEFT JOIN `adresses` a ON a.client_id = c.id"), (["clients", "adresses"], "SELECT"))
        self.assertEqual(J.tables_in_sql("INSERT INTO gestion.journal (a) VALUES (1)"), (["journal"], "INSERT"))
        self.assertEqual(J.tables_in_sql("DELETE FROM contrats WHERE id = 1"), (["contrats"], "DELETE"))
        self.assertEqual(J.tables_in_sql("SELECT * FROM mysql.general_log"), ([], "SELECT"))
        self.assertEqual(J.tables_in_sql(""), ([], None))

    def test_build_steps_and_queries(self):
        steps = J.build_steps(EVENTS, "https://gestion.exemple.fr")
        self.assertEqual([(s["n"], s["kind"], s["path"], s["method"]) for s in steps],
                         [(1, "navigation", "/clients", "GET"), (2, "navigation", "/client/{n}?tab", "GET"), (3, "navigation", "/client/{n}/save", "POST"),
                          (4, "navigation", "/client/{n}", "GET"), (5, "mark", None, None)])
        self.assertEqual(steps[1]["title"], "Client Dupont")
        self.assertEqual(steps[0]["dom"]["tables"][0]["headers"], ["Nom", "Ville"])
        self.assertEqual([a["kind"] for a in steps[1]["actions"]], ["input", "submit"])
        self.assertEqual(steps[1]["forms"][0]["fields"], ["nom", "email", "telephone", "csrf"])
        self.assertTrue(steps[1]["requests"][0]["page"]); self.assertFalse(steps[1]["requests"][1]["page"])
        n = J.attribute_queries(steps, QUERIES)
        self.assertEqual(n, 5)  # SET NAMES et la requête d'avant le parcours écartées
        self.assertEqual(steps[0]["db_tables"], {"clients": {"reads": 1, "writes": 0}, "adresses": {"reads": 1, "writes": 0}})
        self.assertEqual(steps[1]["db_tables"], {"clients": {"reads": 1, "writes": 0}, "produits": {"reads": 1, "writes": 0}})
        self.assertEqual(steps[2]["db_tables"], {"clients": {"reads": 0, "writes": 1}, "journal": {"reads": 0, "writes": 1}})

    def test_functional_map(self):
        steps = J.build_steps(EVENTS, "https://gestion.exemple.fr")
        J.attribute_queries(steps, QUERIES)
        m = J.functional_map(steps, SCAN, "https://gestion.exemple.fr")
        by = {s["screen"]: s for s in m["screens"]}
        self.assertEqual(set(by), {"/clients", "/client/{n}", "/client/{n}/save", "repère : après enregistrement"})
        c = by["/client/{n}"]
        self.assertEqual((c["route"], c["handler"], c["visits"]), ("/client/@id", "ClientController->show", 2))
        save = by["/client/{n}/save"]
        self.assertEqual((save["route"], save["handler"]), ("/client/@id/save", "ClientController->save"))
        self.assertEqual(save["db_tables"], {"clients": {"reads": 0, "writes": 1}, "journal": {"reads": 0, "writes": 1}})
        self.assertEqual(c["files"], ["app/controllers/client.php"])
        self.assertIn("contrats", c["code_tables"]); self.assertIn("adresses", c["code_tables"])
        self.assertIn("produits", c["code_tables"])  # via la requête XHR /api/produits/{n}
        self.assertEqual(c["db_tables"]["clients"], {"reads": 1, "writes": 0})
        self.assertIn("journal", save["tables"])  # vue seulement côté base : pas dans le code scanné
        self.assertEqual(sorted(x["field"] for x in c["template_fields"]), ["email", "nom", "telephone"])
        self.assertEqual(c["forms"][0]["action"], "/client/{n}/save")
        self.assertEqual(m["tables"]["journal"], {"screens": ["/client/{n}/save"], "from_code": False, "from_db": True})
        self.assertEqual(m["counts"]["with_route"], 3)
        # sans scan : écrans et tables de la base seulement, jamais d'exception
        m2 = J.functional_map(steps, None)
        self.assertEqual(m2["counts"]["with_route"], 0)
        self.assertIn("clients", m2["tables"])


def _fake_dba(url, json=None, timeout=None):
    class R:
        status_code = 200
        def json(self):
            return {"columns": ["event_time", "user_host", "thread_id", "argument"],
                    "rows": [[q["at"], "gestion[gestion] @ localhost []", 7, q["sql"]] for q in QUERIES]}
    _fake_dba.seen = (url, json)
    return R()


class RouteTests(unittest.TestCase):
    def setUp(self):
        retro_app.app.config["TESTING"] = True
        self.c = retro_app.app.test_client()

    def _zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("index.php", "<?php\n$f3->route('GET /clients', 'ClientController->index');\n$f3->route('GET /client/@id', 'ClientController->show');\n$f3->route('POST /client/@id/save', 'ClientController->save');\n")
            zf.writestr("app/controllers/client.php", "<?php\nclass ClientController {\n function show() { $m = new DB\\SQL\\Mapper($db, 'clients'); $db->exec('SELECT * FROM clients c JOIN contrats k ON k.client_id = c.id'); }\n}\n")
        buf.seek(0)
        return buf

    def test_full_chain(self):
        # scan conservé pour l'application
        r = self.c.post("/scan?app=gestion", data={"file": (self._zip(), "code.zip")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.data)
        d = r.get_json()
        self.assertEqual(d["saved_for_app"], "gestion")
        self.assertEqual(d["classes"], {"ClientController": "app/controllers/client.php"})
        self.assertEqual(d["file_tables"], {"app/controllers/client.php": ["clients"]})
        r = self.c.post("/apps", json={"label": "gestion", "base_url": "https://gestion.exemple.fr", "dba_connection_id": 3, "dba_database": "gestion"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["has_scan"])
        # parcours créé par le relais (jeton), événements en deux lots, rejeu idempotent
        r = self.c.post("/journeys", json={"app": "gestion", "name": "fiche client", "tester": "freg"}, headers={"X-Relay-Token": "relais-secret"})
        self.assertEqual(r.status_code, 201)
        jid = r.get_json()["id"]
        self.assertEqual(self.c.post(f"/journeys/{jid}/events", json={"events": EVENTS[:5]}).status_code, 401)
        r = self.c.post(f"/journeys/{jid}/events", json={"events": EVENTS[:5]}, headers={"X-Relay-Token": "relais-secret"})
        self.assertEqual(r.get_json()["added"], 5)
        r = self.c.post(f"/journeys/{jid}/events", json={"events": EVENTS[3:]}, headers={"X-Relay-Token": "relais-secret"})
        self.assertEqual((r.get_json()["added"], r.get_json()["events_count"]), (8, 13))
        # collecte du journal général via dba-api (faux)
        with mock.patch.object(retro_app._requests, "post", side_effect=_fake_dba):
            r = self.c.post(f"/journeys/{jid}/queries/collect", json={})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.get_json()["collected"], r.get_json()["attributed"]), (7, 5))
        self.assertIn("mysql.general_log", _fake_dba.seen[1]["sql"])
        self.assertIn("/connections/3/sql", _fake_dba.seen[0])
        # fin, annotation, détail
        r = self.c.post(f"/journeys/{jid}/end", json={"notes": "ok"}, headers={"X-Relay-Token": "relais-secret"})
        self.assertEqual(r.get_json()["status"], "done")
        self.assertEqual(self.c.post(f"/journeys/{jid}/events", json={"events": EVENTS[:1]}, headers={"X-Relay-Token": "relais-secret"}).status_code, 409)
        self.c.post(f"/journeys/{jid}/annotate", json={"step": 2, "text": "écran clé"})
        d = self.c.get(f"/journeys/{jid}").get_json()
        self.assertEqual(len(d["steps"]), 5)
        self.assertEqual(d["steps"][1]["annotation"], "écran clé")
        self.assertEqual(d["steps"][2]["db_tables"]["clients"]["writes"], 1)
        c = [s for s in d["map"]["screens"] if s["screen"] == "/client/{n}"][0]
        self.assertEqual(c["route"], "/client/@id")
        self.assertIn("contrats", c["code_tables"])
        # carte agrégée de l'application et listes
        m = self.c.get("/apps/gestion/map").get_json()
        self.assertEqual(m["journeys"], 1); self.assertGreaterEqual(m["counts"]["tables"], 3)
        self.assertEqual(self.c.get("/journeys?app=gestion").get_json()["journeys"][0]["queries_count"], 7)
        self.assertEqual(self.c.get("/apps").get_json()["apps"][0]["journeys"], 1)
        self.assertEqual(self.c.delete(f"/journeys/{jid}").get_json()["deleted"], True)

    def test_mapper_pattern_with_property(self):
        import php_sql_scanner as scanner
        src = "<?php class C { function show($f3, $p) { $m = new DB\\SQL\\Mapper($this->db, 'clients'); $x = new \\DB\\SQL\\Mapper($f3->get('DB'), 'produits'); } }"
        self.assertEqual(sorted(scanner.scan_php_source(src)["mapper_tables"]), ["clients", "produits"])

    def test_collect_without_connection(self):
        j = self.c.post("/journeys", json={"app": "sansbase"}).get_json()
        r = self.c.post(f"/journeys/{j['id']}/queries/collect", json={})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
