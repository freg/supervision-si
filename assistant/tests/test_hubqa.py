# -*- coding: utf-8 -*-
"""Tests de « Questions sur le hub » (#715) : détection, recherche d'adresses dans un JSON, appariement des
postes, dernier démarrage, catalogue, routes, index construit depuis le dépôt, API avec sources simulées."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ["ASSISTANT_INDEX_AT_START"] = "0"
os.environ.setdefault("ASSISTANT_DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("ASSISTANT_DOCS_DIR", tempfile.mkdtemp())
os.environ.setdefault("ASSISTANT_REPO_DOCS_DIR", tempfile.mkdtemp())
import hubqa  # noqa: E402
import build_hub_index  # noqa: E402

FLEET = {"agents": [
    {"agent_id": "pc-compta-02", "hostname": "PC-COMPTA-02", "label": "Poste comptabilité", "site": "alpha", "os": "Windows 11", "online": "online",
     "last_ip": "192.0.2.42", "summary": {"uptime_seconds": 3 * 86400 + 3600, "host_at": "2026-10-09T10:00:00Z"}},
    {"agent_id": "srv-files", "hostname": "srv-files", "site": "alpha", "os": "Debian 12", "online": "online",
     "summary": {"uptime_seconds": 7200, "host_at": "2026-10-09T10:00:00Z"}},
]}


class Detect(unittest.TestCase):
    def test_intents(self):
        self.assertEqual(hubqa.detect("l'ip 192.0.2.42 est-elle visible quelque part dans le hub ?"), {"intent": "locate", "ips": ["192.0.2.42"], "macs": []})
        self.assertEqual(hubqa.detect("où est la MAC 02-AA-bb-cc-dd-ee ?")["macs"], ["02:aa:bb:cc:dd:ee"])
        self.assertEqual(hubqa.detect("Où trouver le dernier redémarrage du PC-COMPTA-02 ?")["intent"], "boot")
        self.assertEqual(hubqa.detect("quelle API donne les zones DNS ?")["intent"], "api")
        self.assertEqual(hubqa.detect("où sont les onduleurs ?")["intent"], "where")
        self.assertEqual(hubqa.detect("bonjour")["intent"], "other")

    def test_ip_bounds(self):
        self.assertEqual(hubqa.detect("version 1.2.3.4.5 et 300.1.1.1")["intent"], "other")   # ni numéro de version ni octet > 255


class FindInJson(unittest.TestCase):
    def test_exact_subnet_and_context(self):
        doc = {"agents": [{"agent_id": "pc-1", "last_ip": "192.0.2.42"}, {"agent_id": "pc-2", "last_ip": "192.0.2.4"},
                          {"name": "lan", "subnet": "192.0.2.0/24"}, {"name": "rdp", "dst": "192.0.2.42:3389"}]}
        hits = hubqa.find_in_json(doc, ["192.0.2.42"])
        self.assertEqual([h["how"] for h in hits], ["exacte", "sous-réseau 192.0.2.0/24", "exacte"])
        self.assertIn("agent_id=pc-1", hits[0]["context"])
        self.assertEqual(hits[0]["path"], "agents[0].last_ip")
        self.assertFalse(any("pc-2" in h["context"] for h in hits))      # 192.0.2.4 n'est pas 192.0.2.42

    def test_mac_any_writing_and_limit(self):
        doc = [{"mac": "02-AA-BB-CC-DD-EE"}, {"mac": "02:aa:bb:cc:dd:ef"}]
        self.assertEqual(len(hubqa.find_in_json(doc, macs=["02:aa:bb:cc:dd:ee"])), 1)
        many = [{"ip": "198.51.100.7"} for _ in range(30)]
        self.assertEqual(len(hubqa.find_in_json(many, ["198.51.100.7"], limit=5)), 5)


class Hosts(unittest.TestCase):
    def test_match_and_boot(self):
        m = hubqa.match_hosts("dernier reboot du pc PC-COMPTA-02 ?", FLEET["agents"])
        self.assertEqual([a["agent_id"] for a in m], ["pc-compta-02"])
        self.assertEqual(hubqa.match_hosts("redémarrage du poste compta", FLEET["agents"])[0]["agent_id"], "pc-compta-02")
        self.assertEqual(hubqa.match_hosts("reboot de la machine inconnue", FLEET["agents"]), [])
        i = hubqa.boot_info(FLEET["agents"][0])
        self.assertEqual(i["last_boot"], "2026-10-06T09:00:00+00:00")
        self.assertEqual(i["how"], "relevé moins durée de fonctionnement")
        latest = {"host": {"at": "2026-10-09T10:00:00Z", "data": {"system": {"last_boot": "2026-10-06T08:59:30Z", "uptime_seconds": 10, "reboot_required": True}}}}
        j = hubqa.boot_info(FLEET["agents"][0], latest)
        self.assertEqual((j["last_boot"], j["how"], j["reboot_required"]), ("2026-10-06T08:59:30+00:00", "mesure", True))
        txt = hubqa.format_boot([j], "/")
        self.assertIn("PC-COMPTA-02", txt); self.assertIn("redémarrage requis", txt); self.assertIn("/?view=si-agent", txt)
        self.assertIn("Agents connus : PC-COMPTA-02", hubqa.format_boot([], "/", ["PC-COMPTA-02"]))


class CatalogRoutes(unittest.TestCase):
    def test_build_index_from_repo(self):
        root = os.path.dirname(os.path.dirname(HERE))
        idx = build_hub_index.build(root)
        views = {e.get("view") for e in idx["catalog"]}
        self.assertTrue({"si-agent", "ups", "nebula"} <= views)
        self.assertTrue(any(r["module"] == "si-agent" and r["path"] == "/fleet" for r in idx["routes"]))
        hits = hubqa.search_catalog("où sont les onduleurs ?", idx["catalog"], "/")
        self.assertEqual(hits[0]["view"], "ups"); self.assertEqual(hits[0]["link"], "/?view=ups")
        r = hubqa.search_routes("quelle api donne les zones dns ?", idx["routes"])
        self.assertTrue(any(x["module"] == "dns" and x["path"] == "/zones" for x in r))

    def test_parse_routes(self):
        src = 'PREFIX = "/x"\n@app.route(PREFIX + "/items/<int:i>", methods=["GET", "DELETE"])\ndef item(i):\n    """Un élément."""\n'
        self.assertEqual(build_hub_index.parse_routes(src, "m"), [{"module": "m", "path": "/items/<int:i>", "methods": "GET,DELETE", "function": "item", "doc": "Un élément."}])


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as app_mod
        cls.app_mod = app_mod
        cls.client = app_mod.app.test_client()
        app_mod._hub_index = build_hub_index.build(os.path.dirname(os.path.dirname(HERE)))

    def fake_fetch(self, url):
        if url.endswith("/fleet"):
            return FLEET
        if url.endswith("/agents/pc-compta-02/latest"):
            return {"latest": {}}
        if "ipam" in url:
            return [{"ip": "192.0.2.42", "description": "imprimante accueil"}]
        if "dns" in url:
            raise OSError("connexion refusée")
        return {"rien": []}

    def test_locate_and_boot(self):
        r = self.app_mod.hub_ask("l'ip 192.0.2.42 est-elle quelque part ?", fetch=self.fake_fetch)
        srcs = [f["source"] for f in r["data"]["found"]]
        self.assertEqual(sorted(srcs), ["Agents hôtes", "IPAM"])
        self.assertIn("Zones DNS", [e["source"] for e in r["data"]["errors"]])
        self.assertIn("/?view=si-agent", r["answer"])
        b = self.app_mod.hub_ask("dernier redémarrage du PC-COMPTA-02", fetch=self.fake_fetch)
        self.assertEqual(b["intent"], "boot"); self.assertIn("06/10/2026", b["answer"])

    def test_route(self):
        res = self.client.post("/assistant/hub/ask", json={"question": "où sont les onduleurs ?"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("/?view=ups", res.get_json()["answer"])
        self.assertEqual(self.client.post("/assistant/hub/ask", json={}).status_code, 400)
        self.assertGreater(self.client.get("/assistant/hub/sources").get_json()["routes"], 100)


if __name__ == "__main__":
    unittest.main()
