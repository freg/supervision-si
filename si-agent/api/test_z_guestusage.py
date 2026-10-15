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


if __name__ == "__main__":
    unittest.main()
