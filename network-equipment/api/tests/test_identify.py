# -*- coding: utf-8 -*-
"""Tests de la logique pure (#506) : OUI, sysDescr, génération, fusion,
profils, tables SNMP, import Zenoss. `python3 -m pytest tests/` ou
`python3 -m unittest discover tests`."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import identify  # noqa: E402
import oui  # noqa: E402
import profiles  # noqa: E402
import snmp_tables  # noqa: E402
import zenoss_import  # noqa: E402


class OuiTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(oui.normalize_mac("4c:5e:0c:aa:bb:cc"), "4C:5E:0C:AA:BB:CC")
        self.assertEqual(oui.normalize_mac("4C-5E-0C-AA-BB-CC"), "4C:5E:0C:AA:BB:CC")
        self.assertEqual(oui.normalize_mac("4c5e.0caa.bbcc"), "4C:5E:0C:AA:BB:CC")
        self.assertIsNone(oui.normalize_mac("4c:5e:0c"))
        self.assertIsNone(oui.normalize_mac(None))

    def test_seed_lookup(self):
        t = oui.OuiTable()
        self.assertEqual(t.lookup("4C:5E:0C:01:02:03")["vendor"], "MikroTik")
        self.assertEqual(t.lookup("00:00:0C:01:02:03")["vendor"], "Cisco")
        self.assertEqual(t.lookup("08:00:09:01:02:03")["category"], "reseau")
        self.assertEqual(t.lookup("00:50:56:01:02:03")["category"], "virtualisation")
        self.assertEqual(t.lookup("02:42:AC:11:00:02")["vendor"], "Docker")
        self.assertEqual(t.lookup("06:11:22:33:44:55")["category"], "locale")
        self.assertIsNone(t.lookup("FE:DC:BA:98:76:54") and t.lookup("FE:DC:BA:98:76:54").get("vendor"))
        self.assertIsNone(t.lookup("00:AA:BB:01:02:03"))

    def test_file_csv(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write('Registry,Assignment,Organization Name,Organization Address\nMA-L,00AABB,Exemple Networks SA,Villexemple\nMA-L,0000 0C,Cisco Systems Inc,US\n')
            path = fh.name
        t = oui.OuiTable(path)
        self.assertEqual(t.file_entries, 1)  # la seconde ligne a un préfixe invalide
        hit = t.lookup("00:AA:BB:01:02:03")
        self.assertEqual(hit["vendor"], "Exemple Networks SA")
        self.assertEqual(hit["category"], "reseau")
        self.assertEqual(hit["source"], "fichier IEEE")
        os.remove(path)

    def test_file_txt(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("OUI/MA-L  Organization\n00-AA-CC   (hex)\t\tAlpha Virtual Machines\n00AACC     (base 16)\t\tAlpha\n")
            path = fh.name
        t = oui.OuiTable(path)
        self.assertEqual(t.file_entries, 1)
        self.assertEqual(t.lookup("00:AA:CC:00:00:01")["vendor"], "Alpha Virtual Machines")
        os.remove(path)


class SysDescrTests(unittest.TestCase):
    def test_cisco_ios_old(self):
        d = "Cisco Internetwork Operating System Software \r\nIOS (tm) C2600 Software (C2600-I-M), Version 12.2(13), RELEASE SOFTWARE (fc1)"
        p = identify.parse_sys_descr(d)
        self.assertEqual(p["vendor"], "Cisco")
        self.assertEqual(p["model"], "C2600")
        self.assertEqual(p["version"], "12.2(13)")
        gen, reason = identify.generation_of(dict(p, family="C2600"))
        self.assertEqual(gen, "ancien")

    def test_cisco_2900xl(self):
        p = identify.parse_sys_descr("Cisco Internetwork Operating System Software IOS (tm) C2900XL Software (C2900XL-C3H2S-M), Version 12.0(5)WC17")
        self.assertEqual(p["family"], "C2900XL")
        self.assertEqual(identify.generation_of(p)[0], "ancien")

    def test_cisco_ios_recent(self):
        p = identify.parse_sys_descr("Cisco IOS Software, C2960X Software (C2960X-UNIVERSALK9-M), Version 15.2(7)E4, RELEASE SOFTWARE (fc2)")
        self.assertEqual(p["model"], "C2960X")
        self.assertEqual(identify.generation_of(p)[0], "recent")
        p2 = identify.parse_sys_descr("Cisco IOS Software [Everest], Catalyst L3 Switch Software (CAT9K_IOSXE), Version 16.6.4, RELEASE SOFTWARE (fc3)")
        self.assertEqual(p2["os"], "IOS-XE")
        self.assertEqual(identify.generation_of(p2)[0], "recent")

    def test_cisco_2960_12_2_se_is_not_ancient(self):
        p = identify.parse_sys_descr("Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 12.2(55)SE12, RELEASE SOFTWARE (fc2)")
        self.assertEqual(p["model"], "C2960")
        self.assertIsNone(identify.generation_of(p)[0])

    def test_catos(self):
        p = identify.parse_sys_descr("Cisco Systems, Inc. WS-C2948 Cisco Catalyst Operating System Software, Version McpSW: 6.3(3) NmpSW: 6.3(3)")
        self.assertEqual(p["os"], "CatOS")
        self.assertEqual(p["model"], "WS-C2948")
        self.assertEqual(p["kind"], "switch")
        self.assertEqual(identify.generation_of(p)[0], "ancien")

    def test_mikrotik(self):
        p = identify.parse_sys_descr("RouterOS CCR1036-8G-2S+")
        self.assertEqual((p["vendor"], p["model"], p["generation"]), ("MikroTik", "CCR1036-8G-2S+", "recent"))
        p2 = identify.parse_sys_descr("RouterOS v6.49.10 (long-term) on CRS326-24G-2S+")
        self.assertEqual((p2["model"], p2["version"]), ("CRS326-24G-2S+", "6.49.10"))

    def test_hp_procurve(self):
        p = identify.parse_sys_descr("HP J4813A ProCurve Switch 2524, revision F.05.70, ROM F.02.01 (/sw/code/build/info(s02))")
        self.assertEqual(p["vendor"], "HP ProCurve / HPE")
        self.assertEqual(p["model"], "2524")
        self.assertEqual(p["part"], "J4813A")
        self.assertEqual(identify.generation_of(p)[0], "ancien")
        p2 = identify.parse_sys_descr("ProCurve J9028A Switch 1800-24G, revision PB.03.02, ROM PB.03.00")
        self.assertEqual(p2["model"], "1800-24G")
        p3 = identify.parse_sys_descr("Aruba JL256A 2930F-48G-PoE+-4SFP+ Switch, revision WC.16.10.0009, ROM WC.16.01.0006")
        self.assertEqual(p3["vendor"], "Aruba (HPE)")
        self.assertEqual(p3["model"], "2930F-48G-PoE+-4SFP+")
        self.assertEqual(identify.generation_of(p3)[0], "recent")

    def test_threecom_nortel_alcatel(self):
        p = identify.parse_sys_descr("3Com SuperStack 3 Switch 4400, SW Version 6.10")
        self.assertEqual(p["model"], "SuperStack 3 Switch 4400")
        self.assertEqual(p["generation"], "ancien")
        n = identify.parse_sys_descr("BayStack 450-24T HW:RevD  FW:V1.46 SW:v4.5.0.9 ISVN:2")
        self.assertEqual(n["vendor"], "Nortel / Bay Networks")
        self.assertEqual(n["model"], "BayStack 450-24T")
        self.assertEqual(n["version"], "4.5.0.9")
        a = identify.parse_sys_descr("Alcatel-Lucent OS6450-24 6.7.1.71.R04 Service Release, February 19, 2016.")
        self.assertEqual(a["model"], "OS6450-24")
        self.assertEqual(a["version"], "6.7.1.71.R04")

    def test_juniper_netgear_dlink_zyxel(self):
        j = identify.parse_sys_descr("Juniper Networks, Inc. ex2200-24t-4g Ethernet Switch, kernel JUNOS 12.3R6.6, Build date: 2014-03-13")
        self.assertEqual((j["model"], j["version"], j["kind"]), ("ex2200-24t-4g", "12.3R6.6", "switch"))
        self.assertEqual(identify.parse_sys_descr("GS724Tv4")["vendor"], "Netgear")
        self.assertEqual(identify.parse_sys_descr("DGS-1210-24 Gigabit Ethernet Switch")["model"], "DGS-1210-24")
        z = identify.parse_sys_descr("GS1920-24HP")
        self.assertEqual(z["vendor"], "Zyxel")
        self.assertEqual(identify.parse_sys_descr("ZyWALL USG 100")["kind"], "pare-feu")

    def test_hosts_and_others(self):
        l = identify.parse_sys_descr("Linux srv-alpha 5.10.0-8-amd64 #1 SMP Debian 5.10.46-4 (2021-08-03) x86_64")
        self.assertEqual((l["os"], l["version"], l["kind"]), ("Linux", "5.10.0-8-amd64", "hôte"))
        self.assertEqual(identify.parse_sys_descr("Linux pve1 6.8.12-4-pve #1 SMP PREEMPT_DYNAMIC PMX 6.8.12-4 x86_64")["kind"], "hyperviseur")
        w = identify.parse_sys_descr("Hardware: Intel64 Family 6 Model 158 Stepping 9 AT/AT COMPATIBLE - Software: Windows Version 6.3 (Build 19045 Multiprocessor Free)")
        self.assertEqual(w["os"], "Windows")
        a = identify.parse_sys_descr("APC Web/SNMP Management Card (MB:v3.9.2 PF:v3.9.2 PN:apc_hw02_aos_392.bin AF1:v3.9.2 AN1:apc_hw02_sumx_392.bin MN:AP9617 HR:A10 SN: ZA0000000000 MD:01/01/2010)")
        self.assertEqual(a["kind"], "onduleur")
        self.assertEqual(identify.parse_sys_descr("HP ETHERNET MULTI-ENVIRONMENT,ROM none,JETDIRECT,JD153,EEPROM V.40.34")["kind"], "imprimante")
        self.assertEqual(identify.parse_sys_descr(""), {})
        self.assertEqual(identify.parse_sys_descr("texte quelconque sans motif"), {})

    def test_enterprise(self):
        self.assertEqual(identify.enterprise_of("1.3.6.1.4.1.14988.1")[1], "MikroTik")
        self.assertEqual(identify.enterprise_of(".1.3.6.1.4.1.9.1.516")[1], "Cisco")
        self.assertEqual(identify.enterprise_of("1.3.6.1.4.1.11.2.3.7.11.23")[1], "HP / HPE")
        self.assertEqual(identify.enterprise_of("1.3.6.1.4.1.999999.1"), (999999, None, None))
        self.assertIsNone(identify.enterprise_of("1.3.6.1.2.1.1.1.0"))
        self.assertIsNone(identify.enterprise_of(None))


class MergeTests(unittest.TestCase):
    def test_mikrotik_from_snmp(self):
        ev = {"mac": "4C:5E:0C:01:02:03", "oui": {"vendor": "MikroTik", "category": "reseau"},
              "sys_descr": "RouterOS RB5009UG+S+", "sys_object_id": "1.3.6.1.4.1.14988.1", "role_hint": "gateway"}
        r = identify.merge(ev)
        self.assertEqual(r["vendor"], "MikroTik")
        self.assertEqual(r["model"], "RB5009UG+S+")
        self.assertEqual(r["kind"], "routeur")
        self.assertEqual(r["generation"], "recent")
        self.assertIn("sysDescr", r["sources"])
        self.assertGreaterEqual(r["confidence"], 0.8)

    def test_old_cisco_router_oui_only(self):
        r = identify.merge({"mac": "00:10:7B:01:02:03", "oui": {"vendor": "Cisco", "category": "reseau"}, "role_hint": "gateway"})
        self.assertEqual(r["vendor"], "Cisco")
        self.assertEqual(r["kind"], "routeur")
        self.assertIsNone(r["model"])
        self.assertIsNone(r["generation"])
        self.assertLess(r["confidence"], 0.5)

    def test_zenoss_only(self):
        r = identify.merge({"zenoss": {"device_class": "/Network/Router/Cisco", "hw_product": "2621XM", "os_product": "IOS 12.3(26)"}})
        self.assertEqual((r["vendor"], r["model"], r["kind"]), ("Cisco", "2621XM", "routeur"))
        self.assertIn("zenoss", r["sources"])
        r2 = identify.merge({"zenoss": {"device_class": "/Network/Switch/BayStack"}})
        self.assertEqual((r2["vendor"], r2["kind"]), ("Nortel / Bay Networks", "switch"))
        r3 = identify.merge({"zenoss": {"device_class": "/Server/Linux"}})
        self.assertEqual(r3["kind"], "hôte")

    def test_entity_and_manual(self):
        ev = {"sys_descr": "Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 12.2(55)SE12",
              "entity": {"model": "WS-C2960-24TT-L", "serial": "FOC0000X0XX"}}
        r = identify.merge(ev)
        self.assertEqual(r["model"], "WS-C2960-24TT-L")
        self.assertEqual(r["serial"], "FOC0000X0XX")
        self.assertEqual(r["kind"], "switch")
        r2 = identify.merge(dict(ev, manual={"kind": "routeur", "generation": "ancien"}))
        self.assertEqual(r2["kind"], "routeur")
        self.assertEqual(r2["generation"], "ancien")
        self.assertIn("manuel", r2["sources"])

    def test_virtual_mac_never_a_router(self):
        r = identify.merge({"mac": "00:50:56:01:02:03", "oui": {"vendor": "VMware", "category": "virtualisation"}, "role_hint": "gateway"})
        self.assertEqual(r["kind"], "routeur")  # rôle observé prime sur la catégorie OUI
        r2 = identify.merge({"mac": "00:50:56:01:02:03", "oui": {"vendor": "VMware", "category": "virtualisation"}})
        self.assertEqual(r2["kind"], "hôte")
        self.assertIsNone(r2["vendor"])

    def test_services(self):
        r = identify.merge({"ports": [8291, 8728, 22]})
        self.assertEqual(r["kind"], "routeur")
        self.assertEqual(identify.merge({"ports": [3389, 445]})["kind"], "hôte")
        self.assertEqual(identify.merge({})["kind"], "inconnu")


class ProfileTests(unittest.TestCase):
    def test_match(self):
        self.assertEqual(profiles.match_profile({"vendor": "Cisco", "os": "IOS"})["id"], "cisco-ios")
        self.assertEqual(profiles.match_profile({"vendor": "Cisco", "os": "CatOS"})["id"], "cisco-catos")
        self.assertEqual(profiles.match_profile({"vendor": "Cisco", "os": None, "kind": "routeur"})["id"], "generic-bridge")
        self.assertEqual(profiles.match_profile({"vendor": "HP ProCurve / HPE"})["id"], "hp-procurve")
        self.assertEqual(profiles.match_profile({"vendor": "MikroTik", "os": "RouterOS"})["id"], "mikrotik")
        self.assertEqual(profiles.match_profile({"vendor": "Juniper"})["id"], "juniper")
        self.assertEqual(profiles.match_profile({"os": "Linux", "kind": "hôte"})["id"], "generic-host")
        self.assertEqual(profiles.match_profile({"vendor": "3Com", "kind": "switch"})["id"], "generic-bridge")
        self.assertEqual(profiles.match_profile({})["id"], "generic-snmp")

    def test_decode_and_interpret(self):
        self.assertEqual(profiles.decode_value({"enum": profiles.CISCO_ENVMON_STATE}, "2"), "warning")
        self.assertEqual(profiles.decode_value({"unit": "0.1°C"}, "415"), 41.5)
        self.assertEqual(profiles.decode_value({}, "12"), 12)
        self.assertEqual(profiles.decode_value({}, "abc"), "abc")
        cisco = profiles.profile_by_id("cisco-ios")
        s = profiles.interpret(cisco, {"cpu_5min_legacy": 37}, {"mem_used": [{"index": "1", "value": 3000}], "mem_free": [{"index": "1", "value": 1000}],
                                                                  "temp_value": [{"index": "1", "value": 44}], "fan_state": [{"index": "1", "value": "critical"}]})
        self.assertEqual(s["cpu_percent"], 37)
        self.assertEqual(s["memory_percent"], 75.0)
        self.assertEqual(s["temperature_c"], 44)
        self.assertEqual(len(s["alarms"]), 1)
        mt = profiles.profile_by_id("mikrotik")
        s2 = profiles.interpret(mt, {"temp_cpu": 52.0}, {"cpu": [{"index": "1", "value": 10}, {"index": "2", "value": 30}],
                                                         "storage_descr": [{"index": "65536", "value": "main memory"}, {"index": "131072", "value": "system disk"}],
                                                         "storage_size": [{"index": "65536", "value": 1024}, {"index": "131072", "value": 500}],
                                                         "storage_used": [{"index": "65536", "value": 512}, {"index": "131072", "value": 400}]})
        self.assertEqual(s2["cpu_percent"], 20.0)
        self.assertEqual(s2["memory_percent"], 50.0)
        self.assertEqual(s2["temperature_c"], 52.0)
        hp = profiles.profile_by_id("hp-procurve")
        s3 = profiles.interpret(hp, {"cpu": 12, "mem_total": 200, "mem_free": 50}, {"sensor_status": [{"index": "1", "value": "good"}, {"index": "2", "value": "bad"}],
                                                                                    "sensor_descr": [{"index": "1", "value": "Fan Sensor"}, {"index": "2", "value": "Power Supply Sensor"}]})
        self.assertEqual(s3["memory_percent"], 75.0)
        self.assertEqual(s3["alarms"], ["Power Supply Sensor : bad"])


class SnmpTablesTests(unittest.TestCase):
    def test_entity(self):
        rows = [{"oid": "1.3.6.1.2.1.47.1.1.1.1.5.1", "value": "3"}, {"oid": "1.3.6.1.2.1.47.1.1.1.1.13.1", "value": "WS-C2960-24TT-L"},
                {"oid": "1.3.6.1.2.1.47.1.1.1.1.11.1", "value": "FOC0000X0XX"}, {"oid": "1.3.6.1.2.1.47.1.1.1.1.12.1", "value": "Cisco Systems, Inc."},
                {"oid": "1.3.6.1.2.1.47.1.1.1.1.10.1", "value": "12.2(55)SE12"}, {"oid": "1.3.6.1.2.1.47.1.1.1.1.5.2", "value": "10"},
                {"oid": "1.3.6.1.2.1.47.1.1.1.1.13.2", "value": "port"}]
        e = snmp_tables.parse_entity(rows)
        self.assertEqual(e["model"], "WS-C2960-24TT-L")
        self.assertEqual(e["serial"], "FOC0000X0XX")
        self.assertEqual(e["sw"], "12.2(55)SE12")
        self.assertEqual(snmp_tables.parse_entity([]), {})

    def test_lldp_cdp(self):
        rows = [{"oid": "1.0.8802.1.1.2.1.4.1.1.5.0.3.1", "value": "0x4c5e0c010203"}, {"oid": "1.0.8802.1.1.2.1.4.1.1.7.0.3.1", "value": "ether1"},
                {"oid": "1.0.8802.1.1.2.1.4.1.1.9.0.3.1", "value": "routeur-alpha"}, {"oid": "1.0.8802.1.1.2.1.4.1.1.10.0.3.1", "value": "RouterOS RB5009UG+S+"}]
        n = snmp_tables.parse_lldp(rows, {"3": "GigabitEthernet0/3"})
        self.assertEqual(len(n), 1)
        self.assertEqual(n[0]["remote_chassis"], "4C:5E:0C:01:02:03")
        self.assertEqual(n[0]["local_port"], "GigabitEthernet0/3")
        self.assertEqual(n[0]["remote_name"], "routeur-alpha")
        c = snmp_tables.parse_cdp([{"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.4.10105.1", "value": "0xc0000201"}, {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.6.10105.1", "value": "sw-b"},
                                   {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.7.10105.1", "value": "FastEthernet0/24"}, {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1.8.10105.1", "value": "cisco WS-C2950-24"}])
        self.assertEqual(c[0]["remote_address"], "192.0.2.1")
        self.assertEqual(c[0]["remote_platform"], "cisco WS-C2950-24")

    def test_fdb(self):
        rows = [{"oid": "1.3.6.1.2.1.17.4.3.1.2.76.94.12.1.2.3", "value": "5"}, {"oid": "1.3.6.1.2.1.17.4.3.1.2.0.16.123.9.8.7", "value": "24"}]
        q = [{"oid": "1.3.6.1.2.1.17.7.1.2.2.1.2.10.76.94.12.1.2.3", "value": "5"}]
        e = snmp_tables.parse_fdb(rows, {"5": "10105", "24": "10124"}, {"10105": "Fa0/5", "10124": "Fa0/24"}, q)
        by = {(x["mac"], x["vlan"]): x for x in e}
        self.assertEqual(by[("4C:5E:0C:01:02:03", None)]["port"], "Fa0/5")
        self.assertEqual(by[("00:10:7B:09:08:07", None)]["port"], "Fa0/24")
        self.assertEqual(by[("4C:5E:0C:01:02:03", "10")]["vlan"], "10")
        self.assertIsNone(snmp_tables.hex_to_mac("bonjour"))
        self.assertEqual(snmp_tables.hex_to_mac("4c:5e:0c:01:02:03"), "4C:5E:0C:01:02:03")


class ZenossImportTests(unittest.TestCase):
    def test_csv(self):
        text = "Device,IP,Device Class,Prod State\nrtr-alpha,192.0.2.1,/Network/Router/Cisco,Production\nsw-b,192.0.2.2,/Network/Switch/BayStack,Production\n,,,\n"
        devices, skipped, fmt = zenoss_import.parse(text, "devices.csv")
        self.assertEqual(fmt, "csv")
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["device_class"], "/Network/Router/Cisco")
        self.assertEqual(devices[1]["ip"], "192.0.2.2")
        d2, s2, _ = zenoss_import.parse("Device;IP\r\nsw-c;192.0.2.3\r\n")
        self.assertEqual(d2[0]["ip"], "192.0.2.3")
        d3, _, _ = zenoss_import.parse("Colonne1,Colonne2\nx,y\n")
        self.assertEqual(d3, [])

    def test_json(self):
        text = '{"devices": [{"id": "rtr-alpha", "manageIp": "192.0.2.1", "device_class": "/Network/Router/Cisco", "hw_product": "2621XM", "snmp_descr": "Cisco IOS", "interfaces": [{"id": "FastEthernet0_0", "mac": "00:10:7B:09:08:07", "ips": ["192.0.2.1/24"]}]}, 5]}'
        devices, skipped, fmt = zenoss_import.parse(text.encode("utf-8"), "export.json")
        self.assertEqual(fmt, "json")
        self.assertEqual(len(devices), 1)
        self.assertEqual(skipped, 1)
        self.assertEqual(zenoss_import.primary_mac(devices[0]), "00:10:7B:09:08:07")
        self.assertEqual(devices[0]["hw_product"], "2621XM")


if __name__ == "__main__":
    unittest.main()
