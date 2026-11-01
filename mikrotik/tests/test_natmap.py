# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import natmap  # noqa: E402

RULES = [
    {".id": "*1", "chain": "dstnat", "action": "dst-nat", "protocol": "tcp", "dst-port": "8443", "to-addresses": "192.0.2.10", "to-ports": "443", "in-interface": "ether1", "comment": "pve web", "disabled": "false", "packets": "120", "bytes": "8000"},
    {".id": "*2", "chain": "dstnat", "action": "dst-nat", "protocol": "tcp", "dst-port": "8443", "to-addresses": "192.0.2.11", "to-ports": "443", "disabled": "false"},
    {".id": "*3", "chain": "dstnat", "action": "dst-nat", "protocol": "tcp", "dst-port": "2222", "to-addresses": "192.0.2.10", "to-ports": "22", "disabled": "true"},
    {".id": "*4", "chain": "dstnat", "action": "redirect", "protocol": "udp", "dst-port": "53", "to-ports": "53", "disabled": "false"},
    {".id": "*5", "chain": "srcnat", "action": "masquerade", "out-interface": "ether1", "disabled": "false"},
]


class Map(unittest.TestCase):
    def test_build(self):
        m = natmap.build([{"name": "rb", "host": "192.0.2.253", "site": "bureau", "reachable": True, "rules": RULES}, {"name": "rb2", "reachable": False, "error": "injoignable", "rules": []}], names={"192.0.2.10": "pve10"})
        self.assertEqual(m["routers"][0]["inbound"], 3)
        self.assertEqual((m["routers"][0]["outbound"], m["routers"][0]["disabled"]), (1, 1))
        self.assertEqual(m["routers"][1]["reachable"], False)
        self.assertEqual([t["address"] for t in m["targets"]], ["192.0.2.10", "192.0.2.11", "routeur"])
        self.assertEqual(m["targets"][0]["name"], "pve10")
        self.assertEqual(len(m["targets"][0]["flows"]), 2)  # une active + une désactivée
        self.assertEqual(m["conflicts"], [{"router": "rb", "key": "tcp *:8443", "rules": ["*1", "*2"]}])
        self.assertEqual(m["counts"], {"inbound": 3, "outbound": 1, "disabled": 1, "targets": 3, "conflicts": 1})
        f = m["flows"][0]
        self.assertEqual((f["kind"], f["in_iface"], f["packets"], f["dst_ports"], f["to_ports"]), ("inbound", "ether1", 120, ["8443"], ["443"]))
        self.assertEqual(m["flows"][3]["to_address"], "routeur")

    def test_ports_and_filter(self):
        self.assertEqual(natmap._ports("80,443"), ["80", "443"])
        self.assertEqual(natmap._ports(""), ["*"])
        flows = natmap.build([{"name": "rb", "rules": RULES}])["flows"]
        self.assertEqual([f["id"] for f in natmap.filter_flows(flows, "pve")], ["*1"])
        self.assertEqual([f["id"] for f in natmap.filter_flows(flows, "192.0.2.1")], ["*1", "*2", "*3"])
        self.assertEqual([f["id"] for f in natmap.filter_flows(flows, "masq")], ["*5"])


if __name__ == "__main__":
    unittest.main()
