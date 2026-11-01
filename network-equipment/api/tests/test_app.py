# -*- coding: utf-8 -*-
"""Tests de l'API (#506) avec un faux snmp-api / network-agent /
coffre : scénarios réalistes (import exploration, import Zenoss CSV et
JSON, identification SNMP d'un vieux Catalyst et d'un MikroTik, voisins,
table MAC, relevé de profil, choix manuels). `requests` est remplacé par
un simulateur : aucun appel réseau, aucune communauté ne transite dans
les assertions."""
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

_TMP = tempfile.mkdtemp()
os.environ["NETWORK_EQUIPMENT_DATA_DIR"] = _TMP
os.environ["SNMP_API_INTERNAL_URL"] = "http://snmp-api:5000"
os.environ["NETWORK_AGENT_API_URL"] = "http://198.51.100.10:15000"
os.environ["CREDENTIALS_API_URL"] = "http://credentials-api:5000"
os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "jeton-de-test"

import app as appmod  # noqa: E402


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


# --- simulateur : un vieux Catalyst 2950 (192.0.2.2) et un MikroTik (192.0.2.1)
CATALYST = {
    "system": {"sysDescr": "Cisco Internetwork Operating System Software IOS (tm) C2950 Software (C2950-I6Q4L2-M), Version 12.1(22)EA14, RELEASE SOFTWARE (fc1)",
               "sysName": "sw-alpha", "sysUpTime": "123", "sysContact": "", "sysLocation": "Batiment 5"},
    "oid": "1.3.6.1.4.1.9.1.359",
    "walks": {
        "1.3.6.1.2.1.47.1.1.1.1": [{"oid": "1.3.6.1.2.1.47.1.1.1.1.5.1", "value": "3"}, {"oid": "1.3.6.1.2.1.47.1.1.1.1.13.1", "value": "WS-C2950-24"},
                                   {"oid": "1.3.6.1.2.1.47.1.1.1.1.11.1", "value": "FOC0000AAAA"}, {"oid": "1.3.6.1.2.1.47.1.1.1.1.12.1", "value": "Cisco Systems, Inc."}],
        "1.3.6.1.2.1.31.1.1.1.1": [{"oid": "1.3.6.1.2.1.31.1.1.1.1.1", "value": "Fa0/1"}, {"oid": "1.3.6.1.2.1.31.1.1.1.1.24", "value": "Fa0/24"}],
        "1.0.8802.1.1.2.1.4.1.1": [],
        "1.3.6.1.4.1.9.9.23.1.2.1.1": [{"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.4.24.1", "value": "0xc0000201"}, {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.6.24.1", "value": "rtr-alpha"},
                                       {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.7.24.1", "value": "ether1"}, {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.8.24.1", "value": "MikroTik"}],
        "1.3.6.1.2.1.17.1.4.1.2": [{"oid": "1.3.6.1.2.1.17.1.4.1.2.1", "value": "1"}, {"oid": "1.3.6.1.2.1.17.1.4.1.2.24", "value": "24"}],
        "1.3.6.1.2.1.17.4.3.1.2": [{"oid": "1.3.6.1.2.1.17.4.3.1.2.76.94.12.1.2.3", "value": "24"}, {"oid": "1.3.6.1.2.1.17.4.3.1.2.0.80.86.1.2.3", "value": "1"}],
        "1.3.6.1.2.1.17.7.1.2.2.1.2": [],
        "1.3.6.1.4.1.9.9.109.1.1.1.1.8": [{"oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.8.1", "value": "12"}],
        "1.3.6.1.4.1.9.9.48.1.1.1.5": [{"oid": "1.3.6.1.4.1.9.9.48.1.1.1.5.1", "value": "3000"}],
        "1.3.6.1.4.1.9.9.48.1.1.1.6": [{"oid": "1.3.6.1.4.1.9.9.48.1.1.1.6.1", "value": "1000"}],
        "1.3.6.1.4.1.9.9.48.1.1.1.2": [{"oid": "1.3.6.1.4.1.9.9.48.1.1.1.2.1", "value": "Processor"}],
        "1.3.6.1.4.1.9.9.13.1.3.1.3": [], "1.3.6.1.4.1.9.9.13.1.3.1.6": [], "1.3.6.1.4.1.9.9.13.1.4.1.3": [{"oid": "1.3.6.1.4.1.9.9.13.1.4.1.3.1", "value": "1"}],
        "1.3.6.1.4.1.9.9.13.1.5.1.3": [{"oid": "1.3.6.1.4.1.9.9.13.1.5.1.3.1", "value": "3"}],
    },
    "gets": {"1.3.6.1.4.1.9.2.1.58.0": "11", "1.3.6.1.4.1.9.2.1.57.0": "9"},
    "interfaces": [{"ifDescr": "FastEthernet0/1", "ifOperStatus": "up", "ifSpeed": "100000000"}],
}
MIKROTIK = {
    "system": {"sysDescr": "RouterOS RB5009UG+S+", "sysName": "rtr-alpha", "sysUpTime": "5", "sysContact": "", "sysLocation": ""},
    "oid": "1.3.6.1.4.1.14988.1",
    "walks": {"1.3.6.1.2.1.47.1.1.1.1": [], "1.3.6.1.2.1.31.1.1.1.1": [{"oid": "1.3.6.1.2.1.31.1.1.1.1.1", "value": "ether1"}],
              "1.0.8802.1.1.2.1.4.1.1": [{"oid": "1.0.8802.1.1.2.1.4.1.1.5.0.1.1", "value": "0x0010a6010203"}, {"oid": "1.0.8802.1.1.2.1.4.1.1.9.0.1.1", "value": "sw-alpha"},
                                         {"oid": "1.0.8802.1.1.2.1.4.1.1.7.0.1.1", "value": "Fa0/24"}],
              "1.3.6.1.4.1.9.9.23.1.2.1.1": [], "1.3.6.1.2.1.17.1.4.1.2": [], "1.3.6.1.2.1.17.4.3.1.2": [], "1.3.6.1.2.1.17.7.1.2.2.1.2": []},
    "gets": {}, "interfaces": [],
}
DEVICES = {"192.0.2.2": CATALYST, "192.0.2.1": MIKROTIK}
CALLS = []


def fake_post(url, json=None, timeout=None):
    CALLS.append(("POST", url, dict(json or {})))
    body = json or {}
    host = body.get("host")
    if body.get("target_id") == 7:
        host = "192.0.2.2"
    dev = DEVICES.get(host)
    if dev is None:
        return FakeResp(502, {"error": "délai dépassé (5s) -- cible injoignable"})
    if body.get("community") == "mauvaise":
        return FakeResp(502, {"error": "No SNMP response received before timeout"})
    if url.endswith("/query"):
        return FakeResp(200, {"host": host, "system": dev["system"]})
    if url.endswith("/get"):
        values = {}
        for oid in body.get("oids") or []:
            values[oid] = dev["oid"] if oid == "1.3.6.1.2.1.1.2.0" else dev["gets"].get(oid)
        return FakeResp(200, {"values": values})
    if url.endswith("/walk"):
        rows = dev["walks"].get(body.get("oid"))
        if rows is None:
            return FakeResp(200, {"rows": [], "truncated": False})
        return FakeResp(200, {"rows": rows, "truncated": False})
    if url.endswith("/walk-interfaces"):
        return FakeResp(200, {"interfaces": dev["interfaces"]})
    return FakeResp(404, {"error": "route inconnue"})


def fake_get(url, params=None, timeout=None, headers=None):
    CALLS.append(("GET", url, dict(params or {})))
    if "/credentials/reveal/" in url:
        name = url.rsplit("/", 1)[1]
        if headers.get("X-Credentials-Token") != "jeton-de-test":
            return FakeResp(404, {})
        if name == "snmp-lan":
            return FakeResp(200, {"username": "snmp", "password": "communaute-secrete"})
        return FakeResp(404, {"error": "absent"})
    if url.endswith("/devices/services"):
        return FakeResp(200, [{"device_id": 1, "protocol": "tcp", "port": 8291}, {"device_id": 1, "protocol": "tcp", "port": 22}, {"device_id": 2, "protocol": "tcp", "port": 23}])
    if url.endswith("/devices"):
        return FakeResp(200, [
            {"id": 1, "mac_address": "4c:5e:0c:01:02:03", "ip_address": "192.0.2.1", "hostname": "rtr-alpha", "role_hint": "gateway"},
            {"id": 2, "mac_address": "00:10:a6:01:02:03", "ip_address": "192.0.2.2", "hostname": None, "role_hint": None},
            {"id": 3, "mac_address": "00:50:56:01:02:03", "ip_address": "192.0.2.50", "hostname": "vm-bob", "role_hint": None},
            {"id": 4, "mac_address": "pas-une-mac", "ip_address": "192.0.2.51"},
        ])
    return FakeResp(404, {})


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        appmod.requests.post = fake_post
        appmod.requests.get = fake_get
        cls.client = appmod.app.test_client()

    def setUp(self):
        CALLS.clear()

    def test_01_status_and_import_exploration(self):
        r = self.client.get("/status")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["snmp_api"])
        self.assertGreater(r.get_json()["oui"]["seed"], 300)
        r = self.client.post("/import/network-agent", json={})
        self.assertEqual(r.status_code, 200, r.get_json())
        c = r.get_json()
        self.assertEqual((c["seen"], c["created"], c["skipped"]), (4, 3, 1))
        rows = self.client.get("/equipment").get_json()["equipment"]
        by_ip = {e["ip"]: e for e in rows}
        self.assertEqual(by_ip["192.0.2.1"]["vendor"], "MikroTik")
        self.assertEqual(by_ip["192.0.2.1"]["kind"], "routeur")
        self.assertEqual(by_ip["192.0.2.1"]["ports"], [22, 8291])
        self.assertEqual(by_ip["192.0.2.2"]["vendor"], "Cisco")
        self.assertEqual(by_ip["192.0.2.2"]["kind"], "équipement réseau")
        self.assertEqual(by_ip["192.0.2.50"]["kind"], "hôte")
        self.assertIsNone(by_ip["192.0.2.50"]["vendor"])
        # ré-import : rien de créé en double
        c2 = self.client.post("/import/network-agent", json={}).get_json()
        self.assertEqual((c2["created"], c2["updated"]), (0, 3))

    def test_02_zenoss_csv_and_json(self):
        csv_text = "Device,IP,Device Class,Prod State\nsw-alpha,192.0.2.2,/Network/Switch/Cisco,Production\nups-1,192.0.2.9,/Power/UPS/APC,Production\n"
        r = self.client.post("/import/zenoss", data={"file": (io.BytesIO(csv_text.encode("utf-8")), "devices.csv"), "dry_run": "1"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertTrue(body["dry_run"])
        self.assertEqual(body["parsed"], 2)
        self.assertEqual(body["preview"][1]["kind"], "onduleur")
        r = self.client.post("/import/zenoss", data={"file": (io.BytesIO(csv_text.encode("utf-8")), "devices.csv")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.get_json()["created"], r.get_json()["updated"]), (1, 1))  # sw-alpha rapproché par IP
        sw = [e for e in self.client.get("/equipment").get_json()["equipment"] if e["ip"] == "192.0.2.2"][0]
        self.assertEqual(sw["name"], "sw-alpha")
        self.assertEqual(sw["kind"], "switch")
        self.assertEqual(sw["zenoss_class"], "/Network/Switch/Cisco")
        js = {"devices": [{"id": "rtr-alpha", "manageIp": "192.0.2.1", "device_class": "/Network/Router/MikroTik", "hw_product": "RB5009UG+S+",
                           "snmp_descr": "RouterOS RB5009UG+S+", "snmp_oid": "1.3.6.1.4.1.14988.1", "serial": "ABC123",
                           "interfaces": [{"id": "ether1", "mac": "4C:5E:0C:01:02:03", "ips": ["192.0.2.1/24"]}]}]}
        r = self.client.post("/import/zenoss", json={"content": json.dumps(js), "filename": "zenoss.json"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["format"], "json")
        self.assertEqual(r.get_json()["updated"], 1)
        rt = [e for e in self.client.get("/equipment").get_json()["equipment"] if e["ip"] == "192.0.2.1"][0]
        self.assertEqual(rt["model"], "RB5009UG+S+")
        self.assertEqual(rt["serial"], "ABC123")
        self.assertEqual(rt["generation"], "recent")
        self.assertIn("zenoss", rt["sources"])
        r = self.client.post("/import/zenoss", json={"content": "n'importe quoi"})
        self.assertEqual(r.status_code, 400)

    def test_03_identify_snmp_old_catalyst(self):
        sw = [e for e in self.client.get("/equipment").get_json()["equipment"] if e["ip"] == "192.0.2.2"][0]
        # sans accès : erreur claire
        r = self.client.post("/equipment/%d/identify" % sw["id"], json={})
        self.assertEqual(r.status_code, 502)
        self.assertIn("aucun accès SNMP", r.get_json()["error"])
        # via le coffre (genre snmp) : la communauté ne sort jamais de la réponse
        r = self.client.post("/equipment/%d/identify" % sw["id"], json={"credential": "snmp-lan"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertNotIn("communaute-secrete", json.dumps(body))
        ident = body["identification"]
        self.assertEqual(ident["vendor"], "Cisco")
        self.assertEqual(ident["model"], "WS-C2950-24")  # ENTITY-MIB prime sur la famille
        self.assertEqual(ident["serial"], "FOC0000AAAA")
        self.assertEqual(ident["kind"], "switch")
        self.assertEqual(ident["generation"], "ancien")
        self.assertIn("C2950", ident["generation_reason"])
        self.assertEqual(body["equipment"]["snmp_credential"], "snmp-lan")
        self.assertEqual(body["equipment"]["profile_id"], "cisco-ios")
        self.assertEqual(body["fdb"], 2)
        cdp = [n for n in body["equipment"]["neighbors"] if n["protocol"] == "cdp"]
        self.assertEqual(len(cdp), 1)
        self.assertEqual(cdp[0]["local_port"], "Fa0/24")
        self.assertEqual(cdp[0]["remote_address"], "192.0.2.1")
        self.assertIsNotNone(cdp[0]["remote_equipment_id"])  # rapproché par nom/IP au MikroTik
        # la communauté a bien été transmise à snmp-api, jamais journalisée ici
        posted = [c for c in CALLS if c[0] == "POST" and c[1].endswith("/query")]
        self.assertEqual(posted[0][2]["community"], "communaute-secrete")
        # table MAC : où est le MikroTik ?
        r = self.client.get("/where-is?mac=4c:5e:0c:01:02:03")
        self.assertEqual(r.get_json()["seen_on"][0]["port"], "Fa0/24")
        r = self.client.get("/equipment/%d/fdb" % sw["id"])
        fdb = r.get_json()["fdb"]
        self.assertEqual(len(fdb), 2)
        known = [f for f in fdb if f["known"]]
        self.assertEqual(len(known), 2)

    def test_04_identify_mikrotik_by_target_and_topology(self):
        rt = [e for e in self.client.get("/equipment").get_json()["equipment"] if e["ip"] == "192.0.2.1"][0]
        r = self.client.post("/equipment/%d/identify" % rt["id"], json={"community": "mauvaise"})
        self.assertEqual(r.status_code, 502)
        self.assertIn("No SNMP response", r.get_json()["error"])
        self.assertIn("No SNMP response", self.client.get("/equipment/%d" % rt["id"]).get_json()["last_identify_error"])
        r = self.client.post("/equipment/%d/identify" % rt["id"], json={"community": "publique-ponctuelle"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["identification"]["model"], "RB5009UG+S+")
        self.assertEqual(body["equipment"]["profile_id"], "mikrotik")
        self.assertIsNone(body["equipment"]["last_identify_error"])
        self.assertIsNone(body["equipment"].get("snmp_credential"))  # communauté ponctuelle : rien de persistant
        lldp = [n for n in body["equipment"]["neighbors"] if n["protocol"] == "lldp"]
        self.assertEqual(lldp[0]["remote_chassis"], "00:10:A6:01:02:03")
        self.assertIsNotNone(lldp[0]["remote_equipment_id"])
        topo = self.client.get("/topology").get_json()
        self.assertGreaterEqual(len(topo["links"]), 1)
        self.assertTrue(any(l["protocol"] in ("lldp", "cdp") for l in topo["links"]))
        pairs = [tuple(sorted((l["from"], l["to"]))) for l in topo["links"]]
        self.assertEqual(len(pairs), len(set(pairs)))  # un seul lien par paire, même vu des deux côtés
        self.assertEqual(len(topo["nodes"]), 3)  # switch, routeur (LLDP/CDP) et la VM apprise seule sur Fa0/1 (table MAC)
        self.assertTrue(any(l["protocol"] == "fdb" and l["local_port"] == "Fa0/1" for l in topo["links"]))
        detail = self.client.get("/equipment/%d" % rt["id"]).get_json()
        self.assertEqual(detail["profile"]["id"], "mikrotik")
        self.assertGreaterEqual(len(detail["history"]), 2)
        self.assertEqual(detail["where"][0]["port"], "Fa0/24")

    def test_05_poll_profile(self):
        sw = [e for e in self.client.get("/equipment").get_json()["equipment"] if e["ip"] == "192.0.2.2"][0]
        r = self.client.post("/equipment/%d/poll" % sw["id"], json={})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["profile"], "cisco-ios")
        self.assertFalse(body["verified"])
        self.assertEqual(body["gets"]["cpu_5min_legacy"], 11)
        self.assertEqual(body["summary"]["cpu_percent"], 12)  # cpmCPUTotal5minRev prime
        self.assertEqual(body["summary"]["memory_percent"], 75.0)
        self.assertEqual(body["summary"]["alarms"], ["alimentation 1 : critical"])
        self.assertEqual(body["walks"]["cdp"]["device_id"], {"24.1": "rtr-alpha"})
        self.assertEqual(body["walks"]["cdp"]["address"], {"24.1": "192.0.2.1"})
        self.assertEqual(len(body["interfaces"]), 1)
        detail = self.client.get("/equipment/%d" % sw["id"]).get_json()
        self.assertEqual(detail["last_poll"]["summary"]["cpu_percent"], 12)
        # cible injoignable : relevé en erreur, rien d'inventé
        r = self.client.post("/equipment", json={"ip": "192.0.2.77", "name": "sw-fantome"})
        ghost = r.get_json()["equipment"]
        r = self.client.post("/equipment/%d/poll" % ghost["id"], json={"community": "x"})
        self.assertEqual(r.status_code, 502)
        self.assertTrue(r.get_json()["errors"])

    def test_06_manual_and_preview(self):
        rows = self.client.get("/equipment").get_json()["equipment"]
        ghost = [e for e in rows if e["name"] == "sw-fantome"][0]
        r = self.client.put("/equipment/%d" % ghost["id"], json={"vendor": "3Com", "model": "SuperStack II 3300", "kind": "switch", "generation": "ancien", "mac": "00:50:04:aa:bb:cc"})
        self.assertEqual(r.status_code, 200, r.get_json())
        e = r.get_json()["equipment"]
        self.assertEqual((e["vendor"], e["model"], e["kind"], e["generation"]), ("3Com", "SuperStack II 3300", "switch", "ancien"))
        self.assertEqual(e["mac"], "00:50:04:AA:BB:CC")
        self.assertEqual(e["oui_vendor"], "3Com")
        self.assertEqual(e["profile_id"], "generic-bridge")
        self.assertIn("manuel", e["sources"])
        r = self.client.put("/equipment/%d" % ghost["id"], json={"kind": "trottinette"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/identify/preview", json={"sys_descr": "HP J4813A ProCurve Switch 2524, revision F.05.70", "mac": "00:80:5f:01:02:03"})
        p = r.get_json()
        self.assertEqual(p["identification"]["model"], "2524")
        self.assertEqual(p["identification"]["generation"], "ancien")
        self.assertEqual(p["profile"]["id"], "hp-procurve")
        self.assertEqual(p["oui"]["vendor"], "HP ProCurve / HPE")
        r = self.client.get("/oui/lookup?mac=b8:69:f4:00:00:01")
        self.assertEqual(r.get_json()["result"]["vendor"], "MikroTik")
        r = self.client.get("/profiles")
        self.assertGreaterEqual(len(r.get_json()["profiles"]), 8)
        r = self.client.get("/equipment?kind=switch&generation=ancien")
        self.assertTrue(all(e["kind"] == "switch" for e in r.get_json()["equipment"]))
        r = self.client.delete("/equipment/%d" % ghost["id"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/equipment/%d" % ghost["id"]).status_code, 404)
        filt = self.client.get("/equipment?q=alpha").get_json()["equipment"]
        self.assertEqual(len(filt), 2)

    def test_07_oui_import(self):
        content = "Registry,Assignment,Organization Name,Organization Address\n" + "".join("MA-L,%06X,Alpha Networks %d,Villexemple\n" % (i, i) for i in range(150))
        r = self.client.post("/oui/import", data={"file": (io.BytesIO(content.encode("utf-8")), "oui.csv")})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["entries"], 150)
        self.assertEqual(self.client.get("/oui/lookup?mac=00:00:05:01:02:03").get_json()["result"]["vendor"], "Alpha Networks 5")
        self.assertEqual(self.client.get("/status").get_json()["oui"]["file"], 150)
        r = self.client.post("/oui/import", data={"file": (io.BytesIO(b"Registry,Assignment,Organization Name\nMA-L,00AABB,Seul\n"), "oui.csv")})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
