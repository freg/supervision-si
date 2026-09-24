# -*- coding: utf-8 -*-
"""Tests cisco-api (#508) : parseurs sur sorties représentatives (C3750
IOS 12.2, C2970, Nexus 3064PQ NX-OS), API avec fausse session SSH
(sauvegarde, diff, restauration fusion, gestes d'urgence, journal)."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
_TMP = tempfile.mkdtemp()
os.environ["CISCO_DATA_DIR"] = _TMP
os.environ["CISCO_REGISTRY"] = os.path.join(_TMP, "switches.json")
os.environ["CISCO_BACKUP_THREAD"] = "0"
os.environ["CREDENTIALS_API_URL"] = "http://credentials-api:5000"
os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "jeton"
with open(os.environ["CISCO_REGISTRY"], "w") as fh:
    json.dump({"switches": [{"name": "sw-alpha", "host": "192.0.2.2", "platform": "ios", "credential": "cisco"},
                            {"name": "nx-b", "host": "192.0.2.3", "platform": "nxos", "credential": "cisco"}]}, fh)

import app as appmod  # noqa: E402
import parsers  # noqa: E402
from ssh_client import CiscoError, CiscoSession  # noqa: E402

VERSION_3750 = """Cisco IOS Software, C3750 Software (C3750-IPBASEK9-M), Version 12.2(55)SE12, RELEASE SOFTWARE (fc2)
Technical Support: http://www.cisco.com/techsupport
Copyright (c) 1986-2017 by Cisco Systems, Inc.
ROM: Bootstrap program is C3750 boot loader

sw-alpha uptime is 2 years, 14 weeks, 3 days, 2 hours, 10 minutes
System returned to ROM by power-on
System image file is "flash:/c3750-ipbasek9-mz.122-55.SE12/c3750-ipbasek9-mz.122-55.SE12.bin"

cisco WS-C3750G-24TS-1U (PowerPC405) processor (revision H0) with 131072K bytes of memory.
Processor board ID CAT0000AAAA
System serial number            : CAT0000AAAA
Model number                    : WS-C3750G-24TS-S1U
"""
VERSION_NX = """Cisco Nexus Operating System (NX-OS) Software
  NXOS: version 6.0(2)U6(10)
  NXOS image file is: bootflash:///n3000-uk9.6.0.2.U6.10.bin

Hardware
  cisco Nexus 3064 Chassis ("48x10GE + 16x10G/4x40G Supervisor")
  Intel(R) Celeron(R) CPU        P4505  @ 1.87GHz with 3793764 kB of memory.
  Processor Board ID FOC0000BBBB

  Device name: nx-b
  bootflash:    2007040 kB

Kernel uptime is 120 day(s), 3 hour(s), 22 minute(s), 5 second(s)
"""
CPU_IOS = "CPU utilization for five seconds: 12%/0%; one minute: 10%; five minutes: 9%"
MEM_IOS = """                Head    Total(b)     Used(b)     Free(b)   Lowest(b)  Largest(b)
Processor    2B9A3D8    68520232    30184944    38335288    32056000    35962672
      I/O    2C00000    12582912     7521008     5061904     5059664     5059516
"""
RES_NX = """Load average:   1 minute: 0.42   5 minutes: 0.30   15 minutes: 0.25
Processes   :     542 total, 1 running
CPU states  :   3.5% user,   2.0% kernel,  94.5% idle
Memory usage:   3793764K total,   1520008K used,   2273756K free
"""
ENV_IOS = """FAN is OK
TEMPERATURE is OK
Temperature Value: 33 Degree Celsius
POWER SUPPLY 1 is OK
POWER SUPPLY 2 is NOT PRESENT
"""
ENV_NX = """Fan:
Fan             Model                Hw         Status
Fan1(sys_fan1)  N3K-C3064-FAN        --         Ok
Fan2(sys_fan2)  N3K-C3064-FAN        --         Failure
Power Supply:
PS  Model                 Input Power       Actual Output   Total Capacity  Status
1   N2200-PAC-400W        AC       162.00 W    400.00 W    Ok
"""
IF_STATUS = """Port      Name               Status       Vlan       Duplex  Speed Type
Gi1/0/1   serveur-alpha      connected    10         a-full  a-1000 10/100/1000BaseTX
Gi1/0/2                      notconnect   1            auto   auto 10/100/1000BaseTX
Gi1/0/3   borne              err-disabled 20           auto   auto 10/100/1000BaseTX
Gi1/0/25  uplink             connected    trunk        full   1000 1000BaseSX SFP
"""
LOGGING = """Syslog logging: enabled (0 messages dropped, 1 messages rate-limited)
Log Buffer (4096 bytes):
*Mar  1 00:01:02.123: %SYS-5-CONFIG_I: Configured from console by alice on vty0
*Mar  1 00:02:03.456: %LINK-3-UPDOWN: Interface GigabitEthernet1/0/2, changed state to down
*Mar  1 00:02:04.789: %PM-4-ERR_DISABLE: bpduguard error detected on Gi1/0/3, putting Gi1/0/3 in err-disable state
"""
RUNNING = """Building configuration...

Current configuration : 4321 bytes
!
! Last configuration change at 10:00:00 UTC Mon Sep 14 2026 by alice
!
version 12.2
hostname sw-alpha
!
interface GigabitEthernet1/0/1
 description serveur-alpha
 switchport access vlan 10
!
interface GigabitEthernet1/0/2
 shutdown
!
ntp clock-period 17179870
ntp server 192.0.2.100
!
end
"""
SAVED = RUNNING.replace(" shutdown\n", " description libre\n switchport access vlan 30\n").replace("ntp server 192.0.2.100\n", "ntp server 192.0.2.100\nlogging host 192.0.2.50\n")


class FakeSession:
    """Rejoue des sorties « show » et enregistre ce qui est envoyé."""
    outputs = {}
    sent = []
    fail = False

    def __init__(self, host, username, password, port=22, timeout=10, enable_password=None, transport=None, protocol="ssh"):
        self.host, self.platform, self.protocol = host, "ios", protocol
        assert password == "secret-ssh"

    def __enter__(self):
        if FakeSession.fail:
            raise CiscoError("connexion SSH impossible vers %s:22 (timeout)" % self.host)
        return self

    def __exit__(self, *a):
        pass

    def show(self, command, timeout=None):
        FakeSession.sent.append(command)
        key = command.split(" |")[0]
        if key in FakeSession.outputs:
            return FakeSession.outputs[key]
        if command.startswith("show"):
            return ""
        raise CiscoError("refusée")

    def run(self, command, timeout=None):
        FakeSession.sent.append(command)
        return "Reload cancelled."

    def configure(self, lines, timeout=None):
        FakeSession.sent.append("CONF: " + " / ".join(lines))
        return [{"line": l, "error": "% Invalid input"} for l in lines if "invalide" in l]

    def write_memory(self, timeout=None):
        FakeSession.sent.append("write memory")
        return "[OK]"


class ParserTests(unittest.TestCase):
    def test_version(self):
        v = parsers.parse_version(VERSION_3750)
        self.assertEqual((v["platform"], v["version"], v["model"], v["hostname"], v["serial"]), ("ios", "12.2(55)SE12", "WS-C3750G-24TS-1U", "sw-alpha", "CAT0000AAAA"))
        self.assertTrue(v["uptime"].startswith("2 years"))
        n = parsers.parse_version(VERSION_NX)
        self.assertEqual((n["platform"], n["version"], n["hostname"], n["serial"]), ("nxos", "6.0(2)U6(10)", "nx-b", "FOC0000BBBB"))
        self.assertIn("Nexus 3064", n["model"])
        self.assertEqual(parsers.parse_version("")["platform"], "ios")

    def test_cpu_memory(self):
        self.assertEqual(parsers.parse_cpu(CPU_IOS), {"five_sec": 12, "one_min": 10, "five_min": 9})
        self.assertEqual(parsers.parse_cpu(RES_NX, "nxos")["five_min"], 5.5)
        m = parsers.parse_memory(MEM_IOS)
        self.assertEqual((m["total"], m["used_percent"]), (68520232, 44.1))
        self.assertEqual(parsers.parse_memory(RES_NX, "nxos")["used_percent"], 40.1)
        self.assertEqual(parsers.parse_cpu("rien"), {})

    def test_environment(self):
        e = parsers.parse_environment(ENV_IOS)
        self.assertEqual([x["ok"] for x in e], [True, True, True, True])
        self.assertEqual(e[3]["status"], "absent")
        n = parsers.parse_environment(ENV_NX)
        bad = [x for x in n if not x["ok"]]
        self.assertEqual(len(bad), 1)
        self.assertIn("Fan2", bad[0]["item"])

    def test_interfaces_logging_alerts(self):
        rows = parsers.parse_interfaces_status(IF_STATUS)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0], {"port": "Gi1/0/1", "name": "serveur-alpha", "status": "connected", "vlan": "10", "duplex": "a-full", "speed": "a-1000", "type": "10/100/1000BaseTX"})
        self.assertEqual(rows[2]["status"], "err-disabled")
        self.assertEqual(rows[3]["type"], "1000BaseSX SFP")
        logs = parsers.parse_logging(LOGGING)
        self.assertEqual([l["severity"] for l in logs], [5, 3, 4])
        self.assertEqual(logs[1]["facility"], "LINK")
        al = parsers.alerts({"cpu": {"five_min": 92}, "memory": {"used_percent": 85}, "environment": parsers.parse_environment(ENV_NX)}, rows, logs)
        kinds = [(a["kind"], a["severity"]) for a in al]
        self.assertEqual(kinds, [("cpu", "critical"), ("memory", "warning"), ("environment", "critical"), ("interface", "warning"), ("log", "warning")])
        self.assertEqual(parsers.alerts({}, [], []), [])

    def test_strip_and_plan(self):
        self.assertNotIn("Last configuration change", parsers.strip_volatile(RUNNING))
        self.assertNotIn("ntp clock-period", parsers.strip_volatile(RUNNING))
        plan = appmod.restore_plan(SAVED, RUNNING)
        self.assertEqual(plan, ["interface GigabitEthernet1/0/2", " description libre", " switchport access vlan 30", " exit", "logging host 192.0.2.50"])
        self.assertEqual(appmod.restore_plan(RUNNING, RUNNING), [])
        self.assertEqual(appmod.removed_lines(SAVED, RUNNING), ["interface GigabitEthernet1/0/2 > shutdown"])


class SessionTests(unittest.TestCase):
    """Le canal SSH simulé : invite, enable, pagination, écho retiré."""

    class Chan:
        def __init__(self, script):
            self.script, self.buf, self.sent = script, b"", []

        def send(self, data):
            self.sent.append(data)
            key = data.strip()
            self.buf += self.script.get(key, self.script.get("*", b"sw#")) if key or data == "\n" else b""

        def recv_ready(self):
            return bool(self.buf)

        def recv(self, n):
            b, self.buf = self.buf, b""
            return b

        def close(self):
            pass

    def test_enable_and_show(self):
        chan = self.Chan({"": b"\r\nsw>", "enable": b"Password: ", "motdepasse": b"\r\nsw#", "terminal length 0": b"terminal length 0\r\nsw#",
                          "terminal width 511": b"terminal width 511\r\nsw#",
                          "show clock": b"show clock\r\n*10:00:00.000 UTC Mon Sep 14 2026\r\n --More-- reste\r\nsw#"})
        s = CiscoSession("192.0.2.2", "alice", "motdepasse", transport=chan).open()
        self.assertIn("enable\n", chan.sent)
        self.assertIn("motdepasse\n", chan.sent)
        out = s.show("show clock")
        self.assertEqual(out, "*10:00:00.000 UTC Mon Sep 14 2026\n  reste")
        with self.assertRaises(CiscoError):
            s.show("configure terminal")
        chan.script["show bidule"] = b"show bidule\r\n% Invalid input detected at '^' marker.\r\nsw#"
        with self.assertRaises(CiscoError):
            s.show("show bidule")

    def test_enable_refused(self):
        """#585 : mot de passe enable faux -> erreur explicite, plus jamais un « show running-config » refusé en mode utilisateur."""
        chan = self.Chan({"": b"\r\nsw>", "enable": b"Password: ", "faux": b"\r\n% Bad secrets\r\n\r\nsw>"})
        with self.assertRaises(CiscoError) as ctx:
            CiscoSession("192.0.2.2", "alice", "faux", transport=chan).open()
        self.assertIn("enable", str(ctx.exception))
        chan = self.Chan({"": b"\r\nsw>", "enable": b"Password: ", "muet": b"\r\nsw>"})  # refus silencieux : l'invite reste « > »
        with self.assertRaises(CiscoError) as ctx:
            CiscoSession("192.0.2.2", "alice", "muet", transport=chan).open()
        self.assertIn("refusé", str(ctx.exception))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        appmod.SESSION_FACTORY = FakeSession
        appmod.credentials_for = lambda name: ("admin", "secret-ssh")
        cls.c = appmod.app.test_client()

    def setUp(self):
        FakeSession.sent = []
        FakeSession.fail = False
        FakeSession.outputs = {"show version": VERSION_3750, "show processes cpu": CPU_IOS, "show memory statistics": MEM_IOS,
                               "show env all": ENV_IOS, "show interfaces status": IF_STATUS, "show logging": LOGGING, "show running-config": RUNNING}

    def test_1_summary_and_unreachable(self):
        r = self.c.get("/cisco/switches/sw-alpha/summary")
        self.assertEqual(r.status_code, 200, r.get_json())
        b = r.get_json()
        self.assertEqual(b["version"]["model"], "WS-C3750G-24TS-1U")
        self.assertEqual(b["cpu"]["five_min"], 9)
        self.assertEqual(len(b["interfaces"]), 4)
        self.assertEqual([a["kind"] for a in b["alerts"]], ["interface", "log"])
        sw = self.c.get("/cisco/switches").get_json()["switches"]
        self.assertTrue(sw[0]["reachable"])
        self.assertEqual(sw[0]["alerts"], 2)
        FakeSession.fail = True
        r = self.c.get("/cisco/switches/sw-alpha/summary")
        self.assertEqual(r.status_code, 502)
        self.assertFalse(self.c.get("/cisco/switches").get_json()["switches"][0]["reachable"])
        self.assertEqual(self.c.get("/cisco/switches/inconnu/summary").status_code, 404)

    def test_2_backup_diff_restore(self):
        r = self.c.post("/cisco/switches/sw-alpha/configs/backup", json={"login": "alice"})
        self.assertEqual(r.status_code, 200, r.get_json())
        cid = r.get_json()["id"]
        self.assertTrue(r.get_json()["created"])
        r = self.c.post("/cisco/switches/sw-alpha/configs/backup", json={"login": "alice"})
        self.assertFalse(r.get_json()["created"])  # identique
        self.assertEqual(len(self.c.get("/cisco/switches/sw-alpha/configs").get_json()["configs"]), 1)
        self.assertIn("hostname sw-alpha", self.c.get("/cisco/switches/sw-alpha/configs/%s" % cid).get_json()["content"])
        # l'équipement change : diff contre la sauvegarde
        FakeSession.outputs["show running-config"] = SAVED
        d = self.c.get("/cisco/switches/sw-alpha/configs/diff?a=%s&b=running" % cid).get_json()
        self.assertFalse(d["identical"])
        self.assertIn("+logging host 192.0.2.50", d["diff"])
        # restauration : aperçu puis application
        FakeSession.outputs["show running-config"] = RUNNING
        cid2 = self.c.post("/cisco/switches/sw-alpha/configs/backup", json={}).get_json()["id"]
        self.assertEqual(cid2, cid)
        # on archive SAVED comme une version à restaurer
        appmod.save_config("sw-alpha", SAVED, "test")
        sid = self.c.get("/cisco/switches/sw-alpha/configs").get_json()["configs"][-1]["id"]
        r = self.c.post("/cisco/switches/sw-alpha/configs/%s/restore" % sid, json={"dry_run": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["count"], 5)
        self.assertEqual(r.get_json()["removed_not_handled"], ["interface GigabitEthernet1/0/2 > shutdown"])
        r = self.c.post("/cisco/switches/sw-alpha/configs/%s/restore" % sid, json={"dry_run": False})
        self.assertEqual(r.status_code, 400)  # confirmation absente
        r = self.c.post("/cisco/switches/sw-alpha/configs/%s/restore" % sid, json={"dry_run": False, "confirm": "sw-alpha", "login": "alice"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["applied"], 5)
        self.assertTrue(r.get_json()["written"])
        self.assertTrue(any(s.startswith("CONF: interface GigabitEthernet1/0/2") for s in FakeSession.sent))
        self.assertIn("write memory", FakeSession.sent)
        acts = self.c.get("/cisco/switches/sw-alpha/actions").get_json()["actions"]
        self.assertEqual(acts[-1]["by"], "alice")
        self.assertTrue(acts[-1]["action"].startswith("restore"))
        # une sauvegarde « avant restauration » a été prise
        self.assertTrue(any(c.get("source") == "avant restauration" for c in self.c.get("/cisco/switches/sw-alpha/configs").get_json()["configs"]))

    def test_3_emergency(self):
        r = self.c.post("/cisco/switches/sw-alpha/interfaces/Gi1/0/3/shutdown", json={})
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/cisco/switches/sw-alpha/interfaces/Gi1/0/3/no-shutdown", json={"confirm": "sw-alpha", "login": "bob"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIn("CONF: interface Gi1/0/3 /  no shutdown", FakeSession.sent)
        self.assertEqual(self.c.post("/cisco/switches/sw-alpha/interfaces/Gi1;reload/shutdown", json={"confirm": "sw-alpha"}).status_code, 400)
        r = self.c.post("/cisco/switches/sw-alpha/write", json={"confirm": "sw-alpha"})
        self.assertEqual(r.status_code, 200)
        r = self.c.post("/cisco/switches/sw-alpha/reload", json={"confirm": "sw-alpha", "cancel": True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["cancelled"])
        r = self.c.post("/cisco/switches/sw-alpha/show", json={"command": "show ip interface brief | include up"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.post("/cisco/switches/sw-alpha/show", json={"command": "reload"}).status_code, 400)
        self.assertEqual(self.c.post("/cisco/switches/sw-alpha/show", json={"command": "show run | redirect x"}).status_code, 400)
        acts = self.c.get("/cisco/switches/sw-alpha/actions").get_json()["actions"]
        self.assertTrue(any(a["action"] == "no-shutdown Gi1/0/3" and a["by"] == "bob" for a in acts))


if __name__ == "__main__":
    unittest.main()


class TelnetTests(unittest.TestCase):
    """#579 : transport telnet -- équipement simulé sur une socket locale (négociation IAC, login, enable, show)."""

    def test_telnet_session(self):
        import socket, threading
        from ssh_client import CiscoSession, CiscoError
        srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); port = srv.getsockname()[1]
        seen = []
        def device():
            c, _ = srv.accept(); c.settimeout(5)
            c.sendall(bytes([255, 251, 1, 255, 251, 3, 255, 253, 24]) + b"\r\nUser Access Verification\r\n\r\nUsername: ")
            def readline():
                buf = b""
                while not buf.endswith(b"\r\n"):
                    d = c.recv(1)
                    if not d:
                        return buf
                    if d == b"\xff":  # réponse de négociation : IAC cmd opt
                        c.recv(2); continue
                    buf += d
                return buf.strip(b"\r\n")
            seen.append(readline()); c.sendall(b"Password: ")
            seen.append(readline()); c.sendall(b"\r\nsw-old>")
            while True:
                line = readline()
                if line is None or line == b"" and not seen:
                    break
                seen.append(line)
                if line == b"":
                    c.sendall(b"\r\nsw-old#" if b"enable" in seen else b"\r\nsw-old>")
                elif line == b"enable":
                    c.sendall(b"\r\nPassword: ")
                elif line == b"secret-ssh" and seen[-2] == b"enable":
                    c.sendall(b"\r\nsw-old#")
                elif line.startswith(b"terminal"):
                    c.sendall(b"\r\nsw-old#")
                elif line == b"show clock":
                    c.sendall(b"\r\n*10:00:00.000 UTC Tue Sep 23 2026\r\nsw-old#")
                elif line == b"quit":
                    break
                else:
                    c.sendall(b"\r\nsw-old#")
            c.close()
        t = threading.Thread(target=device, daemon=True); t.start()
        s = CiscoSession("127.0.0.1", "admin", "secret-ssh", port=port, timeout=3, protocol="telnet")
        with s:
            out = s.show("show clock")
        self.assertIn("Sep 23 2026", out)
        self.assertEqual(seen[0], b"admin"); self.assertEqual(seen[1], b"secret-ssh")
        srv.close()

    def test_telnet_refused(self):
        import socket, threading
        from ssh_client import CiscoSession, CiscoError
        srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); port = srv.getsockname()[1]
        def device():
            c, _ = srv.accept(); c.settimeout(5); c.sendall(b"Password: ")
            c.recv(100); c.sendall(b"\r\n% Login invalid\r\n\r\nPassword: "); c.recv(100); c.close()
        threading.Thread(target=device, daemon=True).start()
        with self.assertRaises(CiscoError) as cm:
            CiscoSession("127.0.0.1", "admin", "bad", port=port, timeout=3, protocol="telnet").open()
        self.assertIn("refusée", str(cm.exception))
        srv.close()

    def test_registry_edit_from_tile(self):
        """#592 : ajout / modification / suppression depuis la tuile -> switches.local.json (l'exemple n'est jamais réécrit)."""
        import json, tempfile, os
        import app as appmod
        d = tempfile.mkdtemp()
        old = (appmod.REGISTRY, appmod.REGISTRY_LOCAL)
        appmod.REGISTRY, appmod.REGISTRY_LOCAL = os.path.join(d, "switches.json"), os.path.join(d, "switches.local.json")
        json.dump({"switches": [{"name": "exemple-c3750", "host": "192.0.2.10", "credential": "cisco"}]}, open(appmod.REGISTRY, "w"))
        c = appmod.app.test_client()
        try:
            r = c.post("/cisco/switches", json={"name": "routeur-bureau", "host": "192.0.2.249", "transport": "telnet", "credential": "rb", "enable_credential": "rb-en", "platform": "IOS"})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(r.get_json()["action"], "added")
            local = json.load(open(appmod.REGISTRY_LOCAL))["switches"]
            self.assertEqual([x["name"] for x in local], ["routeur-bureau"])  # l'exemple ne migre pas
            self.assertEqual((local[0]["transport"], local[0]["enable_credential"]), ("telnet", "rb-en"))
            self.assertEqual(json.load(open(appmod.REGISTRY))["switches"][0]["name"], "exemple-c3750")  # intact
            self.assertEqual(c.post("/cisco/switches", json={"name": "routeur-bureau", "host": "192.0.2.250", "credential": "rb"}).get_json()["action"], "updated")
            self.assertEqual([s["host"] for s in appmod.load_registry()], ["192.0.2.250"])
            self.assertEqual(c.post("/cisco/switches", json={"name": "a b", "host": "", "platform": "junos"}).status_code, 400)
            self.assertEqual(c.delete("/cisco/switches/routeur-bureau").status_code, 200)
            self.assertEqual(c.delete("/cisco/switches/routeur-bureau").status_code, 404)
        finally:
            appmod.REGISTRY, appmod.REGISTRY_LOCAL = old

    def test_registry_transport(self):
        import json, tempfile, os, importlib
        import app as appmod
        d = tempfile.mkdtemp(); reg = os.path.join(d, "s.json")
        json.dump({"switches": [{"name": "old", "host": "192.0.2.9", "transport": "telnet", "credential": "c"}, {"name": "new", "host": "192.0.2.8", "credential": "c"}, {"name": "x", "host": "192.0.2.7", "transport": "rsh"}]}, open(reg, "w"))
        old = appmod.REGISTRY; appmod.REGISTRY = reg
        try:
            sw = {s["name"]: s for s in appmod.load_registry()}
        finally:
            appmod.REGISTRY = old
        self.assertEqual((sw["old"]["transport"], sw["old"]["port"]), ("telnet", 23))
        self.assertEqual((sw["new"]["transport"], sw["new"]["port"]), ("ssh", 22))
        self.assertEqual(sw["x"]["transport"], "ssh")


class RouterParsers(unittest.TestCase):
    def test_ip_interface_brief(self):
        import parsers
        txt = """Interface                  IP-Address      OK? Method Status                Protocol
FastEthernet0/0            192.0.2.1       YES NVRAM  up                    up
FastEthernet0/1            unassigned      YES NVRAM  administratively down down
Serial0/0                  198.51.100.2    YES manual down                  down
"""
        rows = parsers.parse_ip_interface_brief(txt)
        self.assertEqual([r["status"] for r in rows], ["connected", "disabled", "notconnect"])
        self.assertEqual(rows[0]["name"], "192.0.2.1"); self.assertEqual(rows[1]["name"], "")
