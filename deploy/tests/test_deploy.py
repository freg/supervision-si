# -*- coding: utf-8 -*-
"""Tests du déploiement réparti (#513) : override par nœud, ports VPN, relais,
données d'une cohorte, garde-fous d'import. Exécution : python3 -m unittest deploy/tests/test_deploy.py"""
import io
import json
import os
import sys
import tarfile
import time
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cohorts as co  # noqa: E402
import node_agent as na  # noqa: E402

SERVICES = {
    "memcached": {"image": "memcached:1.6"},
    "credentials-api": {"build": {"context": "."}, "environment": ["MEMCACHED_HOST=memcached", "MEMCACHED_PORT=11211"], "volumes": ["./credentials/data:/data"]},
    "tickets-postgres": {"image": "postgres:16", "volumes": ["tickets_pg_data:/var/lib/postgresql/data"]},
    "tickets-api": {"build": {"context": "."}, "environment": {"DATABASE_URL": "postgresql://u:p@tickets-postgres:5432/t", "CREDENTIALS_API_URL": "http://credentials-api:5000"}, "depends_on": ["tickets-postgres"]},
    "network-agent-api": {"build": {"context": "."}, "network_mode": "host"},
    "keycloak": {"image": "quay.io/keycloak/keycloak:24", "volumes": ["keycloak_data:/opt/keycloak/data"]},
    "tls-proxy": {"build": {"context": "."}, "depends_on": ["keycloak"], "ports": ["6443:6443"]},
}
ORIGIN = {k: ("gateway/docker-compose.yml" if k in ("keycloak", "tls-proxy") else "docker-compose.yml") for k in SERVICES}
COHORTS = {"cohorts": [
    {"name": "core", "manager": True, "services": ["memcached", "credentials-api", "keycloak", "tls-proxy"]},
    {"name": "tickets", "services": ["tickets-postgres", "tickets-api"]},
    {"name": "reseau", "services": ["network-agent-api"]},
], "edge_services": ["tls-proxy"]}
NODES = {"nodes": [
    {"name": "super", "role": "manager", "wg_address": "10.99.0.1", "cohorts": ["core"], "edge": True},
    {"name": "vm-donnees", "wg_address": "10.99.0.2", "cohorts": ["tickets", "reseau"]},
    {"name": "vm-ovh", "wg_address": "10.99.0.4", "cohorts": [], "edge": True},
]}


class Analyse(unittest.TestCase):
    def setUp(self):
        co.proxy_table = lambda: [("tickets-api", 5000), ("credentials-api", 5000)]
        self.info = co.analyse(SERVICES)
        self.where, _ = co.assign(COHORTS, SERVICES)

    def test_dependances_url_host_et_depends_on(self):
        self.assertEqual(self.info["tickets-api"]["depends"], ["credentials-api", "tickets-postgres"])
        self.assertEqual(self.info["credentials-api"]["depends"], ["memcached"])

    def test_ports_internes(self):
        self.assertEqual(self.info["tickets-postgres"]["ports"], [5432])   # URL postgresql://
        self.assertEqual(self.info["memcached"]["ports"], [11211])         # image + *_PORT
        self.assertEqual(self.info["keycloak"]["ports"], [8080])           # image
        self.assertEqual(self.info["credentials-api"]["ports"], [5000])    # table tls-proxy

    def test_port_vpn_stable(self):
        p1 = co.vpn_port(self.info, "tickets-api", 5000)
        self.assertEqual(p1, co.vpn_port(self.info, "tickets-api", 5000))
        self.assertNotEqual(p1, co.vpn_port(self.info, "tickets-postgres", 5432))
        self.assertTrue(20000 <= p1 < 21000)


class Override(unittest.TestCase):
    def setUp(self):
        co.proxy_table = lambda: [("tickets-api", 5000), ("credentials-api", 5000)]
        self.info = co.analyse(SERVICES)
        self.where, _ = co.assign(COHORTS, SERVICES)

    def ov(self, node):
        return co.override(COHORTS, SERVICES, self.info, self.where, ORIGIN, NODES, node)

    def test_manager_publie_et_relaie_les_backends_distants(self):
        out, gw, plan = self.ov("super")
        self.assertEqual(plan["services"], ["credentials-api", "memcached"])
        self.assertEqual(plan["gateway"], ["keycloak", "tls-proxy"])
        self.assertEqual(out["services"]["credentials-api"]["ports"], ["10.99.0.1:%d:5000" % co.vpn_port(self.info, "credentials-api", 5000)])
        self.assertIn("relay-tickets-api", plan["relays"])       # backend de tls-proxy sur vm-donnees
        self.assertNotIn("relay-keycloak", plan["relays"])       # local
        self.assertEqual(gw["services"]["keycloak"]["ports"], ["10.99.0.1:%d:8080" % co.vpn_port(self.info, "keycloak", 8080)])
        r = out["services"]["relay-tickets-api"]
        self.assertEqual(r["networks"]["default"]["aliases"], ["tickets-api"])
        self.assertIn("TCP:10.99.0.2:%d" % co.vpn_port(self.info, "tickets-api", 5000), r["command"][0])
        self.assertEqual(plan["missing"], [])

    def test_worker_relaie_ses_dependances_et_isole_le_reseau_hote(self):
        out, gw, plan = self.ov("vm-donnees")
        self.assertEqual(plan["services"], ["tickets-api", "tickets-postgres"])
        self.assertEqual(plan["host_network"], ["network-agent-api"])
        self.assertEqual(sorted(plan["relays"]), ["relay-credentials-api"])
        self.assertIn("TCP:10.99.0.1:", out["services"]["relay-credentials-api"]["command"][0])
        self.assertEqual(gw, {"services": {}})

    def test_bordure_sans_core_relaie_keycloak(self):
        out, gw, plan = self.ov("vm-ovh")
        self.assertEqual(plan["gateway"], ["tls-proxy"])
        self.assertIn("relay-keycloak", plan["relays"])
        self.assertIn("relay-credentials-api", plan["relays"])

    def test_cohorte_non_affectee_signalee(self):
        nodes = json.loads(json.dumps(NODES))
        nodes["nodes"][1]["cohorts"] = ["reseau"]
        _, _, plan = co.override(COHORTS, SERVICES, self.info, self.where, ORIGIN, nodes, "super")
        self.assertIn("tickets-api", plan["missing"])
        self.assertNotIn("relay-tickets-api", plan["relays"])

    def test_depot_reel_tout_service_affecte(self):
        # #689 : tout service du compose réel (pile principale + passerelle) est dans une cohorte, une seule fois
        try:
            services, _origin = co.load_services()
        except Exception as exc:  # noqa: BLE001 -- PyYAML absent
            self.skipTest("compose illisible ici : %s" % exc)
        _, problems = co.assign(co.load_cohorts(), services)
        self.assertEqual(problems, [])

    def test_noeud_inconnu(self):
        with self.assertRaises(SystemExit):
            self.ov("nulle-part")


class Donnees(unittest.TestCase):
    def test_cohort_data_sur_le_depot(self):
        binds, volumes = na.cohort_data("tickets")
        self.assertIn("supervision-si_tickets_pg_data", volumes)
        self.assertTrue(all(b.startswith(na.ROOT) and b != na.ROOT for b in binds))
        with self.assertRaises(RuntimeError):
            na.cohort_data("inconnue")

    def test_import_refuse_les_chemins_sortants(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w|gz") as tar:
            data = b"x"
            ti = tarfile.TarInfo("bind/../../etc/passwd"); ti.size = 1
            tar.addfile(ti, io.BytesIO(data))
        buf.seek(0)
        with self.assertRaises(RuntimeError):
            na.import_cohort("tickets", buf)

    def test_import_refuse_un_volume_inattendu(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w|gz") as tar:
            ti = tarfile.TarInfo("volume/autre_chose.tar"); ti.size = 1
            tar.addfile(ti, io.BytesIO(b"x"))
        buf.seek(0)
        with self.assertRaises(RuntimeError):
            na.import_cohort("tickets", buf)

    def test_load_env_non_sourcable(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as fh:
            fh.write("A=1\nLDAP_CLASSES=top organizationalPerson inetOrgPerson\nB=\"q\"\n# c\nbad line\n")
        env = na.load_env(fh.name)
        os.unlink(fh.name)
        self.assertEqual(env["LDAP_CLASSES"], "top organizationalPerson inetOrgPerson")
        self.assertEqual(env["B"], "q")
        self.assertNotIn("bad line", env)


class GitUpdate(unittest.TestCase):
    """#659 : mise à jour git d'un nœud -- refus si fichiers modifiés, enchaînement pull puis apply, résultat."""
    def test_git_update(self):
        calls = []
        def fake_run(cmd, check=True, capture=False, stdin=None, env=None):
            calls.append(cmd)
            out = {("git", "status"): "", ("git", "rev-parse"): "main" if "--abbrev-ref" in cmd else "abc1234", ("git", "pull"): "Updating abc1234..def5678\nFast-forward"}
            return type("R", (), {"returncode": 0, "stdout": out.get(tuple(cmd[:2]), ""), "stderr": ""})()
        old_run, old_apply = na.run, na.apply
        na.run, na.apply = fake_run, lambda me, build: {"steps": ["up: 3 services"]}
        try:
            r = na.git_update("n1", True)
            self.assertEqual(r["branch"], "main"); self.assertEqual(r["steps"], ["up: 3 services"]); self.assertIn("Fast-forward", r["pull"])
            self.assertEqual([c[:2] for c in calls][:4], [["git", "checkout"], ["git", "status"], ["git", "rev-parse"], ["git", "rev-parse"]]); self.assertIn(["git", "pull", "--ff-only", "origin", "main"], calls)
            na.run = lambda cmd, **kw: type("R", (), {"returncode": 0, "stdout": " M deploy/x.py\n", "stderr": ""})()
            with self.assertRaises(RuntimeError) as cm:
                na.git_update("n1")
            self.assertIn("deploy/x.py", str(cm.exception))
        finally:
            na.run, na.apply = old_run, old_apply


if __name__ == "__main__":
    unittest.main()


class Mirror(unittest.TestCase):
    """#663 : miroir froid -- archives valides, restauration refusée si des services tournent, chaîne à pousser, âge."""
    def test_node_agent_mirror(self):
        import tempfile
        self.assertTrue(na.ARCHIVE_RE.match("si-full-20261003-1200.tar.gz.enc")); self.assertTrue(na.ARCHIVE_RE.match("si-full-20261003-1200.manifest.json"))
        self.assertFalse(na.ARCHIVE_RE.match("../etc/passwd")); self.assertFalse(na.ARCHIVE_RE.match("x.sh"))
        d = tempfile.mkdtemp()
        open(os.path.join(d, "a.tar.gz.enc"), "wb").write(b"123"); open(os.path.join(d, "a.manifest.json"), "w").write("{}"); open(os.path.join(d, "junk.txt"), "w").write("x")
        self.assertEqual([a["name"] for a in na.mirror_archives(d)], ["a.manifest.json", "a.tar.gz.enc"])
        old_running = na.compose_running
        na.compose_running = lambda: ["hub"]
        try:
            with self.assertRaises(RuntimeError) as cm:
                na.mirror_restore("a.tar.gz.enc")
            self.assertIn("tournent", str(cm.exception))
        finally:
            na.compose_running = old_running
        with self.assertRaises(RuntimeError):
            na.mirror_restore("a.manifest.json")
        with self.assertRaises(RuntimeError):
            na.mirror_takeover("pas-une-ip")

    def test_mirror_primary(self):
        import tempfile, mirror
        d = tempfile.mkdtemp()
        full, inc = os.path.join(d, "full.tar.gz.enc"), os.path.join(d, "inc.tar.gz.enc")
        open(full, "wb").write(b"1234"); open(inc, "wb").write(b"12")
        remote = [{"name": "full.tar.gz.enc", "size": 4}, {"name": "inc.tar.gz.enc", "size": 1}]
        self.assertEqual(mirror.to_push([full, inc], remote), [inc])          # taille différente = à renvoyer
        self.assertEqual(mirror.to_push([full], []), [full])
        self.assertEqual(mirror.age_text(None), "jamais")
        now = time.mktime(time.strptime("2026-10-03T12:00:00", "%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(mirror.age_text("2026-10-03T11:30:00", now), "30 min"); self.assertEqual(mirror.age_text("2026-10-03T09:00:00", now), "3.0 h")
        with self.assertRaises(RuntimeError):
            mirror.load_config(os.path.join(d, "absent.json"))
