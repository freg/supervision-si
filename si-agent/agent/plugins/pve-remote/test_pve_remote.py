# -*- coding: utf-8 -*-
"""Tests #723 : inventaire de PVE distants (ssh simulé)."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pve_remote as pr  # noqa: E402

PCT = "VMID       Status     Lock         Name\n101        stopped                 web-ancien\n106        running                 messagerie\n"
QM = "      VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID\n       200 win-test             stopped    4096              32.00 0\n"
PVESM = "Name             Type     Status           Total            Used       Available        %\nlocal             dir     active      1885338416      1791071520        94266896   95.00%\n"


def fake(outputs):
    def run(args, **k):
        cmd = args[-1]
        for key, val in outputs.items():
            if cmd.startswith(key):
                return subprocess.CompletedProcess(args, 0 if val is not None else 255, val or "", "" if val is not None else "ssh: connect to host x port 22: No route to host")
        return subprocess.CompletedProcess(args, 1, "", "commande inconnue")
    return run


class Inventaire(unittest.TestCase):
    def test_parseurs(self):
        self.assertEqual(pr.parse_pct_list(PCT), [{"vmid": 101, "status": "stopped", "name": "web-ancien", "type": "lxc"},
                                                  {"vmid": 106, "status": "running", "name": "messagerie", "type": "lxc"}])
        self.assertEqual(pr.parse_qm_list(QM)[0]["maxdisk"], 32 * 1024 ** 3)
        s = pr.parse_pvesm(PVESM)[0]
        self.assertEqual((s["storage"], s["active"], s["avail"]), ("local", True, 94266896 * 1024))

    def test_pvesh_et_repli(self):
        res = json.dumps([{"type": "lxc", "vmid": 101, "name": "a", "status": "stopped", "node": "pve1", "maxdisk": 10},
                          {"type": "lxc", "vmid": 300, "name": "ailleurs", "status": "running", "node": "pve2"}, {"type": "storage"}])
        n = pr.inventory({"name": "pve-1", "host": "203.0.113.21"}, runner=fake({"pvesh": res, "hostname": "pve1\n", "pvesm": PVESM}))
        self.assertEqual((n["ok"], n["source"], [g["vmid"] for g in n["guests"]], len(n["storages"])), (True, "pvesh", [101], 1))
        n = pr.inventory({"name": "pve-2", "host": "203.0.113.22"}, runner=fake({"pct list": PCT, "qm list": QM, "pvesm": PVESM}))
        self.assertEqual((n["source"], [g["vmid"] for g in n["guests"]]), ("pct/qm", [101, 106, 200]))
        n = pr.inventory({"name": "pve-3", "host": "203.0.113.23"}, runner=fake({"pvesh": None, "pct": None}))
        self.assertFalse(n["ok"]); self.assertIn("No route", n["error"])
        out = pr.summarize([pr.inventory({"name": "pve-2", "host": "h"}, runner=fake({"pct list": PCT, "qm list": QM})), n])
        self.assertEqual(out["summary"], {"nodes": 2, "reachable": 1, "guests": 3, "running": 1, "stopped": 2})
        self.assertEqual([a["code"] for a in out["alerts"]], ["pve-remote-unreachable:pve-3"])

    def test_snapshots_et_sauvegardes(self):
        snaps = "== lxc 101\n`-> avant-maj    2026-09-01 10:00:00     avant la mise à jour\n    `-> current                    You are here!\n== qemu 200\n`-> current  You are here!\n"
        s = pr.parse_snapshots(snaps)
        self.assertEqual(s, [{"vmid": 101, "type": "lxc", "name": "avant-maj", "at": "2026-09-01 10:00:00", "description": "avant la mise à jour"}])
        bk = ("== local\nVolid                                                  Format  Type        Size VMID\n"
              "local:backup/vzdump-lxc-101-2026_10_01-01_30_00.tar.gz    tgz     backup  123456 101\n"
              "local:vztmpl/debian-9.0-standard_9.7-1_amd64.tar.gz      tgz     vztmpl  1000\n== nfs\n"
              "nfs:backup/vzdump-qemu-200-2026_09_30-02_00_00.vma.lzo   vma.lzo backup  999 200\n")
        b = pr.parse_backups(bk)
        self.assertEqual([(x["storage"], x["vmid"], x["at"], x["size"]) for x in b], [("local", 101, "2026-10-01 01:30:00", 123456), ("nfs", 200, "2026-09-30 02:00:00", 999)])
        n = pr.inventory({"name": "pve-2", "host": "h"}, runner=fake({"pct list": PCT, "qm list": QM, "pvesm status": PVESM, "for id": snaps, "for s": bk}))
        self.assertEqual((len(n["snapshots"]), len(n["backups"])), (1, 2))

    def test_sans_configuration(self):
        self.assertEqual(pr.main(["--config", "/nonexistent.json"]), 0)


if __name__ == "__main__":
    unittest.main()
