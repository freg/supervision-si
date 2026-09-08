# -*- coding: utf-8 -*-
"""Tests du parseur d'exposition (livraison #455)."""
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("rx", os.path.join(os.path.dirname(os.path.abspath(__file__)), "render-exposure.py"))
rx = importlib.util.module_from_spec(spec); spec.loader.exec_module(rx)

COMPOSE = """services:
  api:
    # Service central.
    build: .
    ports:
      - "${API_PORT:-6103}:5000"
    environment:
      - X=1
  rsyslog-listener:
    ports:
      - "${RSYSLOG_LISTENER_PORT:-5514}:5514/udp"
      - "127.0.0.1:${CTRL:-6452}:6452"
  network-agent-api:
    # Sonde en pile réseau hôte.
    network_mode: host
    environment:
      - Y=2
  hub:
    build: .
volumes:
  api_data:
"""

class T(unittest.TestCase):
    def test_resolve_and_port(self):
        self.assertEqual(rx.resolve("${A:-6103}:5000"), "6103:5000")
        self.assertEqual(rx.resolve("${A:-6103}:5000", {"A": "7000"}), "7000:5000")
        p = rx.parse_port("127.0.0.1:6452:6452")
        self.assertEqual((p["bind"], p["host_port"], p["container_port"], p["loopback_only"]), ("127.0.0.1", "6452", "6452", True))
        p = rx.parse_port("5514:514/udp")
        self.assertEqual((p["proto"], p["host_port"], p["container_port"], p["loopback_only"]), ("udp", "5514", "514", False))

    def test_parse_compose(self):
        s = rx.parse_compose(COMPOSE)
        self.assertEqual(sorted(s), ["api", "hub", "network-agent-api", "rsyslog-listener"])
        self.assertEqual(s["api"]["ports"][0]["host_port"], "6103")
        self.assertEqual(s["api"]["comment"], "Service central.")
        self.assertEqual(len(s["rsyslog-listener"]["ports"]), 2)
        self.assertEqual(s["rsyslog-listener"]["ports"][1]["loopback_only"], True)
        self.assertEqual(s["network-agent-api"]["network_mode"], "host")
        self.assertEqual(s["hub"]["ports"], [])
        self.assertNotIn("api_data", s)

    def test_build(self):
        s = rx.parse_compose(COMPOSE)
        out = rx.build_exposure(s, [("API_PORT", "api", 5000, "/api/x/", "api"), ("NA", "__HOST_IP__", 15000, "/api/na/", "api-static")], "6443")
        self.assertEqual(out["counts"], {"gateway_routes": 2, "direct_ports": 3, "direct_public": 2, "host_network": 1})
        self.assertEqual(out["gateway"][1]["service"], "hôte (IP réelle)")
        self.assertEqual(out["direct_ports"][-1]["loopback_only"], True)   # boucle locale en dernier
        self.assertEqual(out["host_network"][0]["service"], "network-agent-api")

if __name__ == "__main__":
    unittest.main()
