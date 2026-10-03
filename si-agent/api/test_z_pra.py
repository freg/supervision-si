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
