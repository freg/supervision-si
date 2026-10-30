# -*- coding: utf-8 -*-
"""#939 : sonde nas-qnap -- analyse pure de la sortie du script SSH."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nas_qnap as nq  # noqa: E402

NOW = time.mktime((2026, 10, 30, 16, 0, 0, 0, 0, -1))
SORTIE = """=== version
5.2.9
20250918
TS-883XU-RP
nas-1
 16:00:02 up 120 days
=== df
Filesystem           1K-blocks      Used Available Use% Mounted on
none                    400000    200000    200000  50% /
/dev/mapper/cachedev1 62000000000 55800000000 6200000000  90% /share/CACHEDEV1_DATA
/dev/mapper/cachedev2 20000000000  4000000000 16000000000  20% /share/CACHEDEV2_DATA
tmpfs                    65536        0     65536   0% /tmp
=== mdstat
Personalities : [linear] [raid0] [raid1] [raid10] [raid6] [raid5] [raid4]
md1 : active raid5 sda3[0] sdb3[1] sdc3[2] sdd3[3]
      11718881856 blocks super 1.0 level 5, 64k chunk, algorithm 2 [4/4] [UUUU]
md2 : active raid1 sde3[0] sdf3[1]
      1953382464 blocks super 1.0 [2/1] [U_]
md322 : active raid1 sdd2[3](S) sdc2[2]
      7235136 blocks super 1.0 [2/2] [UU]
=== smb
[global]
    workgroup = GRPI
[Public]
    path = /share/CACHEDEV1_DATA/Public
    read only = no
[TimeMachine]
    path = /share/CACHEDEV2_DATA/TimeMachine
    fruit:time machine = yes
    browseable = no
[Archives]
    path = /share/CACHEDEV1_DATA/Archives
    read only = yes
=== snapshots
## /share/CACHEDEV1_DATA
/share/CACHEDEV1_DATA/.snapshot/GMT-2026.10.28-01.00.00
/share/CACHEDEV1_DATA/.snapshot/GMT-2026.10.29-01.00.00
/share/CACHEDEV1_DATA/.snapshot/GMT-2026.10.30-01.00.00
## /share/CACHEDEV2_DATA
=== timemachine
TM1 15000000 /share/CACHEDEV2_DATA/TimeMachine/mac-alice.sparsebundle
TM2 9000000 /share/CACHEDEV2_DATA/TimeMachine/mac-bob.backupbundle
=== outils
hbs3.conf
rtrr.conf
qpkg:HybridBackup
/sbin/qcli_snapshot
/usr/local/sbin/snapshot_util
=== fin
""".replace("TM1", str(int(NOW - 5 * 3600))).replace("TM2", str(int(NOW - 10 * 86400)))


class Analyse(unittest.TestCase):
    def setUp(self):
        self.r = nq.analyser("nas-1", "192.0.2.9", SORTIE, now=NOW)

    def test_systeme_volumes_raid(self):
        self.assertEqual((self.r["systeme"]["version"], self.r["systeme"]["modele"], self.r["systeme"]["hostname"]), ("5.2.9", "TS-883XU-RP", "nas-1"))
        self.assertEqual([(v["nom"], v["pct"]) for v in self.r["volumes"]], [("CACHEDEV1_DATA", 90.0), ("CACHEDEV2_DATA", 20.0)])
        self.assertEqual([(r["dev"], r["niveau"], r["degrade"]) for r in self.r["raid"]], [("md1", "RAID 5", False), ("md2", "RAID 1", True), ("md322", "RAID 1", False)])

    def test_partages_snapshots_timemachine(self):
        self.assertEqual(self.r["partages_timemachine"], ["TimeMachine"])
        self.assertEqual([p["nom"] for p in self.r["partages"]], ["Public", "TimeMachine", "Archives"])
        self.assertTrue(self.r["partages"][2]["lecture_seule"] and not self.r["partages"][1]["navigable"])
        s = {x["volume"]: x for x in self.r["snapshots"]}
        self.assertEqual((s["CACHEDEV1_DATA"]["nombre"], s["CACHEDEV1_DATA"]["dernier_age_h"], s["CACHEDEV1_DATA"]["dossier"]), (3, 15.0, "/share/CACHEDEV1_DATA/.snapshot"))
        self.assertEqual(s["CACHEDEV2_DATA"]["nombre"], 0)
        self.assertEqual(self.r["volumes_sans_snapshot"], ["CACHEDEV2_DATA"])
        tm = {b["machine"]: b for b in self.r["timemachine"]}
        self.assertEqual((tm["mac-alice"]["age_h"], tm["mac-alice"]["ko"]), (5.0, 15000000))
        self.assertEqual(tm["mac-bob"]["age_h"], 240.0)
        self.assertIn("qpkg:HybridBackup", self.r["outils"])

    def test_constats(self):
        codes = {a["code"]: a["severity"] for a in self.r["alertes"]}
        self.assertEqual(codes["nas-volume-presque-plein@CACHEDEV1_DATA"], "warning")
        self.assertEqual(codes["nas-raid-degrade@md2"], "critical")
        self.assertEqual(codes["nas-timemachine-vieux@mac-bob"], "warning")
        self.assertNotIn("nas-timemachine-vieux@mac-alice", codes)
        self.assertNotIn("nas-snapshot-vieux@CACHEDEV1_DATA", codes)
        self.assertTrue(all(a["message"].startswith("nas-1 : ") for a in self.r["alertes"]))

    def test_snapshot_vieux_et_tm_vide(self):
        s = SORTIE.replace("GMT-2026.10.30-01.00.00", "GMT-2026.10.20-01.00.00").replace("GMT-2026.10.29-01.00.00", "GMT-2026.10.19-01.00.00").replace("GMT-2026.10.28-01.00.00", "GMT-2026.10.18-01.00.00")
        s = s.split("=== timemachine")[0] + "=== timemachine\n=== outils\n=== fin\n"
        r = nq.analyser("nas-1", "h", s, now=NOW)
        codes = [a["code"] for a in r["alertes"]]
        self.assertIn("nas-snapshot-vieux@CACHEDEV1_DATA", codes)
        self.assertIn("nas-timemachine-vide", codes)

    def test_sortie_vide(self):
        r = nq.analyser("x", "h", "", now=NOW)
        self.assertEqual((r["volumes"], r["raid"], r["snapshots"], r["alertes"]), ([], [], [], []))
        self.assertIsNone(r["systeme"]["version"])


class Main(unittest.TestCase):
    def test_config_absente_et_ssh(self):
        out = nq.main(["--config", "/nonexistent/x.json"])
        self.assertEqual(out["alerts"][0]["code"], "nas-qnap-config")
        import json
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "c.json")
        with open(p, "w") as fh:
            json.dump([{"name": "nas-1", "host": "192.0.2.9", "user": "admin", "key": "/k"}], fh)
        vus = {}

        class R:
            returncode, stdout, stderr = 0, SORTIE, ""

        def runner(argv, **kw):
            vus["argv"] = argv
            vus["input"] = kw.get("input")
            return R()
        out = nq.main(["--config", p], runner=runner, which=lambda x: "/usr/bin/ssh")
        self.assertEqual(out["nas"][0]["systeme"]["modele"], "TS-883XU-RP")
        self.assertEqual(vus["argv"][-3:], ["admin@192.0.2.9", "sh", "-s"])
        self.assertIn("-i", vus["argv"])
        self.assertIn("=== snapshots", vus["input"])
        self.assertNotIn("setcfg", vus["input"], "script en lecture seule")
        self.assertFalse(any(w in vus["input"] for w in ("rm ", "mv ", "snapshot_tool", "setcfg", "reboot")))


if __name__ == "__main__":
    unittest.main()
