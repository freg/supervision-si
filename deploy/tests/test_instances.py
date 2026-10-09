# -*- coding: utf-8 -*-
"""Instances clonées (#731) : clonage des services (noms, données, adresses, chemins, base forcée), registre,
cohortes et affectation au nœud, override du nœud cible (définition complète) et relais ailleurs, routes tls-proxy."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cohorts as co  # noqa: E402
import instances as ins  # noqa: E402

SERVICES = {
    "memcached": {"image": "memcached:1.6"},
    "keycloak": {"image": "quay.io/keycloak/keycloak:24"},
    "tls-proxy": {"build": {"context": "."}, "ports": ["6443:6443"]},
    "tickets-api": {"build": {"context": ".", "dockerfile": "tickets/api/Dockerfile"}, "depends_on": ["memcached"], "container_name": "tickets-api",
                    "environment": ["MEMCACHED_HOST=memcached", "DB_BACKEND=${TICKETS_BACKEND:-sqlite}", "PGHOST=tickets-postgres",
                                    "GOOGLE_OAUTH_REDIRECT_URI=https://h:6443/api/tickets/oauth/google/callback", "KEYCLOAK_INTERNAL_URL=http://keycloak:8080/auth"],
                    "volumes": ["${TICKETS_DATA_DIR:-./tickets/data-generator}:/data"]},
    "tickets-portal": {"build": {"context": "."}, "depends_on": ["tickets-api"], "ports": ["5173:5173"],
                       "environment": {"VITE_TICKETS_API_BASE_URL": "https://h:6443/api/tickets", "VITE_GED_API_BASE_URL": "https://h:6443/api/ged",
                                       "X": "http://tickets-api:5000/x"}},
}
REG = {"instances": [{"name": "formation", "app": "tickets", "node": "worker", "title": "Formation"}]}


def env(d):
    return dict(str(e).partition("=")[::2] for e in d["environment"])


class Clone(unittest.TestCase):
    def test_clone_tickets(self):
        c = ins.clone_app(SERVICES, "tickets", "formation")
        self.assertEqual(sorted(c), ["tickets-api-formation", "tickets-portal-formation"])
        api, portal = c["tickets-api-formation"], c["tickets-portal-formation"]
        self.assertNotIn("container_name", api); self.assertNotIn("ports", portal)
        self.assertEqual(api["volumes"], ["./instances/formation/tickets-api:/data"])
        e = env(api)
        self.assertEqual((e["DB_BACKEND"], e["TICKETS_DB_PATH"], e["SI_INSTANCE"]), ("sqlite", "/data/tickets.db", "formation"))
        self.assertEqual(e["GOOGLE_OAUTH_REDIRECT_URI"], "https://h:6443/api/tickets-formation/oauth/google/callback")
        self.assertEqual(e["KEYCLOAK_INTERNAL_URL"], "http://keycloak:8080/auth")
        p = env(portal)
        self.assertEqual(p["VITE_TICKETS_API_BASE_URL"], "https://h:6443/api/tickets-formation")
        self.assertEqual(p["VITE_GED_API_BASE_URL"], "https://h:6443/api/ged")                 # autre application : intacte
        self.assertEqual((p["X"], p["VITE_BASE"]), ("http://tickets-api-formation:5000/x", "/tickets-formation/"))
        self.assertEqual(portal["depends_on"], ["tickets-api-formation"]); self.assertEqual(portal["labels"]["si.instance"], "formation")
        self.assertEqual(SERVICES["tickets-api"]["container_name"], "tickets-api")               # source non modifiée

    def test_check(self):
        nodes = {"nodes": [{"name": "worker"}]}
        self.assertEqual(ins.check(REG, SERVICES, nodes, ["/tickets/"]), [])
        bad = {"instances": [{"name": "Api", "app": "tickets"}, {"name": "x2", "app": "crm"}, {"name": "aa", "app": "tickets", "node": "nope"},
                             {"name": "aa", "app": "tickets", "node": "worker"}]}
        p = ins.check(bad, SERVICES, nodes, ["/tickets-aa/"])
        self.assertTrue(any("invalide" in x for x in p)); self.assertTrue(any("inconnue" in x for x in p))
        self.assertTrue(any("absent de deploy/nodes.json" in x for x in p)); self.assertTrue(any("en double" in x for x in p))
        self.assertTrue(any("route /tickets-aa/ déjà utilisée" in x for x in p))
        self.assertTrue(any("invalide" in x for x in ins.check({"instances": [{"name": "api", "app": "tickets"}]})))   # mot réservé

    def test_routes_plan_cohorts(self):
        self.assertEqual(ins.routes(REG), [("INSTANCE_FORMATION", "tickets-api-formation", 5000, "/api/tickets-formation/", "api"),
                                           ("INSTANCE_FORMATION", "tickets-portal-formation", 5173, "/tickets-formation/", "spa")])
        p = ins.plan(REG["instances"][0])
        self.assertEqual((p["front"], p["config_export"], p["config_import"]),
                         ("/tickets-formation/", "http://tickets-api:5000/export?scope=config", "http://tickets-api-formation:5000/import?mode=merge"))
        self.assertEqual(p["data"], ["instances/formation/tickets-api"])
        nodes = ins.attach({"nodes": [{"name": "worker", "cohorts": ["tickets", "inst-ancienne"]}, {"name": "super", "cohorts": ["core"]}]}, REG)
        self.assertEqual(nodes["nodes"][0]["cohorts"], ["tickets", "inst-formation"]); self.assertEqual(nodes["nodes"][1]["cohorts"], ["core"])


class Override(unittest.TestCase):
    def setUp(self):
        self.services = dict(SERVICES); self.origin = {k: ("gateway/docker-compose.yml" if k in ("keycloak", "tls-proxy") else "docker-compose.yml") for k in SERVICES}
        clones, corigin = ins.instance_services(REG, SERVICES)
        self.services.update(clones); self.origin.update(corigin)
        cohorts = {"cohorts": [{"name": "core", "services": ["memcached", "keycloak", "tls-proxy"]}, {"name": "tickets", "services": ["tickets-api", "tickets-portal"]}]
                   + ins.instance_cohorts(REG)[0]}
        self.cohorts = cohorts
        self.where, probs = co.assign(cohorts, self.services); self.assertEqual(probs, [])
        self.info = co.analyse(self.services)
        self.nodes = ins.attach({"nodes": [{"name": "super", "wg_address": "10.99.0.1", "cohorts": ["core", "tickets"], "edge": True},
                                           {"name": "worker", "wg_address": "10.99.0.2", "cohorts": []}]}, REG)

    def test_noeud_cible_definition_complete(self):
        out, _, plan = co.override(self.cohorts, self.services, self.info, self.where, self.origin, self.nodes, "worker")
        api = out["services"]["tickets-api-formation"]
        self.assertEqual(api["volumes"], ["./instances/formation/tickets-api:/data"]); self.assertTrue(api["build"])
        self.assertTrue(api["ports"][0].startswith("10.99.0.2:")); self.assertEqual(plan["instances"], ["formation"])
        self.assertIn("relay-memcached", out["services"])                               # dépendance restée sur super

    def test_bordure_relaie_l_instance(self):
        orig = ins.load_registry; ins.load_registry = lambda *a: REG                      # routes tls-proxy lues dans le registre
        self.addCleanup(setattr, ins, "load_registry", orig)
        self.info = co.analyse(self.services)
        out, _, plan = co.override(self.cohorts, self.services, self.info, self.where, self.origin, self.nodes, "super")
        self.assertNotIn("tickets-api-formation", [s for s in out["services"] if not s.startswith("relay-")])
        self.assertIn("relay-tickets-portal-formation", out["services"])                # route tls-proxy -> relais vers worker
        self.assertIn("relay-tickets-api-formation", out["services"])
        self.assertEqual(plan["instances"], [])

    def test_render_nginx(self):
        sys.path.insert(0, os.path.join(co.ROOT, "tls-proxy"))
        import render_nginx_conf as r
        r.instance_routes = lambda: ins.routes(REG)
        conf, summary = r.build_config({})
        self.assertIn("/tickets-formation/", conf); self.assertIn("tickets-api-formation", conf)


if __name__ == "__main__":
    unittest.main()


class Tranche3(unittest.TestCase):
    """#732 : source de configuration relayée, script de clonage de la configuration, redirections Keycloak,
    création sur le nœud cible et orchestration depuis le manager (appels simulés)."""

    def test_source_relayee_sur_le_noeud_cible(self):
        o = Override(); o.setUp()
        e = env(o.services["tickets-api-formation"]); self.assertEqual(e["SI_INSTANCE_SOURCE_URL"], "http://tickets-api:5000")
        out, _, plan = co.override(o.cohorts, o.services, o.info, o.where, o.origin, o.nodes, "worker")
        self.assertIn("relay-tickets-api", out["services"])                                  # la source reste sur super

    def test_script_de_clonage(self):
        import json, subprocess, threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        got = {}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _send(self, obj):
                b = json.dumps(obj).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            def do_GET(self):
                self._send({"status": "ok"} if self.path == "/health" else {"types": [{"id": 1}], "path": self.path})
            def do_POST(self):
                got["path"] = self.path; got["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self._send({"imported": {"types": 1}})
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown)
        script = ins.config_clone_script("tickets").replace("127.0.0.1:5000", "127.0.0.1:%d" % port)
        r = subprocess.run([sys.executable, "-c", script], env=dict(os.environ, SI_INSTANCE_SOURCE_URL="http://127.0.0.1:%d" % port), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(res["import"], {"imported": {"types": 1}}); self.assertEqual(got["path"], "/import?mode=merge")
        self.assertEqual(got["body"]["path"], "/export?scope=config")
        self.assertIsNone(ins.config_clone_script("ged"))

    def test_keycloak(self):
        sys.path.insert(0, os.path.join(co.ROOT, "keycloak"))
        import render
        red = ins.keycloak_redirects(REG, "https://hub.example:6443/")
        self.assertEqual(red, {"tickets-portal": ["https://hub.example:6443/tickets-formation/"]})
        realm = {"clients": [{"clientId": "tickets-portal", "redirectUris": ["https://hub.example:6443/tickets/*"], "webOrigins": ["https://hub.example:6443"],
                              "attributes": {"post.logout.redirect.uris": "https://hub.example:6443/tickets/*"}}, {"clientId": "hub"}]}
        self.assertEqual(render.add_instance_redirects(realm, red), 2)
        self.assertEqual(render.add_instance_redirects(realm, red), 0)                      # idempotent
        c = realm["clients"][0]
        self.assertIn("https://hub.example:6443/tickets-formation/*", c["redirectUris"]); self.assertIn("https://hub.example:6443/tickets-formation", c["redirectUris"])
        self.assertEqual(c["attributes"]["post.logout.redirect.uris"], "https://hub.example:6443/tickets/*##https://hub.example:6443/tickets-formation/*")
        self.assertNotIn("redirectUris", realm["clients"][1])

    def test_creation_et_orchestration(self):
        import json, tempfile
        import node_agent as na
        d = tempfile.mkdtemp(); reg_path = os.path.join(d, "instances.json"); nodes_path = os.path.join(d, "nodes.json")
        json.dump({"nodes": [{"name": "super", "wg_address": "10.99.0.1", "cohorts": ["core"], "edge": True}, {"name": "worker", "wg_address": "10.99.0.2", "cohorts": []}]},
                  open(nodes_path, "w"))
        calls = []
        saved = (na.REGISTRY, na.NODES, na.apply, na.run, na.node_name)
        self.addCleanup(lambda: setattr(na, "REGISTRY", saved[0]) or setattr(na, "NODES", saved[1]) or setattr(na, "apply", saved[2]) or setattr(na, "run", saved[3]) or setattr(na, "node_name", saved[4]))
        na.REGISTRY, na.NODES = reg_path, nodes_path
        na.apply = lambda me, build=False: {"services": ["tickets-api-formation", "tickets-portal-formation"], "steps": ["up"], "gateway": []}

        class R:
            returncode = 0; stdout = '{"exported_bytes": 10, "import": {"ok": true}}\n'; stderr = ""
        na.run = lambda cmd, check=True, capture=False, **k: calls.append(cmd) or R()
        r = na.instance_create("worker", "formation", REG, build=False)
        self.assertEqual(r["config"]["import"], {"ok": True}); self.assertEqual(calls[-1][:4], ["./scripts/run.sh", "exec", "-T", "tickets-api-formation"])
        self.assertEqual(json.load(open(reg_path)), REG)
        with self.assertRaises(RuntimeError): na.instance_create("super", "formation")             # pas le bon nœud
        with self.assertRaises(RuntimeError): na.instance_create("worker", "inconnue")
        na.node_name = lambda: "super"; sent = []
        out = na.instance_deploy("formation", call=lambda n, path, body: sent.append((n["name"], path)) or {"ok": path})
        self.assertEqual(sent, [("worker", "/instance")]); self.assertIn("super", out["gateways"])      # passerelle = ce nœud (local)
        self.assertEqual(na.instance_stop("worker", "formation")["data_kept"], ["instances/formation/tickets-api"])
