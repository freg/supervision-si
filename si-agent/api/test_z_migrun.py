# -*- coding: utf-8 -*-
"""#774 : tuile « Migration 2026-2027 » -- plan, pilotage, erreurs classées avec solution, enchaînement automatique."""
import json
import os
import sys
import tempfile
import time
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import migrun  # noqa: E402
import store  # noqa: E402

PLAN = {"name": "Essai", "vars": {"PVE_A": "198.51.100.10", "PVE_C": ""}, "phases": [
    {"id": "A", "title": "Préparation", "steps": [
        {"id": "a1", "title": "SSH vers pve-a", "agent": "mig-h", "kind": "check_ssh", "params": {"host": "${PVE_A}"}},
        {"id": "a2", "title": "SSH vers pve-c", "agent": "mig-h", "kind": "check_ssh", "params": {"host": "${PVE_C}"}}]},
    {"id": "B", "title": "Copies", "steps": [
        {"id": "b1", "title": "ct103", "agent": "mig-h", "kind": "rsync_pull", "params": {"host": "${PVE_A}", "src": "/var/lib/lxc/103/rootfs", "dest": "/data/ct103"}},
        {"id": "b2", "title": "Bascule DNS", "kind": "manual", "params": {}}]}]}


class Pur(unittest.TestCase):
    def test_validate(self):
        p, e = migrun.validate_plan(PLAN)
        self.assertIsNone(e)
        self.assertEqual([s["id"] for s in migrun.all_steps(p)], ["a1", "a2", "b1", "b2"])
        bad = json.loads(json.dumps(PLAN)); bad["phases"][0]["steps"][1]["id"] = "a1"
        self.assertIn("double", migrun.validate_plan(bad)[1])
        bad = json.loads(json.dumps(PLAN)); bad["phases"][0]["steps"][0]["kind"] = "rm"
        self.assertIn("type inconnu", migrun.validate_plan(bad)[1])
        bad = json.loads(json.dumps(PLAN)); bad["phases"][0]["steps"][0]["params"]["host"] = "${INCONNU}"
        self.assertIn("INCONNU", migrun.validate_plan(bad)[1])
        bad = json.loads(json.dumps(PLAN)); del bad["phases"][0]["steps"][0]["agent"]
        self.assertIn("agent", migrun.validate_plan(bad)[1])

    def test_expand(self):
        p, empty = migrun.expand({"host": "${PVE_A}", "l": ["${PVE_C}x"]}, {"PVE_A": "h1", "PVE_C": ""})
        self.assertEqual((p, empty), ({"host": "h1", "l": ["x"]}, ["PVE_C"]))

    def test_classify(self):
        s = {"id": "b1", "kind": "rsync_pull", "params": {"host": "198.51.100.10", "dest": "/d"}}
        cases = [("Permission denied (publickey).", "ssh-cle", "command"), ("ssh: connect to host x port 22: Connection timed out", "reseau", "retry"),
                 ("UN AUTRE RSYNC ÉCRIT DÉJÀ DANS /d/", "deja-en-cours", "command"), ("rsync: write failed: No space left on device (28)", "espace", "command"),
                 ("rsync error: some files/attrs were not transferred (code 23)", "rsync-partiel", "retry"),
                 ("commande inconnue : migstep", "agent-ancien", "command"), ("ÉTAPE INTERROMPUE (hôte redémarré ?)", "interrompue", "retry"),
                 ("blabla", "inconnue", "retry")]
        for line, code, kind in cases:
            e = migrun.classify(s, {"state": "failed", "rc": 1, "log_tail": ["x", line]}, "pve11")
            self.assertEqual((e["code"], e["solution"]["kind"]), (code, kind), line)
        e = migrun.classify(s, {"state": "failed", "rc": 255, "log_tail": ["Permission denied (publickey)."]}, "pve11")
        self.assertIn("sudo sh -c", e["solution"]["command"]); self.assertIn("198.51.100.10", e["solution"]["command"])
        self.assertEqual(e["solution"]["where"], "maison (Linux)"); self.assertIn("root@pve11", e["solution"]["command"])
        self.assertEqual(migrun.classify(s, {"state": "stopped", "rc": 143, "log_tail": []})["code"], "arret")


class Parcours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client()
        cls.db = appmod.DB_PATH
        store.create_agent(cls.db, "mig-h", "siege", label="mig-h")

    def cmds(self):
        conn = store._connect(self.db)
        try:
            return [(r[0], r[1], json.loads(r[2])) for r in conn.execute("SELECT id, type, params FROM commands WHERE agent_id = 'mig-h' AND status = 'pending' ORDER BY created_at, id")]
        finally:
            conn.close()

    def report(self, sid, state, rc=None, log=(), started=None):
        st = started or time.time()
        Parcours.n = getattr(Parcours, "n", 0) + 1   # un horodatage par mesure (même seconde = doublon ignoré)
        at = "2026-10-17T10:%02d:%02dZ" % divmod(Parcours.n, 60)
        store.ingest_measurements(self.db, "mig-h", [{"task": "plugin:migration", "at": at, "ok": True,
                                                      "data": {"at": at, "steps": [{"id": sid, "state": state, "rc": rc, "started_at": st, "log_tail": list(log)}]}}])

    def test_parcours(self):
        self.assertIsNone(self.c.get("/migration").get_json()["plan"])
        self.assertEqual(self.c.post("/migration/control", json={"action": "start"}).status_code, 409)   # pas de plan
        bad = json.loads(json.dumps(PLAN)); bad["phases"] = []
        self.assertEqual(self.c.put("/migration/plan", json={"plan": bad}).status_code, 400)
        self.assertEqual(self.c.put("/migration/plan", json={"plan": PLAN, "actor": "freg"}).status_code, 200)
        v = self.c.get("/migration").get_json()
        self.assertEqual((v["total"], v["done"], v["next"], v["run"]["state"]), (4, 0, "a1", "arrete"))
        self.assertEqual(v["plan"]["phases"][0]["steps"][1]["missing_vars"], ["PVE_C"])

        # étape 1 : envoyée à l'agent, puis réussie
        r = self.c.post("/migration/control", json={"action": "start", "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json())
        cmds = self.cmds()
        self.assertEqual(len(cmds), 1)
        self.assertEqual((cmds[0][1], cmds[0][2]["action"], cmds[0][2]["step"]["params"]["host"]), ("migstep", "start", "198.51.100.10"))
        self.assertEqual(self.c.post("/migration/control", json={"action": "next"}).status_code, 409)   # une étape tourne déjà
        self.report("a1", "running")
        self.assertEqual(self.c.get("/migration").get_json()["plan"]["phases"][0]["steps"][0]["status"], "en_cours")
        self.report("a1", "done", 0)
        v = self.c.get("/migration").get_json()
        self.assertEqual((v["done"], v["next"]), (1, "a2"))

        # étape 2 : variable vide -> bloquée avant lancement, avec la raison
        r = self.c.post("/migration/control", json={"action": "next"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("PVE_C", r.get_json()["message"])
        st = self.c.get("/migration").get_json()["plan"]["phases"][0]["steps"][1]
        self.assertEqual((st["status"], st["error"]["code"]), ("erreur", "bloque"))
        self.assertEqual(self.c.put("/migration/vars", json={"vars": {"PVE_C": "198.51.100.12", "AUTRE": "x"}}).get_json()["vars"],
                         {"PVE_A": "198.51.100.10", "PVE_C": "198.51.100.12"})
        self.assertEqual(self.c.post("/migration/control", json={"action": "retry", "step": "a2"}).status_code, 200)
        self.report("a2", "failed", 255, ["@@STEP a2", "root@198.51.100.12: Permission denied (publickey)."])
        st = self.c.get("/migration").get_json()["plan"]["phases"][0]["steps"][1]
        self.assertEqual((st["status"], st["error"]["code"], st["error"]["solution"]["kind"]), ("erreur", "ssh-cle", "command"))
        self.assertEqual(self.c.post("/migration/control", json={"action": "skip", "step": "a2"}).status_code, 200)

        # mode automatique : b1 part, réussit, b2 (manuelle) attend « Fait »
        self.assertEqual(self.c.post("/migration/control", json={"action": "auto"}).status_code, 200)
        self.assertEqual(self.c.post("/migration/control", json={"action": "next"}).status_code, 200)
        self.assertEqual(self.cmds()[-1][2]["step"]["id"], "b1")
        self.assertEqual(self.c.post("/migration/control", json={"action": "pause"}).status_code, 200)
        self.assertEqual(self.cmds()[-1][2], {"action": "pause", "id": "b1", "actor": ""})
        self.assertEqual(self.c.post("/migration/control", json={"action": "resume"}).status_code, 200)
        self.assertEqual(self.cmds()[-1][2]["action"], "resume")
        self.report("b1", "done", 0)
        v = self.c.get("/migration").get_json()
        b2 = v["plan"]["phases"][1]["steps"][1]
        self.assertEqual(b2["status"], "manuel")   # lancée d'elle-même par l'automatique
        self.assertEqual(self.c.post("/migration/control", json={"action": "done", "step": "b2"}).status_code, 200)
        v = self.c.get("/migration").get_json()
        self.assertEqual((v["done"], v["total"], v["next"]), (4, 4, None))
        self.assertTrue(any(x["action"] == "sauter" for x in v["log"]))

    def test_refus_agent(self):
        conn = store._connect(self.db)
        try:
            migrun.set_plan(conn, PLAN, "t")
            migrun._set_step(conn, "zz", status="a_faire")
            conn.execute("DELETE FROM mig_steps")
            ok, _m = migrun.control(conn, "retry", "b1", "t")
            self.assertTrue(ok)
            cid = conn.execute("SELECT command_id FROM mig_steps WHERE step_id = 'b1'").fetchone()[0]
            conn.execute("UPDATE commands SET status = 'failed', result = ? WHERE id = ?", (json.dumps({"ok": False, "error": "commande inconnue : migstep"}), cid))
            v = migrun.view(conn)
            b1 = v["plan"]["phases"][1]["steps"][0]
            self.assertEqual((b1["status"], b1["error"]["code"]), ("erreur", "agent-ancien"))
            self.assertIn("agent-ssh.sh", b1["error"]["solution"]["command"])
            conn.execute("DELETE FROM mig_steps"); conn.execute("DELETE FROM mig_plan"); conn.execute("DELETE FROM mig_run")
            conn.commit()
        finally:
            conn.close()

    def test_manuel_devenu_automatique(self):   # B7 « à faire à la main » remplacée par une copie rsync dans le plan réimporté
        conn = store._connect(self.db)
        try:
            migrun.set_plan(conn, PLAN, "t")
            migrun._set_step(conn, "b2", status="manuel")
            migrun._set_step(conn, "a1", status="manuel_fait")
            plan2 = json.loads(json.dumps(PLAN))
            plan2["phases"][1]["steps"][1] = {"id": "b2", "title": "copie", "agent": "mig-h", "kind": "rsync_pull",
                                              "params": {"host": "${PVE_A}", "src": "/var/lib/vz/images/100/", "dest": "/data/img100"}}
            migrun.set_plan(conn, plan2, "t")
            st = dict(conn.execute("SELECT step_id, status FROM mig_steps").fetchall())
            self.assertEqual((st["b2"], st["a1"]), ("a_faire", "manuel_fait"))
            migrun._set_step(conn, "b2", status="manuel")
            migrun.set_plan(conn, PLAN, "t")   # redevenue manuelle : statut inchangé
            self.assertEqual(conn.execute("SELECT status FROM mig_steps WHERE step_id = 'b2'").fetchone()[0], "manuel")
            conn.execute("DELETE FROM mig_steps"); conn.execute("DELETE FROM mig_plan"); conn.execute("DELETE FROM mig_run")
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
