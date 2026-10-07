# -*- coding: utf-8 -*-
"""Tests #712 : NAT de la passerelle (forme documentée de l'OpenAPI) et cohérence des zones invité."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
import gwpolicy as gp  # noqa: E402
import rules  # noqa: E402

NAT = {"oneToOne": [
    {"enabled": True, "name": "serveur-web", "interface": "wan1", "publicIPv4": "198.51.100.10", "privateIPv4": "192.0.2.20",
     "inbound": [{"enabled": True, "protocol": 1, "port": ["443", "80"], "remote": ["any"]},
                 {"enabled": True, "protocol": 1, "port": ["22"], "remote": ["203.0.113.0/24"]}]},
    {"enabled": True, "name": "tout", "publicIPv4": "198.51.100.11", "privateIPv4": "192.0.2.21", "inbound": []},
    {"enabled": False, "name": "ancien", "publicIPv4": "198.51.100.12", "privateIPv4": "192.0.2.22", "inbound": []}],
    "virtualServer": [
    {"enabled": True, "description": "RDP compta", "interface": "wan1", "protocol": 1, "publicIPv4": "198.51.100.10", "publicPorts": "3389", "privateIPv4": "192.0.2.30", "privatePorts": "3389"},
    {"enabled": True, "description": "caméra", "protocol": 3, "publicPorts": "8000-8010", "privateIPv4": "172.16.22.40"},
    {"enabled": True, "description": "orpheline", "publicPorts": "8443", "privateIPv4": "10.99.0.5"}]}
VMAP = {"vlans": [
    {"vid": 10, "subnet": "192.0.2.0/24", "guest": False, "gateway_interface": "lan1", "ssids": [{"name": "Interne", "guest": False}]},
    {"vid": 22, "subnet": "172.16.22.0/24", "guest": True, "gateway_interface": "VLan22", "ssids": [{"name": "Campus", "guest": False}]},
    {"vid": 30, "subnet": "172.16.30.0/24", "guest": False, "gateway_interface": "VLan30", "ssids": [{"name": "Invites", "guest": True}]}]}


class Passerelle(unittest.TestCase):
    def test_nat(self):
        r = gp.parse_nat(NAT)
        self.assertEqual(len(r), 7)
        web = r[0]
        self.assertEqual((web["kind"], web["ports"], web["any_remote"], web["protocol"]), ("1:1", [80, 443], True, "TCP"))
        self.assertEqual((r[1]["ports"], r[1]["any_remote"], r[1]["remote"]), ([22], False, ["203.0.113.0/24"]))
        self.assertTrue(r[2]["all_ports"])
        self.assertEqual((r[4]["kind"], r[4]["ports"], r[4]["private_ports"]), ("redirection", [3389], ["3389"]))
        self.assertEqual(len(r[5]["ports"]), 11)
        self.assertEqual(gp.parse_nat(None), [])
        self.assertEqual(gp._ports(["1-65535"])[1], True); self.assertEqual(gp._ports(["8000-8010", "22-23"])[2], {22, 23})

    def test_anomalies(self):
        found = gp.anomalies(gp.parse_nat(NAT), VMAP)
        kinds = sorted(f["kind"] for f in found)
        self.assertEqual(kinds, ["guest_zone_mixed", "nat_sensitive_port", "nat_sensitive_port_restricted", "nat_to_guest", "nat_unknown_target",
                                 "nat_whole_host", "ssid_guest_not_isolated"])
        rdp = next(f for f in found if f["kind"] == "nat_sensitive_port")
        self.assertIn("3389 (Bureau à distance (RDP))", rdp["message"]); self.assertEqual(rdp["details"]["private_ip"], "192.0.2.30")
        self.assertFalse(any("ancien" in f["message"] for f in found))                      # désactivée : ignorée
        self.assertEqual(gp.anomalies([], {"vlans": []}), [])

    def test_regles(self):
        rs = rules.load_rules(os.path.join(HERE, "..", "..", "rules")) if hasattr(rules, "load_rules") else None
        text = open(os.path.join(HERE, "..", "..", "rules", "reseau-nebula.md"), encoding="utf-8").read()
        parsed = {r["when"] if "when" in r else r.get("kind"): r for r in rules.parse_rules(text, "reseau-nebula.md")}
        for k in ("nat_sensitive_port", "nat_sensitive_port_restricted", "nat_whole_host", "nat_to_guest", "nat_unknown_target", "ssid_guest_not_isolated", "guest_zone_mixed"):
            self.assertIn(k, parsed, k)
        out = rules.apply_rules(gp.anomalies(gp.parse_nat(NAT), VMAP), rules.parse_rules(text))
        self.assertEqual(out[0]["severity"], "haute")
        rdp = next(o for o in out if o["kind"] == "nat_sensitive_port")
        self.assertIn("Retirer la publication des port(s) 3389", rdp["action"])


if __name__ == "__main__":
    unittest.main()
