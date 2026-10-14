"""#749 : analyse du relevé d'activité (texte d'un nœud), débits d'un passage à l'autre, constats."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import node_activity as na  # noqa: E402

S = na.SEP


def sample(cpu_busy, rx, tx, part_size, idle=9000):
    return "\n".join([
        "0.50 0.40 0.30 2/310 999", S,
        "cpu  %d 0 0 %d 0 0 0 0 0 0\ncpu0 %d 0 0 %d 0 0 0 0 0 0\ncpu1 %d 0 0 %d 0 0 0 0 0 0" % (cpu_busy, idle, cpu_busy // 2, idle // 2, cpu_busy // 2, idle // 2), S,
        "MemTotal:       32000000 kB\nMemAvailable:   16000000 kB\nSwapTotal:       8000000 kB\nSwapFree:        6000000 kB", S,
        "Inter-|   Receive\n face |bytes packets errs drop fifo frame compressed multicast|bytes\n"
        "  vmbr0: %d 10 0 0 0 0 0 0 %d 10 0 0 0 0 0 0\n    lo: 5 1 0 0 0 0 0 0 5 1 0 0 0 0 0 0\n tap100i0: 1 1 0 0 0 0 0 0 1 1 0 0 0 0 0 0" % (rx, tx), S,
        "Total: 400\nTCP:   120 (estab 42, closed 60, orphaned 0, timewait 55)\n\nTransport Total     IP        IPv6\nUDP      9", S,
        "Filesystem 1-blocks Used Available Capacity Mounted on\n/dev/sda1 1000 950 50 95% /\nrpool/var-lib-vz 3000 600 2400 20% /var/lib/vz\n/dev/sdb1 100 1 99 1% /boot/efi", S,
        "rpool\t3621000\t3330000\t291000\t50%\t91%\tONLINE", S,
        "16", S,
        "  4242   3600 /usr/bin/perl -T /usr/bin/vzdump 102 --stdout\n  4300    100 ssh -i /root/.ssh/k root@pve-1 vzdump", S,
        "/var/lib/vz/dump/a.tar.gz\t%d\t%d" % (part_size, 1000), S,
        "pve10", S,
        "12345.67 999.0"])


class Analyse(unittest.TestCase):
    def test_deux_passages(self):
        n1, st = na.build_node("local", "local", sample(1000, 1_000_000, 500_000, 10_000), None, 1000)
        self.assertEqual((n1["hostname"], n1["ncpu"], n1["load"], n1["cpu_pct"]), ("pve10", 16, [0.5, 0.4, 0.3], None))
        self.assertEqual((n1["mem_total"], n1["mem_used"], n1["swap_total"], n1["swap_used"]), (32000000 * 1024, 16000000 * 1024, 8000000 * 1024, 2000000 * 1024))
        self.assertEqual((n1["tasks"], n1["uptime_s"]), ({"running": 2, "total": 310}, 12345))
        self.assertEqual([i["iface"] for i in n1["net"]], ["vmbr0"])                   # lo, tap filtrées
        self.assertEqual(n1["conn"], {"tcp": 120, "estab": 42, "timewait": 55, "udp": 9})
        self.assertEqual([d["mount"] for d in n1["disks"]], ["/", "/var/lib/vz"])       # /boot exclu
        self.assertEqual(n1["zpools"][0]["pct"], 91)
        self.assertEqual([p["kind"] for p in n1["procs"]], ["vzdump", "vzdump"])
        self.assertIn("-i …", n1["procs"][1]["cmd"])                                     # chemin de clé masqué
        n2, _ = na.build_node("local", "local", sample(3000, 2_000_000, 1_500_000, 70_000, idle=17000), st, 1010)
        self.assertEqual(n2["cpu_pct"], 20.0)
        self.assertEqual(n2["cores_pct"], [20.0, 20.0])
        self.assertEqual((n2["net"][0]["rx_bps"], n2["net"][0]["tx_bps"]), (800000, 800000))   # (Δ octets / 10 s) × 8
        self.assertEqual(n2["files"][0]["rate_bps"], 6000)
        al = na.alerts_for([n2, {"name": "pve-2", "ok": False, "error": "délai"}])
        self.assertEqual({a["code"].split(":")[0] for a in al}, {"disk-full", "zpool-full", "node-unreachable"})

    def test_taches(self):   # #766
        u = "UPID:pve10:00001A2B:0ABCDEF0:6ACF6000:vzdump::root@pam:"
        txt = "\n".join(["@@TASK " + u, "INFO: starting new backup job: vzdump 9101 9102 9108 9109 --storage pbs10 --mode snapshot",
                         "INFO: Starting Backup of VM 9101 (lxc)", "INFO: root.pxar: had to backup 100 GiB of 112 GiB (compressed 50 GiB) in 3600.00 s",
                         "INFO: Finished Backup of VM 9101 (01:00:12)", "INFO: Starting Backup of VM 9102 (lxc)", "@@LAST INFO: Upload directory '/mnt/vzsnap0'",
                         "@@TASK UPID:pve10:00001A2C:0ABCDEF1:6ACF6100:qmrestore:211:root@pam:", "INFO:  42% (42.0 GiB of 100.0 GiB) in 5m", "@@PBC 77 5000"])
        t = na.parse_tasks(txt, 0x6ACF6000 + 7200)
        self.assertEqual((t[0]["type"], t[0]["guests"], t[0]["done"][0]["vmid"], t[0]["current"], t[0]["read_bytes"], t[0]["elapsed_s"]),
                         ("vzdump", [9101, 9102, 9108, 9109], 9101, 9102, 5000, 7200))
        self.assertIn("had to backup", "had to backup") ; self.assertTrue(t[0]["summary"].startswith("root.pxar"))
        self.assertEqual((t[1]["type"], t[1]["id"], t[1]["percent"], t[1]["read_bytes"]), ("qmrestore", "211", 42, None))
        n, _ = na.build_node("local", "local", sample(1000, 1, 1, 1) + "\n" + na.SEP + "\n" + txt, None, 0x6ACF6000 + 10)
        self.assertEqual(len(n["pve_tasks"]), 2)

    def test_texte_vide(self):
        n, _ = na.build_node("x", "remote", "", None, 1)
        self.assertEqual((n["disks"], n["net"], n["load"]), ([], [], None))


if __name__ == "__main__":
    unittest.main()
