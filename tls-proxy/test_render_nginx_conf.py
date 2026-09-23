"""Tests du rendu nginx (#574 : relais HTTPS sur port dédié)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_nginx_conf as r  # noqa: E402


class Relays(unittest.TestCase):
    def test_relays(self):
        env = {"GATEWAY_PORT": "6443", "HOST_IP": "192.0.2.1", "RELAY1_PORT": "6486", "RELAY1_TARGET": "ssh-tunnels-api:18006", "RELAY1_LABEL": "hyperviseur du site"}
        conf, summary = r.build_config(env)
        self.assertEqual(conf.count("listen 6486 ssl"), 1)
        self.assertIn("https://ssh-tunnels-api:18006", conf); self.assertIn("Upgrade $http_upgrade", conf)
        self.assertTrue(any("6486" in l for l in summary))
        self.assertEqual(r.relays_from_env({"RELAY1_PORT": "6486"}), [])  # cible absente = pas de relais
        for bad in ({"RELAY1_PORT": "80", "RELAY1_TARGET": "x:1"}, {"RELAY1_PORT": "6486", "RELAY1_TARGET": "x"}, {"RELAY1_PORT": "6486", "RELAY1_TARGET": "x:1; rm"}):
            with self.assertRaises(ValueError):
                r.relays_from_env(bad)


if __name__ == "__main__":
    unittest.main()
