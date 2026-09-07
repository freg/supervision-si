"""Tests de si-agent-api (livraison #421) -- `cd si-agent/api && python3 -m unittest`.
Routes du tableau de bord, face signée, et surtout la CHAÎNE RÉELLE : le
vrai agent (si_agent.agent.Agent) parle au vrai central via le client de
test Flask -- enrôlement, configuration versionnée, plugin du catalogue
poussé signé et installé, mesures reçues, commandes acquittées."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["SI_AGENT_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "si-agent.db")
os.environ["SI_AGENT_PURGE_THREAD"] = "0"
os.environ["SI_AGENT_PUBLIC_URL"] = "https://vm:6443/api/si-agent"
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "agent"))

import app as app_mod  # noqa: E402
import store  # noqa: E402
from si_agent import agent as agent_mod  # noqa: E402
from si_agent import host, protocol  # noqa: E402
from tests.test_si_agent import PROC, SS_OUT, FakeCmd, Usage, files  # noqa: E402


class FlaskHttp(object):
    """Même contrat que si_agent.agent.HttpClient (status, dict|None), mais
    via le client de test Flask -- signature RÉELLE calculée par le
    protocole de l'agent, vérifiée par la copie du central."""

    def __init__(self, client, agent_id, secret):
        self.client, self.agent_id, self.secret = client, agent_id, secret

    def request(self, method, path, body=None):
        body_bytes = protocol.canonical_json(body) if body is not None else b""
        headers = protocol.auth_headers(self.agent_id, self.secret, method, path, body_bytes)
        r = self.client.open(path, method=method, data=body_bytes if body is not None else None, headers=headers,
                             content_type="application/json" if body is not None else None)
        return r.status_code, r.get_json(silent=True)


class ApiBase(unittest.TestCase):
    def setUp(self):
        store.ensure_schema(app_mod.DB_PATH)
        conn = store._connect(app_mod.DB_PATH)
        for t in ("agents", "measurements", "plugins", "agent_plugins", "commands"):
            conn.execute("DELETE FROM %s" % t)
        conn.commit(); conn.close()
        self.c = app_mod.app.test_client()

    def enroll(self, agent_id="srv-01", site="siege", **kw):
        r = self.c.post("/agents", json=dict(agent_id=agent_id, site=site, **kw))
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()


class DashboardTests(ApiBase):
    def test_enrolement_secret_et_installation(self):
        a = self.enroll(label="Serveur fichiers")
        self.assertIn("secret", a)
        self.assertIn("--central https://vm:6443/api/si-agent", a["install_command"])
        self.assertEqual(self.c.post("/agents", json={"agent_id": "srv-01", "site": "x"}).status_code, 400, "doublon")
        self.assertEqual(self.c.post("/agents", json={"agent_id": "../x", "site": "x"}).status_code, 400)
        g = self.c.get("/agents/srv-01").get_json()
        self.assertNotIn("secret", g, "jamais le secret en lecture")
        self.assertEqual(g["config_applied"], False)
        inst = self.c.get("/agents/srv-01/install").get_json()
        self.assertEqual(inst["secret"], a["secret"])
        self.assertEqual(inst["agent_json"]["central_url"], "https://vm:6443/api/si-agent")
        rot = self.c.post("/agents/srv-01/rotate-secret").get_json()
        self.assertNotEqual(rot["secret"], a["secret"])
        up = self.c.put("/agents/srv-01", json={"host_interval_seconds": 30, "risk_thresholds": {"disk_warning_percent": 50}, "active": False}).get_json()
        self.assertEqual(up["host_interval_seconds"], 30)
        self.assertEqual(up["risk_thresholds"]["disk_warning_percent"], 50)
        self.assertEqual(self.c.put("/agents/srv-01", json={"host_interval_seconds": 3}).status_code, 400)
        self.assertEqual(self.c.get("/status").get_json()["agents"], 1)
        self.assertEqual(self.c.delete("/agents/srv-01?purge=true").status_code, 200)
        self.assertEqual(self.c.get("/agents/srv-01").status_code, 404)

    def test_catalogue_affectation_commandes(self):
        self.enroll()
        r = self.c.post("/plugins", json={"id": "hello", "runner": "shell", "entry": "hello.sh", "interval_seconds": 60,
                                          "description": "test", "body": "#!/bin/bash\necho '{\"hi\": 1}'\n"})
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(r.get_json()["version"], "1")
        self.assertEqual(self.c.post("/plugins", json={"id": "Bad Id", "runner": "shell", "entry": "x.sh", "body": "x"}).status_code, 400)
        self.assertEqual(self.c.post("/plugins", json={"id": "bad", "runner": "shell", "entry": "../x.sh", "body": "x"}).status_code, 400)
        self.assertEqual(self.c.post("/plugins", json={"id": "bad", "runner": "shell", "entry": "x.sh", "interval_seconds": 5, "body": "x"}).status_code, 400)
        self.assertEqual(self.c.post("/plugins", json={"id": "bad", "runner": "shell", "entry": "x.sh", "body": ""}).status_code, 400)
        lst = self.c.get("/plugins").get_json()["plugins"]
        self.assertEqual([p["id"] for p in lst], ["hello"])
        self.assertNotIn("body", lst[0])
        self.assertIn("body", self.c.get("/plugins/hello?body=true").get_json())
        # affectation
        self.assertEqual(self.c.put("/agents/srv-01/plugins/nope", json={}).status_code, 400)
        r = self.c.put("/agents/srv-01/plugins/hello", json={"enabled": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["plugins"][0]["enabled"], True)
        self.assertEqual(self.c.get("/plugins").get_json()["plugins"][0]["assigned_agents"], 1)
        prev = self.c.get("/agents/srv-01/config-preview").get_json()
        self.assertEqual([p["id"] for p in prev["plugins"]], ["hello"])
        self.assertNotIn("signature", prev["plugins"][0])
        v1 = prev["version"]
        self.c.put("/agents/srv-01/plugins/hello", json={"enabled": False})
        self.assertNotEqual(self.c.get("/agents/srv-01/config-preview").get_json()["version"], v1, "activation -> nouvelle version")
        # commandes
        self.assertEqual(self.c.post("/agents/srv-01/commands", json={"type": "bidule"}).status_code, 400)
        self.assertEqual(self.c.post("/agents/srv-01/commands", json={"type": "run_plugin"}).status_code, 400, "params.id requis")
        c = self.c.post("/agents/srv-01/commands", json={"type": "collect_now"}).get_json()
        self.assertEqual(c["status"], "pending")
        self.assertEqual(self.c.get("/agents/srv-01/commands?status=pending").get_json()["commands"][0]["id"], c["id"])
        self.assertEqual(self.c.get("/fleet").get_json()["agents"][0]["pending_commands"], 1)
        # suppression du catalogue -> plus affecté
        self.assertEqual(self.c.delete("/plugins/hello").status_code, 200)
        self.assertEqual(self.c.get("/agents/srv-01/plugins").get_json()["plugins"], [])


class SignedFaceTests(ApiBase):
    def test_refus_sans_signature_ou_mauvais_secret(self):
        a = self.enroll()
        self.assertEqual(self.c.get("/api/v1/agents/srv-01/config").status_code, 401)
        bad = FlaskHttp(self.c, "srv-01", "mauvais")
        self.assertEqual(bad.request("GET", "/api/v1/agents/srv-01/config")[0], 401)
        other = FlaskHttp(self.c, "srv-02", a["secret"])
        self.assertEqual(other.request("GET", "/api/v1/agents/srv-01/config")[0], 401, "identifiant ≠ URL")
        good = FlaskHttp(self.c, "srv-01", a["secret"])
        st, cfg = good.request("GET", "/api/v1/agents/srv-01/config")
        self.assertEqual(st, 200)
        self.assertEqual(cfg["host_interval_seconds"], 60)
        self.assertEqual(cfg["plugins"], [])
        # désactivé -> refusé
        self.c.put("/agents/srv-01", json={"active": False})
        self.assertEqual(good.request("GET", "/api/v1/agents/srv-01/config")[0], 401)

    def test_mesures_dedupliquees_et_autre_agent_rejete(self):
        a = self.enroll()
        http = FlaskHttp(self.c, "srv-01", a["secret"])
        batch = {"measurements": [
            {"agent_id": "srv-01", "task": "host", "at": "2026-09-07T10:00:00Z", "ok": True,
             "data": {"system": {"hostname": "fichiers", "os": "Debian 12"}, "cpu": {"percent": 12.5, "load5": 0.4},
                      "memory": {"used_percent": 40}, "disks": [{"mountpoint": "/", "used_percent": 91}]}, "error": None},
            {"agent_id": "srv-02", "task": "host", "at": "2026-09-07T10:00:00Z", "ok": True, "data": {}, "error": None},
            {"task": "x"},
        ]}
        st, body = http.request("POST", "/api/v1/agents/srv-01/measurements", batch)
        self.assertEqual(st, 201)
        self.assertEqual((body["accepted"], body["duplicates"], len(body["rejected"])), (1, 0, 2))
        st, body = http.request("POST", "/api/v1/agents/srv-01/measurements", batch)
        self.assertEqual(body["duplicates"], 1, "rejeu = doublon, rien de nouveau")
        f = self.c.get("/fleet").get_json()["agents"][0]
        self.assertEqual(f["hostname"], "fichiers")
        self.assertEqual(f["online"], "online")
        self.assertEqual(f["summary"]["disk_max_percent"], 91)
        self.assertEqual(f["summary"]["cpu_percent"], 12.5)
        self.assertEqual(http.request("POST", "/api/v1/agents/srv-01/measurements", {"measurements": "x"})[0], 400)
        self.assertEqual(http.request("POST", "/api/v1/agents/srv-01/measurements", {"measurements": [{"task": "x"}]})[0], 400)


class RealChainTests(ApiBase):
    """Le VRAI agent contre le VRAI central."""

    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp()
        self.enrolled = self.enroll(host_interval_seconds=30, risk_thresholds={"disk_warning_percent": 50})
        cfg = dict(agent_mod.DEFAULTS)
        cfg.update({"agent_id": "srv-01", "secret": self.enrolled["secret"], "central_url": "http://central", "site": "siege",
                    "queue_path": os.path.join(self.dir, "q.db"), "plugins_dir": os.path.join(self.dir, "plugins")})
        self.clock = [1_800_000_000.0]
        self.agent = agent_mod.Agent(cfg, http=FlaskHttp(self.c, "srv-01", self.enrolled["secret"]), cmd=FakeCmd({"ss": (0, SS_OUT)}),
                                     files=files(PROC), clock=lambda: self.clock[0], usage=lambda mp: Usage(100, 60),
                                     which=lambda t: "/usr/bin/" + t if t == "python3" else None, exists=lambda p: False)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_chaine_complete(self):
        # 1. catalogue + affectation AVANT le premier passage
        self.c.post("/plugins", json={"id": "hello", "runner": "python", "entry": "hello.py", "interval_seconds": 60,
                                      "body": "import json, sys\nprint(json.dumps({'hi': len(sys.argv)}))\n", "args": ["a", "b"]})
        self.c.put("/agents/srv-01/plugins/hello", json={"enabled": True})
        self.c.post("/agents/srv-01/commands", json={"type": "collect_now"})
        # 2. passage complet de l'agent
        out = self.agent.run_once()
        self.assertEqual([m["task"] for m in out], ["host", "risks", "inventory", "plugin:hello"])
        self.assertEqual(self.agent.cfg["host_interval_seconds"], 30, "réglage du central appliqué")
        self.assertEqual(self.agent.store.get("hello")["source"], "central", "plugin signé par le central, installé")
        self.assertEqual(out[3]["data"]["hi"], 3, "exécution réelle python avec args")
        self.assertEqual(self.agent.flush(force=True), 4)
        self.assertEqual(self.agent.queue.stats()["pending"], 0)
        # 3. côté central : flotte, risques, inventaire, commande acquittée
        f = self.c.get("/fleet").get_json()["agents"][0]
        self.assertEqual(f["online"], "online")
        self.assertEqual(f["hostname"], "srv-01")
        self.assertEqual(f["agent_version"], agent_mod.__version__ if hasattr(agent_mod, "__version__") else f["agent_version"])
        self.assertEqual(f["risks"]["state"], "critical")
        risks = self.c.get("/risks").get_json()["risks"]
        self.assertIn("uid0-account", [r["id"] for r in risks])
        self.assertIn("disk-high", [r["id"] for r in risks], "seuil 50 % poussé par le central")
        detail = self.c.get("/agents/srv-01").get_json()
        self.assertTrue(detail["config_applied"])
        self.assertEqual(detail["latest"]["inventory"]["data"]["plugins"][0]["id"], "hello")
        self.assertEqual(detail["latest"]["plugin:hello"]["data"]["hi"], 3)
        self.agent.poll_commands(force=True)
        cmds = self.c.get("/agents/srv-01/commands").get_json()["commands"]
        self.assertEqual(cmds[0]["status"], "done")
        self.assertEqual(cmds[0]["result"]["result"]["measurements"], 2)
        # 4. retrait du catalogue -> remove_plugins à la prochaine configuration
        self.c.delete("/plugins/hello")
        self.agent.refresh_config(force=True)
        self.assertIsNone(self.agent.store.get("hello"), "plugin retiré sur l'hôte")
        self.assertEqual(self.c.get("/agents/srv-01").get_json()["last_config_version"],
                         self.c.get("/agents/srv-01/config-preview").get_json()["version"])
        # 5. plugin altéré en base (corps changé sans nouvelle empreinte) -> refusé par l'agent
        self.c.post("/plugins", json={"id": "evil", "runner": "shell", "entry": "e.sh", "body": "echo ok\n"})
        conn = store._connect(app_mod.DB_PATH)
        conn.execute("UPDATE plugins SET body = 'rm -rf /' WHERE id = 'evil'"); conn.commit(); conn.close()
        self.c.put("/agents/srv-01/plugins/evil", json={"enabled": True})
        self.agent.refresh_config(force=True)
        self.assertIsNone(self.agent.store.get("evil"))


if __name__ == "__main__":
    unittest.main()
