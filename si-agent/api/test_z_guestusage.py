# -*- coding: utf-8 -*-
"""#769 : récapitulatif de l'activité des CT / VM et fiche de paramétrage (jamais de mot de passe)."""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import guestusage as gu  # noqa: E402
import store  # noqa: E402

GU = {"nodes": [{"name": "pve-3", "zone": "distant", "ok": True, "error": None, "guests": [
    {"vmid": 106, "type": "lxc", "name": "ob1", "status": "running", "collected": True, "cpu_avg24": 3.2, "cpu_now": 1.0,
     "web": {"last": {"at": "2026-10-15T10:00:00Z", "ip": "198.51.100.7"}, "hits24": 4, "hits7d": 9, "ips": []},
     "mysql": {"ok": True, "conn7d": 70}, "login": None},
    {"vmid": 110, "type": "lxc", "name": "vieux", "status": "stopped", "collected": False}]},
    {"name": "pve-1", "zone": "distant", "ok": False, "error": "délai", "guests": []}]}
INV = [{"node": "pve-3", "zone": "distant", "vmid": 106, "name": "ob1", "type": "lxc", "status": "running"},
       {"node": "pve-2", "zone": "distant", "vmid": 101, "name": "med10", "type": "lxc", "status": "running", "cpu_pct": 5.0, "ncpu": 2}]


class Assemble(unittest.TestCase):
    def test_assemble(self):
        out = gu.assemble([("a1", "pbs10", "2026-10-15T10:05:00Z", GU)], INV, {("pve-3", 106): {"mysql_user": "modoboa"}})
        keys = [r["key"] for r in out["rows"]]
        self.assertEqual(keys, ["pve-2/101", "pve-3/106", "pve-3/110"])
        r = {x["key"]: x for x in out["rows"]}
        self.assertEqual(r["pve-3/106"]["profile"], {"mysql_user": "modoboa"})
        self.assertEqual((r["pve-3/106"]["cpu"]["avg24"], r["pve-3/106"]["agent_id"]), (3.2, "a1"))
        self.assertEqual((r["pve-2/101"]["source"], r["pve-2/101"]["cpu"]["now"], r["pve-2/101"]["collected"]), ("inventaire", 5.0, False))
        self.assertEqual(out["errors"], [{"node": "pve-1", "agent_id": "a1", "agent": "pbs10", "error": "délai"}])
        self.assertEqual(out["totals"]["collected"], 1)
        self.assertEqual(out["totals"]["profiles"], 1)

    def test_fiche(self):
        p, e = gu.normalize_profile({"unix_accounts": "www-data, deploy", "https_urls": ["https://mail.example.org"], "inconnu": 1, "ignore_ips": "10.0.0.0/24"})
        self.assertIsNone(e)
        self.assertEqual(p, {"unix_accounts": ["www-data", "deploy"], "https_urls": ["https://mail.example.org"], "ignore_ips": ["10.0.0.0/24"]})
        for bad in ({"mysql_password": "x"}, {"owncloud_pass": "x"}, {"token": "x"}):
            p, e = gu.normalize_profile(bad)
            self.assertIsNone(p); self.assertIn("coffre-fort", e)
        self.assertIn("URL", gu.normalize_profile({"owncloud_url": "javascript:alert(1)"})[1])
        self.assertIn("comptes unix", gu.normalize_profile({"unix_accounts": "root; rm -rf /"})[1])


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client()

    def test_routes(self):
        db = appmod.DB_PATH
        store.create_agent(db, "gu-a", "siege", label="gu-a")
        conn = store._connect(db)
        try:
            conn.execute("INSERT INTO measurements (agent_id, task, at, received_at, ok, data) VALUES (?, ?, ?, ?, 1, ?)",
                         ("gu-a", "plugin:guest-usage", "2026-10-15T10:05:00Z", "2026-10-15T10:05:01Z", json.dumps(GU)))
            conn.commit()
        except Exception as e:  # noqa: BLE001
            self.skipTest("insertion directe impossible : %s" % e)
        finally:
            conn.close()
        r = self.c.put("/infra/guests/profile", json={"node": "pve-3", "vmid": 106, "profile": {"unix_accounts": "deploy", "vault_ref": "OB1 / root"}, "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.c.put("/infra/guests/profile", json={"node": "pve-3", "vmid": 106, "profile": {"root_password": "x"}}).status_code, 400)
        self.assertEqual(self.c.put("/infra/guests/profile", json={"node": "../x", "vmid": 106, "profile": {}}).status_code, 400)
        d = self.c.get("/infra/guests").get_json()
        row = next(x for x in d["rows"] if x["key"] == "pve-3/106")
        self.assertEqual(row["profile"]["unix_accounts"], ["deploy"])
        self.assertEqual(row["profile"]["_updated_by"], "freg")
        self.assertNotIn("root_password", json.dumps(d))
        self.assertEqual(self.c.put("/infra/guests/profile", json={"node": "pve-3", "vmid": 106, "profile": {}}).status_code, 200)   # fiche vide = effacée
        d = self.c.get("/infra/guests").get_json()
        self.assertEqual(next(x for x in d["rows"] if x["key"] == "pve-3/106")["profile"], {})


def gu_days(web=(), login=(), mysql=(), rrd=(), weeks=(), deep=False, ok=True):
    return {"nodes": [{"name": "pve-h", "ok": ok, "guests": [{"vmid": 201, "name": "site", "status": "running",
            "days": {"web": list(web), "login": list(login), "mysql": list(mysql), "rrd": list(rrd), "rrd_weeks": list(weeks), "deep": deep}}]}]}


class Activite771(unittest.TestCase):
    """#771 : historique quotidien accumulé à la réception, résumé dans le temps, décision et suivi de migration."""

    def test_fusion(self):
        self.assertEqual(gu.merge_day({"req": 10, "bytes": 5}, {"req": 4, "bytes": 9, "visitors": 1}, "max"), {"req": 10, "bytes": 9, "visitors": 1})
        self.assertEqual(gu.merge_day({"cpu": 9.0}, {"cpu": 2.0}, "replace"), {"cpu": 2.0})
        rows = gu.daily_rows(gu_days(web=[{"day": "2026-10-01", "req": 3, "bytes": "x", "visitors": True}, {"day": "bad", "req": 1}],
                                     weeks=[{"week": "2026-01-05", "cpu": 1.5}]))
        self.assertEqual(rows, [("pve-h", 201, "web", "2026-10-01", {"req": 3}), ("pve-h", 201, "rrdw", "2026-01-05", {"cpu": 1.5})])
        self.assertEqual(gu.daily_rows(gu_days(web=[{"day": "2026-10-01", "req": 3}], ok=False)), [])   # nœud en échec ignoré

    def test_resume(self):
        series = {"web": {"2025-11-03": {"req": 40, "visitors": 3, "bytes": 1000, "bot": 5}, "2026-09-20": {"req": 2, "visitors": 1},
                          "2026-10-10": {"req": 0, "visitors": 0, "bot": 900}},
                  "login": {"2026-03-01": {"logins": 2, "users": 1}},
                  "mysql": {"2026-10-12": {"connections": 0, "questions": 10}},
                  "rrd": {"2026-10-10": {"cpu": 4.0, "netin": 10, "netout": 5}}, "rrdw": {"2025-11-03": {"cpu": 1.0, "netin": 7}}}
        r = gu.summarize(series, "2026-10-16")
        self.assertEqual(r["last_active"], {"web": "2025-11-03", "login": "2026-03-01", "mysql": None, "ssh": None, "sudo": None})   # 2 req. / 10 requêtes : sous les seuils
        self.assertEqual((r["last_any"], r["idle_days"], r["class"]), ("2026-03-01", 229, "inactif"))
        self.assertEqual(r["first_day"], "2025-11-03")
        m = {x["month"]: x for x in r["months"]}
        self.assertEqual((m["2025-11"]["req"], m["2025-11"]["active_days"], m["2025-11"]["cpu"], m["2025-11"]["net"]), (40, 1, 1.0, 7))
        self.assertEqual((m["2026-10"]["bot"], m["2026-10"]["cpu"], m["2026-10"]["net"]), (900, 4.0, 15))
        self.assertEqual(gu.summarize({"web": {"2026-10-14": {"req": 5, "visitors": 2}}}, "2026-10-16")["class"], "actif")
        self.assertEqual(gu.summarize({"web": {"2026-09-01": {"req": 1, "visitors": 1}}}, "2026-10-16")["class"], "inactif")   # relevé, jamais actif
        self.assertEqual(gu.summarize({"rrd": {"2026-10-01": {"cpu": 1.0}}}, "2026-10-16")["class"], "inconnu")               # RRD seul

    def test_decision(self):
        p, e = gu.normalize_profile({"decision": "migrer", "decision_reason": "site encore consulté", "target": "pve10", "planned_for": "2026-11-15",
                                     "migration_status": "planifiee", "decision_by": "direction"})
        self.assertIsNone(e)
        self.assertEqual(p["decision"], "migrer")
        self.assertIsNotNone(gu.normalize_profile({"decision": "supprimer"})[1])
        self.assertIsNotNone(gu.normalize_profile({"planned_for": "15/11/2026"})[1])

    def test_reception_et_routes(self):
        db = appmod.DB_PATH
        store.create_agent(db, "gu-b", "siege", label="gu-b")
        m1 = {"task": "plugin:guest-usage", "at": "2026-10-15T10:00:00Z", "data": gu_days(web=[{"day": "2026-10-15", "req": 3, "visitors": 1}],
                                                                                          rrd=[{"day": "2026-10-15", "cpu": 9.0}])}
        m2 = {"task": "plugin:guest-usage", "at": "2026-10-15T18:00:00Z", "data": gu_days(web=[{"day": "2026-10-15", "req": 2, "visitors": 1, "bytes": 50}],
                                                                                          rrd=[{"day": "2026-10-15", "cpu": 2.0}])}
        bad = {"task": "plugin:guest-usage", "at": "2026-10-15T19:00:00Z", "data": {"nodes": "pas une liste"}}
        store.ingest_measurements(db, "gu-b", [m1, m2, bad])
        conn = store._connect(db)
        try:
            h = gu.history(conn, "pve-h", 201, "2026-01-01")
        finally:
            conn.close()
        self.assertEqual(h["web"], [{"day": "2026-10-15", "req": 3, "visitors": 1, "bytes": 50}])                  # max par champ
        self.assertEqual(h["rrd"], [{"day": "2026-10-15", "cpu": 2.0}])                                              # RRD : dernière valeur
        c = appmod.app.test_client()
        r = c.get("/infra/guests/history?node=pve-h&vmid=201&days=1500").get_json()
        self.assertEqual(r["series"]["web"][0]["req"], 3)
        self.assertEqual(c.get("/infra/guests/history?node=../x&vmid=201").status_code, 400)
        rows = c.get("/infra/guests").get_json()["rows"]
        self.assertTrue(all("activity" in x for x in rows))


if __name__ == "__main__":
    unittest.main()


class Interne777(unittest.TestCase):
    def test_ssh_sudo_comptent_fichiers_indirects(self):
        s = gu.summarize({"ssh": {"2026-09-01": {"logins": 2, "users": 1}}, "sudo": {"2026-09-03": {"cmds": 1}},
                          "files": {"2026-10-10": {"files": 40}}, "mail": {"2026-10-12": {"sent": 3}}}, "2026-10-17")
        self.assertEqual((s["last_any"], s["last_active"]["ssh"], s["last_active"]["sudo"]), ("2026-09-03", "2026-09-01", "2026-09-03"))
        self.assertEqual((s["last_indirect_any"], s["last_indirect"]["files"], s["last_indirect"]["mail"]), ("2026-10-12", "2026-10-10", "2026-10-12"))
        self.assertEqual(s["class"], "dormant")   # les signes indirects ne rendent pas « actif »
        m = {x["month"]: x for x in s["months"]}
        self.assertEqual((m["2026-09"]["ssh_logins"], m["2026-09"]["sudo"], m["2026-10"]["files"], m["2026-10"]["mail_sent"]), (2, 1, 40, 3))

    def test_jours_internes_accumules(self):
        data = {"nodes": [{"name": "pve-a", "ok": True, "guests": [{"vmid": 103, "days": {"ssh": [{"day": "2026-10-15", "logins": 2, "users": 1}],
                                                                                         "files": [{"day": "2026-10-15", "files": 7}]}}]}]}
        rows = gu.daily_rows(data)
        self.assertEqual(sorted((r[2], r[4]) for r in rows), [("files", {"files": 7}), ("ssh", {"logins": 2, "users": 1})])
