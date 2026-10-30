# -*- coding: utf-8 -*-
"""#939 : sonde backuppc -- analyse pure (sortie de BackupPC_serverMesg, fichiers hosts et backups)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backuppc as bp  # noqa: E402

NOW = 1761840000  # 2026-10-30 ~16:00 UTC
STATUS = """%Status = (
  'ob1.groupe-i.fr' => {
    'activeJob' => 0,
    'state' => 'Status_idle',
    'reason' => 'Reason_backup_failed',
    'error' => 'No files dumped for share /',
    'lastGoodBackupTime' => T1,
    'startTime' => T2,
    'endTime' => T3,
    'type' => 'full',
    'deadCnt' => 0,
    'aliveCnt' => 12
  },
  'pc-ok' => {
    'activeJob' => 0,
    'state' => 'Status_idle',
    'reason' => 'Reason_nothing_to_do',
    'lastGoodBackupTime' => T4,
    'error' => '',
    'type' => 'incr'
  },
  'pc-cours' => { 'activeJob' => 1, 'state' => 'Status_backup_in_progress', 'reason' => 'Reason_backup_done', 'lastGoodBackupTime' => T5, 'type' => 'full' },
  'pc-vieux' => { 'activeJob' => 0, 'state' => 'Status_idle', 'reason' => 'Reason_no_ping', 'lastGoodBackupTime' => T6, 'error' => 'no ping response' }
);
"""
for _k, _v in (("T1", NOW - 20 * 86400), ("T2", NOW - 3600), ("T3", NOW - 3500), ("T4", NOW - 5 * 3600), ("T5", NOW - 2 * 3600), ("T6", NOW - 10 * 86400)):
    STATUS = STATUS.replace(_k, str(_v))
INFO = """%Info = (
  'Version' => '3.2.1',
  'pid' => 3030,
  'startTime' => 1744329660,
  'ConfigLTime' => 1733149920,
  'nextWakeup' => TW,
  'cpoolKb' => '261810000',
  'cpoolFileCnt' => 538831,
  'cpoolDirCnt' => 4369,
  'DUlastValue' => 53,
  'DUDailyMax' => 53,
  'DUDailyMaxPrev' => 53,
  'cpoolFileCntRm' => 259,
  'cpoolKbRm' => '40000'
);
""".replace("TW", str(NOW + 2400))
QUEUES = "%QueueLen = ( 'BgQueue' => 0, 'UserQueue' => 0, 'CmdQueue' => 0 );"
HOSTS = """host        dhcp    user    moreUsers     # <--- do not edit this line
#farside     0       craig   jill,jeff
ob1.groupe-i.fr  0  willy
pc-ok   0   alice   bob,carl
pc-cours 0 willy
pc-vieux 0 willy
"""
BACKUPS = "\n".join(["\t".join(["0", "full", str(NOW - 25 * 86400), str(NOW - 25 * 86400 + 3000), "1000", "5000000000", "0", "0", "1000", "5000000000", "0", "0", "0", "0", "1", "0", "0", "0", "-1", "1", "rsync", "0"]),
                     "\t".join(["1", "incr", str(NOW - 20 * 86400), str(NOW - 20 * 86400 + 300), "1010", "5100000000", "0", "0", "10", "100000000", "2", "0", "0", "0", "1", "0", "0", "0", "0", "1", "rsync", "1"])]) + "\n"


class Parse(unittest.TestCase):
    def test_perl_hash(self):
        s = bp.parse_perl_hash(STATUS)
        self.assertEqual(set(s), {"ob1.groupe-i.fr", "pc-ok", "pc-cours", "pc-vieux"})
        self.assertEqual(s["ob1.groupe-i.fr"]["error"], "No files dumped for share /")
        self.assertEqual(s["ob1.groupe-i.fr"]["lastGoodBackupTime"], NOW - 20 * 86400)
        self.assertEqual(s["pc-cours"]["activeJob"], 1)
        i = bp.parse_perl_hash(INFO)
        self.assertEqual((i["Version"], i["pid"], i["cpoolKb"]), ("3.2.1", 3030, "261810000"))
        self.assertEqual(bp.parse_perl_hash(QUEUES), {"BgQueue": 0, "UserQueue": 0, "CmdQueue": 0})
        self.assertEqual(bp.parse_perl_hash("%Status = ( 'h' => { 'error' => 'it\\'s \\\\ broken', 'x' => undef } );")["h"], {"error": "it's \\ broken", "x": None})
        self.assertEqual(bp.parse_perl_hash(""), {})

    def test_hosts_backups(self):
        h = bp.parse_hosts(HOSTS)
        self.assertEqual([x["host"] for x in h], ["ob1.groupe-i.fr", "pc-ok", "pc-cours", "pc-vieux"])
        self.assertEqual(h[1]["more_users"], ["bob", "carl"])
        b = bp.parse_backups(BACKUPS)
        self.assertEqual([(x["num"], x["type"], x["xfer_errs"], x["methode"]) for x in b], [(0, "full", 0, "rsync"), (1, "incr", 2, "rsync")])
        self.assertEqual(bp.parse_backups("garbage\n"), [])


class Analyse(unittest.TestCase):
    def setUp(self):
        self.r = bp.analyser(bp.parse_perl_hash(INFO), bp.parse_perl_hash(STATUS), bp.parse_perl_hash(QUEUES), bp.parse_hosts(HOSTS),
                             {"ob1.groupe-i.fr": bp.parse_backups(BACKUPS)}, (500e9, 265e9, 235e9), now=NOW)

    def test_serveur_pool(self):
        self.assertEqual(self.r["serveur"]["version"], "3.2.1")
        self.assertEqual(self.r["pool"]["cpool_octets"], 261810000 * 1024)
        self.assertEqual(self.r["pool"]["topdir_pct"], 53.0)
        self.assertEqual(self.r["files"]["BgQueue"], 0)
        self.assertEqual(self.r["summary"]["state"], "critical")

    def test_hotes_et_constats(self):
        par = {h["host"]: h for h in self.r["hotes"]}
        ob1 = par["ob1.groupe-i.fr"]
        self.assertEqual((ob1["erreur"], ob1["raison"], ob1["sauvegardes"], ob1["pleines"]), ("No files dumped for share /", "SAUVEGARDE EN ÉCHEC", 2, 1))
        self.assertEqual(ob1["age_h"], 480.0)
        self.assertEqual(ob1["xfer_errs"], 2)
        self.assertEqual(par["pc-ok"]["etat"], "inactif")
        self.assertTrue(par["pc-cours"]["en_cours"])
        codes = {a["code"]: a["severity"] for a in self.r["alerts"]}
        self.assertEqual(codes["backuppc-vieux@ob1.groupe-i.fr"], "critical")
        self.assertEqual(codes["backuppc-vieux@pc-vieux"], "critical")
        self.assertNotIn("backuppc-echec@pc-ok", codes)
        self.assertNotIn("backuppc-retard@pc-cours", codes)
        self.assertEqual([e["host"] for e in self.r["echecs"]], ["ob1.groupe-i.fr", "pc-vieux"])
        self.assertEqual(self.r["hotes"][0]["host"], "ob1.groupe-i.fr", "critiques d'abord, par nom")
        self.assertEqual(self.r["summary"]["echecs"], 2)

    def test_retard_simple_et_serveur_absent(self):
        st = {"pc": {"state": "Status_idle", "reason": "Reason_nothing_to_do", "lastGoodBackupTime": NOW - 60 * 3600, "error": ""}}
        r = bp.analyser({}, st, {}, [{"host": "pc", "user": "u"}], {}, None, now=NOW)
        self.assertEqual([a["code"] for a in r["alerts"]], ["backuppc-retard@pc"])
        r2 = bp.analyser({}, {}, {}, [{"host": "pc", "user": "u"}], {}, None, now=NOW, erreur_serveur="connexion refusée")
        self.assertEqual(r2["alerts"][0]["code"], "backuppc-serveur")
        self.assertEqual(r2["hotes"][0]["age_h"], None)
        self.assertIn("backuppc-jamais@pc", [a["code"] for a in r2["alerts"]])
        r3 = bp.analyser({"DUlastValue": 96}, {}, {}, [], {}, None, now=NOW)
        self.assertEqual(r3["alerts"][0]["code"], "backuppc-pool-plein")


if __name__ == "__main__":
    unittest.main()
