# -*- coding: utf-8 -*-
"""Tests de la sonde path-probe (#527) : analyseurs nmcli/ping, DNS brut et constats."""
import importlib.util
import os
import struct
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("path_probe", os.path.join(HERE, "plugins", "path-probe", "path_probe.py"))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

DHCP = """DHCP4.OPTION[1]:                        dhcp_lease_time = 172800
DHCP4.OPTION[2]:                        dhcp_server_identifier = 192.0.2.1
DHCP4.OPTION[3]:                        domain_name_servers = 192.0.2.1 8.8.8.8
DHCP4.OPTION[4]:                        expiry = 1789740000
DHCP4.OPTION[5]:                        routers = 192.0.2.1
DHCP4.OPTION[6]:                        subnet_mask = 255.255.254.0
"""

PING = """PING 192.0.2.1 (192.0.2.1) from 192.0.2.63 wlan0: 56(84) bytes of data.

--- 192.0.2.1 ping statistics ---
5 packets transmitted, 5 received, 0% packet loss, time 806ms
rtt min/avg/max/mdev = 7.770/14.265/26.311/8.526 ms
"""


def dns_answer(tid, name="www.exemple.test", ips=("203.0.113.7",), rcode=0):
    header = struct.pack(">HHHHHH", tid, 0x8180 | rcode, 1, len(ips), 0, 0)
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    rr = b""
    for ip in ips:
        rr += b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + bytes(int(x) for x in ip.split("."))
    return header + q + rr


def path(**kw):
    base = {"iface": "wlan0", "ssid": "Exemple", "ip": "192.0.2.63", "gateway": "192.0.2.1", "static": False,
            "dhcp": {"server": "192.0.2.1"}, "gw_ping": {"sent": 5, "received": 5, "loss_pct": 0.0, "avg_ms": 8.0},
            "dns": [{"server": "192.0.2.1", "ok": True, "ms": 12.0}, {"server": "8.8.8.8", "ok": True, "ms": 20.0}],
            "dns_public": [{"server": "8.8.8.8", "ok": True, "ms": 9.0}],
            "http": {"ok": True, "status": 200, "ms": 300.0}, "https": {"ok": True, "status": 204, "ms": 400.0}}
    base.update(kw)
    return base


class Parsers(unittest.TestCase):
    def test_dhcp_options(self):
        o = pp.parse_dhcp_options(DHCP)
        self.assertEqual(o["routers"], "192.0.2.1")
        self.assertEqual(o["domain_name_servers"].split(), ["192.0.2.1", "8.8.8.8"])
        self.assertEqual(o["expiry"], "1789740000")
        self.assertEqual(pp.parse_dhcp_options(""), {})

    def test_ip_addr_and_ping(self):
        self.assertEqual(pp.parse_ip_addr("3: wlan0    inet 192.0.2.63/23 brd 192.0.3.255 scope global"), ("192.0.2.63", 23))
        self.assertEqual(pp.parse_ip_addr("nothing"), (None, None))
        p = pp.parse_ping(PING)
        self.assertEqual((p["sent"], p["received"], p["loss_pct"], p["avg_ms"]), (5, 5, 0.0, 14.265))
        self.assertEqual(pp.parse_ping("")["sent"], 0)

    def test_dns_query_build_and_parse(self):
        q = pp.build_dns_query("www.exemple.test", 0x1234)
        self.assertEqual(q[:2], b"\x12\x34")
        self.assertIn(b"\x03www\x07exemple\x04test\x00", q)
        r = pp.parse_dns_response(dns_answer(0x1234, ips=("203.0.113.7", "203.0.113.8")), 0x1234)
        self.assertEqual(r["rcode"], 0)
        self.assertEqual(r["answers"], ["203.0.113.7", "203.0.113.8"])
        self.assertEqual(pp.parse_dns_response(dns_answer(7, ips=(), rcode=3), 7)["rcode"], 3)
        with self.assertRaises(ValueError):
            pp.parse_dns_response(dns_answer(1), 2)  # identifiant inattendu
        with self.assertRaises(ValueError):
            pp.parse_dns_response(b"\x00\x01", 1)


class Evaluate(unittest.TestCase):
    def codes(self, p):
        return [a["code"] for a in pp.evaluate(p)]

    def test_all_good(self):
        self.assertEqual(self.codes(path()), [])
        self.assertEqual(pp.summarize([])["state"], "ok")

    def test_no_ip_and_conn_failed(self):
        self.assertEqual(self.codes(path(ip=None)), ["no-ip"])
        self.assertEqual(self.codes(path(ip=None, up_error="DHCP timeout")), ["conn-up-failed", "no-ip"])

    def test_dns_server_down_among_others(self):
        # le scénario de l'incident : le serveur interne est mort, un secours répond
        p = path(dns=[{"server": "192.0.2.5", "ok": False, "error": "délai dépassé"}, {"server": "8.8.8.8", "ok": True, "ms": 15.0}])
        c = self.codes(p)
        self.assertIn("dns-server-down", c)
        self.assertNotIn("dns-all-down", c)
        self.assertEqual(pp.summarize(pp.evaluate(p))["state"], "warning")

    def test_dns_single_and_all_down(self):
        p = path(dns=[{"server": "192.0.2.5", "ok": False, "error": "délai dépassé"}])
        c = self.codes(p)
        self.assertIn("dns-single", c)
        self.assertIn("dns-all-down", c)
        self.assertEqual(pp.summarize(pp.evaluate(p))["state"], "critical")
        self.assertEqual(self.codes(path(dns=[])), ["dns-none"])
        # adresse statique : pas de constat sur la distribution DHCP
        self.assertEqual(self.codes(path(dns=[], static=True, dhcp=None)), [])

    def test_gateway_and_public(self):
        self.assertEqual(self.codes(path(gw_ping={"sent": 5, "received": 0, "loss_pct": 100.0, "avg_ms": None})), ["gw-unreachable"])
        self.assertEqual(self.codes(path(gw_ping={"sent": 5, "received": 4, "loss_pct": 20.0, "avg_ms": 5.0})), ["gw-loss"])
        self.assertEqual(self.codes(path(dns_public=[{"server": "8.8.8.8", "ok": False}])), ["dns-public-down"])
        # passerelle morte : pas de constat public redondant
        self.assertNotIn("dns-public-down", self.codes(path(gw_ping={"sent": 5, "received": 0, "loss_pct": 100.0}, dns_public=[{"server": "8.8.8.8", "ok": False}])))

    def test_http(self):
        self.assertEqual(self.codes(path(http={"ok": False, "status": 503, "ms": 100.0})), ["http-failed"])
        self.assertEqual(self.codes(path(http={"ok": False, "portal": True, "detail": "redirigé vers http://portail.exemple/"})), ["captive-portal"])
        self.assertEqual(self.codes(path(https={"ok": True, "status": 204, "ms": 4500.0})), ["https-slow"])
        self.assertEqual(self.codes(path(dns=[{"server": "192.0.2.1", "ok": True, "ms": 900.0}, {"server": "8.8.8.8", "ok": True, "ms": 20.0}])), ["dns-slow"])


class Collect(unittest.TestCase):
    def test_collect_no_iface(self):
        pp.detect_ifaces = lambda: []
        r = pp.collect(["auto"], [], state_path="/tmp/path-probe-test.json")
        self.assertIn("error", r)
        self.assertEqual(r["summary"]["state"], "ok")

    def test_rotate_order(self):
        calls = []
        pp.run = lambda cmd, timeout=30: (calls.append(cmd) or (0, "192.0.2.9/24\n", "")) if cmd[:2] == ["nmcli", "-g"] else (calls.append(cmd) or (0, "", ""))
        self.assertEqual(pp.rotate_connection(["a", "b"], {"last_connection": "a"})[0], "b")
        self.assertEqual(pp.rotate_connection(["a", "b"], {"last_connection": "b"})[0], "a")
        self.assertEqual(pp.rotate_connection(["a", "b"], {})[0], "a")
        self.assertEqual(pp.rotate_connection([], {}), (None, None))
        pp.run = lambda cmd, timeout=30: (4, "", "Error: Connection activation failed: No suitable device")
        name, err = pp.rotate_connection(["a"], {})
        self.assertEqual(name, "a")
        self.assertIn("activation failed", err)


if __name__ == "__main__":
    unittest.main()
