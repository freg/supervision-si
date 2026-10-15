# -*- coding: utf-8 -*-
"""#769 : activité des CT / VM -- découpage de la sortie d'un nœud, agrégation awk RÉELLE d'un journal d'accès,
`last`, MySQL (compteur comparé d'un passage à l'autre), RRD, assemblage."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guest_usage as gu  # noqa: E402

NOW = dt.datetime(2026, 10, 15, 12, 0, 0, tzinfo=dt.timezone.utc)
T0 = int(NOW.timestamp())

LOG = "\n".join([
    '198.51.100.7 - - [08/Oct/2026:09:00:00 +0200] "GET / HTTP/1.1" 200 512 "-" "Mozilla"',
    '198.51.100.7 - - [15/Oct/2026:08:30:00 +0200] "GET /index.php HTTP/1.1" 200 512 "-" "Mozilla"',
    '203.0.113.9 - alice [15/Oct/2026:09:15:00 +0200] "PROPFIND /owncloud/remote.php/webdav/ HTTP/1.1" 207 900 "-" "mirall/2.4"',
    '203.0.113.9 - bob [15/Oct/2026:13:45:10 +0200] "GET /ocs/v1.php/cloud/capabilities HTTP/1.1" 200 90 "-" "mirall/2.4"',
    'ligne illisible',
    '192.0.2.1 - - [15/Oct/2026:13:59:59 +0200] "GET /robots.txt HTTP/1.1" 404 10 "-" "bot"',
]) + "\n"

LAST = """alice    pts/0        203.0.113.9      Wed Oct 15 10:01:02 2026 - Wed Oct 15 10:30:00 2026  (00:28)
root     pts/1        198.51.100.7     Mon Oct 13 08:00:00 2026   still logged in
reboot   system boot  5.4.0            Sun Oct 12 07:00:00 2026   still running
alice    pts/0        203.0.113.9      Tue Sep 30 18:00:00 2026 - Tue Sep 30 19:00:00 2026  (01:00)

wtmp begins Mon Sep  1 00:00:00 2026"""


def rrd(points):
    return json.dumps([{"time": T0 - i * 1800, "cpu": c, "maxcpu": 2, "netin": 100, "netout": 50} for i, c in enumerate(points)][::-1])


def guest_text(web, mysql=True, conns=120):
    s = "## os\nDebian GNU/Linux 9 (stretch)\n## web\n" + web + "## login\n" + LAST + "\n"
    if mysql:
        s += ("## mysql status\nAborted_connects\t2\nConnections\t%d\nMax_used_connections\t7\nQuestions\t9000\nThreads_connected\t2\nUptime\t86400\n"
              "## mysql proc\nmodoboa\tlocalhost\tmodoboa\tSleep\t12\nsystem user\t\t\tDaemon\t0\n## mysql version\n10.1.48-MariaDB-0+deb9u2\n" % conns)
    return s + "## end\n"


class AwkReel(unittest.TestCase):
    """Le script de l'invité est exécuté pour de vrai (sh + awk + sort de la machine) sur un journal factice."""

    def setUp(self):
        if not shutil.which("awk") or not shutil.which("sh"):
            self.skipTest("awk absent")
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "apache2"))
        with open(os.path.join(self.d, "apache2", "site-access.log"), "w") as fh:
            fh.write(LOG)
        with open(os.path.join(self.d, "apache2", "site-access.log.1"), "w") as fh:
            fh.write('198.51.100.7 - - [01/Oct/2026:09:00:00 +0200] "GET / HTTP/1.1" 200 1 "-" "x"\n')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_agregation(self):
        script = gu.GUEST_SH.replace("/var/log/apache2", os.path.join(self.d, "apache2")).replace("command -v mysql", "command -v mysql_absent_pour_le_test")
        out = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30).stdout
        parts = gu.parse_guest(out)
        self.assertIn("end", parts)
        self.assertNotIn("mysql status", parts)
        w = gu.parse_web(parts["web"], NOW)
        self.assertEqual(len(w["files"]), 2)
        self.assertTrue(w["files"][0].endswith(".log.1"))                        # le plus ancien d'abord
        self.assertEqual(w["last"], {"at": "2026-10-15T11:59:59Z", "ip": "192.0.2.1"})
        self.assertEqual(w["hits24"], 4)                                           # 15/10 depuis 14/10 12:00 UTC
        self.assertEqual(w["hits7d"], 4)                                           # 08/10 09:00+0200 = 07:00Z : hors des 7 j (08/10 12:00Z)
        self.assertEqual(w["owncloud"], {"last_at": "2026-10-15T11:45:10Z", "last_user": "bob", "hits7d": 2})
        ips = {i["ip"]: i for i in w["ips"]}
        self.assertEqual(ips["198.51.100.7"]["hits"], 3)
        self.assertEqual(ips["198.51.100.7"]["last_at"], "2026-10-15T06:30:00Z")
        self.assertEqual([d["day"] for d in w["per_day"]], ["2026-10-08", "2026-10-15"])   # 01/10 hors des 14 j gardés

    def test_sans_journal(self):
        script = gu.GUEST_SH.replace("/var/log/apache2", "/nonexistent").replace("/var/log/nginx", "/nonexistent").replace("/var/log/httpd", "/nonexistent")
        out = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30).stdout
        self.assertIsNone(gu.parse_web(gu.parse_guest(out)["web"], NOW))

    def test_script_du_noeud_syntaxe(self):
        if not shutil.which("bash"):
            self.skipTest("bash absent")
        p = subprocess.run(["bash", "-n"], input=gu.driver_script(), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("si_main </dev/null", gu.driver_script())


class Analyse(unittest.TestCase):
    def test_last(self):
        r = gu.parse_last(LAST, NOW)
        self.assertEqual(r["last"], {"user": "alice", "from": "203.0.113.9", "at": "2026-10-15T10:01:02"})
        self.assertEqual([u["user"] for u in r["users"]], ["alice", "root"])       # reboot ignoré
        self.assertEqual(r["users"][0]["count"], 2)
        self.assertEqual(r["count7d"], 2)
        self.assertEqual(gu.parse_last("", NOW)["last"], None)
        court = gu.parse_last("root     pts/0        10.0.0.1         Wed Dec 31 23:00   still logged in", dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc))
        self.assertEqual(court["last"]["at"], "2025-12-31T23:00:00")               # année absente : décembre de l'an passé

    def test_mysql(self):
        my = gu.parse_mysql("Connections\t100\nUptime\t50\nQuestions\t10", "app\t10.0.0.5\tbase\tQuery\t3", "10.1.48")
        self.assertTrue(my["ok"]); self.assertEqual(my["sessions"][0]["host"], "10.0.0.5")
        self.assertFalse(gu.parse_mysql("ERROR 1045 (28000): Access denied for user 'root'@'localhost'", "", "")["ok"])
        a1, s1 = gu.mysql_step(dict(my, sessions=[]), None, NOW)
        self.assertIsNone(a1["conn_since_last"]); self.assertIsNone(a1["last_activity_at"])
        a2, s2 = gu.mysql_step(dict(my, connections=103, uptime_s=1850, sessions=[]), s1, NOW + dt.timedelta(minutes=30))
        self.assertEqual(a2["conn_since_last"], 0)                                 # 3 connexions = la sonde elle-même
        a3, s3 = gu.mysql_step(dict(my, connections=120, uptime_s=3650, sessions=[]), s2, NOW + dt.timedelta(hours=1))
        self.assertEqual((a3["conn_since_last"], a3["last_activity_at"], a3["conn7d"]), (14, "2026-10-15T13:00:00Z", 14))
        a4, _ = gu.mysql_step(dict(my, connections=10, uptime_s=60, sessions=[{"user": "app"}]), s3, NOW + dt.timedelta(hours=2))
        self.assertEqual(a4["conn_since_last"], 7)                                 # redémarrage : repart du compteur
        self.assertEqual(a4["users_seen"][0]["user"], "app")

    def test_rrd(self):
        r = gu.rrd_stats(rrd([0.10, 0.30, 0.20]), rrd([0.05] * 40), NOW)
        self.assertEqual((r["cpu_now"], r["cpu_max24"], r["cpu_avg24"], r["cpu_avg7d"], r["ncpu"]), (10.0, 30.0, 20.0, 5.0, 2))
        self.assertEqual(r["netin24"], 100 * 3 * 1800)
        self.assertEqual(gu.rrd_stats("", "erreur", NOW)["cpu_avg24"], None)

    def test_noeud_complet(self):
        qga = json.dumps({"exitcode": 0, "exited": 1, "out-data": guest_text("", mysql=False)})
        text = "\n".join(["@@node pve-3", "=== lxc 106 running ob1", "## rrd day", rrd([0.2, 0.4]), "## rrd week", rrd([0.1]), "## exec",
                          guest_text("F /var/log/apache2/access.log\nL 20261015100000+0200 198.51.100.7\nH 2026101510+0200 12 3\n"),
                          "=== lxc 110 stopped vieux", "## rrd day", "[]", "## rrd week", "[]",
                          "=== qemu 200 running win", "## rrd day", rrd([0.5]), "## rrd week", rrd([0.5]), "## qga", qga,
                          "=== qemu 201 running sansagent", "## rrd day", "[]", "## rrd week", "[]", "## qga", "No QEMU guest agent configured",
                          "@@done"])
        node, guests, done = gu.parse_driver(text)
        self.assertEqual((node, done, [g["vmid"] for g in guests]), ("pve-3", True, [106, 110, 200, 201]))
        rows, st = gu.build("pve-3", guests, {"106": {"connections": 100, "uptime_s": 80000, "at": T0 - 1800}}, NOW)
        r = {x["vmid"]: x for x in rows}
        self.assertTrue(r[106]["collected"]); self.assertEqual(r[106]["web"]["hits24"], 12)
        self.assertEqual(r[106]["mysql"]["conn_since_last"], 17)
        self.assertEqual(r[106]["login"]["last"]["user"], "alice")
        self.assertEqual(st["106"]["connections"], 120)
        self.assertFalse(r[110]["collected"]); self.assertIsNone(r[110]["error"])
        self.assertTrue(r[200]["collected"]); self.assertIsNone(r[200]["mysql"])
        self.assertFalse(r[201]["collected"]); self.assertIn("agent", r[201]["error"])
        al = gu.alerts_for([{"name": "pve-3", "ok": True, "guests": [dict(r[106], mysql={"ok": False, "error": "ERROR 1045"})]},
                            {"name": "pve-1", "ok": False, "error": "timeout"}])
        self.assertEqual([a["code"] for a in al], ["guest-usage-mysql:pve-3:106", "guest-usage-unreachable:pve-1"])

    def test_run_node_cle_absente(self):
        with self.assertRaises(RuntimeError) as c:
            gu.run_node({"host": "h", "key": "/nonexistent/k"}, "x")
        self.assertIn("ProtectHome", str(c.exception))
        fake = lambda args, **kw: type("P", (), {"stdout": "@@node n\n@@done", "stderr": "", "returncode": 0})()
        self.assertIn("@@node", gu.run_node(None, "x", runner=fake))


if __name__ == "__main__":
    unittest.main()
