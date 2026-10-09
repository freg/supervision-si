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
