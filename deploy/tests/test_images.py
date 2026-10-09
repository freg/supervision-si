# -*- coding: utf-8 -*-
"""#738 : images construites par le nœud constructeur, tirées ailleurs (override d'images, apply sans construction)."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import images  # noqa: E402
import node_agent as na  # noqa: E402

COMPOSE = {"services": {"hub": {"build": {"context": "."}}, "tickets-api": {"build": "."}, "memcached": {"image": "memcached:1.6"}}}


class Images(unittest.TestCase):
    def test_override_et_registre(self):
        ov = images.image_override(COMPOSE, "10.99.0.3:5005", "abc123")
        self.assertEqual(ov, {"services": {"hub": {"image": "10.99.0.3:5005/supervision-si/hub:abc123"},
                                           "tickets-api": {"image": "10.99.0.3:5005/supervision-si/tickets-api:abc123"}}})
        self.assertEqual(images.registry({"SI_REGISTRY": "10.99.0.3:5005/"}), "10.99.0.3:5005")
        self.assertEqual(images.registry({}), "")
        with self.assertRaises(ValueError):
            images.registry({"SI_REGISTRY": "x; rm -rf /"})

    def _agent(self, nodes, env):
        d = tempfile.mkdtemp(); p = os.path.join(d, "nodes.json"); json.dump(nodes, open(p, "w"))
        saved = (na.NODES, na.make_plan, na.run, na.load_env, na.compose_running)
        self.addCleanup(lambda: (setattr(na, "NODES", saved[0]), setattr(na, "make_plan", saved[1]), setattr(na, "run", saved[2]),
                                 setattr(na, "load_env", saved[3]), setattr(na, "compose_running", saved[4])))
        calls = []
        na.NODES = p
        na.make_plan = lambda me: {"services": ["hub", "tickets-api"], "relays": [], "gateway": [], "host_network": []}
        na.run = lambda cmd, check=True, capture=False, **k: calls.append(cmd) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        na.load_env = lambda *a: env
        na.compose_running = lambda: ["hub", "tickets-api"]
        return calls

    def test_apply_tire_au_lieu_de_construire(self):
        calls = self._agent({"nodes": [{"name": "super"}, {"name": "travail", "builder": True}]}, {"SI_REGISTRY": "10.99.0.3:5005"})
        os.environ.pop("SI_REGISTRY", None)
        plan = na.apply("super", build=True)
        self.assertTrue(calls[0][-3:] == ["pull", "hub", "tickets-api"] and calls[0][1].endswith("images.py"))
        self.assertIn("--no-build", calls[1]); self.assertNotIn("--build", calls[1])
        self.assertIn("images tirées du registre", plan["steps"])

    def test_constructeur_construit_et_pousse(self):
        calls = self._agent({"nodes": [{"name": "travail", "builder": True}]}, {"SI_REGISTRY": "10.99.0.3:5005"})
        na.apply("travail", build=True)
        self.assertEqual(calls[0][-1], "build"); self.assertIn("--no-build", calls[1])

    def test_sans_registre_inchange(self):
        calls = self._agent({"nodes": [{"name": "super"}]}, {})
        na.apply("super", build=True)
        self.assertIn("--build", calls[0]); self.assertEqual(len(calls), 1)

    def test_build_images(self):
        self._agent({"nodes": [{"name": "super", "wg_address": "10.99.0.1"}, {"name": "travail", "wg_address": "10.99.0.3", "builder": True}]}, {"SI_REGISTRY": "r:5005"})
        saved = na.node_name; self.addCleanup(setattr, na, "node_name", saved); na.node_name = lambda: "super"
        sent = []
        r = na.build_images(call=lambda n, path, body, timeout=0: sent.append((n["name"], path, body)) or {"ok": 1})
        self.assertEqual(sent, [("travail", "/update", {"build": True})]); self.assertEqual(r["builder"], "travail")


if __name__ == "__main__":
    unittest.main()
