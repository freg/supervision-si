# -*- coding: utf-8 -*-
"""#661 : socle commun -- découpage passerelle / principal / dépendances non démarrées, extension +tuile, commandes, reprise."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import socle

INFO = {"tls-proxy": {"depends": ["keycloak"]}, "keycloak": {"depends": []}, "hub": {"depends": []}, "services-api": {"depends": ["si-agent-api"]},
        "si-agent-api": {"depends": ["memcached"]}, "memcached": {"depends": []}, "sniffer": {"depends": [], "host_network": True}}
ORIGIN = {"tls-proxy": "gateway/docker-compose.yml", "keycloak": "gateway/docker-compose.yml"}
ORIGIN.update({k: "docker-compose.yml" for k in INFO if k not in ORIGIN})

class Socle(unittest.TestCase):
    def test_split_and_commands(self):
        g, m, skipped = socle.split(["tls-proxy", "services-api", "hub", "memcached"], INFO, ORIGIN)
        self.assertEqual(g, ["tls-proxy", "keycloak"]); self.assertEqual(m, ["services-api", "hub", "memcached"]); self.assertEqual(skipped, ["si-agent-api"])
        cmds = socle.commands(g, m, build=True)
        self.assertEqual(cmds[0], ["./gateway/scripts/run.sh", "up", "-d", "--build", "tls-proxy", "keycloak"])
        self.assertEqual(cmds[1], ["./scripts/run.sh", "up", "-d", "--no-deps", "--build", "services-api", "hub", "memcached"])
        with self.assertRaises(RuntimeError):
            socle.split(["inconnu"], INFO, ORIGIN)

    def test_extend(self):
        self.assertEqual(socle.extend(["hub"], ["si-agent-api", "sniffer"], INFO), ["hub", "si-agent-api", "memcached"])   # host_network ignoré, dépendances suivies

    def test_check_files(self):
        self.assertEqual(socle.check_files("/x", exists=lambda p: True), [])
        miss = socle.check_files("/x", exists=lambda p: p.endswith(".env"))
        self.assertEqual([m["file"] for m in miss], ["pki/ca/ca.crt", "pki/ca/ca.key"]); self.assertIn("si-proxy", miss[1]["hint"])

    def test_real_compose(self):
        """Sur le vrai docker-compose : le socle se découpe sans service inconnu et tls-proxy entraîne keycloak."""
        import cohorts as C
        services, origin = C.load_services(); info = C.analyse(services)
        g, m, _ = socle.split(socle.SOCLE, info, origin)
        self.assertIn("keycloak", g); self.assertIn("hub", m); self.assertNotIn("si-agent-api", m)

if __name__ == "__main__":
    unittest.main()
