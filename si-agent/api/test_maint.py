# -*- coding: utf-8 -*-
"""#705 : maintenance des Proxmox -- détecteurs sur mesures simulées, évaluation (constat acquis, coche, exécution),
modèles, planificateur, vue des sauvegardes, routes sur une application de test (base temporaire)."""
import json, os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import si_agent_plugins  # noqa: F401  (image Docker)
except ImportError:  # dépôt de développement : même alias que app.py
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    import si_agent.plugins as _plugins
    from si_agent import control as _control
    sys.modules.setdefault("si_agent_plugins", _plugins)
    sys.modules.setdefault("si_agent_control", _control)
from flask import Flask  # noqa: E402
import maint, pra, store  # noqa: E402

NOW = 1_800_000_000


def px(vms_a=None, vms_b=None, at=NOW, stale_b=False, storages_a=None, jobs=None):
    return [
        {"agent_id": "pve-alpha", "hostname": "pve-alpha", "at": at, "ok": True, "node": {"name": "pve-alpha"},
         "storages": storages_a if storages_a is not None else [{"storage": "local", "type": "dir", "avail": 50 * maint.GIB, "total": 400 * maint.GIB, "content": "rootdir,backup"}],
         "vms": vms_a if vms_a is not None else [
             {"vmid": 101, "name": "ct-a", "type": "lxc", "status": "stopped", "last_backup": {"at": NOW - 3600, "volid": "local:backup/vzdump-lxc-101.tar.zst"}, "backup_jobs": ["j1"]},
             {"vmid": 102, "name": "ct-b", "type": "lxc", "status": "stopped", "last_backup": None, "backup_jobs": []}],
         "backups": {"jobs": jobs if jobs is not None else [{"id": "j1", "enabled": True, "storage": "local", "vmids": [101], "all": False, "schedule": "sun 01:00"}]}},
        {"agent_id": "pve-beta", "hostname": "pve-beta", "at": at - (10 * 3600 if stale_b else 0), "ok": True, "node": {"name": "pve-beta"},
         "storages": [{"storage": "pbs-lan", "type": "pbs", "avail": 900 * maint.GIB, "total": 1000 * maint.GIB, "content": "backup"}],
         "vms": vms_b or [{"vmid": 201, "name": "web", "type": "qemu", "status": "running", "last_backup": {"at": NOW - 100 * 3600, "volid": "pbs-lan:backup/vm/201"},
                           "backup_jobs": [], "last_backup_run": {"ok": False}}]},
    ]


def snap(**kw):
    return maint.snapshot(px(**kw), NOW, {"pve-alpha": "0.5.45", "pve-beta": "0.5.40"})


class Detecteurs(unittest.TestCase):
    def c(self, t, s=None, **p):
        return maint.check({"type": t, "params": p}, s or snap())

    def test_ct(self):
        self.assertEqual(self.c("guest_absent", vmid=101, node="pve-alpha")["state"], "pending")
        self.assertEqual(self.c("guest_absent", vmid=999, node="pve-alpha")["state"], "done")
        self.assertEqual(self.c("guest_absent", vmid=999)["state"], "done")
        self.assertEqual(self.c("guest_absent", s=snap(stale_b=True), vmid=999)["state"], "unknown")        # un nœud muet : pas de conclusion
        self.assertEqual(self.c("guest_absent", s=snap(stale_b=True), vmid=201, node="pve-beta")["state"], "unknown")
        self.assertEqual(self.c("guest_present", vmid=201, node="pve-beta")["state"], "done")
        self.assertEqual(self.c("guest_status", vmid=201, status="stopped")["state"], "pending")
        self.assertEqual(self.c("guest_status", vmid=101, status="stopped", node="pve-alpha")["state"], "done")
        self.assertEqual(self.c("guest_absent", vmid=1, node="pve-gamma")["state"], "unknown")

    def test_sauvegardes_stockage_tache_version(self):
        self.assertEqual(self.c("backup_recent", vmid=101, max_age_h=24)["state"], "done")
        self.assertEqual(self.c("backup_recent", vmid=101, max_age_h=24, storage="pbs-lan")["state"], "pending")
        self.assertEqual(self.c("backup_recent", vmid=102, max_age_h=24)["state"], "pending")
        self.assertEqual(self.c("backup_recent", vmid=201, max_age_h=24)["state"], "pending")
        self.assertEqual(self.c("backup_recent", vmid=999, max_age_h=24)["state"], "unknown")
        self.assertEqual(self.c("storage_free", node="pve-alpha", storage="local", min_free_gb=40)["state"], "done")
        r = self.c("storage_free", node="pve-alpha", storage="local", min_free_gb=100)
        self.assertEqual(r["state"], "pending"); self.assertIn("50.0 Go libres", r["detail"])
        self.assertEqual(self.c("storage_present", node="pve-beta", storage="pbs-lan", type="pbs")["state"], "done")
        self.assertEqual(self.c("storage_present", node="pve-alpha", storage="pbs-lan")["state"], "pending")
        self.assertEqual(self.c("backup_job", storage="local", vmid=101)["state"], "done")
        self.assertEqual(self.c("backup_job", storage="local", vmid=102)["state"], "pending")
        self.assertEqual(self.c("backup_job", storage="pbs-lan")["state"], "pending")
        self.assertEqual(self.c("agent_version", agent_id="pve-beta", min_version="0.5.44")["state"], "pending")
        self.assertEqual(self.c("agent_version", agent_id="pve-alpha", min_version="0.5.9")["state"], "done")   # 45 > 9 (numérique)
        self.assertEqual(self.c("inconnu")["state"], "unknown")


def CAMP():
    c, err = maint.validate({"name": "Libérer alpha", "status": "active", "stages": [
        {"title": "Sauvegarder", "actions": [
            {"title": "Sauvegarde 102", "kind": "pra", "step": {"agent_id": "pve-alpha", "vmid": 102, "kind": "lxc", "action": "backup", "params": {"storage": "local"}},
             "detector": {"type": "backup_recent", "params": {"vmid": 102, "max_age_h": 24}}, "at": NOW - 60, "auto": True},
            {"title": "Sauvegarde 101", "kind": "manual", "detector": {"type": "backup_recent", "params": {"vmid": 101, "max_age_h": 24}}}]},
        {"title": "Supprimer", "require_previous": True, "actions": [
            {"title": "Supprimer 101", "kind": "pra", "step": {"agent_id": "pve-alpha", "vmid": 101, "kind": "lxc", "action": "destroy", "params": {"confirm": 101}},
             "detector": {"type": "guest_absent", "params": {"vmid": 101, "node": "pve-alpha"}}, "at": NOW - 60, "auto": True}]},
        {"title": "Contrôle", "actions": [{"title": "Vérifier à la main", "kind": "manual"}]}]})
    assert not err, err
    return c


class Evaluation(unittest.TestCase):
    def test_validation(self):
        v = maint.validate
        self.assertEqual(v({})[1], "nom de la campagne requis")
        self.assertIn("titre requis", v({"name": "x", "stages": [{"actions": []}]})[1])
        self.assertIn("paramètre storage requis", v({"name": "x", "stages": [{"title": "a", "actions": [{"kind": "pra", "step": {"agent_id": "a", "vmid": 1, "action": "backup"}}]}]})[1])
        self.assertIn("champ(s) requis : vmid", v({"name": "x", "stages": [{"title": "a", "actions": [{"title": "t", "detector": {"type": "guest_absent", "params": {}}}]}]})[1])
        c = v({"name": "x", "stages": [{"title": "a", "actions": [{"title": "t", "at": "12", "auto": True}]}]})[0]
        self.assertEqual((c["stages"][0]["actions"][0]["at"], c["stages"][0]["actions"][0]["auto"]), (12, False))   # auto : actions pra seulement

    def test_avancement_constate_et_acquis(self):
        c, changed = maint.evaluate(CAMP(), snap(), now=NOW)
        a1, a2 = c["stages"][0]["actions"]
        self.assertEqual((a1["state"], a2["state"], a2["done_how"]), ("todo", "done", "detected"))
        self.assertTrue(changed); self.assertEqual(a2["detected_at"], NOW)
        self.assertEqual((c["stages"][0]["state"], c["stages"][1]["state"], c["stages"][2]["state"]), ("doing", "blocked", "todo"))
        self.assertEqual(c["progress"], {"done": 1, "total": 4, "pct": 25})
        self.assertEqual([a["title"] for a in maint.due_actions(c, NOW)], ["Sauvegarde 102"])          # « Supprimer » bloquée
        # 102 sauvegardé, 101 supprimé : la sauvegarde de 101 n'est plus mesurable mais reste acquise
        vms = [{"vmid": 102, "type": "lxc", "status": "stopped", "last_backup": {"at": NOW - 60, "volid": "local:x"}}]
        c["stages"][0]["actions"][0]["run"] = {"run_id": 7}
        c, _ = maint.evaluate(c, snap(vms_a=vms), runs={7: "done"}, now=NOW)
        self.assertEqual([a["state"] for st in c["stages"] for a in st["actions"]], ["done", "done", "done", "todo"])
        self.assertIn("constaté le", c["stages"][0]["actions"][1]["detail"])
        self.assertEqual(c["stages"][1]["state"], "done")
        c["stages"][2]["actions"][0]["manual_done"] = True
        c, _ = maint.evaluate(c, snap(vms_a=vms), now=NOW)
        self.assertEqual(c["progress"]["pct"], 100); self.assertEqual(c["stages"][2]["actions"][0]["done_how"], "manual")

    def test_execution_en_echec_et_sans_detecteur(self):
        c = CAMP()
        c["stages"][0]["actions"][0]["run"] = {"run_id": 3}
        c, _ = maint.evaluate(c, snap(), runs={3: "failed"}, now=NOW)
        self.assertEqual(c["stages"][0]["actions"][0]["state"], "failed")
        self.assertEqual(maint.due_actions(c, NOW), [])                                                   # déjà lancée : pas de relance
        d = dict(CAMP(), status="draft")                                                                 # brouillon : rien d'automatique
        self.assertEqual(maint.due_actions(maint.evaluate(d, snap(), now=NOW)[0], NOW), [])

    def test_modeles(self):
        s = snap()
        t = maint.template("free_node", {"node": "pve-alpha", "agent_id": "pve-alpha", "vmids": [101, 102], "backup_storage": "local", "free_storage": "local", "min_free_gb": 100}, s)
        c, err = maint.validate(dict(t, status="draft"))
        self.assertIsNone(err, err)
        self.assertEqual([st["title"] for st in c["stages"]], ["Sauvegarder", "Contrôler les sauvegardes", "Supprimer", "Constater l'espace libéré"])
        self.assertEqual(c["stages"][2]["actions"][0]["step"], {"agent_id": "pve-alpha", "vmid": 101, "kind": "lxc", "action": "destroy", "params": {"confirm": 101}, "label": ""} if False else c["stages"][2]["actions"][0]["step"])
        self.assertEqual(c["stages"][2]["actions"][0]["step"]["action"], "destroy")
        self.assertTrue(c["stages"][2]["require_previous"])
        p = maint.validate(dict(maint.template("pbs_setup", {"pbs_storage": "pbs-lan", "nodes": ["pve-alpha", "pve-beta"], "vmids": [201]}, s), status="draft"))[0]
        e, _ = maint.evaluate(p, s, now=NOW)
        decl = e["stages"][2]["actions"]
        self.assertEqual([a["state"] for a in decl], ["todo", "done"])
        m = maint.validate(dict(maint.template("move_guest", {"vmids": [201], "source_node": "pve-beta", "source_agent": "pve-beta", "target_node": "pve-alpha"}, s), status="draft"))
        self.assertIsNone(m[1], m[1])
        with self.assertRaises(ValueError):
            maint.template("free_node", {}, s)

    def test_vue_sauvegardes(self):
        o = maint.pbs_overview(snap())
        g = {x["vmid"]: x for x in o["guests"]}
        self.assertEqual(g[101]["flags"], [])
        self.assertEqual(g[102]["flags"], ["hors tâche planifiée", "jamais sauvegardé"])
        self.assertEqual(g[201]["flags"], ["hors tâche planifiée", "sauvegarde de plus de 48 h", "dernière sauvegarde en échec"])
        self.assertTrue(o["has_pbs"])
        self.assertEqual(o["summary"], {"guests": 3, "uncovered": 2, "never": 1, "old": 1, "failed": 1, "on_pbs": 1})


class Signalements(unittest.TestCase):
    def test_transitions(self):
        c = CAMP()
        c["stages"][0]["actions"][0]["run"] = {"run_id": 9}
        c, _ = maint.evaluate(c, snap(), runs={9: "failed"}, now=NOW)
        ev = maint.transitions(c, NOW)
        self.assertEqual([e[0] for e in ev], ["maint.echec"])                          # « Supprimer 101 » prévue il y a 1 min : pas encore en retard
        self.assertEqual(maint.transitions(c, NOW), [])                                 # signalé une fois
        ev = maint.transitions(c, NOW + 20 * 60)
        self.assertEqual([e[0] for e in ev], ["maint.retard"]); self.assertIn("Supprimer 101", ev[0][2])
        # tout fait : étapes puis campagne terminées
        vms = [{"vmid": 102, "type": "lxc", "status": "stopped", "last_backup": {"at": NOW - 60, "volid": "local:x"}}]
        c["stages"][0]["actions"][0]["run"] = {"run_id": 10}
        c["stages"][2]["actions"][0]["manual_done"] = True
        c, _ = maint.evaluate(c, snap(vms_a=vms), runs={10: "done"}, now=NOW)
        kinds = [e[0] for e in maint.transitions(c, NOW + 30 * 60)]
        self.assertEqual(kinds, ["maint.etape"] * 3 + ["maint.campagne"])
        c["history"] = [{"event": "completed"}]
        self.assertEqual(maint.transitions(c, NOW + 31 * 60), [])


class SauvegardesTirees714(unittest.TestCase):
    def test_detecteur_modele_vue(self):
        pulled = [{"host": "pve-1", "vmid": 108, "at": NOW - 5 * 3600, "ok": True, "size": 3 * maint.GIB, "present": True},
                  {"host": "pve-1", "vmid": 102, "at": None, "ok": False, "last_error": "ssh"},
                  {"host": "pve-3", "vmid": 113, "at": NOW - 400 * 3600, "ok": True, "present": True}]
        s = maint.snapshot(px(), NOW, {}, pulled)
        c = lambda **p: maint.check({"type": "pulled_backup", "params": p}, s)
        self.assertEqual(c(vmid=108, host="pve-1", max_age_h=24)["state"], "done"); self.assertIn("3.0 Go", c(vmid=108, host="pve-1")["detail"])
        self.assertEqual(c(vmid=102, host="pve-1")["state"], "pending")
        self.assertEqual(c(vmid=113, host="pve-3", max_age_h=24)["state"], "pending")
        self.assertEqual(c(vmid=101, host="pve-1")["state"], "pending")
        self.assertEqual(maint.check({"type": "pulled_backup", "params": {"vmid": 1, "host": "x"}}, snap())["state"], "unknown")   # aucune sonde
        t = maint.template("free_node", {"node": "pve-alpha", "agent_id": "pve-alpha", "vmids": [101], "pull_host": "198.51.100.5"}, s)
        a = t["stages"][0]["actions"][0]
        self.assertEqual((a["kind"], a["detector"]["type"], a["detector"]["params"]["host"]), ("manual", "pulled_backup", "pve-alpha"))
        self.assertIn("PULL_NAME=pve-alpha /usr/local/sbin/pve-pull-backup.sh 198.51.100.5 101 stop", a["notes"])
        self.assertIsNone(maint.validate(dict(t, status="draft"))[1])
        self.assertEqual(len(maint.pbs_overview(s)["pulled"]), 3)


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = os.path.join(tempfile.mkdtemp(), "t.db")
        store.ensure_schema(cls.db); pra.init(cls.db)
        store.create_agent(cls.db, "pve-alpha", "siege", label="pve-alpha")
        cls.data = {"px": px()}
        cls.events = []
        app = Flask("t")
        maint.register(app, cls.db, lambda: cls.data["px"], start_loop=False, emit=lambda *a: cls.events.append(a))
        cls.c = app.test_client()

    def test_cycle(self):
        r = self.c.post("/maint/templates/free_node", json={"node": "pve-alpha", "agent_id": "pve-alpha", "vmids": [102], "backup_storage": "local"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = dict(r.get_json()["campaign"], status="active", actor="freg")
        self.assertEqual(self.c.post("/maint/templates/xx", json={}).status_code, 400)
        r = self.c.post("/maint/campaigns", json=body)
        self.assertEqual(r.status_code, 201, r.get_json())
        camp = r.get_json()["campaign"]; cid = camp["id"]
        self.assertEqual(camp["progress"]["total"], 4)
        cat = self.c.get("/maint/catalog").get_json()
        self.assertEqual([n["node"] for n in cat["nodes"]], ["pve-alpha", "pve-beta"]); self.assertIn("backup_recent", cat["detectors"])
        # coche d'une action manuelle
        man = camp["stages"][1]["actions"][0]["id"]
        r = self.c.post("/maint/campaigns/%d/actions/%s" % (cid, man), json={"op": "mark", "actor": "freg"})
        self.assertEqual(r.get_json()["campaign"]["stages"][1]["actions"][0]["state"], "done")
        # simulation d'une opération : plan PRA d'une étape, rien n'est envoyé
        bk = camp["stages"][0]["actions"][0]["id"]
        r = self.c.post("/maint/campaigns/%d/actions/%s" % (cid, bk), json={"op": "simulate", "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json()); self.assertTrue(r.get_json()["run_id"])
        # destruction refusée tant que l'étape précédente n'est pas terminée
        de = camp["stages"][2]["actions"][0]["id"]
        self.assertEqual(self.c.post("/maint/campaigns/%d/actions/%s" % (cid, de), json={"op": "execute"}).status_code, 409)
        # modification : l'état acquis suit l'action
        r = self.c.put("/maint/campaigns/%d" % cid, json={"name": "Libérer alpha (v2)", "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["campaign"]["stages"][1]["actions"][0]["state"], "done")
        lst = self.c.get("/maint/campaigns").get_json()["campaigns"]
        self.assertEqual((lst[0]["name"], lst[0]["progress"]["done"]), ("Libérer alpha (v2)", 1))
        self.assertEqual(self.c.get("/maint/backups").get_json()["summary"]["guests"], 3)
        # #714 : mesure de la sonde pulled-backups relue par le central
        conn = store._connect(self.db)
        conn.execute("INSERT INTO measurements (agent_id, task, at, ok, data, received_at) VALUES ('pve-alpha', 'plugin:pulled-backups', '2026-10-08T09:00:00Z', 1, ?, '2026-10-08T09:00:01Z')",
                     (json.dumps({"backups": [{"host": "pve-alpha", "vmid": 102, "at": time.time() - 60, "ok": True, "present": True}]}),))
        conn.commit(); conn.close()
        self.assertEqual(self.c.get("/maint/backups").get_json()["pulled"][0]["agent_id"], "pve-alpha")
        self.assertEqual(self.c.delete("/maint/campaigns/%d" % cid).status_code, 200)
        self.assertEqual(self.c.get("/maint/campaigns/%d" % cid).status_code, 404)

    def test_planificateur(self):
        body = {"name": "auto", "status": "active", "stages": [{"title": "s", "actions": [
            {"title": "sauvegarde 102", "kind": "pra", "step": {"agent_id": "pve-alpha", "vmid": 102, "kind": "lxc", "action": "backup", "params": {"storage": "local"}},
             "at": int(time.time()) - 5, "auto": True}]}]}
        cid = self.c.post("/maint/campaigns", json=body).get_json()["campaign"]["id"]
        orig = pra.start_run
        pra.start_run = lambda db, plan, mode, by, background=True: 4242
        try:
            self.assertIn(4242, maint.tick())
            self.assertNotIn(4242, maint.tick())                                      # pas de seconde exécution
        finally:
            pra.start_run = orig
        camp = self.c.get("/maint/campaigns/%d" % cid).get_json()["campaign"]
        self.assertEqual(camp["stages"][0]["actions"][0]["run"]["run_id"], 4242)
        self.assertEqual(camp["history"][-1]["event"], "auto-run")
        self.data["px"] = px(vms_a=[{"vmid": 102, "type": "lxc", "status": "stopped", "last_backup": {"at": time.time() - 60, "volid": "local:x"}}])
        conn = store._connect(self.db)
        conn.execute("INSERT INTO pra_runs (id, plan_id, mode, status, started_at) VALUES (4242, 1, 'execute', 'done', '')"); conn.commit(); conn.close()
        maint.tick()
        self.assertEqual([e[0] for e in self.events][-2:], ["maint.etape", "maint.campagne"])
        self.assertEqual(self.events[-1][3]["campaign_id"], cid)
        n = len(self.events); maint.tick(); self.assertEqual(len(self.events), n)
        self.data["px"] = px()
        self.c.delete("/maint/campaigns/%d" % cid)


if __name__ == "__main__":
    unittest.main()
