# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import natrules  # noqa: E402
import ssh_client  # noqa: E402
from ssh_client import RouterOSError, RouterOSSsh  # noqa: E402


class Parse(unittest.TestCase):
    def test_kv_list(self):
        rows = ssh_client.parse_kv_list('.id=*1;chain=dstnat;action=dst-nat;protocol=tcp;dst-port=8443;to-addresses=192.0.2.10;to-ports=443;comment=hub; interne;disabled=false\n.id=*2;chain=srcnat;action=masquerade;out-interface=ether1\n\n')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][".id"], "*1")
        self.assertEqual(rows[0]["comment"], "hub; interne")
        self.assertEqual(rows[1]["out-interface"], "ether1")

    def test_print_single(self):
        self.assertEqual(ssh_client.parse_print_single("  uptime: 3d2h\n  version: 6.49.10 (long-term)\n  cpu-load: 4\n")["version"], "6.49.10 (long-term)")

    def test_menu_and_quote(self):
        self.assertEqual(ssh_client.menu_path("ip/firewall/nat"), "/ip firewall nat")
        with self.assertRaises(RouterOSError):
            ssh_client.menu_path("ip/firewall; reboot")
        self.assertEqual(ssh_client.to_cli("disabled", "true"), 'disabled="yes"')
        with self.assertRaises(RouterOSError):
            ssh_client.quote('x" ; /system reset')

    def test_read_only(self):
        for ok in ("/ip address print", "/ip route print where active", "/interface monitor-traffic ether1 once", "/export", "/ip dhcp-server lease print detail"):
            self.assertTrue(ssh_client.read_only_command(ok), ok)
        for bad in ("/ip address add address=1.1.1.1/24", "/system reboot", "/ip firewall nat print; /system reset", ":put [/system get]", "/ip address print $x", "/tool fetch url=x", "/user set 0 password=x"):
            self.assertFalse(ssh_client.read_only_command(bad), bad)


class Session(unittest.TestCase):
    def setUp(self):
        self.cmds = []
        script = {
            ":put [/system identity get]": "name=routeur-bureau\n",
            ":put [/system resource get]": "uptime=3d2h;version=6.49.10 (long-term);cpu-load=4;free-memory=1000;total-memory=2000\n",
            ":foreach i in=[/interface find] do={:put [/interface get $i]}": ".id=*1;name=ether1;type=ether;running=true;disabled=false\n.id=*2;name=ether2;type=ether;running=false;disabled=true\n",
            ":foreach i in=[/ip firewall nat find] do={:put [/ip firewall nat get $i]}": ".id=*A;chain=dstnat;action=dst-nat;protocol=tcp;dst-port=8443;to-addresses=192.0.2.10;to-ports=443;disabled=false\n",
            "/interface set *2 disabled=\"no\"": "",
            '/ip firewall nat add chain="dstnat" action="dst-nat" protocol="tcp" dst-port="2222" to-addresses="192.0.2.20" to-ports="22" comment="ssh vers vm"': "*B\n",
            "/ip firewall nat remove *B": "",
            "/ping address=\"192.0.2.1\" count=\"2\"": "  SEQ HOST SIZE TTL TIME STATUS\n    0 192.0.2.1 56 64 1ms\n    1 192.0.2.1 56 64 1ms\n  sent=2 received=2\n",
            "/ip firewall nat set *Z disabled=\"yes\"": "no such item\n",
        }

        def runner(cmd):
            self.cmds.append(cmd)
            if cmd not in script:
                return "syntax error (line 1 column 2)\n", 0
            return script[cmd], 0
        self.s = RouterOSSsh("192.0.2.253", 22, "hub", "pw", runner=runner)

    def test_get(self):
        self.assertEqual(self.s.get("system/identity")["name"], "routeur-bureau")
        self.assertEqual(self.s.get("system/resource")["version"], "6.49.10 (long-term)")
        ifaces = self.s.get("interface")
        self.assertEqual([i["name"] for i in ifaces], ["ether1", "ether2"])
        self.assertEqual(self.s.nat_list()[0]["to-ports"], "443")

    def test_actions(self):
        self.s.patch("interface/*2", {"disabled": "false"})
        self.assertIn('/interface set *2 disabled="no"', self.cmds)
        r = self.s.nat_add({"chain": "dstnat", "action": "dst-nat", "protocol": "tcp", "dst-port": "2222", "to-addresses": "192.0.2.20", "to-ports": "22", "comment": "ssh vers vm"})
        self.assertEqual(r["id"], "*B")
        self.s.nat_remove("*B")
        out = self.s.post_action("ping", {"address": "192.0.2.1", "count": "2"})
        self.assertEqual(len(out), 4)
        with self.assertRaises(RouterOSError):
            self.s.nat_set("*Z", {"disabled": "true"})
        with self.assertRaises(RouterOSError):
            self.s.nat_remove("*B; /system reset")
        with self.assertRaises(RouterOSError):
            self.s.run("/bidule print")


class Rules(unittest.TestCase):
    def test_ok(self):
        out, errs = natrules.validate({"chain": "dstnat", "action": "dst-nat", "protocol": "tcp", "dst-address": "203.0.113.5", "dst-port": "8443",
                                       "to-addresses": "192.0.2.10", "to-ports": "443", "comment": "hub", "disabled": "no", "in-interface": "ether1"})
        self.assertEqual(errs, [])
        self.assertEqual(out["disabled"], "false")
        self.assertEqual(natrules.describe(out), "tcp 203.0.113.5:8443 → 192.0.2.10:443")
        out, errs = natrules.validate({"chain": "srcnat", "action": "masquerade", "out-interface": "ether1"})
        self.assertEqual(errs, [])
        self.assertEqual(natrules.describe(out), "masquerade * sortant par ether1")

    def test_errors(self):
        _, errs = natrules.validate({"chain": "input", "action": "drop", "protocol": "sctp", "dst-address": "x", "dst-port": "99999", "to-addresses": "1.2.3", "comment": 'a"b', "bidule": 1})
        self.assertGreaterEqual(len(errs), 7)
        _, errs = natrules.validate({"chain": "dstnat", "action": "dst-nat", "dst-port": "80", "to-addresses": "192.0.2.1"})
        self.assertIn("un port exige protocol tcp ou udp", errs)
        _, errs = natrules.validate({"chain": "srcnat", "action": "dst-nat", "to-addresses": "192.0.2.1"})
        self.assertTrue(any("dstnat" in e for e in errs))
        out, errs = natrules.validate({"disabled": "yes"}, partial=True)
        self.assertEqual((out, errs), ({"disabled": "true"}, []))
        self.assertTrue(natrules._ports("80,443,8000-8010"))
        self.assertFalse(natrules._ports("8010-8000"))


if __name__ == "__main__":
    unittest.main()
