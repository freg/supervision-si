# -*- coding: utf-8 -*-
"""Livraison #428 -- découverte passive (netview) et revue de l'hôte
(review) : parseurs sur fixtures, synthèse, collecte avec commandes
simulées. python3 -m unittest tests.test_netview_review (depuis si-agent/agent)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from si_agent import host, netview, review  # noqa: E402

ADDR = [
    {"ifname": "lo", "flags": ["LOOPBACK", "UP"], "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8, "scope": "host"}]},
    {"ifname": "eth0", "address": "02:fc:00:00:00:01", "operstate": "UP", "mtu": 1500, "flags": ["BROADCAST", "UP"],
     "addr_info": [{"family": "inet", "local": "10.50.7.12", "prefixlen": 24, "scope": "global"}, {"family": "inet6", "local": "fe80::1", "prefixlen": 64, "scope": "link"}]},
]
ROUTE = [
    {"dst": "default", "gateway": "10.50.7.1", "dev": "eth0", "flags": []},
    {"dst": "10.50.7.0/24", "dev": "eth0", "protocol": "kernel", "scope": "link", "prefsrc": "10.50.7.12", "flags": []},
    {"dst": "192.168.100.0/24", "gateway": "10.50.7.254", "dev": "eth0", "protocol": "static", "flags": []},
]
NEIGH = [
    {"dst": "10.50.7.1", "dev": "eth0", "lladdr": "aa:bb:cc:00:00:01", "state": ["REACHABLE"]},
    {"dst": "10.50.7.254", "dev": "eth0", "lladdr": "aa:bb:cc:00:00:fe", "state": ["STALE"]},
    {"dst": "10.50.7.99", "dev": "eth0", "state": ["FAILED"]},
    {"dst": "192.168.100.5", "dev": "eth0", "lladdr": "aa:bb:cc:01:00:05", "state": ["REACHABLE"]},
]
SS = """tcp 0      0      10.50.7.12:43552 192.168.100.5:443 users:(("curl",pid=475,fd=14))
tcp 0      0      10.50.7.12:49688 192.168.100.5:443 users:(("curl",pid=466,fd=9))
tcp 0      0      10.50.7.12:22 10.50.7.30:51000 users:(("sshd",pid=900,fd=4))
udp 0      0      127.0.0.1:53 127.0.0.1:40000
tcp 0      0      [::1]:6379 [::1]:50000
"""


class FakeCmd(object):
    def __init__(self, outputs):
        self.outputs = outputs

    def __call__(self, argv, timeout=15, env=None):
        key = " ".join(argv[:2]) if argv[0] in ("ip", "ss", "ps", "systemctl", "lsblk") else argv[0]
        for k, (rc, out) in self.outputs.items():
            if key.startswith(k):
                return host.CmdResult(rc, out, "")
        return host.CmdResult(-127, "", "absent")


class NetviewTests(unittest.TestCase):
    def test_parseurs(self):
        itf = netview.parse_ip_addr(ADDR)
        self.assertEqual([i["name"] for i in itf], ["eth0"], "loopback exclu")
        self.assertEqual(itf[0]["addresses"][0], {"ip": "10.50.7.12", "prefix": 24, "family": "inet", "scope": "global"})
        routes = netview.parse_ip_route(ROUTE)
        self.assertEqual([r["kind"] for r in routes], ["default", "direct", "via"])
        neigh = netview.parse_ip_neigh(NEIGH)
        self.assertEqual([n["ip"] for n in neigh], ["10.50.7.1", "10.50.7.254", "192.168.100.5"], "FAILED écarté")
        self.assertEqual(neigh[1]["state"], "stale")
        conns = netview.parse_ss_connections(SS)
        self.assertEqual(len(conns), 5)
        self.assertEqual(conns[0]["remote_ip"], "192.168.100.5"); self.assertEqual(conns[0]["process"], "curl"); self.assertEqual(conns[0]["pid"], 475)
        self.assertEqual(conns[4]["local_ip"], "::1")
        self.assertEqual(netview.parse_resolv_conf("# x\nnameserver 10.50.7.1\nsearch lan.local corp\n"), {"servers": ["10.50.7.1"], "search": ["lan.local", "corp"]})
        self.assertEqual(netview.parse_ss_connections(""), [])

    def test_synthese_sous_reseau_isole_route_directe(self):
        s = netview.summarize(netview.parse_ip_addr(ADDR), netview.parse_ip_route(ROUTE), netview.parse_ip_neigh(NEIGH), netview.parse_ss_connections(SS))
        self.assertEqual(s["attached_subnets"], ["10.50.7.0/24"])
        self.assertEqual((s["default_gateway"], s["default_gateway_state"]), ("10.50.7.1", "reachable"))
        self.assertEqual(s["reachable_subnets"], [{"subnet": "192.168.100.0/24", "gateway": "10.50.7.254", "dev": "eth0", "gateway_state": "stale"}])
        peers = {p["ip"]: p for p in s["peers"]}
        self.assertEqual(set(peers), {"192.168.100.5", "10.50.7.30"}, "loopback jamais un pair")
        self.assertEqual((peers["192.168.100.5"]["connections"], peers["192.168.100.5"]["ports"], peers["192.168.100.5"]["local"]), (2, ["tcp/443"], False))
        self.assertEqual(peers["10.50.7.30"]["local"], True)
        self.assertEqual([n["ip"] for n in s["neighbors_outside_attached"]], ["192.168.100.5"], "voisin ARP hors sous-réseau attaché = indice de route directe / proxy ARP")
        self.assertEqual(s["counts"], {"interfaces": 1, "neighbors": 3, "connections": 5, "peers": 2})

    def test_collecte_avec_sources_absentes(self):
        cmd = FakeCmd({"ip -j": (0, json.dumps(ADDR))})  # même sortie pour addr/route/neigh : peu importe, ss absent
        d = netview.collect(cmd=cmd, files=lambda p: "nameserver 1.1.1.1\n")
        self.assertIn("ss", d["partial"])
        self.assertEqual(d["dns"]["servers"], ["1.1.1.1"])
        d = netview.collect(cmd=FakeCmd({}), files=lambda p: "")
        self.assertEqual(sorted(d["partial"]), ["ip-addr", "ip-neigh", "ip-route", "ss"])
        self.assertEqual(d["summary"]["counts"]["peers"], 0)


LSBLK = {"blockdevices": [{"name": "sda", "type": "disk", "size": "465.8G", "model": "Samsung SSD 870", "serial": "S5Y", "rota": False, "tran": "sata", "vendor": "ATA"},
                          {"name": "loop0", "type": "loop", "size": "64M"}, {"name": "sr0", "type": "rom", "size": "1M"}]}
LSCPU = "Architecture:  x86_64\nCPU(s):  4\nModel name:  Intel(R) Core(TM) i5\nThread(s) per core:  2\nCore(s) per socket:  2\nSocket(s):  1\nHypervisor vendor:  KVM\nVirtualization type:  full\n"
PS = "  475 root      11.6  0.2  22840     120 python3\n  900 www-data   0.5  3.1 130000 86400 nginx\nbad line\n"


class ReviewTests(unittest.TestCase):
    def test_materiel(self):
        files = lambda p: {"/sys/class/dmi/id/sys_vendor": "Dell Inc.\n", "/sys/class/dmi/id/product_name": "OptiPlex 7090\n",
                           "/proc/meminfo": "MemTotal:       16000000 kB\n", "/sys/class/net/eth0/speed": "1000\n"}.get(p, "")
        cmd = FakeCmd({"lscpu": (0, LSCPU), "lsblk": (0, json.dumps(LSBLK)), "systemd-detect-virt": (1, "none\n"),
                       "ip -j": (0, json.dumps([{"ifname": "lo", "link_type": "loopback"}, {"ifname": "eth0", "link_type": "ether", "address": "aa:bb:cc:dd:ee:ff", "operstate": "UP"}]))})
        hw = review.collect_hardware(cmd=cmd, files=files)
        self.assertEqual((hw["vendor"], hw["product"]), ("Dell Inc.", "OptiPlex 7090"))
        self.assertEqual(hw["cpu"]["model"], "Intel(R) Core(TM) i5"); self.assertEqual(hw["cpu"]["cpus"], 4); self.assertEqual(hw["cpu"]["hypervisor"], "KVM")
        self.assertEqual(hw["memory_total_bytes"], 16000000 * 1024)
        self.assertEqual([d["name"] for d in hw["disks"]], ["sda"], "loop et rom exclus")
        self.assertEqual(hw["disks"][0]["rotational"], False)
        self.assertEqual(hw["nics"], [{"name": "eth0", "mac": "aa:bb:cc:dd:ee:ff", "state": "up", "speed_mbps": 1000}])
        self.assertEqual(hw["virtualization"], "none")
        self.assertEqual(hw["partial"], [])
        pi = review.collect_hardware(cmd=FakeCmd({}), files=lambda p: "Raspberry Pi 4 Model B Rev 1.4\x00" if p == "/proc/device-tree/model" else "")
        self.assertEqual((pi["vendor"], pi["product"]), ("Raspberry Pi Foundation", "Raspberry Pi 4 Model B Rev 1.4"))
        self.assertEqual(sorted(pi["partial"]), ["ip-link", "lsblk", "lscpu"])

    def test_activite(self):
        procs = review.parse_ps(PS)
        self.assertEqual(len(procs), 2)
        self.assertEqual(procs[1], {"pid": 900, "user": "www-data", "cpu_percent": 0.5, "mem_percent": 3.1, "rss_bytes": 130000 * 1024, "elapsed_seconds": 86400, "command": "nginx"})
        self.assertEqual(review.parse_who("freg     pts/0        2026-09-08 09:12 (192.168.1.35)\n"), [{"user": "freg", "tty": "pts/0", "since": "2026-09-08 09:12", "from": "192.168.1.35"}])
        last = review.parse_last("freg     pts/0        192.168.1.35     Mon Sep  8 09:12:00 2026   still logged in\nreboot   system boot  6.1.0 Mon Sep  1 08:00:00 2026 - Mon Sep  8 09:00:00 2026 (7+01:00)\n\nwtmp begins Mon Sep  1\n")
        self.assertEqual(len(last), 2); self.assertEqual(last[0]["from"], "192.168.1.35"); self.assertIsNone(last[1]["from"])
        cmd = FakeCmd({"ps": (0, PS), "who": (0, ""), "last": (-127, ""), "systemctl list-units": (0, "ssh.service loaded active running OpenBSD\ncron.service loaded active running Regular\n")})
        a = review.collect_activity(cmd=cmd, files=lambda p: "2 mises à jour peuvent être appliquées immédiatement.\n" if p.endswith("updates-available") else "")
        self.assertEqual(a["process_count"], 3)
        self.assertEqual(a["top_cpu"][0]["command"], "python3")
        self.assertEqual(a["running_services"], ["ssh.service", "cron.service"]); self.assertEqual(a["running_services_count"], 2)
        self.assertEqual(a["updates_available"], 2)
        self.assertEqual(a["partial"], ["last"])


class HostRootTests(unittest.TestCase):
    """#430 : agent en conteneur, système de fichiers de l'hôte sous /host."""

    def test_montages_sous_le_root_hote(self):
        mounts = "/dev/vda1 /host ext4 rw 0 0\n/dev/vdb /host/data ext4 rw 0 0\noverlay / overlay rw 0 0\nproc /host/proc proc rw 0 0\n"

        class U(object):
            def __init__(self, *a):
                self.total, self.used, self.free = 100, 40, 60
        d = host.collect_disks(files=lambda p: mounts, usage=U, host_root="/host")
        self.assertEqual([x["mountpoint"] for x in d], ["/", "/data"], "montages de l'hôte seuls, sans le préfixe ; overlay du conteneur exclu")
        self.assertEqual([x["mountpoint"] for x in host.collect_disks(files=lambda p: mounts, usage=U, host_root="")], ["/host", "/host/data"])

    def test_chemins_prefixes(self):
        old = host.HOST_ROOT
        try:
            host.HOST_ROOT = "/host"
            self.assertEqual(host.host_path("/etc/passwd"), "/host/etc/passwd")
            self.assertEqual(host.host_path("/var/run/reboot-required"), "/host/var/run/reboot-required")
            self.assertEqual(host.host_path("/proc/meminfo"), "/proc/meminfo", "procfs : celui du noyau, jamais préfixé")
            self.assertEqual(host.host_path("/sys/class/dmi/id/sys_vendor"), "/sys/class/dmi/id/sys_vendor")
        finally:
            host.HOST_ROOT = old


if __name__ == "__main__":
    unittest.main()
