# -*- coding: utf-8 -*-
"""#653 : plans PRA -- validation des étapes, simulation (agents connus/inconnus), exécution séquentielle avec acquittements
simulés (done puis failed → arrêt), continue_on_error, refus d'une double exécution."""
import os, sys, json, tempfile, unittest, threading, time
# Nommé test_z_pra pour passer APRÈS test_si_agent_api dans l'ordre de découverte : la suite importe `app` une seule fois
# et ce fichier-là fixe l'environnement (chemin de CA, URL publique) que ses propres tests relisent ensuite.
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
sys.path.insert(0, os.path.dirname(__file__))
import app as appmod, store, pra

class Pra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        # identifiants propres à ce fichier et nettoyés ensuite : la suite partage une seule base (app importé une fois)
        for a in ("pra-pve10", "pra-pve11"):
            store.create_agent(cls.db, a, "siege", label=a)

    @classmethod
    def tearDownClass(cls):
        conn = store._connect(cls.db)
        try:
            for t, col in (("commands", "agent_id"), ("events", "agent_id"), ("agents", "agent_id")):
                try: conn.execute("DELETE FROM %s WHERE %s LIKE 'pra-pve%%'" % (t, col))
                except Exception: pass
            conn.execute("DELETE FROM pra_runs"); conn.execute("DELETE FROM pra_plans"); conn.commit()
        finally:
            conn.close()

    def test_validate(self):
        self.assertEqual(pra.validate_steps([])[1], "au moins une étape")
        self.assertEqual(pra.validate_steps([{"agent_id": "pra-pve11", "vmid": 101, "action": "migrate"}])[1], "étape 1 (migrate) : paramètre target requis")
        self.assertEqual(pra.validate_steps([{"agent_id": "pra-pve11", "vmid": "x", "action": "start"}])[1], "étape 1 : vmid entier requis")
        st, err = pra.validate_steps([{"agent_id": "pra-pve11", "vmid": "101", "action": "Migrate", "params": {"target": "pra-pve10"}, "label": "super → pve10"}])
        self.assertIsNone(err); self.assertEqual(pra.command_params(st[0]), {"target": "pra-pve10", "vmid": 101, "action": "migrate", "kind": "qemu"})

    def test_plan_simulate_execute(self):
        r = self.c.post("/pra/plans", json={"name": "PRA super", "steps": [
            {"agent_id": "pra-pve11", "vmid": 101, "action": "backup", "params": {"storage": "pbs"}, "label": "sauvegarde"},
            {"agent_id": "pra-pve11", "vmid": 101, "action": "migrate", "params": {"target": "pra-pve10"}},
            {"agent_id": "inconnu", "vmid": 7, "action": "start"}]})
        self.assertEqual(r.status_code, 201, r.json); pid = r.json["plan"]["id"]
        r = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "simulate"}); rid = r.json["run_id"]
        run = self.c.get("/pra/runs/%d" % rid).json["run"]; self.assertEqual(run["status"], "failed"); self.assertEqual([s["ok"] for s in run["steps"]], [True, True, False])
        self.assertEqual(run["steps"][0]["params"]["storage"], "pbs"); self.assertEqual(store.list_commands(self.db, "pra-pve11"), [])      # rien envoyé
        # exécution : un faux agent acquitte la 1re commande ok, la 2e en échec -> arrêt, 3e jamais envoyée
        def fake_agent():
            seen = 0
            for _ in range(200):
                time.sleep(0.05)
                for c in store.list_commands(self.db, "pra-pve11", status="pending"):
                    seen += 1; store.ack_command(self.db, "pra-pve11", c["id"], {"ok": seen == 1, "error": None if seen == 1 else "migration refusée"})
                    if seen == 2: return
        t = threading.Thread(target=fake_agent, daemon=True); t.start()
        r = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute", "actor": "freg"}); self.assertEqual(r.status_code, 202); rid = r.json["run_id"]
        pra._runs[rid].join(timeout=20); t.join(timeout=5)
        run = self.c.get("/pra/runs/%d" % rid).json["run"]
        self.assertEqual(run["status"], "failed"); self.assertEqual([s["status"] for s in run["steps"]], ["done", "failed", "pending"])
        self.assertEqual(run["steps"][1]["result"]["error"], "migration refusée"); self.assertTrue(run["finished_at"])
        self.assertEqual(len(self.c.get("/pra/plans/%d/runs" % pid).json["runs"]), 2)
        self.assertEqual(self.c.put("/pra/plans/%d" % pid, json={"steps": [{"agent_id": "pra-pve11", "vmid": 1, "action": "fly"}]}).status_code, 400)
        self.assertEqual(self.c.delete("/pra/plans/%d" % pid).json["ok"], True)

if __name__ == "__main__": unittest.main()


class PraTriggersAndRoles(unittest.TestCase):
    """#654 : déclencheurs à la perte d'un agent (proposé / auto avec délai de garde) et rôles (bascule, vérification, étape de plan)."""
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH; store.create_agent(cls.db, "pra-pve12", "siege", label="pra-pve12")

    @classmethod
    def tearDownClass(cls):
        conn = store._connect(cls.db)
        try:
            conn.execute("DELETE FROM agents WHERE agent_id = 'pra-pve12'"); conn.execute("DELETE FROM pra_runs"); conn.execute("DELETE FROM pra_plans"); conn.execute("DELETE FROM pra_roles"); conn.commit()
        finally: conn.close()

    def test_triggers(self):
        p1 = self.c.post("/pra/plans", json={"name": "proposé", "trigger_agent_id": "pra-pve12", "steps": [{"agent_id": "pra-pve12", "vmid": 1, "action": "start"}]}).json["plan"]
        p2 = self.c.post("/pra/plans", json={"name": "auto", "trigger_agent_id": "pra-pve12", "trigger_mode": "auto", "trigger_cooldown_s": 3600, "steps": [{"agent_id": "pra-pve12", "vmid": 1, "action": "start"}]}).json["plan"]
        self.assertEqual((p1["trigger_mode"], p2["trigger_mode"]), ("notify", "auto"))
        events, started = [], []
        emit = lambda kind, sev, msg, aid, det: events.append((kind, sev, aid, det.get("plan_id")))
        fired = pra.on_agent_offline(self.db, "pra-pve12", emit, start=lambda plan: started.append(plan["id"]) or 77)
        self.assertEqual(sorted(f[1] for f in fired), ["auto", "notify"]); self.assertEqual(started, [p2["id"]])
        self.assertIn(("pra-suggested", "warning", "pra-pve12", p1["id"]), events); self.assertIn(("pra-triggered", "critical", "pra-pve12", p2["id"]), events)
        # exécution réelle récente -> délai de garde : proposé seulement
        conn = store._connect(self.db); conn.execute("INSERT INTO pra_runs (plan_id, mode, status, started_at) VALUES (?,?,?,?)", (p2["id"], "execute", "done", store.now_iso())); conn.commit(); conn.close()
        events.clear(); started.clear(); pra.on_agent_offline(self.db, "pra-pve12", emit, start=lambda plan: started.append(plan["id"]))
        self.assertEqual(started, []); self.assertTrue(any(e[0] == "pra-suggested" and e[3] == p2["id"] for e in events))
        self.assertEqual(pra.on_agent_offline(self.db, "aucun-plan", emit), [])

    def test_roles_and_switch(self):
        self.assertEqual(self.c.post("/pra/roles", json={"name": "web", "candidates": []}).status_code, 400)
        self.assertIn("router et rule_id", self.c.post("/pra/roles", json={"name": "web", "candidates": [{"address": "10.0.0.1"}], "mechanism": {"kind": "mikrotik_nat"}}).json["error"])
        r = self.c.post("/pra/roles", json={"name": "web", "service_url": "http://web.exemple/", "candidates": [{"label": "principal", "address": "10.0.0.1"}, {"label": "secours", "address": "10.0.0.2:8080"}],
                                            "mechanism": {"kind": "mikrotik_nat", "router": "rt-bureau", "rule_id": "*1A"}})
        self.assertEqual(r.status_code, 201, r.json); role = r.json["role"]; self.assertEqual(role["active"], 0)
        applied, checks = [], []
        def fake_apply(mech, cand): applied.append((mech["router"], mech["rule_id"], cand["address"])); return {"router": mech["router"], "to_addresses": cand["address"].split(":")[0]}
        res = pra.switch_role(self.db, role["id"], 1, by_user="freg", apply=fake_apply, http_get=lambda url: checks.append(url) or (200, 12))
        self.assertTrue(res["ok"]); self.assertEqual(applied, [("rt-bureau", "*1A", "10.0.0.2:8080")]); self.assertEqual(res["applied"]["to_addresses"], "10.0.0.2"); self.assertEqual(checks, ["http://web.exemple/"])
        self.assertEqual(pra.get_role(self.db, role["id"])["active"], 1); self.assertTrue(pra.get_role(self.db, role["id"])["last_check"]["ok"])
        res = pra.switch_role(self.db, role["id"], 0, apply=fake_apply, http_get=lambda url: (503, 5)); self.assertFalse(res["ok"]); self.assertIn("ne répond pas", res["error"])
        self.assertEqual(pra.switch_role(self.db, role["id"], 5)["error"], "candidat inconnu"); self.assertEqual(pra.switch_role(self.db, 999, 0)["error"], "rôle inconnu")
        res = pra.switch_role(self.db, role["id"], 1, apply=lambda m, c: (_ for _ in ()).throw(RuntimeError("timeout")), http_get=lambda u: (200, 1)); self.assertIn("mécanisme mikrotik_nat : timeout", res["error"])
        # étape de plan role_switch : simulation puis exécution (mécanisme manuel, sans URL = pas de vérification)
        m = self.c.post("/pra/roles", json={"name": "dns", "candidates": [{"address": "ns1"}, {"address": "ns2"}], "mechanism": {"kind": "manual"}}).json["role"]
        p = self.c.post("/pra/plans", json={"name": "bascule", "kind": "bascule", "steps": [{"action": "role_switch", "role_id": m["id"], "to": 1, "label": "dns → ns2"}, {"action": "role_switch", "role_id": 999, "to": 0}]})
        self.assertEqual(p.status_code, 201, p.json); pid = p.json["plan"]["id"]
        self.assertEqual(self.c.post("/pra/plans", json={"name": "x", "steps": [{"action": "role_switch", "role_id": "a"}]}).status_code, 400)
        rid = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "simulate"}).json["run_id"]; run = self.c.get("/pra/runs/%d" % rid).json["run"]
        self.assertEqual([s["ok"] for s in run["steps"]], [True, False]); self.assertEqual(run["steps"][1]["error"], "rôle inconnu")
        rid = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute"}).json["run_id"]; pra._runs[rid].join(timeout=10); run = self.c.get("/pra/runs/%d" % rid).json["run"]
        self.assertEqual([s["status"] for s in run["steps"]], ["done", "failed"]); self.assertEqual(pra.get_role(self.db, m["id"])["active"], 1); self.assertEqual(run["status"], "failed")
        self.assertEqual(self.c.get("/pra/roles").json["roles"][0]["name"], "dns")
        self.assertEqual(self.c.delete("/pra/roles/%d" % role["id"]).json["ok"], True)


class RoleMechanisms656(unittest.TestCase):
    """#656 : mécanismes dns (dns-api simulée) et keepalived (commandes vrrp_set acquittées par un faux agent)."""
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        for a in ("pra-web1", "pra-web2"): store.create_agent(cls.db, a, "siege", label=a)

    @classmethod
    def tearDownClass(cls):
        conn = store._connect(cls.db)
        try:
            conn.execute("DELETE FROM commands WHERE agent_id LIKE 'pra-web%'"); conn.execute("DELETE FROM agents WHERE agent_id LIKE 'pra-web%'"); conn.execute("DELETE FROM pra_roles"); conn.commit()
        finally: conn.close()

    def test_dns_mechanism(self):
        self.assertIn("zone et record", self.c.post("/pra/roles", json={"name": "web", "candidates": [{"address": "203.0.113.5"}], "mechanism": {"kind": "dns"}}).json["error"])
        role = self.c.post("/pra/roles", json={"name": "web", "candidates": [{"label": "a", "address": "203.0.113.5"}, {"label": "b", "address": "203.0.113.6:8080"}], "mechanism": {"kind": "dns", "zone": "exemple.fr", "record": "www", "ttl": 60}}).json["role"]
        seen = {}
        class Resp:
            status = 200
            def __init__(self, body): self._b = body
            def read(self): return json.dumps(self._b).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False
        import urllib.request
        def fake_open(req, timeout=0): seen["url"] = req.full_url; seen["body"] = json.loads(req.data); seen["method"] = req.get_method(); return Resp({"status": "partial", "change": {"results": {"ovh": {"ok": False}, "intranet": {"ok": True}}}})
        old = (urllib.request.urlopen, pra.DNS_API_URL); urllib.request.urlopen = fake_open; pra.DNS_API_URL = "http://dns-api:5000"
        try: res = pra.switch_role(self.db, role["id"], 1, http_get=lambda u: (200, 1))
        finally: urllib.request.urlopen, pra.DNS_API_URL = old
        self.assertTrue(res["ok"], res); self.assertEqual(seen["url"], "http://dns-api:5000/zones/exemple.fr/records"); self.assertEqual(seen["method"], "PUT")
        self.assertEqual(seen["body"]["value"], "203.0.113.6"); self.assertEqual(seen["body"]["ttl"], 60); self.assertEqual(res["applied"]["status"], "partial")

    def test_keepalived_mechanism(self):
        self.assertIn("agent_id", self.c.post("/pra/roles", json={"name": "vip", "candidates": [{"address": "192.0.2.11"}], "mechanism": {"kind": "keepalived", "instance": "VI_WEB"}}).json["error"])
        role = self.c.post("/pra/roles", json={"name": "vip", "candidates": [{"label": "web1", "address": "192.0.2.11", "agent_id": "pra-web1"}, {"label": "web2", "address": "192.0.2.12", "agent_id": "pra-web2"}], "mechanism": {"kind": "keepalived", "instance": "VI_WEB"}}).json["role"]
        def fake_agents():
            for _ in range(100):
                time.sleep(0.05); done = 0
                for a in ("pra-web1", "pra-web2"):
                    for cmd in store.list_commands(self.db, a, status="pending"):
                        store.ack_command(self.db, a, cmd["id"], {"ok": True, "result": cmd["params"]}); done += 1
                if done: return
        t = threading.Thread(target=fake_agents, daemon=True); t.start()
        res = pra.switch_role(self.db, role["id"], 1, http_get=lambda u: (200, 1)); t.join(timeout=5)
        self.assertTrue(res["ok"], res); pr = res["applied"]["priorities"]; self.assertEqual((pr["pra-web2"]["priority"], pr["pra-web1"]["priority"]), (200, 100))
        cmds = store.list_commands(self.db, "pra-web2"); self.assertEqual(cmds[0]["type"], "vrrp_set"); self.assertEqual(cmds[0]["params"]["instance"], "VI_WEB")


class PraMigration(unittest.TestCase):
    """#658 (item 112) : plan de migration généré (image / rebuild, transitions, retour), exécution avec checkpoint (pause ->
    Reprendre), image attendue par événement, Abandonner avec retour en arrière, téléchargement signé d'une image par un nœud."""
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client(); cls.db = appmod.DB_PATH
        for a in ("mig-srv", "mig-pve"): store.create_agent(cls.db, a, "siege", label=a)
        pra.IMAGE_TIMEOUT = 20; pra.SLEEP = lambda n: time.sleep(min(n, 0.05))     # wait_s du plan raccourci

    @classmethod
    def tearDownClass(cls):
        conn = store._connect(cls.db)
        try:
            for t, col in (("commands", "agent_id"), ("events", "agent_id"), ("agents", "agent_id")): conn.execute("DELETE FROM %s WHERE %s LIKE 'mig-%%'" % (t, col))
            conn.execute("DELETE FROM pra_runs"); conn.execute("DELETE FROM pra_plans"); conn.commit()
        finally: conn.close()

    def test_build(self):
        import migration
        self.assertEqual(migration.build({})[1], "method : image ou rebuild" if False else "source_agent_id (agent du serveur à migrer) requis")
        self.assertIn("image_target", migration.build({"source_agent_id": "mig-srv", "pve_agent_id": "mig-pve", "vmid": 200, "storage": "local-lvm"})[1])
        plan, err = migration.build({"source_agent_id": "mig-srv", "pve_agent_id": "mig-pve", "vmid": 200, "storage": "local-lvm", "image_target": "/mnt/images", "os": "windows", "role_id": 3, "role_from": 0, "role_to": 1, "purge_on_rollback": True})
        self.assertIsNone(err); acts = [s["action"] for s in plan["steps"]]
        self.assertEqual(acts, ["checkpoint", "image_host", "create", "import_disk", "start", "checkpoint", "set", "role_switch", "checkpoint", "host_shutdown"])
        self.assertEqual(plan["steps"][3]["params"]["source"], "{{image}}"); self.assertEqual(plan["steps"][3]["params"]["attach"], "sata0"); self.assertEqual(plan["steps"][2]["params"]["ostype"], "win11"); self.assertEqual(plan["steps"][2]["params"]["link_down"], 1)
        self.assertEqual([s["action"] for s in plan["rollback_steps"]], ["role_switch", "set", "shutdown", "checkpoint", "destroy"]); self.assertEqual(plan["rollback_steps"][0]["to"], 0)
        plan, err = migration.build({"method": "rebuild", "source_agent_id": "mig-srv", "pve_agent_id": "mig-pve", "vmid": 201, "storage": "local-lvm", "template": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst", "ip": "192.0.2.10/24"})
        self.assertIsNone(err); self.assertEqual([s["action"] for s in plan["steps"]], ["checkpoint", "create", "start", "checkpoint", "checkpoint", "checkpoint", "host_shutdown"]); self.assertEqual(plan["steps"][1]["kind"], "lxc")
        self.assertEqual([s["action"] for s in plan["rollback_steps"]], ["shutdown", "checkpoint"])
        # validation des nouvelles actions
        self.assertIn("confirm", pra.validate_steps([{"agent_id": "mig-pve", "vmid": 200, "action": "destroy", "params": {"confirm": "201"}}])[1])
        self.assertIn("consigne", pra.validate_steps([{"agent_id": "central", "action": "checkpoint"}])[1])
        st, err = pra.validate_steps([{"agent_id": "mig-srv", "action": "image_host", "params": {"target": "/mnt/images"}}, {"agent_id": "mig-srv", "action": "host_shutdown"}])
        self.assertIsNone(err); self.assertEqual(pra.command_type(st[0]), "image_host"); self.assertEqual(pra.command_params(st[1]), {"action": "shutdown"}); self.assertEqual(pra.command_type(st[1]), "power_action")

    def test_preview_save_run_resume_abort(self):
        body = {"source_agent_id": "mig-srv", "pve_agent_id": "mig-pve", "vmid": 200, "storage": "local-lvm", "image_target": "/mnt/images", "plan_name": "Migration test"}
        r = self.c.post("/pra/migrations/plan", json=body); self.assertEqual(r.status_code, 200); self.assertEqual(r.json["plan"]["kind"], "migration"); self.assertNotIn("id", r.json["plan"])
        r = self.c.post("/pra/migrations/plan", json=dict(body, save=True)); self.assertEqual(r.status_code, 201); plan = r.json["plan"]; pid = plan["id"]
        self.assertEqual(len(plan["rollback_steps"]), 3); self.assertEqual(plan["steps"][0]["action"], "checkpoint")
        sim = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "simulate"}).json["run_id"]
        run = self.c.get("/pra/runs/%d" % sim).json["run"]; self.assertEqual(run["status"], "done"); self.assertEqual(run["steps"][1]["command"], "image_host"); self.assertEqual(run["steps"][0]["hostname"], "opérateur")
        # exécution : checkpoint -> paused ; un faux agent acquitte image_host puis le central reçoit l'événement image-received ;
        # create / import_disk / start acquittés ; 2e checkpoint -> Abandonner avec retour -> exécution de retour (set, shutdown, checkpoint)
        def fake_agents():
            for _ in range(400):
                time.sleep(0.05)
                for aid in ("mig-srv", "mig-pve"):
                    for c in store.list_commands(self.db, aid, status="pending"):
                        store.ack_command(self.db, aid, c["id"], {"ok": True, "error": None, "result": {"target": "/mnt/images/mig-srv-x.img.zst"} if c["type"] == "image_host" else {}})
                        if c["type"] == "image_host":
                            time.sleep(0.2); appmod._event("image-received", "info", "image reçue", agent_id="mig-srv", details={"path": "/data/images/mig-srv/mig-srv-x.img.zst", "sha256": "0"})
        t = threading.Thread(target=fake_agents, daemon=True); t.start()
        rid = self.c.post("/pra/plans/%d/run" % pid, json={"mode": "execute", "actor": "freg"}).json["run_id"]
        for _ in range(100):
            time.sleep(0.05)
            if self.c.get("/pra/runs/%d" % rid).json["run"]["status"] == "paused": break
        run = self.c.get("/pra/runs/%d" % rid).json["run"]; self.assertEqual(run["status"], "paused"); self.assertEqual(run["steps"][0]["status"], "waiting")
        self.assertEqual(self.c.post("/pra/runs/%d/rollback" % rid, json={}).status_code, 409)
        self.assertEqual(self.c.post("/pra/runs/%d/resume" % rid).status_code, 200)
        for _ in range(200):
            time.sleep(0.05)
            run = self.c.get("/pra/runs/%d" % rid).json["run"]
            if run["status"] == "paused" and run["steps"][5]["status"] == "waiting": break
        self.assertEqual([s["status"] for s in run["steps"][:6]], ["done", "done", "done", "done", "done", "waiting"], run["steps"])
        self.assertEqual(run["steps"][1]["result"]["image"]["name"], "mig-srv-x.img.zst"); self.assertEqual(run["steps"][3]["params"]["source"], "central:mig-srv/mig-srv-x.img.zst")
        cmds = store.list_commands(self.db, "mig-pve"); self.assertEqual([c["type"] for c in cmds], ["vm_action"] * 3); self.assertEqual(sorted(c["params"]["action"] for c in cmds), ["create", "import_disk", "start"])
        r = self.c.post("/pra/runs/%d/abort" % rid, json={"rollback": True, "actor": "freg"}); self.assertEqual(r.status_code, 200, r.json); rb = r.json["rollback_run_id"]
        pra._runs[rid].join(timeout=10); run = self.c.get("/pra/runs/%d" % rid).json["run"]; self.assertEqual(run["status"], "failed"); self.assertEqual(run["steps"][5]["status"], "aborted")
        for _ in range(200):
            time.sleep(0.05)
            back = self.c.get("/pra/runs/%d" % rb).json["run"]
            if back["status"] == "paused": break
        self.assertEqual(back["mode"], "rollback"); self.assertEqual(back["parent_run_id"], rid); self.assertEqual([s["status"] for s in back["steps"]], ["done", "done", "waiting"])
        self.assertEqual(self.c.post("/pra/runs/%d/resume" % rb).status_code, 200); pra._runs[rb].join(timeout=10)
        self.assertEqual(self.c.get("/pra/runs/%d" % rb).json["run"]["status"], "done")
        self.assertEqual(self.c.post("/pra/runs/%d/rollback" % rid, json={}).status_code, 202)      # retour relançable après coup
        self.assertEqual(self.c.post("/pra/runs/%d/resume" % 99999).status_code, 409)

    def test_image_download(self):
        protocol = appmod.protocol
        os.makedirs(os.path.join(appmod.IMAGES_DIR, "mig-srv"), exist_ok=True)
        with open(os.path.join(appmod.IMAGES_DIR, "mig-srv", "img.bin"), "wb") as fh: fh.write(b"0123456789")
        secret = store.get_secret(self.db, "mig-pve")["secret"]
        path = protocol.API_PREFIX + "/agents/mig-pve/images/mig-srv/img.bin/download"
        r = self.c.get(path, headers=protocol.auth_headers("mig-pve", secret, "GET", path, b"")); self.assertEqual(r.status_code, 200); self.assertEqual(r.data, b"0123456789")
        r = self.c.get(path, headers=dict(protocol.auth_headers("mig-pve", secret, "GET", path, b""), Range="bytes=6-")); self.assertEqual(r.status_code, 206); self.assertEqual(r.data, b"6789")
        self.assertEqual(self.c.get(path).status_code, 401)
        p2 = protocol.API_PREFIX + "/agents/mig-pve/images/mig-srv/absent/download"
        self.assertEqual(self.c.get(p2, headers=protocol.auth_headers("mig-pve", secret, "GET", p2, b"")).status_code, 404)
