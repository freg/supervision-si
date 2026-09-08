# -*- coding: utf-8 -*-
"""#440 : collecteurs Windows -- traduction PURE des sorties JSON des scripts
PowerShell (échantillons représentatifs d'un Windows 11 : MAC avec tirets,
états « Up », routes Windows) et, si `pwsh` est disponible, exécution
réelle des scripts (syntaxe, enchaînement, JSON) même sans les sources
Windows (tout en `partial`)."""
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import winhost, risks, plugins, control  # noqa: E402
from si_agent.host import CmdResult  # noqa: E402

HOST_RAW = {
    "system": {"hostname": "PC-COMPTA", "os": "Microsoft Windows 11 Pro", "os_version": "10.0.22631", "build": "22631", "display_version": "23H2",
               "arch": "64 bits", "install_date": "2024-03-02T10:00:00Z", "last_boot": "2026-09-07T06:00:00Z", "uptime_seconds": 90000,
               "cpu_model": "13th Gen Intel(R) Core(TM) i5-1335U", "cpus": 12, "domain": "WORKGROUP", "part_of_domain": False, "reboot_required": True},
    "cpu": {"percent": 7}, "memory": {"total_bytes": 17179869184, "available_bytes": 8589934592, "page_total_bytes": 4294967296, "page_used_bytes": 1073741824},
    "disks": [{"mountpoint": "C:\\", "label": "Windows", "fstype": "NTFS", "drive_type": 3, "provider": None, "total_bytes": 511000000000, "free_bytes": 51100000000},
              {"mountpoint": "Z:\\", "label": None, "fstype": "NTFS", "drive_type": 4, "provider": "\\\\nas\\partage", "total_bytes": 2000000000000, "free_bytes": 500000000000},
              {"mountpoint": "E:\\", "label": None, "fstype": None, "drive_type": 2, "provider": None, "total_bytes": None, "free_bytes": None}],
    "services": {"failed": ["gupdate", "SysMain"], "running_count": 143},
    "ports": [{"proto": "tcp", "address": "0.0.0.0", "port": 3389, "pid": 1200, "process": "svchost"}, {"proto": "tcp", "address": "127.0.0.1", "port": 5939, "pid": 4000, "process": "TeamViewer_Service"}],
    "logs": [{"time": "2026-09-08T07:10:00Z", "log": "System", "source": "Service Control Manager", "id": 7000, "level": 2, "message": "Le service X n'a pas pu démarrer"}],
    "accounts": {"admins": ["PC-COMPTA\\Administrateur", "PC-COMPTA\\freg"], "local_users": ["freg", "Invité"], "console_user": "PC-COMPTA\\freg"},
    "windows": {"updates": {"pending_reboot": True, "last_hotfix": "KB5041585", "last_hotfix_date": "2026-08-20T00:00:00Z"},
                "defender": {"enabled": True, "realtime": False, "signatures_age_days": 12, "last_quick_scan": "2026-09-01T00:00:00Z"},
                "firewall": [{"profile": "Domain", "enabled": True}, {"profile": "Private", "enabled": True}, {"profile": "Public", "enabled": False}], "bitlocker_c": "On"},
    "partial": [],
}
NETVIEW_RAW = {
    "adapters": [{"index": 5, "name": "Ethernet", "description": "Intel(R) Ethernet Connection", "mac": "A4-BB-6D-11-22-33", "status": "Up", "mtu": 1500, "speed": "1 Gbps", "virtual": False},
                 {"index": 12, "name": "Wi-Fi", "description": "Intel(R) Wi-Fi 6", "mac": "A4-BB-6D-44-55-66", "status": "Disconnected", "mtu": 1500, "speed": "0 bps", "virtual": False}],
    "addresses": [{"index": 5, "alias": "Ethernet", "ip": "192.168.1.35", "prefix": 24, "family": "IPv4", "origin": "Dhcp", "state": "Preferred"},
                  {"index": 5, "alias": "Ethernet", "ip": "fe80::1c2b:3d4e:5f60:7a8b", "prefix": 64, "family": "IPv6", "origin": "WellKnown", "state": "Preferred"},
                  {"index": 1, "alias": "Loopback Pseudo-Interface 1", "ip": "127.0.0.1", "prefix": 8, "family": "IPv4", "origin": "WellKnown", "state": "Preferred"}],
    "routes": [{"dst": "0.0.0.0/0", "gateway": "192.168.1.1", "alias": "Ethernet", "index": 5, "metric": 0, "protocol": "NetMgmt", "family": "IPv4"},
               {"dst": "192.168.1.0/24", "gateway": "0.0.0.0", "alias": "Ethernet", "index": 5, "metric": 256, "protocol": "Local", "family": "IPv4"},
               {"dst": "192.168.1.35/32", "gateway": "0.0.0.0", "alias": "Ethernet", "index": 5, "metric": 256, "protocol": "Local", "family": "IPv4"},
               {"dst": "10.20.0.0/16", "gateway": "192.168.1.254", "alias": "Ethernet", "index": 5, "metric": 10, "protocol": "NetMgmt", "family": "IPv4"},
               {"dst": "224.0.0.0/4", "gateway": "0.0.0.0", "alias": "Ethernet", "index": 5, "metric": 256, "protocol": "Local", "family": "IPv4"},
               {"dst": "::/0", "gateway": "fe80::1", "alias": "Ethernet", "index": 5, "metric": 256, "protocol": "NetMgmt", "family": "IPv6"}],
    "neighbors": [{"ip": "192.168.1.1", "mac": "00-11-22-33-44-55", "alias": "Ethernet", "state": "Reachable", "family": "IPv4"},
                  {"ip": "192.168.1.254", "mac": "00-11-22-33-44-FE", "alias": "Ethernet", "state": "Stale", "family": "IPv4"},
                  {"ip": "224.0.0.251", "mac": "01-00-5E-00-00-FB", "alias": "Ethernet", "state": "Permanent", "family": "IPv4"}],
    "connections": [{"proto": "tcp", "local_ip": "192.168.1.35", "local_port": 51000, "remote_ip": "10.20.3.7", "remote_port": 443, "pid": 3300, "process": "OUTLOOK"},
                    {"proto": "tcp", "local_ip": "192.168.1.35", "local_port": 51001, "remote_ip": "192.168.1.21", "remote_port": 445, "pid": 4, "process": "System"}],
    "dns": {"servers": ["192.168.1.1", "9.9.9.9"], "search": ["groupe-x.lan"]}, "partial": [],
}
HARDWARE_RAW = {
    "vendor": "Dell Inc.", "product": "Latitude 5540", "product_version": None, "serial": "ABC1234 ", "uuid": "4C4C4544-0000", "chassis": "2",
    "bios": "Dell Inc. 1.12.0 (2025-01-10T00:00:00Z)", "board": "Dell Inc. 0ABCDE",
    "cpu": {"model": "13th Gen Intel(R) Core(TM) i5-1335U", "sockets": 1, "cores": 10, "cpus": 12, "cores_per_socket": 10, "threads_per_core": 1, "mhz_max": 1300, "arch": "AMD64", "hypervisor": None},
    "memory_total_bytes": 17179869184,
    "disks": [{"name": "\\\\.\\PHYSICALDRIVE0", "model": "NVMe SK hynix 512GB", "serial": "0025_38B7", "size_bytes": 512110190592, "interface": "SCSI", "media": "SSD", "bus": "NVMe", "health": "Healthy"}],
    "nics": [{"name": "Ethernet", "description": "Intel(R) Ethernet Connection", "mac": "A4:BB:6D:11:22:33", "state": "up", "speed_mbps": 1000}],
    "gpus": ["Intel(R) Iris(R) Xe Graphics"], "monitors": [], "virtualization": "none",
    "software": [{"name": "7-Zip 23.01", "version": "23.01", "publisher": "Igor Pavlov", "installed": "20240302"}], "software_count": 1, "partial": [],
}
ACTIVITY_RAW = {
    "process_count": 210, "top_cpu": [{"pid": 3300, "command": "OUTLOOK", "cpu_percent": 12.5, "rss_bytes": 400000000, "elapsed_seconds": 3600, "user": None}],
    "top_memory": [{"pid": 3300, "command": "OUTLOOK", "cpu_percent": 12.5, "rss_bytes": 400000000, "elapsed_seconds": 3600, "user": None}],
    "sessions": [], "sessions_raw": [" UTILISATEUR           SESSION            ID  ÉTAT    TEMPS INACT.  TEMPS SESSION",
                                     ">freg                  console             1  Actif        aucun   08/09/2026 08:01",
                                     " admin                                     2  Déco          1:12   07/09/2026 18:30"],
    "last_logins": [{"user": "PC-COMPTA\\freg", "type": 2, "from": "-", "at": "2026-09-08T06:01:00Z"}, {"user": "GROUPE-X\\tech", "type": 10, "from": "192.168.1.50", "at": "2026-09-07T16:00:00Z"}],
    "running_services": ["Dhcp", "Dnscache", "WinDefend"], "running_services_count": 3, "updates_available": 3, "partial": [],
}


class MapTests(unittest.TestCase):
    def test_host(self):
        d = winhost.map_host(HOST_RAW)
        s = d["system"]
        self.assertEqual((s["hostname"], s["os_id"], s["kernel"], s["cpus"], s["reboot_required"]), ("PC-COMPTA", "windows", "build 22631", 12, True))
        self.assertEqual(d["memory"]["used_percent"], 50.0)
        self.assertEqual(d["memory"]["swap_used_percent"], 25.0)
        c, z, e = d["disks"]
        self.assertEqual((c["mountpoint"], c["used_percent"], c["remote"]), ("C:\\", 90.0, False))
        self.assertEqual((z["device"], z["remote"], z["used_percent"]), ("\\\\nas\\partage", True, 75.0))
        self.assertIsNone(e["used_percent"]); self.assertIn("taille inconnue", e["error"])
        self.assertTrue(d["ports"]["ports"][0]["exposed"]); self.assertFalse(d["ports"]["ports"][1]["exposed"])
        self.assertIn("Service Control Manager (7000)", d["logs"]["lines"][0])
        self.assertEqual(d["accounts"]["sudoers"], ["PC-COMPTA\\Administrateur", "PC-COMPTA\\freg"])
        self.assertEqual(d["services"]["failed"], ["gupdate", "SysMain"])
        self.assertEqual(d["windows"]["defender"]["realtime"], False)
        # risques : disque plein, redémarrage, services, RDP exposé, Defender, pare-feu
        d["activity"] = winhost.map_activity(ACTIVITY_RAW)
        found = risks.evaluate(d)
        ids = {r["id"] for r in found}
        self.assertTrue({"disk-high", "reboot-required", "service-failed", "defender-realtime-off", "firewall-profile-off", "updates-pending"} <= ids, ids)
        svc = [r for r in found if r["id"] == "service-failed"][0]
        self.assertIn("service Windows", svc["message"])

    def test_host_empty(self):
        d = winhost.map_host({})
        self.assertEqual(d["system"]["os_id"], "windows")
        self.assertIn("os", d["partial"])
        self.assertEqual(risks.evaluate(d), [])

    def test_netview(self):
        d = winhost.map_netview(NETVIEW_RAW)
        eth = [i for i in d["interfaces"] if i["name"] == "Ethernet"][0]
        self.assertEqual(eth["mac"], "a4:bb:6d:11:22:33")
        self.assertEqual([(a["ip"], a["family"], a["scope"]) for a in eth["addresses"]], [("192.168.1.35", "inet", "global"), ("fe80::1c2b:3d4e:5f60:7a8b", "inet6", "link")])
        self.assertEqual([(r["kind"], r["dst"], r["gateway"]) for r in d["routes"]],
                         [("default", "default", "192.168.1.1"), ("via", "10.20.0.0/16", "192.168.1.254"), ("direct", "192.168.1.0/24", None)])
        self.assertEqual([(n["ip"], n["state"]) for n in d["neighbors"]], [("192.168.1.1", "reachable"), ("192.168.1.254", "stale")])
        s = d["summary"]
        self.assertEqual(s["attached_subnets"], ["192.168.1.0/24"])
        self.assertEqual((s["default_gateway"], s["default_gateway_state"]), ("192.168.1.1", "reachable"))
        self.assertEqual(s["reachable_subnets"][0]["subnet"], "10.20.0.0/16")
        self.assertEqual([p["ip"] for p in s["peers"]], ["10.20.3.7", "192.168.1.21"])
        self.assertEqual(d["dns"]["servers"], ["192.168.1.1", "9.9.9.9"])

    def test_hardware_and_activity(self):
        h = winhost.map_hardware(HARDWARE_RAW)
        self.assertEqual((h["vendor"], h["product"], h["serial"]), ("Dell Inc.", "Latitude 5540", "ABC1234"))
        self.assertEqual(h["cpu"]["cpus"], 12)
        self.assertEqual((h["disks"][0]["size"], h["disks"][0]["rotational"], h["disks"][0]["transport"]), ("476.9G", False, "nvme"))
        self.assertEqual(h["software_count"], 1)
        a = winhost.map_activity(ACTIVITY_RAW)
        self.assertEqual(a["top_cpu"][0]["command"], "OUTLOOK")
        self.assertEqual([(s["user"], s["tty"]) for s in a["sessions"]], [("freg", "console"), ("admin", "déconnectée")])
        self.assertEqual(a["sessions"][0]["since"], "08/09/2026 08:01")
        self.assertEqual([(l["tty"], l["from"]) for l in a["last_logins"]], [("console", None), ("rdp", "192.168.1.50")])
        self.assertEqual(a["updates_available"], 3)

    def test_quser_columns(self):
        rows = winhost.parse_quser([" USERNAME              SESSIONNAME        ID  STATE   IDLE TIME  LOGON TIME",
                                    ">bob                   console             1  Active      none   9/8/2026 8:01 AM",
                                    " alice                 rdp-tcp#3           2  Active         .   9/8/2026 9:00 AM"])
        self.assertEqual([(r["user"], r["session"], r["id"]) for r in rows], [("bob", "console", "1"), ("alice", "rdp-tcp#3", "2")])
        self.assertEqual(winhost.parse_quser([]), [])

    def test_run_ps_errors(self):
        def missing(argv, timeout=None, **kw):
            return CmdResult(-127, "", "binaire introuvable : powershell.exe")
        raw, err = winhost.run_ps(missing, "host")
        self.assertIsNone(raw); self.assertIn("introuvable", err)
        data, prev = winhost.collect_all(cmd=missing, include_tools=False)
        self.assertEqual(data["partial"], ["powershell:host"]); self.assertIsNone(prev)
        def noisy(argv, timeout=None, **kw):
            return CmdResult(0, "\ufeffWARNING: bla\n{\"system\": {\"hostname\": \"X\"}, \"partial\": []}\n", "")
        raw, err = winhost.run_ps(noisy, "host")
        self.assertEqual(raw["system"]["hostname"], "X")

    def test_plugins_powershell_runner(self):
        ok, why = plugins.validate_manifest({"id": "win-check", "version": "1", "runner": "powershell", "entry": "check.ps1", "interval_seconds": 300})
        self.assertTrue(ok, why)
        seen = {}
        def cmd(argv, timeout=None, **kw):
            seen["argv"] = argv
            return CmdResult(0, json.dumps({"ok": 1}), "")
        m = plugins.run_plugin({"id": "win-check", "runner": "powershell", "path": "/x/check.ps1", "present": True, "timeout_seconds": 30}, cmd, now=0)
        self.assertTrue(m["ok"]); self.assertEqual(seen["argv"][-1], "/x/check.ps1"); self.assertIn("-ExecutionPolicy", seen["argv"])
        env = control.plugin_env("a1", "siege", "p", base_env={"SystemRoot": "C:\\Windows", "SECRET_TOKEN": "x", "PATH": "C:\\Windows"})
        self.assertNotIn("SECRET_TOKEN", env); self.assertEqual(env["SystemRoot"], "C:\\Windows"); self.assertEqual(env["SI_AGENT_SITE"], "siege")


PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if os.path.exists("/opt/pwsh/pwsh") else None)


@unittest.skipIf(not PWSH, "pwsh absent")
class RealScriptsTests(unittest.TestCase):
    """Les 4 scripts exécutés réellement (PowerShell 7 sous Linux : aucune
    source Windows, tout en partial) : syntaxe, enchaînement, JSON valide."""

    def _cmd(self, argv, timeout=None, **kw):
        import subprocess
        argv = [PWSH] + argv[1:]
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout or 120)
        return CmdResult(p.returncode, p.stdout, p.stderr)

    def test_scripts(self):
        data, _ = winhost.collect_all(cmd=self._cmd, include_tools=False)
        self.assertEqual(data["system"]["os_id"], "windows")
        self.assertNotIn("powershell:host", data["partial"], data.get("error"))
        a = winhost.collect_activity(cmd=self._cmd)
        self.assertIsInstance(a["process_count"], int)   # Get-Process existe sous pwsh Linux
        self.assertNotIn("powershell:activity", a["partial"], a.get("error"))
        h = winhost.collect_hardware(cmd=self._cmd)
        self.assertNotIn("powershell:hardware", h["partial"], h.get("error"))
        n = winhost.collect_netview(cmd=self._cmd)
        self.assertNotIn("powershell:netview", n["partial"], n.get("error"))
        self.assertIn("summary", n)


if __name__ == "__main__":
    unittest.main()
