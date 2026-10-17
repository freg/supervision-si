# -*- coding: utf-8 -*-
"""#775 : latence des IP publiques -- cibles, points de mesure (agent, direct, indirect), diagnostic, erreurs, parcours."""
import json
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app as appmod  # noqa: E402
import latency as lat  # noqa: E402
import store  # noqa: E402

M_OK = {"ping_ms": 12.0, "ping_loss": 0.0, "tcp": {"443": 13.1},
        "https": {"www.example.org": {"ip": {"dns_ms": 0, "connect_ms": 12.5, "tls_ms": 40.0, "ttfb_ms": 60.0, "total_ms": 115.0, "code": 200, "ok": True},
                                      "name": {"dns_ms": 3, "connect_ms": 12.0, "tls_ms": 41.0, "ttfb_ms": 61.0, "total_ms": 120.0, "code": 200, "ok": True},
                                      "resolved": ["198.51.100.7"]}}}
M_SLOW = {"ping_ms": 12.0, "ping_loss": 0.0, "tcp": {"443": 14.0, "22": None},
          "https": {"www.example.org": {"ip": {"dns_ms": 0, "connect_ms": 13.0, "tls_ms": 7900.0, "ttfb_ms": 60.0, "total_ms": 8000.0, "code": 200, "ok": True},
                                        "resolved": ["203.0.113.9"]}}}


class Pur(unittest.TestCase):
    def test_validate(self):
        t, e = lat.validate_target({"label": "Frontal A", "ip": "198.51.100.7", "ports": "443, 22", "names": "www.example.org"})
        self.assertIsNone(e)
        self.assertEqual((t["id"], t["ports"], t["names"]), ("Frontal-A", [22, 443], ["www.example.org"]))
        for bad in ({"ip": "1.2.3.4; rm"}, {"ip": "198.51.100.7", "ports": [70000]}, {"ip": "198.51.100.7", "names": ["a b"]}):
            self.assertIsNotNone(lat.validate_target(bad)[1], bad)
        p, e = lat.validate_point({"mode": "direct", "agent": "super", "host": "198.51.100.7", "sudo": True})
        self.assertIsNone(e)
        self.assertEqual((p["login"], p["port"], p["id"]), ("francois", 22, "198.51.100.7"))
        self.assertIn("rebond", lat.validate_point({"mode": "indirect", "agent": "super", "host": "h"})[1])
        self.assertIsNone(lat.validate_point({"mode": "indirect", "agent": "super", "host": "10.0.0.5", "jump": "freg@gw.example.org:9922"})[1])
        self.assertIsNotNone(lat.validate_point({"mode": "direct", "agent": "super", "host": "h", "login": "root;id"})[1])
        self.assertIsNotNone(lat.validate_point({"mode": "agent", "agent": ""})[1])

    def test_command_params(self):
        tl = [lat.validate_target({"id": "a", "ip": "198.51.100.7"})[0], lat.validate_target({"id": "b", "ip": "198.51.100.8", "enabled": False})[0]]
        p = lat.validate_point({"mode": "direct", "agent": "super", "host": "h.example.org", "sudo": True})[0]
        params, n = lat.command_params(p, tl)
        self.assertEqual(n, 1)
        self.assertEqual(params["via"], {"login": "francois", "host": "h.example.org", "port": 22, "jump": "", "sudo": True, "key": ""})
        self.assertNotIn("via", lat.command_params(lat.validate_point({"agent": "super"})[0], tl)[0])

    def test_diagnose(self):
        self.assertEqual(lat.diagnose(M_OK, "198.51.100.7"), ("ok", []))
        lvl, notes = lat.diagnose(M_SLOW, "198.51.100.7")
        self.assertEqual(lvl, "critical")
        txt = " ".join(notes)
        self.assertIn("poignée TLS lente (7900 ms", txt)
        self.assertIn("port 22 fermé", txt)
        self.assertIn("résout vers 203.0.113.9", txt)
        self.assertEqual(lat.diagnose({"ping_ms": None, "ping_loss": 100.0, "tcp": {}, "https": {}}, "x")[0], "ok")   # ping filtré seul : information
        self.assertEqual(lat.summarize([(1, M_OK), (2, M_SLOW)])["total_p95"], 8000.0)

    def test_classify(self):
        p = {"login": "francois", "host": "198.51.100.7", "jump": "freg@gw.example.org:9922", "port": 22}
        e = lat.classify(p, "connexion SSH francois@198.51.100.7 impossible : francois@198.51.100.7: Permission denied (publickey).", "super")
        self.assertEqual(e["code"], "ssh-cle")
        self.assertIn("ssh root@super", e["solution"]["command"]); self.assertIn("-J freg@gw.example.org:9922 francois@198.51.100.7", e["solution"]["command"])
        self.assertEqual(lat.classify(p, "sudo: a password is required", "super")["code"], "sudo")
        self.assertEqual(lat.classify(p, "commande inconnue : latency", "super")["code"], "agent-ancien")
        self.assertEqual(lat.classify(p, "missing:curl", "super")["code"], "outils")
        self.assertEqual(lat.classify(p, "SILENCE", "super")["code"], "silence")
        self.assertEqual(lat.classify(p, "quelque chose", "super")["code"], "inconnue")


class Parcours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client()
        cls.db = appmod.DB_PATH
        store.create_agent(cls.db, "lat-a", "siege", label="lat-a")

    def pending(self):
        conn = store._connect(self.db)
        try:
            return [(r[0], json.loads(r[1])) for r in conn.execute("SELECT id, params FROM commands WHERE agent_id = 'lat-a' AND type = 'latency' AND status = 'pending' ORDER BY created_at")]
        finally:
            conn.close()

    def test_parcours(self):
        r = self.c.put("/latency/config", json={"actor": "freg", "settings": {"period_minutes": 15},
                                                 "targets": [{"id": "fa", "label": "Frontal A", "ip": "198.51.100.7", "ports": [443, 22], "names": ["www.example.org"]}],
                                                 "points": [{"id": "lan", "mode": "agent", "agent": "lat-a"},
                                                            {"id": "fa-in", "mode": "direct", "agent": "lat-a", "host": "198.51.100.7", "sudo": True},
                                                            {"id": "bad", "mode": "agent", "agent": "inconnu"}]})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["imported"], {"targets": 1, "points": 3})
        self.assertEqual(self.c.put("/latency/targets", json={"target": {"ip": "x;y"}}).status_code, 400)
        r = self.c.post("/latency/run", json={})
        self.assertEqual(r.get_json()["launched"], 2)   # « bad » : agent inconnu -> échec classé, pas de commande
        cmds = self.pending()
        self.assertEqual(len(cmds), 2)
        via = [p for _i, p in cmds if p.get("via")][0]["via"]
        self.assertEqual((via["login"], via["sudo"]), ("francois", True))
        cid_lan = [i for i, p in cmds if not p.get("via")][0]
        cid_in = [i for i, p in cmds if p.get("via")][0]
        store.ack_command(self.db, "lat-a", cid_lan, {"ok": True, "result": {"host": "lat-a", "missing": [], "targets": {"fa": M_SLOW}}})
        store.ack_command(self.db, "lat-a", cid_in, {"ok": False, "error": "connexion SSH impossible : sudo: a password is required"})
        v = self.c.get("/latency").get_json()
        cell = v["cells"]["fa|lan"]
        self.assertEqual((cell["level"], cell["metrics"]["tls_ms"]), ("critical", 7900.0))
        st = {s["id"]: s for s in v["states"]}
        self.assertEqual((st["lan"]["status"], st["fa-in"]["error"]["code"], st["bad"]["error"]["code"]), ("done", "sudo", "agent-inconnu"))
        h = self.c.get("/latency/history?target=fa&point=lan").get_json()
        self.assertEqual(h["n"], 1)
        exp = self.c.get("/latency/config").get_json()
        self.assertEqual(sorted(p["id"] for p in exp["points"]), ["bad", "fa-in", "lan"])
        self.assertNotIn("updated_by", json.dumps(exp))
        # créneau régulier : une seule commande par point et par période, même si le chien de garde passe plusieurs fois
        conn = store._connect(self.db)
        try:
            n1 = lat.tick(conn, now=1_800_000_000.0); n2 = lat.tick(conn, now=1_800_000_030.0)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual((n1, n2), (2, 0))
        self.assertTrue(self.c.delete("/latency/point/bad").get_json()["ok"])


class Image(unittest.TestCase):
    def test_dockerfile_copie_les_modules(self):
        """Tout module local importé par app.py / store.py est copié dans l'image (vu #774 : migrun oublié, central arrêté)."""
        docker = open(os.path.join(HERE, "Dockerfile")).read()
        mods = set()
        for f in ("app.py", "store.py"):
            mods |= set(re.findall(r"^\s*import ([a-z_][a-z0-9_]*)", open(os.path.join(HERE, f)).read(), re.M))
        local = sorted(m for m in mods if os.path.exists(os.path.join(HERE, m + ".py")))
        missing = [m for m in local if "si-agent/api/%s.py" % m not in docker]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
