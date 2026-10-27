# -*- coding: utf-8 -*-
"""Tests #873 : sonde lan-audit (analyse XML nmap, enchaînement découverte -> détail, cas sans nmap ou sans cible)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lan_audit as la  # noqa: E402

DECOUVERTE = """<?xml version="1.0"?><nmaprun>
<host><status state="up"/><address addr="192.0.2.20" addrtype="ipv4"/><address addr="02:00:00:00:00:20" addrtype="mac" vendor="Dell"/></host>
<host><status state="up"/><address addr="192.0.2.100" addrtype="ipv4"/></host>
<host><status state="down"/><address addr="192.0.2.7" addrtype="ipv4"/></host></nmaprun>"""
DETAIL = """<?xml version="1.0"?><nmaprun>
<host><status state="up"/><address addr="192.0.2.20" addrtype="ipv4"/><address addr="02:00:00:00:00:20" addrtype="mac" vendor="Dell"/>
<hostnames><hostname name="nms.exemple" type="PTR"/></hostnames>
<ports><port protocol="tcp" portid="22"><state state="open"/><service name="ssh" product="OpenSSH" version="5.1p1 Debian 5" extrainfo="protocol 2.0"/></port>
<port protocol="tcp" portid="80"><state state="open"/><service name="http" product="Apache httpd" version="2.2.9" extrainfo="(Debian) PHP/5.2.6-1+lenny16"><cpe>cpe:/a:apache:http_server:2.2.9</cpe></service></port>
<port protocol="tcp" portid="23"><state state="closed"/></port></ports>
<os><osmatch name="Linux 2.6.18 - 2.6.32" accuracy="95"><osclass osfamily="Linux" osgen="2.6.X" vendor="Linux"/></osmatch>
<osmatch name="Linux 3.2" accuracy="88"><osclass osfamily="Linux" osgen="3.X" vendor="Linux"/></osmatch></os></host>
<host><status state="up"/><address addr="192.0.2.100" addrtype="ipv4"/>
<ports><port protocol="tcp" portid="3389"><state state="open"/><service name="ms-wbt-server" product="Microsoft Terminal Services"/></port></ports>
<os><osmatch name="Microsoft Windows Server 2012 R2" accuracy="96"><osclass osfamily="Windows" osgen="2012" vendor="Microsoft"/></osmatch></os></host></nmaprun>"""


class Run:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        out = DECOUVERTE if "-sn" in cmd else DETAIL
        return type("P", (), {"stdout": out, "stderr": ""})()


class LanAudit(unittest.TestCase):
    def test_parse(self):
        h = la.parse_xml(DETAIL)
        self.assertEqual([x["ip"] for x in h], ["192.0.2.20", "192.0.2.100"])
        self.assertEqual(h[0]["hostname"], "nms.exemple")
        self.assertEqual(h[0]["os"]["name"], "Linux 2.6.18 - 2.6.32")      # meilleure précision
        self.assertEqual([p["port"] for p in h[0]["ports"]], [22, 80])     # port fermé écarté
        self.assertEqual(h[0]["ports"][1]["cpe"], ["cpe:/a:apache:http_server:2.2.9"])
        self.assertEqual(la.parse_xml("pas du xml"), [])
        self.assertEqual(len(la.parse_xml(DECOUVERTE)), 2)                 # hôte « down » écarté

    def test_enchainement(self):
        r = Run()
        out = la.main(["--targets", "192.0.2.0/24, 198.51.100.0/24", "--exclude", "192.0.2.5"], runner=r, which=lambda x: "/usr/bin/nmap")
        self.assertEqual(len(r.calls), 2)
        self.assertIn("-sn", r.calls[0]); self.assertIn("--exclude", r.calls[0])
        self.assertEqual(r.calls[1][-2:], ["192.0.2.20", "192.0.2.100"])  # détail sur les seuls vivants
        self.assertIn("-sV", r.calls[1]); self.assertIn("-O", r.calls[1])
        self.assertEqual(out["stats"]["vivants"], 2)
        self.assertEqual(out["targets"], ["192.0.2.0/24", "198.51.100.0/24"])
        out = la.main(["--targets", "192.0.2.0/24", "--no-os", "--no-versions"], runner=Run(), which=lambda x: "/usr/bin/nmap")
        self.assertEqual(out["stats"]["vivants"], 2)

    def test_sans_nmap_ou_sans_cible(self):
        self.assertEqual(la.main(["--targets", "192.0.2.0/24"], which=lambda x: None)["alerts"][0]["code"], "lan-audit-nmap")
        self.assertEqual(la.main([], runner=Run(), which=lambda x: "/usr/bin/nmap")["alerts"][0]["code"], "lan-audit-cibles")


if __name__ == "__main__":
    unittest.main()
