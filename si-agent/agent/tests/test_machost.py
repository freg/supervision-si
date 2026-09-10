# -*- coding: utf-8 -*-
"""Tests des parseurs macOS (livraison #451) sur des sorties représentatives
de commandes macOS réelles. Purs : aucune machine macOS requise."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from si_agent import machost  # noqa: E402


class Res(object):
    def __init__(self, out="", code=0, err=""):
        self.stdout, self.returncode, self.stderr = out, code, err


class TestSystemParsers(unittest.TestCase):
    def test_sw_vers(self):
        self.assertEqual(machost.parse_sw_vers("ProductName:\tmacOS\nProductVersion:\t14.5\nBuildVersion:\t23F79"),
                         {"name": "macOS", "version": "14.5", "build": "23F79"})

    def test_boottime(self):
        import time
        recent = int(time.time()) - 3600
        up = machost.parse_boottime("{ sec = %d, usec = 0 } ..." % recent)
        self.assertTrue(3500 < up < 3700)
        self.assertIsNone(machost.parse_boottime("rien"))

    def test_vm_stat(self):
        txt = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
               "Pages free:                          100000.\n"
               "Pages active:                        200000.\n"
               "Pages inactive:                       50000.\n"
               "Pages speculative:                    10000.\n"
               "Pages wired down:                    150000.\n"
               "Pages purgeable:                       5000.\n")
        avail_pages, page, counts = machost.parse_vm_stat(txt)
        self.assertEqual(page, 16384)
        self.assertEqual(avail_pages, 100000 + 50000 + 10000 + 5000)
        self.assertEqual(counts["wired down"], 150000)

    def test_swapusage_and_cpu_load(self):
        self.assertEqual(machost.parse_swapusage("total = 3072.00M  used = 1536.00M  free = 1536.00M  (encrypted)"),
                         (3072 * 1024 * 1024, 1536 * 1024 * 1024))
        self.assertEqual(machost.parse_cpu_usage("CPU usage: 4.76% user, 9.52% sys, 85.72% idle"), 14.3)
        self.assertEqual(machost.parse_loadavg("{ 1.98 2.04 2.11 }"), {"load1": 1.98, "load5": 2.04, "load15": 2.11})

    def test_netmask(self):
        self.assertEqual(machost._netmask_to_prefix("0xffffff00"), 24)
        self.assertEqual(machost._netmask_to_prefix("0xfffffc00"), 22)
        self.assertEqual(machost._netmask_to_prefix("255.255.255.0"), 24)


class TestDisks(unittest.TestCase):
    def test_df_with_mount(self):
        mounts = machost.parse_mount(
            "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n"
            "/dev/disk3s5 on /System/Volumes/Data (apfs, local, journaled, nobrowse)\n"
            "//alice@nas._smb._tcp.local/partage on /Volumes/partage (smbfs, nodev, nosuid, mounted by freg)\n")
        self.assertTrue(mounts["/"]["readonly"])
        self.assertEqual(mounts["/Volumes/partage"]["fstype"], "smbfs")
        df = ("Filesystem   1024-blocks      Used Available Capacity iused      ifree %iused  Mounted on\n"
              "/dev/disk3s1s1 971350180  22000000 900000000     3%  500000 4000000000    0%   /\n"
              "/dev/disk3s5   971350180  60000000 900000000     7%  600000 4000000000    0%   /System/Volumes/Data\n"
              "//alice@nas/partage 500000000 100000000 400000000 20% 0 0 0% /Volumes/partage\n"
              "/dev/disk4s1   10000000   9990000     10000    99%  100 100 50% /Volumes/GParted\n")
        disks = machost.parse_df(df, mounts)
        mnts = {d["mountpoint"]: d for d in disks}
        # « / » scellé + Data fusionnés : une seule entrée « / » portant l'usage réel (Data), inscriptible
        self.assertIn("/", mnts)
        self.assertNotIn("/System/Volumes/Data", mnts)
        self.assertFalse(mnts["/"]["readonly"])
        self.assertEqual(mnts["/"]["used_bytes"], 60000000 * 1024)
        self.assertEqual(mnts["/"]["total_bytes"], 971350180 * 1024)
        self.assertTrue(mnts["/Volumes/partage"]["remote"])
        self.assertTrue(mnts["/Volumes/partage"]["removable"])
        self.assertEqual(mnts["/Volumes/GParted"]["used_percent"], round(100.0 * 9990000 * 1024 / (10000000 * 1024), 1))

    def test_df_skips_system_vm(self):
        mounts = {}
        df = ("Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on\n"
              "/dev/disk3s6 971350180 20480 900000000 1% 1 1 0% /System/Volumes/VM\n"
              "/dev/disk3s1s1 971350180 22000000 900000000 3% 1 1 0% /\n")
        disks = machost.parse_df(df, mounts)
        self.assertEqual([d["mountpoint"] for d in disks], ["/"])


class TestServicesPorts(unittest.TestCase):
    def test_launchctl(self):
        txt = ("PID\tStatus\tLabel\n"
               "123\t0\tcom.apple.some.agent\n"
               "-\t0\tcom.apple.idle\n"
               "-\t78\tcom.acme.brokendaemon\n"
               "456\t0\tcom.acme.worker\n")
        failed, running = machost.parse_launchctl_list(txt)
        self.assertEqual(failed, ["com.acme.brokendaemon (code 78)"])
        self.assertEqual(running, 2)

    def test_launchctl_sigkill_systeme_ignore(self):
        # macOS réel : les démons com.apple.* tués par le système (code -9)
        # sont du bruit -- à écarter ; un -9 tiers ou un autre code reste signalé
        txt = ("PID\tStatus\tLabel\n"
               "-\t-9\tcom.apple.security.cryptexd\n"
               "-\t-9\tcom.apple.modelcatalogd\n"
               "-\t-9\tcom.avg.hub.xpc\n"
               "-\t1\tcom.apple.reallybroken\n")
        failed, _ = machost.parse_launchctl_list(txt)
        self.assertEqual(failed, ["com.avg.hub.xpc (code -9)",
                                  "com.apple.reallybroken (code 1)"])

    def test_lsof_listen(self):
        txt = ("COMMAND   PID USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME\n"
               "launchd     1 root   28u  IPv4 0x1234      0t0  TCP *:22 (LISTEN)\n"
               "launchd     1 root   30u  IPv6 0x5678      0t0  TCP [::1]:631 (LISTEN)\n"
               "Python    900 freg    3u  IPv4 0x9abc      0t0  TCP 127.0.0.1:6100 (LISTEN)\n"
               "Python    900 freg    4u  IPv4 0x9abd      0t0  TCP 127.0.0.1:6100 (LISTEN)\n")
        ports = machost.parse_lsof_listen(txt)
        # NAME est « *:22 (LISTEN) » -> le dernier champ est "(LISTEN)", pas l'adresse
        self.assertTrue(any(p["port"] == 22 and p["exposed"] for p in ports))
        self.assertTrue(any(p["port"] == 6100 and not p["exposed"] and p["process"] == "Python" for p in ports))
        # dédoublonnage du 6100 répété
        self.assertEqual(sum(1 for p in ports if p["port"] == 6100), 1)


class TestAccounts(unittest.TestCase):
    def test_dscl(self):
        self.assertEqual(machost.parse_dscl_group("GroupMembership: root freg eve"), ["root", "freg", "eve"])
        users = machost.parse_dscl_users("_mbsetupuser 248\ndaemon 1\nfreg 501\neve 502\nroot 0\n")
        self.assertEqual(users, ["freg", "eve"])


class TestActivity(unittest.TestCase):
    def test_ps_and_etime(self):
        self.assertEqual(machost._etime_seconds("01:02:03"), 3723)
        self.assertEqual(machost._etime_seconds("2-03:00:00"), 2 * 86400 + 3 * 3600)
        self.assertEqual(machost._etime_seconds("05:30"), 330)
        txt = ("  1 root  0.5  0.1  12000 10-00:00:00 launchd\n"
               "900 freg  25.3 3.2 800000 01:23:45 /Applications/Xcode.app/Contents/MacOS/Xcode\n")
        procs = machost.parse_ps_macos(txt)
        self.assertEqual(procs[1]["command"], "/Applications/Xcode.app/Contents/MacOS/Xcode")
        self.assertEqual(procs[1]["rss_bytes"], 800000 * 1024)
        self.assertEqual(procs[0]["elapsed_seconds"], 10 * 86400)

    def test_who_last(self):
        who = machost.parse_who_macos("freg      console  Sep  8 09:12 \nfreg      ttys000  Sep  8 10:00 (192.168.1.5)\n")
        self.assertEqual(who[1]["from"], "192.168.1.5")
        last = machost.parse_last_macos("freg   ttys000   192.168.1.5   Mon Sep  8 10:00   still logged in\nreboot  ~          Mon Sep  8 08:00\n")
        self.assertEqual(len(last), 1)
        self.assertEqual(last[0]["from"], "192.168.1.5")


class TestHardware(unittest.TestCase):
    def test_map_hardware(self):
        sp = {"SPHardwareDataType": [{"machine_model": "MacBookPro18,1", "serial_number": "C02XY", "platform_UUID": "UUID-1",
                                      "physical_memory": "32 GB", "chip_type": "Apple M1 Pro", "number_processors": "proc 10:8:2",
                                      "boot_rom_version": "10151.1.1"}]}
        ns = ("Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: ac:de:48:00:11:22\n\n"
              "Hardware Port: Thunderbolt Bridge\nDevice: bridge0\nEthernet Address: N/A\n")
        hw = machost.map_hardware(sp, ns)
        self.assertEqual(hw["vendor"], "Apple")
        self.assertEqual(hw["product"], "MacBookPro18,1")
        self.assertEqual(hw["serial"], "C02XY")
        self.assertEqual(hw["memory_total_bytes"], 32 * 1024 ** 3)
        self.assertEqual(hw["cpu"]["model"], "Apple M1 Pro")
        self.assertEqual(hw["cpu"]["cpus"], 10)
        self.assertEqual(hw["nics"][0], {"name": "en0", "mac": "ac:de:48:00:11:22", "state": None, "speed_mbps": None, "description": "Wi-Fi"})
        self.assertIsNone(hw["nics"][1]["mac"])


class TestNetview(unittest.TestCase):
    IFCONFIG = (
        "lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384\n"
        "\tinet 127.0.0.1 netmask 0xff000000\n"
        "\tinet6 ::1 prefixlen 128\n"
        "en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500\n"
        "\tether ac:de:48:00:11:22\n"
        "\tinet6 fe80::1%en0 prefixlen 64 scopeid 0x8\n"
        "\tinet 192.168.1.20 netmask 0xffffff00 broadcast 192.168.1.255\n"
        "\tstatus: active\n"
        "en5: flags=8863<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> mtu 1500\n"
        "\tether aa:bb:cc:dd:ee:ff\n"
        "\tstatus: inactive\n")

    def test_ifconfig(self):
        itfs = machost.parse_ifconfig(self.IFCONFIG)
        names = {i["name"]: i for i in itfs}
        self.assertNotIn("lo0", names)   # boucle locale écartée
        self.assertNotIn("en5", names)   # sans adresse écartée
        en0 = names["en0"]
        self.assertEqual(en0["mac"], "ac:de:48:00:11:22")
        self.assertEqual(en0["state"], "up")
        self.assertEqual(en0["mtu"], 1500)
        v4 = [a for a in en0["addresses"] if a["family"] == "inet"][0]
        self.assertEqual((v4["ip"], v4["prefix"], v4["scope"]), ("192.168.1.20", 24, "global"))

    def test_routes(self):
        rt = ("Routing tables\n\nInternet:\n"
              "Destination        Gateway            Flags        Netif Expire\n"
              "default            192.168.1.1        UGScg          en0\n"
              "192.168.1.0/24     link#8             UCS            en0\n"
              "192.168.1.1        ac:de:48:0:11:1    UHLWIir        en0\n")
        routes = machost.parse_netstat_routes(rt)
        self.assertEqual(routes[0]["kind"], "default")
        self.assertEqual(routes[0]["gateway"], "192.168.1.1")
        direct = [r for r in routes if r["dst"] == "192.168.1.0/24"][0]
        self.assertEqual(direct["kind"], "direct")

    def test_arp_conns(self):
        arp = ("? (192.168.1.1) at ac:de:48:0:11:1 on en0 ifscope [ethernet]\n"
               "? (192.168.1.9) at (incomplete) on en0 ifscope [ethernet]\n"
               "? (224.0.0.251) at 1:0:5e:0:0:fb on en0 ifscope permanent [ethernet]\n")
        neigh = machost.parse_arp(arp)
        self.assertEqual(len(neigh), 2)
        self.assertEqual(neigh[0]["state"], "reachable")
        self.assertIsNone(neigh[1]["mac"])
        self.assertEqual(neigh[1]["state"], "failed")
        cn = ("Active Internet connections (including servers)\n"
              "Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)\n"
              "tcp4       0      0  192.168.1.20.52345     140.82.121.3.443       ESTABLISHED\n"
              "tcp4       0      0  *.22                   *.*                    LISTEN\n")
        conns = machost.parse_netstat_conns(cn)
        self.assertEqual(len(conns), 1)
        self.assertEqual((conns[0]["remote_ip"], conns[0]["remote_port"], conns[0]["local_port"]), ("140.82.121.3", 443, 52345))


class TestCollectAll(unittest.TestCase):
    def _fake_cmd(self, argv, timeout=15):
        key = " ".join(argv)
        table = {
            "sw_vers": "ProductName:\tmacOS\nProductVersion:\t14.5\nBuildVersion:\t23F79",
            "sysctl -n hw.model": "MacBookPro18,1",
            "sysctl -n machdep.cpu.brand_string": "",
            "sysctl -n hw.ncpu": "10",
            "uname -m": "arm64",
            "sysctl -n kern.boottime": "{ sec = %d, usec = 0 }" % (int(__import__("time").time()) - 7200),
            "scutil --get ComputerName": "Mac-de-Freg",
            "top -l 1 -n 0": "CPU usage: 5.00% user, 5.00% sys, 90.00% idle",
            "sysctl -n vm.loadavg": "{ 2.00 2.10 2.20 }",
            "sysctl -n hw.memsize": str(32 * 1024 ** 3),
            "vm_stat": "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100000.\nPages inactive: 50000.\nPages speculative: 10000.\nPages purgeable: 0.\n",
            "sysctl -n vm.swapusage": "total = 2048.00M  used = 512.00M  free = 1536.00M",
            "df -k": "Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on\n/dev/disk3s1s1 971350180 22000000 900000000 3% 1 1 0% /\n",
            "mount": "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n",
            "launchctl list": "PID\tStatus\tLabel\n1\t0\tcom.apple.launchd\n-\t2\tcom.acme.bad\n",
            "lsof -nP -iTCP -sTCP:LISTEN": "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\nsshd 100 root 3u IPv4 0x1 0t0 TCP *:22 (LISTEN)\n",
            "dscl . -read /Groups/admin GroupMembership": "GroupMembership: root freg",
            "dscl . -list /Users UniqueID": "_mbsetup 248\nfreg 501\nroot 0\n",
            "stat -f %Su /dev/console": "freg",
        }
        for k, v in table.items():
            if key == k:
                return Res(v)
        if key.startswith("log show"):
            return Res("Timestamp Thread Type\n2026-09-08 10:00:00 error kernel something failed\n")
        return Res("", code=1, err="inconnu")

    def test_collect_all_shape(self):
        data, prev = machost.collect_all(cmd=self._fake_cmd, which=lambda t: "/usr/bin/" + t if t in ("bash", "python3") else None)
        self.assertIsNone(prev)
        self.assertEqual(data["system"]["os_id"], "macos")
        self.assertEqual(data["system"]["os"], "macOS 14.5")
        self.assertEqual(data["system"]["cpus"], 10)
        self.assertTrue(7000 < data["system"]["uptime_seconds"] < 7400)
        self.assertEqual(data["cpu"]["percent"], 10.0)
        self.assertEqual(data["cpu"]["load1"], 2.0)
        self.assertEqual(data["memory"]["total_bytes"], 32 * 1024 ** 3)
        self.assertIsNotNone(data["memory"]["used_percent"])
        self.assertEqual(data["disks"][0]["mountpoint"], "/")
        self.assertTrue(data["disks"][0]["readonly"])
        self.assertEqual(data["services"]["failed"], ["com.acme.bad (code 2)"])
        self.assertTrue(any(p["port"] == 22 for p in data["ports"]["ports"]))
        self.assertEqual(data["accounts"]["sudoers"], ["root", "freg"])
        self.assertEqual(data["accounts"]["console_user"], "freg")
        self.assertEqual(data["logs"]["source"], "unified-log")
        self.assertEqual(data["tools"], ["bash", "python3"])
        self.assertEqual(data["partial"], [])


if __name__ == "__main__":
    unittest.main()
