"""Routes des sondes distribuées sur netprobe-api (livraison #406) --
`app.test_client()` avec un scénario complet : création de la flotte,
provisionnement, flotte signée du collecteur, ingestion de lots signés
(collecteur puis sonde directe), déduplication, périmètre de site,
lectures pour le hub.

Lancer depuis netprobe/api : NETPROBE_DB_PATH=/tmp/x.db python3 -m unittest test_agents_routes
(le fichier fixe lui-même une base temporaire s'il est lancé tel quel)."""
import json
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ.setdefault("NETPROBE_DB_PATH", os.path.join(_tmp, "netprobe-test.db"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))

import app as appmod  # noqa: E402
import agents_store  # noqa: E402
from netprobe_agent import protocol  # noqa: E402


def signed_headers(device_id, secret, method, path, body_bytes=b""):
    return protocol.auth_headers(device_id, secret, method, path, body_bytes)


class AgentsRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = appmod.app.test_client()
        cls.db = appmod.DB_PATH

    def setUp(self):
        # Base propre entre les tests -- la table est petite, on repart de zéro.
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM agent_measurements"); conn.execute("DELETE FROM probe_agents"); conn.commit(); conn.close()

    def create(self, agent_id, role="probe", site="alpha", tasks=None, label=None):
        r = self.client.post("/agents", json={"agent_id": agent_id, "role": role, "site": site, "tasks": tasks, "label": label})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def post_signed(self, device_id, secret, path, body):
        raw = protocol.canonical_json(body)
        return self.client.post(path, data=raw, headers=signed_headers(device_id, secret, "POST", path, raw),
                                content_type="application/json")

    # -- flotte ----------------------------------------------------------
    def test_create_list_get_update_delete(self):
        created = self.create("alpha-sonde-01", tasks=[{"type": "wifi_link", "every": 30}], label="Accueil")
        self.assertIn("secret", created, "le secret est renvoyé à la création")
        self.assertTrue(len(created["secret"]) >= 32)
        listed = self.client.get("/agents?site=alpha").get_json()["agents"]
        self.assertEqual([a["agent_id"] for a in listed], ["alpha-sonde-01"])
        self.assertNotIn("secret", listed[0], "jamais de secret en liste")
        got = self.client.get("/agents/alpha-sonde-01").get_json()
        self.assertEqual(got["tasks"], [{"type": "wifi_link", "every": 30}])
        self.assertNotIn("secret", got)
        v1 = got["tasks_version"]
        upd = self.client.put("/agents/alpha-sonde-01", json={"tasks": [{"type": "sys", "every": 60}], "label": "Accueil RDC"}).get_json()
        self.assertEqual(upd["label"], "Accueil RDC")
        self.assertNotEqual(upd["tasks_version"], v1, "changer les tâches change la version")
        same = self.client.put("/agents/alpha-sonde-01", json={"label": "Accueil RDC"}).get_json()
        self.assertEqual(same["tasks_version"], upd["tasks_version"], "changer le libellé ne change pas la version des tâches")
        self.assertEqual(self.client.put("/agents/inconnue", json={}).status_code, 404)
        self.assertEqual(self.client.delete("/agents/alpha-sonde-01").status_code, 200)
        self.assertEqual(self.client.get("/agents/alpha-sonde-01").status_code, 404)

    def test_create_validation(self):
        self.assertEqual(self.client.post("/agents", json={"agent_id": "a b", "site": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/agents", json={"agent_id": "-x", "site": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/agents", json={"agent_id": "ok", "site": ""}).status_code, 400)
        self.assertEqual(self.client.post("/agents", json={"agent_id": "ok", "site": "x", "role": "roi"}).status_code, 400)
        self.create("ok")
        r = self.client.post("/agents", json={"agent_id": "ok", "site": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("déjà", r.get_json()["error"])

    def test_provision_and_rotate(self):
        s = self.create("alpha-sonde-02", tasks=[{"type": "ping", "every": 60, "params": {"host": "10.0.0.1"}}])
        c = self.create("alpha-collecteur-01", role="collector")
        p = self.client.get("/agents/alpha-sonde-02/provision?collector_url=http://192.168.10.20:6127").get_json()
        self.assertEqual(p["secret"], s["secret"])
        self.assertEqual(p["collector_url"], "http://192.168.10.20:6127")
        self.assertEqual(p["default_tasks"][0]["type"], "ping")
        self.assertEqual(p["interface"], "wlan0")
        pc = self.client.get("/agents/alpha-collecteur-01/provision?central_url=https://vm:6443/api/netprobe").get_json()
        self.assertEqual(pc["collector_id"], "alpha-collecteur-01")
        self.assertEqual(pc["secret"], c["secret"])
        self.assertEqual(pc["port"], 6127)
        rot = self.client.post("/agents/alpha-sonde-02/rotate-secret").get_json()
        self.assertNotEqual(rot["secret"], s["secret"])
        self.assertEqual(self.client.get("/agents/alpha-sonde-02/provision").get_json()["secret"], rot["secret"])
        self.assertEqual(self.client.post("/agents/nope/rotate-secret").status_code, 404)

    # -- flotte signée pour le collecteur ---------------------------------
    def test_fleet_requires_collector_signature_and_site_scope(self):
        s1 = self.create("alpha-sonde-01", tasks=[{"type": "sys", "every": 60}])
        self.create("alpha-sonde-off"); self.client.put("/agents/alpha-sonde-off", json={"active": False})
        self.create("autre-sonde", site="autre")
        c = self.create("alpha-collecteur-01", role="collector")
        path = "/fleet?site=alpha"
        r = self.client.get(path, headers=signed_headers(c["agent_id"], c["secret"], "GET", path))
        self.assertEqual(r.status_code, 200, r.get_json())
        fleet = r.get_json()
        self.assertEqual(sorted(fleet["agents"]), ["alpha-sonde-01"], "actives du site seulement, pas le collecteur")
        self.assertEqual(fleet["agents"]["alpha-sonde-01"]["secret"], s1["secret"])
        self.assertEqual(fleet["agents"]["alpha-sonde-01"]["tasks"], [{"type": "sys", "every": 60}])
        self.assertTrue(fleet["version"])
        # Autre site : refusé
        path2 = "/fleet?site=autre"
        r = self.client.get(path2, headers=signed_headers(c["agent_id"], c["secret"], "GET", path2))
        self.assertEqual(r.status_code, 403)
        # Une sonde ne peut pas demander la flotte
        path3 = "/fleet?site=alpha"
        r = self.client.get(path3, headers=signed_headers(s1["agent_id"], s1["secret"], "GET", path3))
        self.assertEqual(r.status_code, 401)
        # Mauvais secret / pas d'en-têtes
        r = self.client.get(path, headers=signed_headers(c["agent_id"], "faux", "GET", path))
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get(path).status_code, 401)
        # Sans ?site= : le site du collecteur
        r = self.client.get("/fleet", headers=signed_headers(c["agent_id"], c["secret"], "GET", "/fleet"))
        self.assertEqual(r.get_json()["site"], "alpha")

    # -- ingestion --------------------------------------------------------
    def test_bulk_ingest_by_collector(self):
        s1 = self.create("alpha-sonde-01"); s2 = self.create("alpha-sonde-02")
        self.create("autre-sonde", site="autre")
        c = self.create("alpha-collecteur-01", role="collector")
        body = {"site": "alpha", "collector_id": c["agent_id"], "measurements": [
            {"agent_id": "alpha-sonde-01", "task": "wifi_link", "at": "2026-09-06T10:00:00Z", "ok": True, "data": {"bssid": "aa", "signal_dbm": -60}},
            {"agent_id": "alpha-sonde-01", "task": "wifi_link", "at": "2026-09-06T10:00:30Z", "ok": True, "data": {"bssid": "aa", "signal_dbm": -62}},
            {"agent_id": "alpha-sonde-02", "task": "ping:10.0.0.1", "at": "2026-09-06T10:00:00Z", "ok": False, "error": "100% perte"},
            {"agent_id": "alpha-sonde-01", "task": "wifi_link", "at": "2026-09-06T10:00:00Z", "ok": True},   # doublon
            {"agent_id": "autre-sonde", "task": "sys", "at": "2026-09-06T10:00:00Z"},                           # hors site
            {"agent_id": "fantome", "task": "sys", "at": "2026-09-06T10:00:00Z"},                               # inconnue
            {"task": "sys", "at": ""},                                                                          # invalide
        ]}
        r = self.post_signed(c["agent_id"], c["secret"], "/agents/measurements/bulk", body)
        self.assertEqual(r.status_code, 200, r.get_json())
        out = r.get_json()
        self.assertEqual((out["accepted"], out["duplicates"], len(out["rejected"])), (3, 1, 3))
        reasons = " ".join(x["error"] for x in out["rejected"])
        self.assertIn("hors du site", reasons); self.assertIn("inconnue", reasons); self.assertIn("forme invalide", reasons)
        # Dernier contact : sondes vues VIA le collecteur, collecteur vu en direct
        a1 = self.client.get("/agents/alpha-sonde-01").get_json()
        self.assertEqual(a1["last_seen_via"], "alpha-collecteur-01")
        self.assertIsNotNone(a1["last_seen_at"])
        self.assertEqual(self.client.get("/agents/alpha-collecteur-01").get_json()["last_seen_via"], "direct")
        # Lectures
        ms = self.client.get("/agents/alpha-sonde-01/measurements?task=wifi_link").get_json()["measurements"]
        self.assertEqual([m["at"] for m in ms], ["2026-09-06T10:00:30Z", "2026-09-06T10:00:00Z"], "plus récente d'abord")
        self.assertEqual(ms[0]["data"]["signal_dbm"], -62)
        self.assertEqual(ms[0]["via"], "alpha-collecteur-01")
        since = self.client.get("/agents/alpha-sonde-01/measurements?since=2026-09-06T10:00:30Z").get_json()["measurements"]
        self.assertEqual(len(since), 1)
        latest = self.client.get("/agents/latest?site=alpha").get_json()["latest"]
        self.assertEqual([(m["agent_id"], m["task"], m["at"]) for m in latest],
                         [("alpha-sonde-01", "wifi_link", "2026-09-06T10:00:30Z"), ("alpha-sonde-02", "ping:10.0.0.1", "2026-09-06T10:00:00Z")])
        self.assertEqual(self.client.get("/agents/latest?site=autre").get_json()["latest"], [])
        self.assertEqual(self.client.get("/agents/nope/measurements").status_code, 404)

    def test_bulk_ingest_by_probe_is_limited_to_itself(self):
        s1 = self.create("alpha-sonde-01"); self.create("alpha-sonde-02")
        body = {"measurements": [
            {"agent_id": "alpha-sonde-02", "task": "sys", "at": "2026-09-06T10:00:00Z", "data": {"load1": 1}},   # usurpation
            {"task": "sys", "at": "2026-09-06T10:00:01Z", "data": {"load1": 2}},
        ]}
        r = self.post_signed(s1["agent_id"], s1["secret"], "/agents/measurements/bulk", body)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["accepted"], 2)
        ms = self.client.get("/agents/alpha-sonde-01/measurements").get_json()["measurements"]
        self.assertEqual(len(ms), 2, "les deux sont attribuées à la sonde signataire")
        self.assertTrue(all(m["via"] == "direct" for m in ms))
        self.assertEqual(self.client.get("/agents/alpha-sonde-02/measurements").get_json()["measurements"], [])

    def test_bulk_ingest_rejections(self):
        s1 = self.create("alpha-sonde-01")
        self.client.put("/agents/alpha-sonde-01", json={"active": False})
        r = self.post_signed(s1["agent_id"], s1["secret"], "/agents/measurements/bulk", {"measurements": []})
        self.assertEqual(r.status_code, 401, "sonde désactivée : signature refusée")
        self.client.put("/agents/alpha-sonde-01", json={"active": True})
        r = self.post_signed(s1["agent_id"], s1["secret"], "/agents/measurements/bulk", {"measurements": "non"})
        self.assertEqual(r.status_code, 400)
        r = self.post_signed(s1["agent_id"], s1["secret"], "/agents/measurements/bulk", {"measurements": [{"task": "", "at": ""}]})
        self.assertEqual(r.status_code, 400)
        raw = protocol.canonical_json({"measurements": []})
        h = signed_headers(s1["agent_id"], s1["secret"], "POST", "/agents/measurements/bulk", raw)
        r = self.client.post("/agents/measurements/bulk", data=raw + b" ", headers=h, content_type="application/json")
        self.assertEqual(r.status_code, 401, "corps altéré après signature")
        r = self.client.post("/agents/measurements/bulk", json={"measurements": []})
        self.assertEqual(r.status_code, 401, "sans signature")

    def test_delete_with_purge(self):
        s1 = self.create("alpha-sonde-01")
        self.post_signed(s1["agent_id"], s1["secret"], "/agents/measurements/bulk",
                         {"measurements": [{"task": "sys", "at": "2026-09-06T10:00:00Z"}]})
        self.assertEqual(self.client.delete("/agents/alpha-sonde-01?purge=true").get_json()["measurements_purged"], True)
        self.assertEqual(agents_store.list_measurements(self.db, "alpha-sonde-01"), [])


if __name__ == "__main__":
    unittest.main()
