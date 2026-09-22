# -*- coding: utf-8 -*-
"""Carte des VLAN (livraison #548) : analyse des réglages de ports, liaisons LLDP, anomalies."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import vlanmap  # noqa: E402

DEVICES = [
    {"devId": "core", "name": "XS3800-28", "model": "XS3800-28", "type": "SW", "mac": "02:00:00:00:00:01"},
    {"devId": "edge", "name": "GS2220-50HP-1", "model": "GS2220-50HP", "type": "SW", "mac": "02:00:00:00:00:02"},
    {"devId": "ap1", "name": "Borne", "model": "WBE660S", "type": "AP"},
    {"devId": "fw", "name": "USG", "model": "USG FLEX 700H", "type": "FIREWALL"},
]
PORTS = {
    "core": [{"portNum": 1, "enabled": True, "trunk": True, "portVid": 1, "allowedVLAN": ["1", "10", "20-21"]},
             {"portNum": 2, "enabled": True, "trunk": False, "portVid": 10}],
    "edge": [{"portNum": 49, "enabled": True, "trunk": True, "portVid": 1, "allowedVLAN": ["1", "10"]},   # VLAN 20, 21 manquants
             {"portNum": 5, "enabled": True, "trunk": False, "portVid": 20}],
}
LLDP = {"core": [{"lldpRemLocalPortNum": "1", "lldpRemPortId": "49", "lldpRemSysName": "GS2220-50HP-1", "lldpRemChassisId": "02:00:00:00:00:02"},
                 {"lldpRemLocalPortNum": "3", "lldpRemPortId": "eth0", "lldpRemSysName": "pc-inconnu", "lldpRemChassisId": "aa"}],
        "edge": [{"lldpRemLocalPortNum": "49", "lldpRemPortId": "1", "lldpRemSysName": "XS3800-28", "lldpRemChassisId": "02:00:00:00:00:01"}]}
GW = {"wan": [{"interface": "wan1", "vlan": 0}], "lan": [{"interface": "vlan10", "ipv4Address": "192.0.2.1", "ipv4Netmask": "255.255.255.0", "guestZone": False},
                                                          {"interface": "lan2", "ipv4Address": "198.51.100.1", "ipv4Netmask": "255.255.255.0"}]}
WLANS = [{"name": "Campus", "enabled": True, "vlan": 10}, {"name": "Invites", "enabled": True, "vlan": 20, "guestNetwork": True}, {"name": "Robots", "enabled": False, "vlan": 30}]


class Parse(unittest.TestCase):
    def test_vlan_list(self):
        self.assertEqual(vlanmap.parse_vlan_list(["1", "10", "20-22", "x"]), {1, 10, 20, 21, 22})
        self.assertEqual(vlanmap.parse_vlan_list("1,5-6"), {1, 5, 6})
        self.assertEqual(vlanmap.parse_vlan_list(["all"]), {"all"})
        self.assertEqual(vlanmap.parse_vlan_list(None), set())

    def test_switch_vlans(self):
        by_vlan, by_port = vlanmap.switch_vlans(PORTS["core"])
        self.assertEqual(by_vlan[10], {"untagged": [2], "tagged": [1]})
        self.assertEqual(by_vlan[21]["tagged"], [1])
        self.assertEqual(by_port[2]["trunk"], False)
        self.assertTrue(vlanmap.port_carries(by_port[1], 20)); self.assertFalse(vlanmap.port_carries(by_port[2], 20))

    def test_gateway(self):
        nets = vlanmap.gateway_networks(GW)
        self.assertEqual(nets[10]["subnet"], "192.0.2.1/24")
        self.assertNotIn(0, nets)


class Map(unittest.TestCase):
    def test_full_map(self):
        m = vlanmap.build_vlan_map(DEVICES, PORTS, LLDP, GW, WLANS, {"core": [{"interface": "vlan1", "vlan": 1}]},
                                   {"core": [{"macAddress": "a", "vlan": 10, "portNum": 2}, {"macAddress": "b", "vlan": 10, "portNum": 1}]},
                                   {"data": [{"macAddress": "a", "vlan": 10}, {"macAddress": "c", "vlan": 99}]})
        vids = [v["vid"] for v in m["vlans"]]
        self.assertEqual(vids, [1, 10, 20, 21, 30])
        v10 = next(v for v in m["vlans"] if v["vid"] == 10)
        self.assertEqual(v10["subnet"], "192.0.2.1/24"); self.assertEqual([s["name"] for s in v10["ssids"]], ["Campus"])
        self.assertEqual(v10["switches"]["XS3800-28"], {"untagged": [2], "tagged": [1]})
        self.assertEqual((v10["mac_count"], v10["clients"]), (2, 1))
        self.assertEqual(next(v for v in m["vlans"] if v["vid"] == 1)["management"], ["XS3800-28"])
        # liaison dédoublonnée, VLAN manquants côté GS2220
        inter = [l for l in m["links"] if not l["external"]]
        self.assertEqual(len(inter), 1)
        l = inter[0]
        self.assertEqual({l["a_name"], l["b_name"]}, {"XS3800-28", "GS2220-50HP-1"})
        missing = l["missing_on_a"] or l["missing_on_b"]
        self.assertEqual(missing, [20, 21])
        self.assertEqual(len([l for l in m["links"] if l["external"]]), 1)
        # anomalies en phrases
        self.assertTrue(any("VLAN 20, 21 portés côté XS3800-28 mais absents côté GS2220-50HP-1" in a for a in m["anomalies"]), m["anomalies"])
        self.assertTrue(any(a.startswith("VLAN 30 : utilisé par le SSID Robots mais présent sur aucun port") for a in m["anomalies"]))
        rows = vlanmap.to_csv_rows(m)
        self.assertEqual(rows[0][0], "vlan"); self.assertTrue(any(r[0] == 30 and r[4] == "" for r in rows[1:]))

    def test_empty(self):
        m = vlanmap.build_vlan_map([], {})
        self.assertEqual(m, {"vlans": [], "links": [], "switches": [], "anomalies": []})


if __name__ == "__main__":
    unittest.main()
