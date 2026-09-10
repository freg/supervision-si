# -*- coding: utf-8 -*-
"""Tests de si_agent_import (#437) : logique pure (fiche d'un hôte, champs
GLPI, dédoublonnage, mise à jour, comparaison des flottes) et routes de
glpi-api sous mock (si-agent-api simulé par `requests.get`, GLPI par un
faux client). `python3 -m unittest test_si_agent_import`."""
import os
import unittest
from unittest import mock

os.environ.setdefault("GLPI_BASE_URL", "")
os.environ.setdefault("SI_AGENT_API_URL", "http://si-agent-api.test")

import si_agent_import as sai  # noqa: E402
import app as glpi_app  # noqa: E402
import glpi_client as glpi  # noqa: E402

AGENT = {"agent_id": "srv-01", "hostname": "srv-01", "site": "Arobase-5", "label": "Serveur de fichiers", "os": "Ubuntu 24.04.4 LTS",
         "last_ip": "10.5.0.12", "agent_version": "0.3.1", "last_seen_at": "2026-09-08T09:00:00Z", "online": "online"}
LATEST = {
    "inventory": {"at": "2026-09-08T08:00:00Z", "data": {"agent_version": "0.3.1", "hardware": {
        "serial": "VMware-42 1a", "vendor": "Dell Inc.", "product": "PowerEdge R340", "virtualization": None,
        "cpu": {"model": "Intel(R) Xeon(R) E-2234", "cpus": 8, "hypervisor": None}, "memory_total_bytes": 34359738368,
        "disks": [{"name": "sda", "size": "1.8T", "model": "PERC H330"}, {"name": "sr0", "size": None}],
        "nics": [{"name": "eno1", "mac": "aa:bb:cc:dd:ee:01", "state": "up"}, {"name": "docker0", "mac": "02:42:00:00:00:01"}, {"name": "lo", "mac": "00:00:00:00:00:00"}]}}},
    "host": {"at": "2026-09-08T09:00:00Z", "data": {"system": {"hostname": "srv-01", "kernel": "6.8.0-45-generic", "os": "Ubuntu 24.04.4 LTS"}}},
}


class FakeGlpi:
    """Faux GlpiClient : `existing` = liste d'items Computer, journal
    des créations / mises à jour / dropdowns."""
    def __init__(self, existing=None, agents=None):
        self.existing = existing or []
        self.agents = agents or []
        self.created, self.updated, self.dropdowns = [], [], {}
        self.session_token = "t"

    def get_items(self, itemtype, range_str="0-999", search_text=None):
        if itemtype == "Agent":
            return self.agents
        if itemtype in ("Manufacturer", "ComputerModel", "Location"):
            return [{"id": i, "name": n} for (t, n), i in self.dropdowns.items() if t == itemtype and n == (search_text or {}).get("name")]
        rows = self.existing
        for k, v in (search_text or {}).items():
            rows = [r for r in rows if v.lower() in str(r.get(k) or "").lower()]
        return rows

    def add_item(self, itemtype, fields):
        self.created.append((itemtype, fields))
        return 100 + len(self.created)

    def update_item(self, itemtype, item_id, fields):
        self.updated.append((itemtype, item_id, fields))
        return {}

    def get_or_create_dropdown(self, itemtype, name):
        key = (itemtype, name)
        if key not in self.dropdowns:
            self.dropdowns[key] = 10 + len(self.dropdowns)
        return self.dropdowns[key]

    def kill_session(self):
        self.session_token = None


class PureTests(unittest.TestCase):
    def test_host_facts_and_fields(self):
        f = sai.host_facts(AGENT, LATEST)
        self.assertEqual(f["serial"], "VMware-42 1a")
        self.assertEqual(f["memory"], "32.0 Gio")
        self.assertEqual(f["disks"], ["sda 1.8T (PERC H330)"])
        self.assertEqual(f["nics"], ["eno1 aa:bb:cc:dd:ee:01"])  # docker0 / lo écartés
        fields = sai.build_glpi_fields(f, {"manufacturers_id": 3, "computermodels_id": 4, "locations_id": 5})
        self.assertEqual(fields["name"], "srv-01")
        self.assertEqual(fields["otherserial"], "si-agent:srv-01")
        self.assertEqual(fields["serial"], "VMware-42 1a")
        self.assertEqual((fields["manufacturers_id"], fields["computermodels_id"], fields["locations_id"]), (3, 4, 5))
        self.assertIn("OS : Ubuntu 24.04.4 LTS (noyau 6.8.0-45-generic)", fields["comment"])
        self.assertIn("CPU : Intel(R) Xeon(R) E-2234 ×8", fields["comment"])
        self.assertIn("Dernière IP : 10.5.0.12", fields["comment"])
        self.assertEqual(sai.dropdown_names(f), {"manufacturers_id": ("Manufacturer", "Dell Inc."), "computermodels_id": ("ComputerModel", "PowerEdge R340"),
                                                 "locations_id": ("Location", "Arobase-5")})

    def test_minimal_agent_without_inventory(self):
        f = sai.host_facts({"agent_id": "x1", "hostname": "pc-x", "os": "Debian 12"}, {})
        fields = sai.build_glpi_fields(f)
        self.assertEqual(fields["name"], "pc-x")
        self.assertNotIn("serial", fields)
        self.assertIn("OS : Debian 12", fields["comment"])
        self.assertEqual(sai.dropdown_names(f), {})

    def test_dry_run_lists_candidates_and_dropdowns(self):
        s = sai.import_hosts(FakeGlpi(), [AGENT, {"agent_id": "x1", "hostname": "pc-x", "last_seen_at": "2026-09-08T09:00:00Z"}], {"srv-01": LATEST}, dry_run=True)
        self.assertEqual([c["key"] for c in s["created"]], ["srv-01", "x1"])
        self.assertEqual(s["created"][0]["dropdowns"], {"manufacturers_id": "Dell Inc.", "computermodels_id": "PowerEdge R340", "locations_id": "Arobase-5"})
        self.assertEqual({(d["itemtype"], d["name"]) for d in s["dropdowns"]}, {("Manufacturer", "Dell Inc."), ("ComputerModel", "PowerEdge R340"), ("Location", "Arobase-5")})
        self.assertEqual(len(s["warnings"]), 1)  # x1 sans inventaire
        self.assertEqual(s["skipped_existing"], [])

    def test_dry_run_with_dedup_check(self):
        g = FakeGlpi(existing=[{"id": 7, "name": "SRV-01", "otherserial": ""}])
        s = sai.import_hosts(g, [AGENT], {"srv-01": LATEST}, dry_run=True, check_existing=True)
        self.assertEqual(s["created"], [])
        self.assertIn("id 7, par name", s["skipped_existing"][0])
        s2 = sai.import_hosts(g, [AGENT], {"srv-01": LATEST}, dry_run=True, check_existing=True, update_existing=True)
        self.assertEqual(s2["updated"][0]["glpi_id"], 7)
        self.assertEqual(s2["updated"][0]["matched_by"], "name")

    def test_real_import_creates_with_dropdowns(self):
        g = FakeGlpi()
        s = sai.import_hosts(g, [AGENT], {"srv-01": LATEST}, dry_run=False)
        self.assertEqual(len(g.created), 1)
        itemtype, fields = g.created[0]
        self.assertEqual(itemtype, "Computer")
        self.assertEqual(fields["manufacturers_id"], g.dropdowns[("Manufacturer", "Dell Inc.")])
        self.assertEqual(fields["locations_id"], g.dropdowns[("Location", "Arobase-5")])
        self.assertIn("id GLPI 101", s["created"][0])

    def test_real_import_dedup_and_update(self):
        g = FakeGlpi(existing=[{"id": 9, "name": "autre", "otherserial": "si-agent:srv-01"}])
        s = sai.import_hosts(g, [AGENT], {"srv-01": LATEST}, dry_run=False)
        self.assertEqual(g.created, [])
        self.assertIn("par agent", s["skipped_existing"][0])
        s2 = sai.import_hosts(g, [AGENT], {"srv-01": LATEST}, dry_run=False, update_existing=True)
        self.assertEqual(len(g.updated), 1)
        _t, item_id, fields = g.updated[0]
        self.assertEqual(item_id, 9)
        self.assertNotIn("name", fields)  # jamais renommé
        self.assertIn("mis à jour", s2["updated"][0])

    def test_never_seen_agent_excluded_by_default(self):
        never = {"agent_id": "n1", "hostname": "srv-jamais-vu", "site": "siege"}
        s = sai.import_hosts(FakeGlpi(), [AGENT, never], {"srv-01": LATEST}, dry_run=True)
        self.assertEqual([c["key"] for c in s["created"]], ["srv-01"])
        self.assertIn("jamais vu", s["skipped_excluded"][0])
        s2 = sai.import_hosts(FakeGlpi(), [AGENT, never], {"srv-01": LATEST}, dry_run=True, include_never_seen=True)
        self.assertEqual([c["key"] for c in s2["created"]], ["srv-01", "n1"])

    def test_selection_and_serial_dedup(self):
        g = FakeGlpi(existing=[{"id": 4, "name": "zz", "serial": "VMware-42 1a"}])
        s = sai.import_hosts(g, [AGENT, {"agent_id": "x1", "hostname": "pc-x", "last_seen_at": "2026-09-08T09:00:00Z"}], {"srv-01": LATEST}, dry_run=False, only_agents=["srv-01"])
        self.assertEqual(len(s["skipped_unselected"]), 1)
        self.assertIn("par serial", s["skipped_existing"][0])

    def test_compare_fleets(self):
        glpi_agents = [{"id": 1, "name": "SRV-01.exemple.fr", "deviceid": "srv-01-2026-01-02-03-04-05", "version": "1.11", "last_contact": "2026-09-08 08:00:00", "itemtype": "Computer", "items_id": 7},
                       {"id": 2, "name": None, "deviceid": "poste-42-2025-11-30-10-00-00"}, "junk"]
        si_agents = [AGENT, {"agent_id": "cloud-01", "hostname": "vm", "site": "cloud"}]
        r = sai.compare_fleets(glpi_agents, si_agents)
        self.assertEqual(r["counts"], {"both": 1, "only_si": 1, "only_glpi": 1})
        both = [x for x in r["rows"] if x["status"] == "both"][0]
        self.assertEqual(both["glpi"]["items_id"], 7)
        self.assertEqual(both["si"]["agent_id"], "srv-01")
        self.assertEqual([x["hostname"] for x in r["rows"] if x["status"] == "only_glpi"], ["poste-42-2025-11-30-10-00-00"])
        self.assertEqual(sai.host_key("PC-01-2024-05-03-10-22-41"), "pc-01")


class FakeResp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, str(data)

    def json(self):
        return self._data


def fake_si_agent_get(url, params=None, timeout=None):
    if url.endswith("/fleet"):
        return FakeResp({"agents": [AGENT, {"agent_id": "x1", "hostname": "pc-x", "os": "Debian 12", "last_seen_at": "2026-09-08T09:00:00Z"}]})
    if url.endswith("/agents/srv-01/latest"):
        return FakeResp({"agent_id": "srv-01", "latest": LATEST})
    if url.endswith("/agents/x1/latest"):
        return FakeResp({"error": "agent inconnu"}, 404)
    return FakeResp({"error": "?"}, 404)


class RouteTests(unittest.TestCase):
    def setUp(self):
        glpi_app.app.config["TESTING"] = True
        self.c = glpi_app.app.test_client()

    def test_dry_run_without_glpi(self):
        with mock.patch.object(glpi_app.requests, "get", side_effect=fake_si_agent_get):
            r = self.c.post("/import/si-agent-hosts?dry_run=true", json={})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["dry_run"])
        self.assertEqual(d["source_agent_count"], 2)
        self.assertEqual([c["key"] for c in d["created"]], ["srv-01", "x1"])
        self.assertTrue(any("dédoublonnage non vérifié" in w for w in d["warnings"]))
        self.assertTrue(any("x1 : dernières mesures illisibles" in w for w in d["warnings"]))

    def test_real_import_with_selection(self):
        fake = FakeGlpi()
        with mock.patch.object(glpi_app.requests, "get", side_effect=fake_si_agent_get), mock.patch.object(glpi_app, "_connect", return_value=fake):
            r = self.c.post("/import/si-agent-hosts?dry_run=false", json={"only_agents": ["srv-01"]})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(len(fake.created), 1)
        self.assertEqual(len(d["skipped_unselected"]), 1)
        self.assertIsNone(fake.session_token)  # session fermée

    def test_dry_run_with_glpi_dedup(self):
        fake = FakeGlpi(existing=[{"id": 3, "name": "pc-x"}])
        with mock.patch.object(glpi_app.requests, "get", side_effect=fake_si_agent_get), mock.patch.object(glpi_app, "_connect", return_value=fake), \
                mock.patch.object(glpi_app, "GLPI_BASE_URL", "https://glpi.test/apirest.php"):
            r = self.c.post("/import/si-agent-hosts", json={})
        d = r.get_json()
        self.assertEqual([c["key"] for c in d["created"]], ["srv-01"])
        self.assertIn("id 3", d["skipped_existing"][0])
        self.assertFalse(any("dédoublonnage non vérifié" in w for w in d["warnings"]))

    def test_si_agent_unreachable(self):
        with mock.patch.object(glpi_app.requests, "get", side_effect=glpi_app.requests.ConnectionError("refusé")):
            r = self.c.post("/import/si-agent-hosts", json={})
        self.assertEqual(r.status_code, 502)
        self.assertIn("si-agent-api", r.get_json()["error"])

    def test_manage_right_enforced(self):
        with mock.patch.object(glpi_app, "RIGHTS_API_URL", "http://rights.test"), \
                mock.patch.object(glpi_app.requests, "post", return_value=FakeResp({"allowed": False})):
            r = self.c.post("/import/si-agent-hosts", json={"groups": ["invites"]})
        self.assertEqual(r.status_code, 403)

    def test_agents_comparison(self):
        fake = FakeGlpi(agents=[{"id": 1, "name": "srv-01", "deviceid": "srv-01-2026-01-02-03-04-05", "version": "1.11"}])
        with mock.patch.object(glpi_app.requests, "get", side_effect=fake_si_agent_get), mock.patch.object(glpi_app, "_connect", return_value=fake):
            r = self.c.get("/agents-comparison")
        d = r.get_json()
        self.assertEqual(d["counts"], {"both": 1, "only_si": 1, "only_glpi": 0})
        self.assertIsNone(d["glpi_error"])
        # GLPI non configuré : la flotte si-agent seule, l'erreur GLPI en clair, jamais un 500
        with mock.patch.object(glpi_app.requests, "get", side_effect=fake_si_agent_get):
            r = self.c.get("/agents-comparison")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertIn("GLPI_BASE_URL", d["glpi_error"])
        self.assertEqual(d["counts"]["only_si"], 2)


if __name__ == "__main__":
    unittest.main()
