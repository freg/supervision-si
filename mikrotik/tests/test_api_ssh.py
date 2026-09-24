# -*- coding: utf-8 -*-
"""#587 : routes NAT et commande libre de l'API avec un routeur SSH simulé
(registre local temporaire, coffre simulé)."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp()
REG = os.path.join(TMP, "routers.json")
with open(REG, "w", encoding="utf-8") as fh:
    json.dump({"routers": [{"name": "rb", "host": "192.0.2.253", "transport": "ssh", "credential": "rb-ssh"},
                           {"name": "rest", "host": "192.0.2.1"}]}, fh)
os.environ["MIKROTIK_REGISTRY"] = REG
os.environ["MIKROTIK_REGISTRY_LOCAL"] = os.path.join(TMP, "absent.json")
os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "t"

import app as appmod  # noqa: E402
from ssh_client import RouterOSSsh  # noqa: E402


class FakeSsh(RouterOSSsh):
    cmds = []

    def __init__(self, host, port, user, password, timeout=12):
        def runner(cmd):
            FakeSsh.cmds.append(cmd)
            if cmd.startswith(":foreach i in=[/ip firewall nat find]"):
                return ".id=*A;chain=dstnat;action=dst-nat;protocol=tcp;dst-port=8443;to-addresses=192.0.2.10;to-ports=443;disabled=false\n", 0
            if cmd.startswith("/ip firewall nat add"):
                return "*B\n", 0
            if cmd == "/ip address print":
                return "Flags: X - disabled\n #   ADDRESS            NETWORK\n 0   192.0.2.253/24     192.0.2.0\n", 0
            return "", 0
        RouterOSSsh.__init__(self, host, port, user, password, timeout=timeout, runner=runner)


class Api(unittest.TestCase):
    def setUp(self):
        appmod.RouterOSSsh = FakeSsh
        appmod.credentials_for = lambda cred: ("hub", "pw", None)
        FakeSsh.cmds = []
        self.c = appmod.app.test_client()

    def test_registry_transport(self):
        routers, _ = appmod.load_registry()
        self.assertEqual((routers[0]["transport"], routers[0]["port"]), ("ssh", 22))
        self.assertEqual((routers[1]["transport"], routers[1]["port"]), ("rest", 443))

    def test_nat_flow(self):
        r = self.c.get("/mikrotik/routers/rb/nat").get_json()
        self.assertEqual(r["rules"][0]["summary"], "tcp *:8443 → 192.0.2.10:443")
        bad = self.c.post("/mikrotik/routers/rb/nat", json={"chain": "dstnat", "action": "dst-nat", "dst-port": "22", "to-addresses": "x"})
        self.assertEqual(bad.status_code, 400)
        self.assertTrue(bad.get_json()["errors"])
        ok = self.c.post("/mikrotik/routers/rb/nat", json={"chain": "dstnat", "action": "dst-nat", "protocol": "tcp", "dst-port": "2222", "to-addresses": "192.0.2.20", "to-ports": "22", "comment": "ssh vm"})
        self.assertEqual(ok.status_code, 200, ok.get_json())
        self.assertIn('/ip firewall nat add chain="dstnat" action="dst-nat" protocol="tcp" to-addresses="192.0.2.20" dst-port="2222" to-ports="22" comment="ssh vm"', FakeSsh.cmds)
        self.assertEqual(self.c.patch("/mikrotik/routers/rb/nat/*A", json={"disabled": "yes"}).status_code, 200)
        self.assertIn('/ip firewall nat set *A disabled="yes"', FakeSsh.cmds)
        self.assertEqual(self.c.patch("/mikrotik/routers/rb/nat/*A", json={"chain": "input"}).status_code, 400)
        self.assertEqual(self.c.delete("/mikrotik/routers/rb/nat/*A", json={}).status_code, 400)
        self.assertEqual(self.c.delete("/mikrotik/routers/rb/nat/*A", json={"confirm": "REMOVE"}).status_code, 200)
        self.assertEqual(self.c.delete("/mikrotik/routers/rb/nat/1;reboot", json={"confirm": "REMOVE"}).status_code, 400)

    def test_registry_edit(self):
        """#592 : ajout depuis la tuile -> routers.local.json, puis visible dans le registre."""
        r = self.c.post("/mikrotik/routers", json={"name": "rb2", "host": "192.0.2.254", "transport": "SSH", "credential": "bureau", "site": "bureau"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["action"], "added")
        names = {x["name"]: x for x in appmod.load_registry()[0]}
        self.assertEqual((names["rb2"]["transport"], names["rb2"]["port"]), ("ssh", 22))
        self.assertIn("rb", names)  # les entrées existantes (non « exemple ») sont conservées
        self.assertEqual(self.c.post("/mikrotik/routers", json={"name": "rb2", "host": "x y", "credential": ""}).status_code, 400)
        self.assertEqual(self.c.delete("/mikrotik/routers/rb2").status_code, 200)
        self.assertNotIn("rb2", {x["name"] for x in appmod.load_registry()[0]})
        self.assertEqual(self.c.get("/mikrotik/credentials").status_code, 200)

    def test_command(self):
        r = self.c.post("/mikrotik/routers/rb/command", json={"command": "/ip address print"}).get_json()
        self.assertEqual(len(r["output"]), 3)
        self.assertEqual(self.c.post("/mikrotik/routers/rb/command", json={"command": "/system reboot"}).status_code, 400)
        self.assertEqual(self.c.post("/mikrotik/routers/rest/command", json={"command": "/ip address print"}).status_code, 400)
        self.assertTrue(self.c.get("/mikrotik/commands").get_json()["commands"])


if __name__ == "__main__":
    unittest.main()
