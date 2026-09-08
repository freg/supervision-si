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
os.environ["SI_AGENT_CA_FILE"] = os.path.join(tempfile.mkdtemp(), "ca.crt")
os.environ["SI_AGENT_NOTIFY_SYNC"] = "1"
os.environ["SI_AGENT_NOTIFY_COOLDOWN_SECONDS"] = "0"
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "agent"))

import app as app_mod  # noqa: E402
import notify  # noqa: E402
import store  # noqa: E402
from si_agent import agent as agent_mod  # noqa: E402
from si_agent import control, host, protocol  # noqa: E402
from tests.test_si_agent import PROC, SS_OUT, FakeCmd, Usage, files  # noqa: E402


class FlaskHttp(object):
    """Même contrat que si_agent.agent.HttpClient (status, dict|None), mais
    via le client de test Flask -- signature RÉELLE calculée par le
    protocole de l'agent, vérifiée par la copie du central."""

    def __init__(self, client, agent_id, secret):
        self.client, self.agent_id, self.secret = client, agent_id, secret
        self.last_raw, self.last_headers = b"", {}

    def request(self, method, path, body=None):
        body_bytes = protocol.canonical_json(body) if body is not None else b""
        headers = protocol.auth_headers(self.agent_id, self.secret, method, path, body_bytes)
        r = self.client.open(path, method=method, data=body_bytes if body is not None else None, headers=headers,
                             content_type="application/json" if body is not None else None)
        self.last_raw, self.last_headers = r.get_data(), dict(r.headers.items())
        return r.status_code, r.get_json(silent=True)


class ApiBase(unittest.TestCase):
    def setUp(self):
        store.ensure_schema(app_mod.DB_PATH)
        conn = store._connect(app_mod.DB_PATH)
        for t in ("agents", "measurements", "plugins", "agent_plugins", "commands", "events", "settings"):
            conn.execute("DELETE FROM %s" % t)
        conn.commit(); conn.close()
        self.c = app_mod.app.test_client()
        notify._last_sent.clear()

    def kinds(self, **q):
        return [e["kind"] for e in self.c.get("/events", query_string=q).get_json()["events"]]

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
        # #446 : commande Windows exécutable telle quelle (politique d'exécution contournée, guillemets doubles compris par cmd et PowerShell)
        w = inst["install_command_windows"]
        self.assertTrue(w.startswith("powershell -NoProfile -ExecutionPolicy Bypass -File .\\windows\\install.ps1 -Agent \"srv-01\" -Secret \"%s\"" % a["secret"]), w)
        self.assertIn('-Central "https://vm:6443/api/si-agent" -Site "siege"', w)
        self.assertNotIn("'", w)
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
        self.assertEqual(control.verify_response(a["secret"], good.last_headers, good.last_raw), (True, "ok"), "réponse signée (#422)")
        self.assertFalse(control.verify_response("autre", good.last_headers, good.last_raw)[0])
        self.assertIn("issued_at", cfg)
        self.assertFalse(cfg["blocked"])
        self.assertIn("auth-refused", self.kinds(), "refus journalisé comme événement")
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


class CaptureRelayTests(ApiBase):
    """#436 : mesure plugin:capture-relay -> network-agent-api (relais sous mock)."""

    def test_relais(self):
        import app as api  # noqa: PLC0415
        old = api.NETWORK_AGENT_API_URL
        api.NETWORK_AGENT_API_URL = "http://na.test"
        calls = []

        class R:
            status_code, content = 200, b"{}"

            def json(self):
                return {"packets": 3}
        try:
            n = api.relay_capture_measurements("srv-01", {"site": "siege"}, [
                {"task": "plugin:capture-relay", "at": "x", "ok": True, "data": {"pcap_base64": "AAAA", "cidr": "10.0.0.0/24", "interface": "eth0"}},
                {"task": "plugin:capture-relay", "at": "y", "ok": False, "data": {"error": "tcpdump absent"}},
                {"task": "host", "at": "z", "ok": True, "data": {}},
            ], post=lambda url, payload: (calls.append((url, payload)) or R()))
            self.assertEqual(n, 1)
            self.assertEqual(calls[0][0], "http://na.test/capture/upload")
            self.assertEqual((calls[0][1]["segment"], calls[0][1]["cidr"], calls[0][1]["site"]), ("srv-01", "10.0.0.0/24", "siege"))
            api.NETWORK_AGENT_API_URL = ""
            self.assertEqual(api.relay_capture_measurements("srv-01", {}, [{"task": "plugin:capture-relay", "ok": True, "data": {"pcap_base64": "AAAA"}}]), 0, "sans URL : rien")
        finally:
            api.NETWORK_AGENT_API_URL = old


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
        self.assertEqual([m["task"] for m in out], ["host", "risks", "netview", "inventory", "plugin:hello"])
        self.assertEqual(self.agent.cfg["host_interval_seconds"], 30, "réglage du central appliqué")
        self.assertEqual(self.agent.store.get("hello")["source"], "central", "plugin signé par le central, installé")
        self.assertEqual(out[4]["data"]["hi"], 3, "exécution réelle python avec args")
        self.assertGreaterEqual(self.agent.flush(force=True), 4, "mesures + événements de l'agent")
        self.assertEqual(self.agent.queue.stats()["pending"], 0)
        agent_events = self.c.get("/events?agent=srv-01").get_json()["events"]
        self.assertIn("plugin-installed", [e["kind"] for e in agent_events if e["source"] == "agent"], "événement de l'agent dans le journal du central")
        self.assertIn("config-applied", [e["kind"] for e in agent_events if e["source"] == "agent"])
        # 3. côté central : flotte, risques, inventaire, commande acquittée
        nv = self.c.get("/netview").get_json()["netviews"]
        self.assertEqual([n["agent_id"] for n in nv], ["srv-01"], "#432 : vue réseau passive par agent")
        self.assertIn("counts", nv[0]["summary"])
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


class BlockAndEventsTests(ApiBase):
    """#422 : blocage général / individuel, journal, notifications, CA."""

    def make_agent(self, enrolled):
        d = tempfile.mkdtemp()
        cfg = dict(agent_mod.DEFAULTS)
        cfg.update({"agent_id": enrolled["agent_id"], "secret": enrolled["secret"], "central_url": "http://central", "site": enrolled["site"],
                    "queue_path": os.path.join(d, "q.db"), "plugins_dir": os.path.join(d, "plugins"), "state_path": os.path.join(d, "state.json"),
                    "block_file": os.path.join(d, "BLOCKED")})
        clock = [1_800_000_000.0]
        a = agent_mod.Agent(cfg, http=FlaskHttp(self.c, enrolled["agent_id"], enrolled["secret"]), cmd=FakeCmd({"ss": (0, SS_OUT)}),
                            files=files(PROC), clock=lambda: clock[0], usage=lambda mp: Usage(100, 10),
                            which=lambda t: None, exists=lambda p: False)
        a._clock = clock
        return a

    def test_blocage_general_puis_individuel_chaine_reelle(self):
        a1 = self.make_agent(self.enroll("srv-01"))
        a2 = self.make_agent(self.enroll("srv-02"))
        self.c.post("/plugins", json={"id": "hello", "runner": "shell", "entry": "h.sh", "interval_seconds": 60, "body": "echo '{}'\n"})
        for aid in ("srv-01", "srv-02"):
            self.c.put("/agents/%s/plugins/hello" % aid, json={"enabled": True})
        for a in (a1, a2):
            a.refresh_config(force=True)
            self.assertEqual(len(a.run_plugins()), 1)
        # BLOCAGE GÉNÉRAL : configuration + commande immédiate pour tous
        r = self.c.post("/block", json={"reason": "compromission suspectée"})
        self.assertTrue(r.get_json()["blocked"])
        self.assertEqual(self.c.get("/status").get_json()["fleet_blocked"], True)
        for a in (a1, a2):
            done = a.poll_commands(force=True)
            self.assertEqual([c["type"] for c, _ in done], ["block_all"])
            self.assertTrue(a.is_blocked())
            a._clock[0] += 120
            self.assertEqual(a.run_plugins(), [])
            a.refresh_config(force=True)
            self.assertTrue(a.central_blocked, "aussi déclaratif : survit à un redémarrage sans commande")
            a.collect_inventory(force=True); a.flush(force=True)
        f = {x["agent_id"]: x for x in self.c.get("/fleet").get_json()["agents"]}
        self.assertTrue(f["srv-01"]["host_blocked"], "l'agent DIT qu'il est bloqué (inventaire)")
        ev = self.c.get("/events?min_severity=warning").get_json()["events"]
        self.assertIn("fleet-blocked", [e["kind"] for e in ev])
        self.assertIn("blocked", [e["kind"] for e in ev if e["source"] == "agent"], "l'agent a journalisé son blocage")
        # déblocage général, mais srv-02 reste bloqué individuellement
        self.c.post("/agents/srv-02/block", json={"reason": "en cours d'analyse"})
        self.c.post("/unblock")
        for a in (a1, a2):
            a.poll_commands(force=True)
            a.refresh_config(force=True)
        self.assertFalse(a1.is_blocked())
        self.assertTrue(a2.is_blocked())
        self.assertEqual(a2.block_reason(), "en cours d'analyse")
        a1._clock[0] += 120
        self.assertEqual(len(a1.run_plugins()), 1)
        self.c.post("/agents/srv-02/unblock")
        a2.poll_commands(force=True); a2.refresh_config(force=True)
        self.assertFalse(a2.is_blocked())
        # blocage d'UNE sonde sur srv-01
        self.c.put("/agents/srv-01/plugins/hello", json={"blocked": True, "reason": "sortie suspecte"})
        a1.poll_commands(force=True)
        a1._clock[0] += 120
        self.assertEqual(a1.run_plugins(), [])
        a1.refresh_config(force=True)
        self.assertTrue(a1.store.get("hello")["blocked"], "et déclaratif via le manifeste")
        self.c.put("/agents/srv-01/plugins/hello", json={"blocked": False})
        a1.poll_commands(force=True); a1.refresh_config(force=True)
        a1._clock[0] += 120
        self.assertEqual(len(a1.run_plugins()), 1)
        summary = self.c.get("/events/summary").get_json()
        self.assertGreater(summary["counts"]["warning"] + summary["counts"]["critical"], 0)
        self.assertFalse(summary["fleet_blocked"])
        self.assertIn("kinds", summary)

    def test_privilege_et_rejeu_chaine_reelle(self):
        a = self.make_agent(self.enroll("srv-01"))
        self.c.post("/plugins", json={"id": "rooty", "runner": "shell", "entry": "r.sh", "privileged": True, "body": "id -u\n"})
        self.c.put("/agents/srv-01/plugins/rooty", json={"enabled": True})
        a.refresh_config(force=True)
        self.assertTrue(a.store.get("rooty")["privileged"], "drapeau privileged signé par le central, accepté")
        self.assertEqual(self.c.get("/plugins").get_json()["plugins"][0]["privileged"], True)
        # commande rejouée : le central n'acquitte qu'une fois, l'agent n'exécute qu'une fois
        c = self.c.post("/agents/srv-01/commands", json={"type": "collect_now"}).get_json()
        a.poll_commands(force=True)
        self.assertEqual(self.c.get("/commands/%s" % c["id"]).get_json()["status"], "done")
        self.assertIn(c["id"], a.state["done_commands"])

    def test_chien_de_garde_hors_ligne_et_notifications(self):
        # webhook réel : petit serveur HTTP local
        import http.server, threading
        received = []
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(204); self.end_headers()
            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        os.environ["SI_AGENT_NOTIFY_WEBHOOK_URL"] = "http://127.0.0.1:%d/hook" % srv.server_port
        try:
            self.assertTrue(notify.describe()["channels"]["webhook"])
            a = self.make_agent(self.enroll("srv-01"))
            a.collect_host(force=True); a.flush(force=True)
            app_mod.watchdog_tick()
            self.assertNotIn("agent-offline", self.kinds())
            # on vieillit le dernier contact : passage hors ligne détecté et notifié
            conn = store._connect(app_mod.DB_PATH)
            conn.execute("UPDATE agents SET last_seen_at = '2020-01-01T00:00:00Z' WHERE agent_id = 'srv-01'"); conn.commit(); conn.close()
            app_mod.watchdog_tick()
            self.assertIn("agent-offline", self.kinds())
            self.assertTrue(any(r["event"]["kind"] == "agent-offline" for r in received), "webhook appelé")
            ev = [e for e in self.c.get("/events?kind=agent-offline").get_json()["events"]][0]
            self.assertTrue(ev["notified"]["webhook"])
            # retour en ligne
            a._clock[0] += 60
            a.collect_host(force=True); a.flush(force=True)
            app_mod.watchdog_tick()
            self.assertIn("agent-online", self.kinds())
            # info : sous le seuil, non notifié
            n_before = len(received)
            self.c.post("/agents/srv-01/plugins/x", json={}) # 400, aucun événement
            self.c.post("/plugins", json={"id": "p", "runner": "shell", "entry": "p.sh", "body": "echo 1\n"})
            self.assertEqual(len(received), n_before, "événement info non notifié (seuil warning)")
            r = self.c.post("/notifications/test", json={}).get_json()
            self.assertTrue(r["webhook"])
            # anti-tempête
            os.environ["SI_AGENT_NOTIFY_COOLDOWN_SECONDS"] = "3600"
            ok, why = notify.should_notify({"kind": "k", "agent_id": "a", "severity": "warning"})
            self.assertTrue(ok)
            ok, why = notify.should_notify({"kind": "k", "agent_id": "a", "severity": "warning"})
            self.assertFalse(ok); self.assertIn("déjà notifié", why)
        finally:
            os.environ["SI_AGENT_NOTIFY_COOLDOWN_SECONDS"] = "0"
            os.environ.pop("SI_AGENT_NOTIFY_WEBHOOK_URL", None)
            srv.shutdown()

    def test_ca_et_commande_installation(self):
        self.assertEqual(self.c.get("/ca").status_code, 404, "pas de CA configurée")
        a = self.enroll("srv-01")
        self.assertIn("--ca /chemin/ca.crt", a["install_command"])
        # une vraie CA auto-signée
        import subprocess
        path = os.environ["SI_AGENT_CA_FILE"]
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", path + ".key", "-out", path,
                        "-days", "1", "-subj", "/CN=test-ca"], check=True, capture_output=True)
        r = self.c.get("/ca")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"BEGIN CERTIFICATE", r.data)
        fp = self.c.get("/status").get_json()["ca"]["sha256"]
        self.assertEqual(len(fp), 64)
        self.assertIn("--ca-fingerprint " + fp, self.c.get("/agents/srv-01/install").get_json()["install_command"])
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
