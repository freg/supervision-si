# -*- coding: utf-8 -*-
"""Tests de la logique pure de full_backup.py (livraison #458)."""
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("fb", os.path.join(os.path.dirname(os.path.abspath(__file__)), "full_backup.py"))
fb = importlib.util.module_from_spec(spec); spec.loader.exec_module(fb)

COMPOSE = """services:
  api:
    volumes:
      - api_data:/data
      - ${PREFS_DATA_DIR:-./prefs-api/data}:/data/prefs
      - ./CHANGELOG.md:/data/CHANGELOG.md:ro
      - ./tls-proxy/generated:/etc/nginx/conf.d:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - ${PKI_DIR:-./pki}/ca/ca.crt:/ca/ca.crt:ro
      - ./pixel-grid/data-generator/schema.postgres.sql:/docker-entrypoint-initdb.d/schema.sql:ro
      - .:/project:ro
      - ${SSH_TUNNELS_KEYS_DIR:-./ssh-tunnels/keys}:/keys
volumes:
  api_data:
  pixel_grid_pg_data:
networks:
  default:
"""

class T(unittest.TestCase):
    def test_env_and_resolve(self):
        e = fb.parse_env("A=1\n# c\nB='x y'\nHOST_IP=10.0.0.5\n")
        self.assertEqual(e, {"A": "1", "B": "x y", "HOST_IP": "10.0.0.5"})
        self.assertEqual(fb.resolve("${X:-./d}/ca", {}), "./d/ca")
        self.assertEqual(fb.resolve("${X:-./d}/ca", {"X": "/srv/pki"}), "/srv/pki/ca")

    def test_mounts(self):
        m = fb.host_mounts_from_compose(COMPOSE, {}, "")
        paths = [x["path"] for x in m if x["kind"] != "volume"]
        self.assertEqual(paths, ["prefs-api/data", "pki/ca/ca.crt", "ssh-tunnels/keys"])
        self.assertEqual([x["kind"] for x in m if x["kind"] != "volume"], ["dir", "file", "dir"])
        self.assertIn({"path": "api_data", "kind": "volume", "raw": "api_data"}, m)
        m2 = fb.host_mounts_from_compose(COMPOSE, {"PKI_DIR": "/home/alice/pki"}, "gateway")
        self.assertIn("/home/alice/pki/ca/ca.crt", [x["path"] for x in m2])
        self.assertIn("gateway/prefs-api/data", [x["path"] for x in m2])

    def test_named_volumes_and_matching(self):
        self.assertEqual(fb.named_volumes_from_compose(COMPOSE), ["api_data", "pixel_grid_pg_data"])
        matched = fb.match_docker_volumes(["api_data", "keycloak_data"], ["supervision-si_api_data", "keycloak_data", "autre_truc", "x_api_data_old"])
        self.assertEqual(matched, [{"name": "supervision-si_api_data", "declared": "api_data"}, {"name": "keycloak_data", "declared": "keycloak_data"}])
        self.assertEqual(fb.project_prefix("supervision-si_api_data", "api_data"), "supervision-si")
        self.assertEqual(fb.project_prefix("keycloak_data", "keycloak_data"), "")

    def test_rewrite_env(self):
        env = ("HOST_IP=192.168.1.2\nSI_AGENT_PUBLIC_URL=https://192.168.1.2:6443/api/si-agent\n# commentaire 192.168.1.2\n"
               "SSH_TUNNELS_CRED_SALT=abc192.168.1.2\nSI_PROXY_HOST_TOKEN=old\nSI_PROXY_CLIENT_TOKEN=\nOTHER=x\n")
        out, ch = fb.rewrite_env_for_host(env, "192.168.1.2", "10.0.0.9")
        self.assertIn("HOST_IP=10.0.0.9", out)
        self.assertIn("SI_AGENT_PUBLIC_URL=https://10.0.0.9:6443/api/si-agent", out)
        self.assertIn("# commentaire 192.168.1.2", out)                 # commentaires intacts
        self.assertIn("SSH_TUNNELS_CRED_SALT=abc192.168.1.2", out)       # jamais un sel
        self.assertEqual(ch, ["HOST_IP", "SI_AGENT_PUBLIC_URL"])
        out2, ch2 = fb.rewrite_env_for_host(env, "192.168.1.2", "10.0.0.9", rotate_tokens=True)
        self.assertNotIn("SI_PROXY_HOST_TOKEN=old", out2)
        self.assertIn("SI_PROXY_CLIENT_TOKEN=\n", out2)                  # vide reste vide
        self.assertIn("SI_PROXY_HOST_TOKEN", ch2)
        self.assertNotIn("SSH_TUNNELS_CRED_SALT", ch2)

    def test_manifest_and_checklist(self):
        m = fb.build_manifest({"HOST_IP": "1.2.3.4", "GATEWAY_PORT": "6443"}, [], [], {"branch": "dev", "commit": "abc", "delivery": "458"})
        self.assertEqual((m["host_ip"], m["git"]["delivery"], m["format"]), ("1.2.3.4", "458", 1))
        c = fb.checklist(m, "5.6.7.8", ["HOST_IP"], True)
        self.assertIn("1.2.3.4 -> nouveau : 5.6.7.8", c)
        self.assertIn("RÉGÉNÉRÉ", c)
        self.assertIn("install-host.sh --relay 5.6.7.8:6450", c)

if __name__ == "__main__":
    unittest.main()
