# -*- coding: utf-8 -*-
"""Tests de services-api (#584) : jeton vérifié + liste blanche, inventaire
(Docker et HTTP simulés), redémarrage limité au projet, « rouges » sans les
protégés, journal. Le SDK Docker est remplacé par un module factice si
absent (tests sans Docker)."""
import json
import os
import sys
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ROOT, "si-proxy", "admin"))  # auth.py partagé (après HERE : app.py = le nôtre)
os.environ["SERVICES_ADMIN_USERS"] = "freg"
os.environ["COMPOSE_PROJECT_NAME"] = "proj"
if "docker" not in sys.modules:
    try:
        import docker  # noqa: F401
    except ImportError:
        sys.modules["docker"] = types.SimpleNamespace(from_env=lambda: None)
try:
    import requests  # noqa: F401
except ImportError:
    sys.modules["requests"] = types.SimpleNamespace(get=None, exceptions=types.SimpleNamespace(ConnectionError=Exception, Timeout=Exception, RequestException=Exception))

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jwt.algorithms import RSAAlgorithm  # noqa: E402

import app as appmod  # noqa: E402
import auth  # noqa: E402

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks():
    j = json.loads(RSAAlgorithm.to_jwk(KEY.public_key()))
    j.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    return {"keys": [j]}


def token(username="freg"):
    claims = {"preferred_username": username, "name": username, "exp": int(time.time()) + 300, "iat": int(time.time()), "typ": "Bearer"}
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})


class FakeContainer(object):
    def __init__(self, service, status="running", port=5000, project="proj", health=None):
        self.name = "proj-%s-1" % service
        self.id = ("%s0000000000000000" % service)[:24]
        self.status = status
        self.image = types.SimpleNamespace(tags=["%s:latest" % service])
        self.attrs = {"Config": {"Labels": {"com.docker.compose.project": project, "com.docker.compose.service": service},
                                 "ExposedPorts": ({"%d/tcp" % port: {}} if port else {})},
                      "State": {"StartedAt": "2026-09-24T06:00:00Z", "Health": ({"Status": health} if health else {})}, "RestartCount": 0}
        self.actions = []

    def restart(self, timeout=10):
        self.actions.append("restart")
        self.status = "running"

    def start(self):
        self.actions.append("start")
        self.status = "running"

    def logs(self, tail=80, timestamps=True):
        return b"l1\nl2\nl3\n"


class FakeDocker(object):
    def __init__(self, containers):
        self._c = containers
        self.containers = types.SimpleNamespace(list=lambda all=True: list(self._c))

    def ping(self):
        return True


class TestApi(unittest.TestCase):
    def setUp(self):
        appmod.verifier = auth.KeycloakVerifier("u", ["freg"], fetch=lambda _u: jwks())
        self.cs = [FakeContainer("nebula-api"), FakeContainer("hub", port=5173), FakeContainer("ged-api", status="exited"),
                   FakeContainer("tls-proxy", status="exited", port=443), FakeContainer("pg", port=None, health="healthy"),
                   FakeContainer("autre", project="ailleurs")]
        appmod.docker_client = lambda: FakeDocker(self.cs)
        appmod.app.docker_client = appmod.docker_client
        probes = {"proj-nebula-api-1": {"code": 200, "ms": 10, "content": "json", "status": "ok"}, "proj-hub-1": {"code": 200, "ms": 20, "content": "html"}}
        appmod._http_probe = lambda host, port: probes.get(host, {"error": "connexion refusée"})
        appmod._cache["rows"] = None
        self.c = appmod.app.test_client()
        self.h = {"Authorization": "Bearer " + token()}

    def test_auth(self):
        self.assertEqual(self.c.get("/services").status_code, 401)
        self.assertEqual(self.c.get("/services", headers={"Authorization": "Bearer " + token("bob")}).status_code, 403)
        self.assertEqual(self.c.get("/health").status_code, 200)

    def test_inventory(self):
        r = self.c.get("/services", headers=self.h)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        names = [s["service"] for s in d["services"]]
        self.assertNotIn("autre", names)  # hors projet
        self.assertEqual(names[:2], ["ged-api", "tls-proxy"])  # rouges d'abord
        by = {s["service"]: s for s in d["services"]}
        self.assertEqual(by["nebula-api"]["light"], "green")
        self.assertEqual(by["hub"]["kind"], "front")
        self.assertEqual(by["pg"]["light"], "green")
        self.assertTrue(by["tls-proxy"]["protected"])
        self.assertEqual(d["summary"]["verdict"], "red")
        self.assertEqual(d["summary"]["counts"]["red"], 2)

    def test_restart(self):
        self.assertEqual(self.c.post("/services/ged-api/restart", headers=self.h).get_json()["action"], "start")
        self.assertEqual(self.cs[2].actions, ["start"])
        self.assertEqual(self.c.post("/services/nebula-api/restart", headers=self.h).get_json()["action"], "restart")
        self.assertEqual(self.c.post("/services/autre/restart", headers=self.h).status_code, 404)

    def test_restart_red(self):
        d = self.c.post("/services/restart-red", headers=self.h).get_json()
        self.assertEqual(d["restarted"], ["ged-api"])
        self.assertEqual(d["skipped_protected"], ["tls-proxy"])
        self.assertEqual(self.cs[3].actions, [])

    def test_logs(self):
        d = self.c.get("/services/hub/logs?tail=2", headers=self.h).get_json()
        self.assertEqual(d["tail"], 10)  # borne basse
        self.assertEqual(d["lines"], ["l1", "l2", "l3"])
        self.assertEqual(self.c.get("/services/autre/logs", headers=self.h).status_code, 404)


if __name__ == "__main__":
    unittest.main()
