# -*- coding: utf-8 -*-
"""Stockage de l'hôte Linux (livraison #503) : parseurs purs sur des
sorties représentatives (lsblk, LVM JSON, /proc/mdstat, zpool, zfs),
collecte contre un faux runner, risques dérivés."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from si_agent import risks, storage  # noqa: E402

NOW = 1_780_000_000

LSBLK = {"blockdevices": [
    {"name": "sda", "type": "disk", "size": 1000204886016, "fstype": None, "mountpoint": None, "model": "ST1000", "rota": True, "rm": False,
     "children": [{"name": "sda1", "type": "part", "size": 536870912, "fstype": "vfat", "mountpoint": "/boot/efi", "rota": True, "rm": False},
                  {"name": "sda2", "type": "part", "size": 999666000000, "fstype": "LVM2_member", "mountpoint": None, "rota": True, "rm": False,
                   "children": [{"name": "pve-root", "type": "lvm", "size": 100000000000, "fstype": "ext4", "mountpoint": "/", "rota": True, "rm": False},
                                {"name": "pve-data", "type": "lvm", "size": 800000000000, "fstype": None, "mountpoint": None, "rota": True, "rm": False}]}]},
    {"name": "zd0", "type": "disk", "size": 34359738368, "fstype": None, "mountpoints": [None], "rota": False, "rm": False}]}

LVS = json.dumps({"report": [{"lv": [
    {"lv_name": "root", "vg_name": "pve", "lv_size": "100000000000", "lv_attr": "-wi-ao----", "data_percent": "", "metadata_percent": "", "pool_lv": "", "origin": ""},
    {"lv_name": "data", "vg_name": "pve", "lv_size": "800000000000", "lv_attr": "twi-aotz--", "data_percent": "91.20", "metadata_percent": "3.10", "pool_lv": "", "origin": ""},
    {"lv_name": "vm-100-disk-0", "vg_name": "pve", "lv_size": "32000000000", "lv_attr": "Vwi-aotz--", "data_percent": "40.00", "metadata_percent": "", "pool_lv": "data", "origin": ""}]}]})
VGS = json.dumps({"report": [{"vg": [{"vg_name": "pve", "vg_size": "999666000000", "vg_free": "16000000000", "pv_count": "1", "lv_count": "3"}]}]})
PVS = json.dumps({"report": [{"pv": [{"pv_name": "/dev/sda2", "vg_name": "pve", "pv_size": "999666000000", "pv_free": "16000000000"}]}]})

MDSTAT = """Personalities : [raid1] [raid10]
md0 : active raid1 sdb1[0] sdc1[1]
      976630464 blocks super 1.2 [2/2] [UU]
      bitmap: 0/8 pages [0KB], 65536KB chunk

md1 : active raid10 sdd1[0] sde1[1] sdf1[2]
      1953260544 blocks super 1.2 512K chunks 2 near-copies [4/3] [UUU_]
      [==>..................]  recovery = 12.5% (244157440/1953260544) finish=120.4min speed=236552K/sec

unused devices: <none>
"""

ZPOOL_LIST = "rpool\t1000000000000\t850000000000\t150000000000\t12\t85\tONLINE\ntank\t4000000000000\t1000000000000\t3000000000000\t3\t25\tDEGRADED\n"
ZPOOL_STATUS = """  pool: rpool
 state: ONLINE
  scan: scrub repaired 0B in 00:10:12 with 0 errors on Sun Aug 10 00:34:13 2026
config:

	NAME        STATE     READ WRITE CKSUM
	rpool       ONLINE       0     0     0
	  mirror-0  ONLINE       0     0     0
	    sda3    ONLINE       0     0     0
	    sdb3    ONLINE       0     0     2

errors: No known data errors

  pool: tank
 state: DEGRADED
status: One or more devices could not be opened.
  scan: none requested
config:

	NAME        STATE     READ WRITE CKSUM
	tank        DEGRADED     0     0     0
	  raidz1-0  DEGRADED     0     0     0
	    sdc     ONLINE       0     0     0
	    sdd     UNAVAIL      0     0     0
	    sde     ONLINE       0     0     0

errors: No known data errors
"""
ZFS_LIST = ("rpool\tfilesystem\t850000000000\t150000000000\t96000\t/rpool\t1.10x\t0\t-\n"
            "rpool/data\tfilesystem\t700000000000\t150000000000\t96000\t/rpool/data\t1.35x\t0\t-\n"
            "rpool/data/vm-100-disk-0\tvolume\t34000000000\t150000000000\t34000000000\t-\t1.00x\t-\t34359738368\n"
            "tank/backup\tfilesystem\t95000000000\t5000000000\t95000000000\t/tank/backup\t1.00x\t100000000000\t-\n")
SNAPS = ("rpool/data/vm-100-disk-0@avant-maj\t2000000\t%d\n"
         "rpool/data/vm-100-disk-0@autosnap_2026\t1000000\t%d\n"
         "tank/backup@daily\t0\t%d\n") % (NOW - 40 * 86400, NOW - 3600, NOW - 86400)


class Fake(object):
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def runner(outputs):
    def cmd(argv, timeout=20):
        key = argv[0]
        return Fake(0, outputs[key]) if key in outputs else Fake(1, "")
    return cmd


class ParseursTests(unittest.TestCase):
    def test_lsblk_aplati(self):
        rows = storage.flatten_lsblk(LSBLK)
        names = [r["name"] for r in rows]
        self.assertEqual(names, ["sda", "sda1", "sda2", "pve-root", "pve-data", "zd0"])
        self.assertEqual([r for r in rows if r["name"] == "pve-root"][0]["parent"], "sda2")
        self.assertEqual([r for r in rows if r["name"] == "sda1"][0]["mountpoint"], "/boot/efi")
        self.assertIs([r for r in rows if r["name"] == "zd0"][0]["rotational"], False)

    def test_lvm(self):
        s = storage.lvm_summary(storage.parse_lvm_report(PVS, "pv"), storage.parse_lvm_report(VGS, "vg"), storage.parse_lvm_report(LVS, "lv"))
        self.assertEqual(s["groups"][0]["vg"], "pve")
        pool = [v for v in s["volumes"] if v["lv"] == "data"][0]
        self.assertEqual((pool["kind"], pool["data_percent"], pool["active"]), ("thin-pool", 91.2, True))
        thin = [v for v in s["volumes"] if v["lv"] == "vm-100-disk-0"][0]
        self.assertEqual((thin["kind"], thin["pool"]), ("thin", "data"))
        self.assertEqual(storage.parse_lvm_report("pas du json", "lv"), [])

    def test_mdstat(self):
        arrays = storage.parse_mdstat(MDSTAT)
        self.assertEqual(len(arrays), 2)
        self.assertEqual((arrays[0]["level"], arrays[0]["degraded"], arrays[0]["devices"]), ("raid1", False, ["sdb1", "sdc1"]))
        self.assertTrue(arrays[1]["degraded"])
        self.assertEqual((arrays[1]["active"], arrays[1]["total"]), (3, 4))
        self.assertIn("recovery", arrays[1]["resync"])
        self.assertEqual(storage.parse_mdstat(""), [])

    def test_zpool(self):
        pools = storage.parse_zpool_list(ZPOOL_LIST)
        self.assertEqual(pools[0]["capacity_percent"], 85.0)
        st = storage.parse_zpool_status(ZPOOL_STATUS, now=NOW)
        self.assertEqual(st["rpool"]["state"], "ONLINE")
        self.assertIsNotNone(st["rpool"]["scrub_age_s"])
        self.assertEqual([d for d in st["rpool"]["devices"] if d["name"] == "sdb3"][0]["cksum"], 2)
        self.assertEqual(st["tank"]["state"], "DEGRADED")
        self.assertIsNone(st["tank"]["scrub_age_s"])
        self.assertEqual([d["state"] for d in st["tank"]["devices"] if d["name"] == "sdd"], ["UNAVAIL"])

    def test_zfs_list_et_snapshots(self):
        ds = storage.parse_zfs_list(ZFS_LIST)
        self.assertEqual(len(ds), 4)
        vol = [d for d in ds if d["type"] == "volume"][0]
        self.assertEqual((vol["volsize"], vol["mountpoint"], vol["pool"]), (34359738368, None, "rpool"))
        quota = [d for d in ds if d["name"] == "tank/backup"][0]
        self.assertEqual((quota["quota"], quota["used_percent"]), (100000000000, 95.0))
        agg = storage.aggregate_snapshots(SNAPS, now=NOW)
        self.assertEqual(agg["rpool/data/vm-100-disk-0"]["count"], 2)
        self.assertEqual(agg["rpool/data/vm-100-disk-0"]["used"], 3000000)
        self.assertEqual(agg["rpool/data/vm-100-disk-0"]["oldest_age_s"], 40 * 86400)
        self.assertEqual(agg["rpool/data/vm-100-disk-0"]["newest_age_s"], 3600)


class CollecteTests(unittest.TestCase):
    def test_toutes_couches(self):
        cmd = runner({"lsblk": json.dumps(LSBLK), "pvs": PVS, "vgs": VGS, "lvs": LVS,
                      "zpool": None, "zfs": None})
        # zpool/zfs : le faux runner distingue par arguments
        def cmd2(argv, timeout=20):
            if argv[0] == "zpool":
                return Fake(0, ZPOOL_LIST if argv[1] == "list" else ZPOOL_STATUS)
            if argv[0] == "zfs":
                return Fake(0, SNAPS if "snapshot" in argv else ZFS_LIST)
            return cmd(argv, timeout)
        files = lambda p: MDSTAT if p == "/proc/mdstat" else None  # noqa: E731
        out = storage.collect_storage(cmd=cmd2, files=files, which=lambda t: True, now=NOW)
        self.assertEqual(out["available"], ["lsblk", "lvm", "md", "zfs"])
        self.assertEqual(len(out["blocks"]), 6)
        self.assertEqual(out["zfs"]["pools"][1]["state"], "DEGRADED")
        self.assertEqual(out["zfs"]["snapshot_total"], 3)
        vol = [d for d in out["zfs"]["datasets"] if d["type"] == "volume"][0]
        self.assertEqual(vol["snapshots"]["count"], 2)

    def test_sans_outils(self):
        out = storage.collect_storage(cmd=runner({}), files=lambda p: None, which=lambda t: False, now=NOW)
        self.assertEqual(out["available"], [])
        self.assertEqual((out["blocks"], out["lvm"], out["md"], out["zfs"]), ([], None, [], None))

    def test_outil_en_panne(self):
        def boom(argv, timeout=20):
            raise OSError("cassé")
        out = storage.collect_storage(cmd=boom, files=lambda p: None, which=lambda t: True, now=NOW)
        self.assertEqual(out["available"], [])


class RisquesTests(unittest.TestCase):
    def test_risques_stockage(self):
        st = {"zfs": {"pools": [
                  {"pool": "rpool", "state": "ONLINE", "capacity_percent": 85.0, "scrub_age_s": 40 * 86400, "scan": "scrub repaired", "errors": "No known data errors",
                   "devices": [{"name": "sdb3", "state": "ONLINE", "read": 0, "write": 0, "cksum": 2}]},
                  {"pool": "tank", "state": "DEGRADED", "capacity_percent": 25.0, "scrub_age_s": None, "scan": "none requested", "errors": "No known data errors", "devices": []}],
                  "datasets": [{"name": "tank/backup", "quota": 100, "used_percent": 95.0}]},
              "lvm": {"volumes": [{"lv": "data", "vg": "pve", "kind": "thin-pool", "data_percent": 91.2, "metadata_percent": 3.1}]},
              "md": [{"array": "md1", "level": "raid10", "degraded": True, "active": 3, "total": 4}, {"array": "md0", "level": "raid1", "degraded": False, "resync": "check 10.0%"}]}
        ids = {r["id"]: r["severity"] for r in risks.evaluate_storage(st)}
        self.assertEqual(ids.get("zpool-high"), "warning")
        self.assertEqual(ids.get("zpool-errors"), "warning")
        self.assertEqual(ids.get("zpool-scrub-old"), "info")
        self.assertEqual(ids.get("zpool-degraded"), "critical")
        self.assertEqual(ids.get("zpool-scrub-never"), "info")
        self.assertEqual(ids.get("dataset-quota"), "warning")
        self.assertEqual(ids.get("thin-pool-high"), "warning")
        self.assertEqual(ids.get("md-degraded"), "critical")
        self.assertEqual(ids.get("md-resync"), "info")
        # intégré à evaluate() sur une mesure host ; absent = rien
        self.assertEqual([r for r in risks.evaluate({"storage": None}) if r["id"].startswith("zpool")], [])
        self.assertTrue(any(r["id"] == "md-degraded" for r in risks.evaluate({"storage": st})))


if __name__ == "__main__":
    unittest.main(verbosity=1)
