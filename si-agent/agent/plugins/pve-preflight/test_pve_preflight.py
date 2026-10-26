# -*- coding: utf-8 -*-
"""Tests #815 : sonde pve-preflight -- découpage sur des sorties de PVE 5.4 représentatives, et pilote réel (bash)
exécuté de bout en bout avec de faux pvecm / pvesh / pct / qm / pvesm / pvesr."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import pve_preflight as P  # noqa: E402

PVECM = """Quorum information
------------------
Date:             Wed Oct 21 20:01:02 2026
Quorum provider:  corosync_votequorum
Nodes:            2
Node ID:          0x00000002
Ring ID:          1/88
Quorate:          Yes

Votequorum information
----------------------
Expected votes:   2
Highest expected: 2
Total votes:      2
Quorum:           2
Flags:            Quorate

Membership information
----------------------
    Nodeid      Votes Name
0x00000001          1 192.0.2.11
0x00000002          1 192.0.2.12 (local)
"""
PVESR = """JobID      Enabled    Target                           LastSync             NextSync   Duration  FailCount State
102-0      Yes        local/pve-3           2026-10-21_19:45:01  2026-10-21_20:00:00   12.4          0 OK
119-0      Yes        local/pve-3           -                    pending                -          3 command 'zfs send' failed
"""
STORAGECFG = """dir: local
\tpath /var/lib/vz
\tcontent iso,vztmpl,backup

zfspool: local-zfs
\tpool rpool/data
\tcontent images,rootdir

nfs: sauvegardes
\texport /backup
\tserver 192.0.2.50
\tcontent backup
"""
PVESM = """Name             Type     Status           Total            Used       Available        %
local             dir     active        98559220        41297948        52211724   41.90%
local-zfs     zfspool     active      1855467584      512345678      1343121906   27.61%
sauvegardes       nfs   inactive               0               0               0    0.00%
"""
BACKUPS = """== local
local:backup/vzdump-lxc-102-2026_10_12-03_00_01.tar.lzo tar.lzo 51234567890 102
local:backup/vzdump-lxc-119-2026_09_01-03_00_01.tar.lzo     51234567 119
== local-zfs
"""
CRON = """PATH="/usr/sbin:/usr/bin:/sbin:/bin"

0 3 * * 6           root vzdump 102 119 --quiet 1 --mode snapshot --storage local --compress lzo
30 2 * * *          root vzdump --all 1 --exclude 105,106 --storage sauvegardes
"""
JOBS = """vzdump: backup-1a2b
\tschedule sat 03:00
\tall 1
\tstorage pbs1
\tenabled 1
"""
CONF_CT = """arch: amd64
cores: 4
hostname: med
memory: 8192
net0: name=eth0,bridge=vmbr0,gw=192.0.2.254,hwaddr=02:00:00:AB:CD:EF,ip=192.0.2.20/32,type=veth
onboot: 1
rootfs: local-zfs:subvol-102-disk-0,size=400G
"""
RRD = [{"time": 1, "cpu": 0.10, "maxcpu": 4, "mem": 2e9, "maxmem": 8e9, "netin": 1000, "netout": 3000},
       {"time": 2, "cpu": 0.30, "maxcpu": 4, "mem": 4e9, "maxmem": 8e9, "netin": 3000, "netout": 1000}]
RRDMAX = [{"time": 1, "cpu": 0.95, "mem": 7.6e9, "maxmem": 8e9}, {"time": 2, "cpu": 0.5, "mem": 3e9, "maxmem": 8e9}]
TASKS = [{"type": "vzdump", "id": "102", "starttime": 1792540800, "status": "OK"},
         {"type": "vzdump", "id": "102", "starttime": 1792454400, "status": "job errors"},
         {"type": "vzdump", "id": "119", "starttime": 1792454400, "status": "command 'tar' failed: exit code 2"},
         {"type": "vzmigrate", "id": "102", "starttime": 1792500000, "status": "OK"},
         {"type": "vzmigrate", "id": "103", "starttime": 1000, "status": "OK"},
         {"type": "qmstart", "id": "300", "starttime": 1792500000, "status": "OK"}]
NOW = 1792605600.0


class Decoupage(unittest.TestCase):
    def test_quorum(self):
        q = P.parse_pvecm(PVECM)
        self.assertEqual((q["quorate"], q["nodes"], q["expected"], q["total"], q["quorum"], q["qdevice"]), (True, 2, 2, 2, 2, False))
        self.assertEqual([(m["name"], m["votes"], m["local"]) for m in q["membres"]], [("192.0.2.11", 1, False), ("192.0.2.12", 1, True)])
        self.assertIsNone(P.parse_pvecm("Error: Corosync config '/etc/pve/corosync.conf' does not exist - is this node part of a cluster?"))
        qd = P.parse_pvecm(PVECM.replace("Flags:            Quorate", "Flags:            Quorate Qdevice").replace("Total votes:      2", "Total votes:      3")
                           + "0x00000000          1 Qdevice\n")
        self.assertTrue(qd["qdevice"])
        self.assertEqual(qd["total"], 3)
        sans = P.parse_pvecm(PVECM.replace("Quorate:          Yes", "Quorate:          No").replace("Flags:            Quorate", "Flags:"))
        self.assertFalse(sans["quorate"])

    def test_replication_stockages_sauvegardes(self):
        r = P.parse_pvesr(PVESR)
        self.assertEqual([(j["job"], j["vmid"], j["target"], j["fail_count"]) for j in r], [("102-0", 102, "pve-3", 0), ("119-0", 119, "pve-3", 3)])
        self.assertEqual(r[0]["last_sync"], "2026-10-21 19:45:01")
        self.assertIsNone(r[1]["last_sync"])
        self.assertEqual(r[1]["state"], "command 'zfs send' failed")
        cfg = P.parse_storage_cfg(STORAGECFG)
        self.assertEqual((cfg["local"]["shared"], cfg["sauvegardes"]["shared"], cfg["local"]["content"]), (False, True, ["iso", "vztmpl", "backup"]))
        st = P.parse_pvesm_status(PVESM)
        self.assertEqual((st["local"]["active"], st["sauvegardes"]["active"], st["local-zfs"]["avail"]), (True, False, 1343121906 * 1024))
        b = P.parse_backups(BACKUPS)
        self.assertEqual([(x["vmid"], x["storage"], x["at"], x["size"]) for x in b],
                         [(102, "local", "2026-10-12T03:00:01", 51234567890), (119, "local", "2026-09-01T03:00:01", 51234567)])

    def test_taches_planifiees_et_recentes(self):
        c = P.parse_vzdump_cron(CRON)
        self.assertEqual([(j["schedule"], j["all"], j["vmids"], j["storage"], j["exclude"]) for j in c],
                         [("0 3 * * 6", False, [102, 119], "local", []), ("30 2 * * *", True, [], "sauvegardes", [105, 106])])
        j = P.parse_jobs_cfg(JOBS)[0]
        self.assertEqual((j["schedule"], j["all"], j["storage"]), ("sat 03:00", True, "pbs1"))
        t = P.tasks_summary(TASKS, NOW)
        self.assertEqual(t["last_vzdump"]["102"], {"at": 1792540800, "ok": True, "status": "OK"})
        self.assertFalse(t["last_vzdump"]["119"]["ok"])
        self.assertEqual([m["vmid"] for m in t["migrations"]], [102])               # la migration de 103 est trop ancienne

    def test_invite(self):
        c = P.parse_conf(CONF_CT)
        self.assertEqual((c["vmac"], c["onboot"], c["cores"], c["memory_mb"], c["disks"]), (True, True, 4, 8192, ["local-zfs"]))
        self.assertFalse(P.parse_conf("net0: virtio=BC:24:11:00:00:01,bridge=vmbr0\nscsi0: local-lvm:vm-200-disk-0,size=32G\nide2: local:iso/d.iso,media=cdrom")["vmac"])
        s = P.rrd_stats(RRD, RRDMAX)
        self.assertEqual((s["cpu_avg_pct"], s["cpu_max_pct"], s["mem_avg_pct"], s["mem_max_pct"], s["points"]), (20.0, 95.0, 37.5, 95.0, 2))
        self.assertIsNone(P.rrd_stats([])["cpu_avg_pct"])
        ch = P.parse_checks("@@src journal\n@@err 12\n@@warn 40\n@@failed 1\n@@http 20000 150 900\n@@fin\n")
        self.assertEqual((ch["src"], ch["err_24h"], ch["warn_24h"], ch["failed_units"], ch["http_total"], ch["http_5xx"], ch["http_4xx"], ch["complet"]),
                         ("journal", 12, 40, 1, 20000, 150, 900, True))
        self.assertFalse(P.parse_checks("sh: 1: journalctl: not found")["complet"])
        self.assertEqual(P.unwrap_qga('{"exitcode": 0, "exited": 1, "out-data": "@@fin\\n"}'), ("@@fin\n", None))
        self.assertEqual(P.unwrap_qga("QEMU guest agent is not running")[1], "QEMU guest agent is not running")


FAUX = {
    "pveversion": "echo 'pve-manager/5.4-15/d0ec33c6 (running kernel: 4.15.18-30-pve)'",
    "pvecm": "cat <<'EOF'\n%s\nEOF" % PVECM,
    "ha-manager": "echo 'quorum OK'",
    "pvesm": 'if [ "$1" = status ]; then cat <<\'EOF\'\n%s\nEOF\nelse grep "^$2:" "$FIXT/backups" || true; fi' % PVESM,
    "pvesr": "cat <<'EOF'\n%s\nEOF" % PVESR,
    "pvesh": 'case "$2" in /cluster/resources) echo \'[{"vmid":102,"type":"lxc","node":"pve-2","name":"med","status":"running","disk":120000000000,"maxdisk":429496729600}]\';; '
             '*/tasks) cat "$FIXT/tasks";; */rrddata) echo \'[{"cpu":0.2,"maxcpu":4,"mem":1,"maxmem":4}]\';; *) echo "[]";; esac',
    "pct": 'case "$1" in list) printf "VMID       Status     Lock         Name\\n102        running                 med\\n103        stopped                 vieux\\n";; '
           'config) cat <<\'EOF\'\n%s\nEOF\n;; exec) shift 3; sh -s;; esac' % CONF_CT,
    "qm": 'case "$1" in list) printf "      VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID\\n       300 win                  running    4096              32.00 1234\\n";; '
          'config) echo "net0: virtio=BC:24:11:00:00:01,bridge=vmbr0";; guest) echo "QEMU guest agent is not running";; esac',
    "journalctl": 'case "$*" in *"-p 3"*) printf "a\\nb\\n";; *"-p 4"*) printf "a\\nb\\nc\\n";; *) echo x;; esac',
    "systemctl": "echo 'x.service loaded failed failed X'",
}


class PiloteReel(unittest.TestCase):
    def test_bout_en_bout(self):
        d = tempfile.mkdtemp()
        bin_ = os.path.join(d, "bin")
        os.makedirs(bin_)
        for nom, corps in FAUX.items():
            f = os.path.join(bin_, nom)
            with open(f, "w") as fh:
                fh.write("#!/bin/sh\n" + corps + "\n")
            os.chmod(f, os.stat(f).st_mode | stat.S_IEXEC)
        with open(os.path.join(d, "backups"), "w") as fh:
            fh.write("local:backup/vzdump-lxc-102-2026_10_12-03_00_01.tar.lzo tar.lzo 51234567890 102\n")
        with open(os.path.join(d, "tasks"), "w") as fh:
            json.dump(TASKS, fh)
        env = dict(os.environ, PATH=bin_ + ":" + os.environ["PATH"], FIXT=d)
        p = subprocess.run(["bash", "-s"], input=P.driver_script(), capture_output=True, text=True, env=env, timeout=60)
        node, nsec, guests, done = P.parse_driver(p.stdout)
        self.assertTrue(done, p.stdout[-500:] + p.stderr[-500:])
        n = P.build_node(node, "local", nsec, guests, done, NOW)
        self.assertEqual(n["pveversion"], "pve-manager/5.4-15/d0ec33c6 (running kernel: 4.15.18-30-pve)")
        self.assertEqual((n["quorum"]["quorate"], len(n["replication"]), n["backups"][0]["vmid"], n["tasks"]["migrations"][0]["vmid"]), (True, 2, 102, 102))
        g = {x["vmid"]: x for x in n["guests"]}
        self.assertEqual(sorted(g), [102, 103, 300])
        self.assertEqual((g[102]["checks"]["err_24h"], g[102]["checks"]["warn_24h"], g[102]["checks"]["failed_units"]), (2, 3, 1))
        self.assertTrue(g[102]["conf"]["vmac"])
        self.assertEqual(g[102]["disk"], 120000000000)
        self.assertIsNone(g[103]["checks"])                                            # arrêté : rien dans l'invité
        self.assertEqual(g[300]["checks"]["erreur"], "QEMU guest agent is not running")
        self.assertEqual(g[102]["charge"]["cpu_avg_pct"], 20.0)
        self.assertEqual(P.alerts_for([n])[0]["code"], "pve-replication:119-0")


if __name__ == "__main__":
    unittest.main()


class Ips(unittest.TestCase):
    def test_ips_de_la_conf(self):
        c = P.parse_conf("net0: name=eth0,bridge=vmbr0,hwaddr=02:00:00:15:45:EE,ip=198.51.100.7/32,gw=198.51.100.1,type=veth\n"
                         "net1: name=eth1,bridge=vmbr1,ip=dhcp\nipconfig0: ip=192.0.2.9/24,gw=192.0.2.1\ndescription: ip=203.0.113.1\n")
        self.assertEqual(c["ips"], ["198.51.100.7", "192.0.2.9"])
