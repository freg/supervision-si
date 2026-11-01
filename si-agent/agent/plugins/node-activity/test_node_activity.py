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


class Destinations773(unittest.TestCase):
    SECTION = "\n".join([
        "data\t130000000000\t/data", "data/ovh\t2000000000\t/data/ovh", "data/ovh/pve1\t1500000000\t/data/ovh/pve1",
        "rpool/data/vm-120-disk-0\t2600000000000\t-", "@@ZEND",
        "@@XFER 10\t/opt/10ToExterne/pbs10/vm-120-disk-0@usb1.zfs\t500000000000\trpool/data/vm-120-disk-0@usb1\t2500000000000\tzfs send -cv rpool/data/vm-120-disk-0@usb1",
        "@@XFER 11\tpipe:[1]\t\troot@pve-1.groupe-i.fr\t\trsync -aHAX --bwlimit=40000 root@pve-1.groupe-i.fr:/var/lib/lxc/103/rootfs/ /data/ovh/pve1/ct103/",
        "@@XFER 12\tpipe:[1]\t\t\t\tssh -l root pve-1.groupe-i.fr rsync --server --sender -logDtpHAXre.iLsfxC . /var/lib/lxc/103/rootfs/",
        "@@XFER 13\tpipe:[2]\t\tdata/ovh/pve3/subvol-102-disk-0\t\tzfs recv -s -u data/ovh/pve3/subvol-102-disk-0",
        "@@XFER 14\tpipe:[3]\t\t\t\trsync -aHAX root@pve-1.groupe-i.fr:/var/lib/lxc/104/rootfs/ /data/ovh/pve1/ct104/",
        "@@XFER 15\tpipe:[4]\t\t\t\trsync -a /src/ /mnt/usb/copie/"])

    def test_destinations(self):
        zl, xf = na.parse_xfer_section(self.SECTION)
        self.assertEqual(len(xf), 6)
        t = {x["key"]: x for x in na.xfer_targets(xf, zl, [{"mount": "/", "used": 5}, {"mount": "/mnt/usb", "used": 77}])}
        self.assertEqual(sorted(t), ["df:/mnt/usb", "file:/opt/10ToExterne/pbs10/vm-120-disk-0@usb1.zfs", "zfs:data/ovh", "zfs:data/ovh/pve1"])
        f = t["file:/opt/10ToExterne/pbs10/vm-120-disk-0@usb1.zfs"]
        self.assertEqual((f["measure"], f["size"], f["total"], f["label"]), ("fichier", 500000000000, 2500000000000, "zfs send rpool/data/vm-120-disk-0@usb1"))
        self.assertEqual(t["zfs:data/ovh/pve1"]["dest"], "/data/ovh/pve1/ct103/")          # un seul rsync retenu par volume
        self.assertEqual(t["zfs:data/ovh"]["dest"], "data/ovh/pve3/subvol-102-disk-0 (dans data/ovh)")   # volume en cours de réception
        self.assertEqual(t["df:/mnt/usb"]["measure"], "système de fichiers")

    def test_debit_fin_estimee_et_blocage(self):
        t = [{"key": "file:/x", "size": 1000 * 2**20, "total": 4000 * 2**20}]
        r, st = na.xfer_rates(t, {"file:/x": [880 * 2**20, 0]}, 120)
        self.assertEqual((r[0]["rate_bps"], r[0]["pct"], r[0]["eta_s"]), (2**20, 25.0, 3000))
        for _ in range(3):
            r, st = na.xfer_rates([{"key": "file:/x", "size": 1000 * 2**20, "total": None}], st, 120)
        self.assertEqual(r[0]["stalled_runs"], 3)
        al = na.alerts_for([{"name": "pve11", "ok": True, "xfers": [dict(r[0], label="rsync", dest="/data/ovh/pve1/ct103/")]}])
        self.assertIn("ne progresse plus", al[0]["message"])
        self.assertIsNone(na.xfer_rates([{"key": "k", "size": 5, "total": None}], None, 0)[0][0]["rate_bps"])   # premier passage


if __name__ == "__main__":
    unittest.main()
