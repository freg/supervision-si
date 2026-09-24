# -*- coding: utf-8 -*-
"""Tests de services-api (#584) : jeton vérifié + liste blanche, inventaire
(Docker et HTTP simulés), redémarrage limité au projet, « rouges » sans les
protégés, journal. Le SDK Docker est remplacé par un module factice si
absent (tests sans Docker)."""
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ROOT, "si-proxy", "admin"))  # auth.py partagé (après HERE : app.py = le nôtre)
os.environ["SERVICES_ADMIN_USERS"] = "freg"
os.environ["COMPOSE_PROJECT_NAME"] = "proj"
PROJ = tempfile.mkdtemp(prefix="tower-")
os.environ["SERVICES_PROJECT_DIR"] = PROJ
os.environ["SERVICES_HEAL_THREAD"] = "0"
os.environ["SERVICES_RUNNER_IMAGE"] = "img:test"
os.environ["SERVICES_HOST_IP"] = "192.0.2.5"
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
    runs = []

    def __init__(self, containers):
        self._c = containers
        self.containers = types.SimpleNamespace(list=lambda all=True, filters=None: [] if filters else list(self._c),
                                                run=lambda *a, **k: FakeDocker.runs.append((a, k)))

    def ping(self):
        return True


class TestApi(unittest.TestCase):
    def setUp(self):
        appmod.verifier = auth.KeycloakVerifier("u", ["freg"], fetch=lambda _u: jwks())
        self.cs = [FakeContainer("nebula-api"), FakeContainer("hub", port=5173), FakeContainer("ged-api", status="exited"),
                   FakeContainer("tls-proxy", status="exited", port=443), FakeContainer("pg", port=None, health="healthy"),
                   FakeContainer("autre", project="ailleurs"), FakeContainer("pg2", port=5432), FakeContainer("api-down", port=5000)]
        appmod.docker_client = lambda: FakeDocker(self.cs)
        appmod.app.docker_client = appmod.docker_client
        probes = {"proj-nebula-api-1": {"code": 200, "ms": 10, "content": "json", "status": "ok"}, "proj-hub-1": {"code": 200, "ms": 20, "content": "html"},
                  "proj-pg2-1": {"tcp_only": True, "ms": 2}}
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
        self.assertEqual(names[:3], ["api-down", "ged-api", "tls-proxy"])  # rouges d'abord
        by = {s["service"]: s for s in d["services"]}
        self.assertEqual(by["nebula-api"]["light"], "green")
        self.assertEqual(by["hub"]["kind"], "front")
        self.assertEqual(by["pg"]["light"], "green")
        self.assertEqual(by["pg2"]["light"], "green")  # port ouvert non HTTP (#588)
        self.assertEqual((by["api-down"]["light"], by["api-down"]["hard"]), ("red", False))  # HTTP refusé mais conteneur en marche
        self.assertTrue(by["tls-proxy"]["protected"])
        self.assertEqual(d["summary"]["verdict"], "red")
        self.assertEqual(d["summary"]["counts"]["red"], 3)

    def test_restart(self):
        self.assertEqual(self.c.post("/services/ged-api/restart", headers=self.h).get_json()["action"], "start")
        self.assertEqual(self.cs[2].actions, ["start"])
        self.assertEqual(self.c.post("/services/nebula-api/restart", headers=self.h).get_json()["action"], "restart")
        self.assertEqual(self.c.post("/services/autre/restart", headers=self.h).status_code, 404)

    def test_restart_red(self):
        d = self.c.post("/services/restart-red", headers=self.h).get_json()
        self.assertEqual(d["restarted"], ["api-down", "ged-api"])  # geste humain : les rouges HTTP aussi
        self.assertEqual(d["skipped_protected"], ["tls-proxy"])
        self.assertEqual(self.cs[3].actions, [])

    def test_logs(self):
        d = self.c.get("/services/hub/logs?tail=2", headers=self.h).get_json()
        self.assertEqual(d["tail"], 10)  # borne basse
        self.assertEqual(d["lines"], ["l1", "l2", "l3"])
        self.assertEqual(self.c.get("/services/autre/logs", headers=self.h).status_code, 404)



def put(rel, text):
    path = os.path.join(PROJ, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TestTower(TestApi):
    """#586 : configurations JSON, livraison zip -> plan -> job runner, réglages, auto-réparation."""

    def setUp(self):
        TestApi.setUp(self)
        FakeDocker.runs = []
        put("docker-compose.yml", "services:\n  nebula-api:\n    build: {context: ., dockerfile: nebula/Dockerfile}\n"
            "  hub:\n    build: {context: ., dockerfile: hub/Dockerfile}\n  ged-api:\n    build: {context: ., dockerfile: ged/Dockerfile}\n")
        put("nebula/Dockerfile", "COPY nebula/api/ .\n")
        put("hub/Dockerfile", "COPY hub/ .\n")
        put("ged/Dockerfile", "COPY ged/ .\n")
        put("nebula/api/app.py", "v1\n")
        put("shared/DELIVERY_NUMBER", "585\n")
        put(".env", "SECRET=1\n")
        put("cisco/switches.json", '{"switches": [{"name": "exemple", "host": "192.0.2.10", "credential": "cisco"}]}')

    def test_configs(self):
        d = self.c.get("/configs/cisco", headers=self.h).get_json()
        self.assertEqual((d["source"], d["items"][0]["name"]), ("exemple", "exemple"))
        r = self.c.put("/configs/cisco", headers=self.h, json={"data": {"switches": [{"name": "a b", "host": "x"}]}})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.get_json()["errors"])
        r = self.c.put("/configs/cisco", headers=self.h, json={"data": [{"name": "routeur-bureau", "host": "192.0.2.249", "transport": "telnet", "credential": "rb"}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.load(open(os.path.join(PROJ, "cisco/switches.local.json")))["switches"][0]["transport"], "telnet")
        self.assertEqual(self.c.get("/configs/cisco", headers=self.h).get_json()["source"], "local")
        self.c.put("/configs/cisco", headers=self.h, json={"data": []})
        self.assertTrue(os.listdir(os.path.join(PROJ, "services/data/config-history")))  # ancienne version gardée
        self.assertEqual(self.c.get("/configs/inconnu", headers=self.h).status_code, 404)
        self.assertEqual(self.c.put("/configs/cisco", json=[]).status_code, 401)

    def _zip(self, files, number="586"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for rel, text in files.items():
                zf.writestr("supervision-si/" + rel, text)
            zf.writestr("supervision-si/shared/DELIVERY_NUMBER", number + "\n")
        buf.seek(0)
        return buf

    def test_delivery(self):
        files = {"nebula/api/app.py": "v2\n", "hub/src/New.jsx": "x", ".env": "PIRATE=1", "../evil": "x", "CHANGELOG.md": "c"}
        r = self.c.post("/deliveries", headers=self.h, data={"file": (self._zip(files), "supervision-si.zip")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_json())
        d = r.get_json()
        self.assertEqual((d["current"], d["number"], d["downgrade"]), ("585", "586", False))
        self.assertIn("nebula/api/app.py", d["changed"])
        self.assertIn("hub/src/New.jsx", d["added"])
        self.assertEqual(d["protected"], [".env"])
        self.assertEqual(d["unsafe"], ["supervision-si/../evil"])
        # nebula-api en marche -> reconstruit ; hub en marche aussi (fixture) ; ged-api arrêté -> non démarré
        self.assertEqual(d["plan"]["rebuild"], ["hub", "nebula-api"])
        a = self.c.post("/deliveries/%s/apply" % d["id"], headers=self.h, json={}).get_json()
        self.assertTrue(a["applied"])
        self.assertEqual(open(os.path.join(PROJ, "nebula/api/app.py")).read(), "v2\n")
        self.assertEqual(open(os.path.join(PROJ, ".env")).read(), "SECRET=1\n")  # jamais écrasé
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(PROJ), "evil")))
        self.assertEqual(len(FakeDocker.runs), 1)
        args, kw = FakeDocker.runs[0]
        self.assertEqual(args[0], "img:test")
        self.assertIn(PROJ, kw["volumes"])
        self.assertEqual(kw["environment"], {"HOST_IP": "192.0.2.5"})
        script = open(os.path.join(PROJ, "services/data/jobs/%s.sh" % a["job"])).read()
        self.assertIn("./scripts/run.sh up -d --build hub nebula-api", script)
        self.assertEqual(self.c.get("/jobs/%s" % a["job"], headers=self.h).get_json()["status"], "lost")  # runner factice : ni rc ni conteneur
        self.assertEqual(self.c.post("/deliveries/%s/apply" % d["id"], headers=self.h, json={}).status_code, 409)
        ev = [e["event"] for e in self.c.get("/events", headers=self.h).get_json()["events"]]
        self.assertIn("delivery-applied", ev)

    def test_downgrade_guard(self):
        d = self.c.post("/deliveries", headers=self.h, data={"file": (self._zip({"x.py": "1"}, number="500"), "old.zip")}, content_type="multipart/form-data").get_json()
        self.assertTrue(d["downgrade"])
        self.assertEqual(self.c.post("/deliveries/%s/apply" % d["id"], headers=self.h, json={}).status_code, 409)
        self.assertEqual(self.c.post("/deliveries/%s/apply" % d["id"], headers=self.h, json={"allow_downgrade": True}).status_code, 200)

    def test_settings_ignored_and_heal(self):
        s = self.c.put("/settings", headers=self.h, json={"ignored": ["ged-api", "x; y"], "heal_threshold": 1, "auto_heal": True}).get_json()
        self.assertEqual(s["ignored"], ["ged-api"])
        rows = {r["service"]: r for r in self.c.get("/services?refresh=1", headers=self.h).get_json()["services"]}
        self.assertEqual(rows["ged-api"]["light"], "grey")
        self.c.put("/settings", headers=self.h, json={"ignored": []})
        appmod._heal_state.clear()
        self.assertEqual(appmod.heal_once(), ["ged-api"])  # tls-proxy rouge mais protégé ; api-down rouge HTTP seulement -> jamais (#588)
        self.assertEqual(self.cs[2].actions, ["start"])

    def test_rebuild_job(self):
        j = self.c.post("/services/nebula-api/rebuild", headers=self.h).get_json()
        self.assertEqual(j["steps"][0]["cmd"], "./scripts/run.sh up -d --build nebula-api")
        self.assertEqual(self.c.post("/services/tls-proxy/rebuild", headers=self.h).get_json()["kind"], "rebuild")
        self.assertEqual(self.c.post("/services/inconnu/rebuild", headers=self.h).status_code, 404)


if __name__ == "__main__":
    unittest.main()
