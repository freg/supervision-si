# -*- coding: utf-8 -*-
"""Tests #856 : sonde copies-inventory -- découpage de sorties représentatives (pool concaténé dégradé, instantanés,
PBS, fichiers) et pilote réel (bash) exécuté de bout en bout avec de faux zpool / zfs / pct / qm / pvesh / pvesr."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import copies_inventory as C  # noqa: E402

ZSTATUS = """  pool: rpool
 state: DEGRADED
status: One or more devices has experienced an unrecoverable error.
config:

\tNAME                                               STATE     READ WRITE CKSUM
\trpool                                              DEGRADED     0     0     0
\t  nvme-eui.0026b738446d0d15-part3                  ONLINE       0     0     0
\t  /dev/sda                                         ONLINE       0     0     0
\t  /dev/sdb                                         DEGRADED    35    18     0  too many errors

errors: No known data errors

  pool: data
 state: ONLINE
config:

\tNAME        STATE     READ WRITE CKSUM
\tdata        ONLINE       0     0     0
\t  mirror-0  ONLINE       0     0     0
\t    /dev/sdc  ONLINE       0     0     0
\t    /dev/sdd  ONLINE       0     1     0
\tlogs
\t  /dev/nvme1n1p4  ONLINE       0     0     0

errors: No known data errors
"""
ZFS = "\n".join("\t".join(x) for x in [
    ("rpool/subvol-101-disk-0", "filesystem", "190000000000", "177000000000", "200000000000", "1700000000", "0", "/rpool/subvol-101-disk-0"),
    ("rpool/subvol-101-disk-0@mig1", "snapshot", "0", "177000000000", "200000000000", "1792000000", "177000000000", "-"),
    ("rpool/data/vm-100-disk-1", "volume", "1", "2", "3", "4", "5", "-"),
])
PBS = """== pbs10
Volid                                              Format  Type        Size VMID
pbs10:backup/ct/9101/2026-10-25T00:30:02Z          pbs-ct  backup 119000000000 9101
"""


class Parse(unittest.TestCase):
    def test_zpool_status(self):
        st = C.parse_zpool_status(ZSTATUS)
        self.assertEqual((st["rpool"]["state"], st["rpool"]["redondance"], st["rpool"]["disques_simples"]), ("DEGRADED", "non", 3))
        self.assertEqual(st["rpool"]["vdevs"][2]["erreurs"], 53)
        self.assertEqual((st["data"]["redondance"], len(st["data"]["vdevs"]), st["data"]["vdevs"][0]["erreurs"]), ("oui", 1, 1))   # journal ignoré

    def test_zfs_et_pbs(self):
        z = C.parse_zfs(ZFS)
        self.assertEqual((z[1]["dataset"], z[1]["snap"], z[1]["written"], z[2]["mountpoint"]), ("rpool/subvol-101-disk-0", "mig1", 177000000000, None))
        b = C.parse_pvesm_pbs(PBS)
        self.assertEqual((b[0]["vmid"], b[0]["type"], b[0]["size"], b[0]["storage"]), (9101, "lxc", 119000000000, "pbs10"))
        d = C.parse_pbsds("P 1792900000.5 /srv/backup/datastore/vm/101/2026-10-24T22:00:00Z")
        self.assertEqual((d[0]["vmid"], d[0]["type"]), (101, "qemu"))

    def test_files(self):
        t = "\n".join(["@@df ext4 /dev/sdd2 9900000000000 5500000000000 /opt/usb",
                       "F 400 1792900000.1 /opt/usb/pve10/vzdump-qemu-100-2026_10_26-10_03_01.vma.zst",
                       "F 5 1792900000.1 /opt/usb/pve10/vzdump-qemu-100-2026_10_26-10_03_01.log",
                       "F 90 1792900000.1 /var/lib/vz/dump/vzdump-lxc-101-pve3-2026-10-26.tar.gz",
                       "F 77 1791000000.0 /opt/usb/pbs10/vm-101-disk-1@usb1.zfs",
                       "D 1792950000.3 1790000000.0 /opt/usb/ovh/pve2/subvol-100-disk-0"])
        sup, arch, flux, dirs = C.parse_files(t)
        self.assertEqual(sup["/opt/usb"]["fs"], "ext4")
        self.assertEqual([(a["vmid"], a["type"], a["compresse"]) for a in arch], [(100, "qemu", True), (101, "lxc", True)])   # journal écarté
        self.assertEqual(arch[1]["at"], 1792900000)                                    # nom libre : date du fichier
        self.assertEqual((flux[0]["vmid"], flux[0]["snap"], flux[0]["disk"]), (101, "usb1", "vm-101-disk-1"))
        self.assertEqual((dirs[0]["vmid"], dirs[0]["at"]), (100, 1792950000))

    def test_pvesr_et_du(self):
        r = C.parse_pvesr("JobID Enabled Target LastSync NextSync Duration FailCount State\n100-0 Yes local/pve-3 2026-10-26_08:30:01 2026-10-26_08:45:00 4.6 0 OK")
        self.assertEqual((r[0]["vmid"], r[0]["target"], r[0]["last_sync"]), (100, "pve-3", "2026-10-26 08:30:01"))
        self.assertEqual(C.du_needed([{"path": "/a", "at": 5}, {"path": "/b", "at": 6}], {"/a": [5, 10], "/b": [1, 10]}), ["/b"])
        self.assertEqual(C.parse_du("@@du 123 /a b\n@@du ? /c"), {"/a b": 123})


FAUX = {
    "zpool": """#!/bin/sh
case "$1" in list) printf 'rpool\\t100\\t60\\t40\\tONLINE\\n';; status) echo "  pool: rpool"; echo " state: ONLINE";; esac""",
    "zfs": """#!/bin/sh
printf 'rpool/subvol-101-disk-0\\tfilesystem\\t10\\t10\\t20\\t1700000000\\t0\\t/rpool/subvol-101-disk-0\\n'""",
    "pct": """#!/bin/sh
echo "VMID       Status     Lock         Name"; echo "101        stopped                 MED86\"""",
    "qm": "#!/bin/sh\nexit 0",
    "pvesh": """#!/bin/sh
echo '[{"vmid":101,"node":"pve-3","name":"MED86","type":"lxc","status":"stopped"}]'""",
    "pvesr": "#!/bin/sh\necho 'JobID Enabled Target LastSync NextSync Duration FailCount State'",
}


class Pilote(unittest.TestCase):
    def test_bout_en_bout(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            for n, body in FAUX.items():
                f = os.path.join(bindir, n)
                with open(f, "w") as fh:
                    fh.write(body + "\n")
                os.chmod(f, os.stat(f).st_mode | stat.S_IEXEC)
            usb = os.path.join(tmp, "usb")
            os.makedirs(os.path.join(usb, "ovh", "pve3", "subvol-101-disk-0", "etc"))
            with open(os.path.join(usb, "ovh", "pve3", "subvol-101-disk-0", "etc", "hostname"), "w") as fh:
                fh.write("med86\n")
            with open(os.path.join(usb, "vzdump-lxc-101-2026_10_23-16_07_47.tar.gz"), "wb") as fh:
                fh.write(b"x" * 2048)
            env = dict(os.environ, PATH=bindir + ":" + os.environ["PATH"])

            def runner(args, **kw):
                return subprocess.run(args, env=env, **kw)
            cache = os.path.join(tmp, "du.json")
            hosts = os.path.join(tmp, "hosts.json")
            with open(hosts, "w") as fh:
                json.dump([{"name": "pve10", "local": True, "paths": [usb]}], fh)
            import io
            import contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                C.main(["--hosts", hosts], runner=runner, cache_file=cache)
            d = json.loads(out.getvalue())
            h = d["hosts"][0]
            self.assertTrue(h["ok"], h)
            self.assertTrue(h["complete"])
            self.assertEqual(h["guests"], [{"type": "lxc", "vmid": 101, "status": "stopped", "name": "MED86"}])
            self.assertEqual(h["pools"][0]["health"], "ONLINE")
            self.assertEqual([a["vmid"] for a in h["archives"]], [101])
            self.assertEqual(h["dirs"][0]["vmid"], 101)
            self.assertGreater(h["dirs"][0]["size"], 0)          # du calculé puis mis en cache
            self.assertTrue(os.path.exists(cache))


if __name__ == "__main__":
    unittest.main()
