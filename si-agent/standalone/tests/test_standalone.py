# -*- coding: utf-8 -*-
"""Tests du mode autonome (#517) : templates nginx rendus sans variable
oubliée, régimes d'authentification (agents sans auth basique, humains
avec), compose lisible, run.sh cohérent. python3 -m unittest si-agent/standalone/tests/test_standalone.py"""
import os
import re
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SA = os.path.dirname(HERE)


def render(path, env):
    s = open(path, encoding="utf-8").read()
    for k, v in env.items():
        s = s.replace("${%s}" % k, v)
    return s


def blocks(conf):
    """[(directive location, corps)] -- découpage grossier suffisant ici."""
    return re.findall(r"location\s+([^{]+)\{([^}]*)\}", conf)


class Front(unittest.TestCase):
    def setUp(self):
        self.conf = render(os.path.join(SA, "front.conf.template"), {"SI_STANDALONE_HTTP_PORT": "6480"})

    def test_aucune_variable_oubliee(self):
        self.assertNotIn("${", self.conf)
        self.assertIn("listen 6480;", self.conf)

    def test_agents_sans_auth_basique_humains_avec(self):
        b = dict((loc.strip(), body) for loc, body in blocks(self.conf))
        self.assertNotIn("auth_basic", b["/api/si-agent/api/v1/"])
        self.assertNotIn("auth_basic", b["= /api/si-agent/ca"])
        self.assertIn("auth_basic", b["/api/si-agent/"])
        self.assertIn("auth_basic", b["/agents/"])
        self.assertIn("proxy_pass http://si-agent-api:5000/api/v1/", b["/api/si-agent/api/v1/"])
        self.assertIn("proxy_pass http://si-agent-api:5000/;", b["/api/si-agent/"], "préfixe retiré comme tls-proxy")

    def test_variables_nginx_intactes(self):
        self.assertIn("try_files $uri", self.conf)


class Edge(unittest.TestCase):
    def test_edge(self):
        conf = render(os.path.join(SA, "edge", "edge.conf.template"), {"GATEWAY_PORT": "6443", "SI_STANDALONE_UPSTREAM": "192.0.2.20:6480"})
        self.assertNotIn("${", conf)
        self.assertIn("listen 6443 ssl;", conf)
        self.assertIn("proxy_pass http://192.0.2.20:6480;", conf)
        self.assertIn("/etc/nginx/tls/server.crt", conf)


class Compose(unittest.TestCase):
    def test_compose_et_run(self):
        import yaml
        d = yaml.safe_load(open(os.path.join(SA, "docker-compose.yml"), encoding="utf-8"))
        self.assertEqual(sorted(d["services"]), ["front", "memcached", "si-agent-api"])
        self.assertIn("si-agent/api/Dockerfile", d["services"]["si-agent-api"]["build"]["dockerfile"])
        e = yaml.safe_load(open(os.path.join(SA, "edge", "docker-compose.yml"), encoding="utf-8"))
        self.assertEqual(list(e["services"]), ["edge"])
        r = subprocess.run(["bash", "-n", os.path.join(SA, "run.sh")])
        self.assertEqual(r.returncode, 0)
        s = open(os.path.join(SA, "run.sh"), encoding="utf-8").read()
        self.assertIn("openssl passwd -apr1", s)
        self.assertNotIn('echo "$pwd', s, "le mot de passe n'est jamais affiché")


if __name__ == "__main__":
    unittest.main()
