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
import time
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


class Historique771(unittest.TestCase):
    """#771 : activité par jour, reprise de l'historique (journaux .gz compris), RRD mois / année, MySQL par jour."""

    def setUp(self):
        if not shutil.which("awk") or not shutil.which("sh") or not shutil.which("zcat"):
            self.skipTest("awk / zcat absent")
        import gzip
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "apache2"))
        with open(os.path.join(self.d, "apache2", "site-access.log"), "w") as fh:
            fh.write(LOG)
        old = ('198.51.100.7 - - [01/Mar/2026:09:00:00 +0100] "GET / HTTP/1.1" 200 1000 "-" "Mozilla/5.0"\n'
               '198.51.100.8 - - [01/Mar/2026:10:00:00 +0100] "GET /a HTTP/1.1" 200 500 "-" "Mozilla/5.0"\n'
               '198.51.100.7 - - [01/Mar/2026:11:00:00 +0100] "GET /b HTTP/1.1" 200 1 "-" "Mozilla/5.0"\n'
               '127.0.0.1 - - [01/Mar/2026:11:00:00 +0100] "GET /status HTTP/1.1" 200 7 "-" "Mozilla/5.0"\n'
               '192.0.2.50 - - [02/Mar/2026:11:00:00 +0100] "GET / HTTP/1.1" 200 9 "-" "curl/7.88"\n')
        with gzip.open(os.path.join(self.d, "apache2", "site-access.log.5.gz"), "wt") as fh:
            fh.write(old)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_guest(self, deep):
        script = gu.GUEST_SH.replace("/var/log/apache2", os.path.join(self.d, "apache2")).replace("command -v mysql", "command -v mysql_absent_pour_le_test")
        env = dict(os.environ, SI_DEEP="1" if deep else "0")
        return gu.parse_guest(subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30, env=env).stdout)

    def test_jours_courants_sans_gz(self):
        days, deep = gu.parse_days(self.run_guest(False)["days"])
        self.assertFalse(deep)
        self.assertEqual([d["day"] for d in days], ["2026-10-08", "2026-10-15"])     # le .gz n'est lu qu'en reprise
        d15 = days[1]
        self.assertEqual((d15["req"], d15["visitors"], d15["owncloud"], d15["bot"]), (3, 2, 2, 1))   # « bot » à part
        self.assertEqual(d15["bytes"], 512 + 900 + 90)

    def test_reprise_lit_les_gz(self):
        days, deep = gu.parse_days(self.run_guest(True)["days"])
        self.assertTrue(deep)
        by = {d["day"]: d for d in days}
        self.assertEqual((by["2026-03-01"]["req"], by["2026-03-01"]["visitors"], by["2026-03-01"]["bytes"]), (3, 2, 1501))
        self.assertEqual((by["2026-03-01"]["bot"], by["2026-03-01"]["bot_bytes"]), (1, 7))             # boucle locale
        self.assertEqual((by["2026-03-02"]["req"], by["2026-03-02"]["bot"]), (0, 1))                   # curl = outil

    def test_jours_de_connexion(self):
        rows = gu._last_rows(LAST, NOW)
        self.assertEqual(gu.login_days(rows), [{"day": "2026-09-30", "logins": 1, "users": 1},
                                               {"day": "2026-10-13", "logins": 1, "users": 1},
                                               {"day": "2026-10-15", "logins": 1, "users": 1}])
        self.assertEqual(gu.parse_last(LAST, NOW)["last"]["user"], "alice")                            # inchangé

    def test_rrd_jours_et_semaines(self):
        base = T0 - T0 % 86400
        month = json.dumps([{"time": base - 86400 + i * 43200, "cpu": c, "netin": 10, "netout": 5, "diskread": 1, "diskwrite": 2}
                            for i, c in enumerate([0.1, 0.3, 0.2])])
        d = gu.rrd_days(month)
        self.assertEqual([x["day"] for x in d], ["2026-10-14", "2026-10-15"])
        self.assertEqual(d[0]["cpu"], 20.0)
        self.assertEqual(d[0]["netin"], 10 * 2 * 43200)
        year = json.dumps([{"time": base - 14 * 86400, "cpu": 0.05, "netin": 1, "netout": 1}, {"time": base - 7 * 86400, "cpu": None}])
        w = gu.rrd_weeks(year)
        self.assertEqual([x["week"] for x in w], ["2026-10-01", "2026-10-08"])
        self.assertEqual((w[0]["cpu"], w[0]["netin"], w[1]["cpu"]), (5.0, 7 * 86400, None))

    def test_mysql_par_jour(self):
        my = {"connections": 100, "questions": 1000, "uptime_s": 500, "bytes_in": 10, "bytes_out": 90, "sessions": []}
        _add, st = gu.mysql_step(my, None, NOW)
        my2 = dict(my, connections=110, questions=1503, uptime_s=2300, bytes_in=110, bytes_out=990)
        add, st = gu.mysql_step(my2, st, NOW + dt.timedelta(minutes=30))
        self.assertEqual(add["days"], [{"day": "2026-10-15", "connections": 7, "questions": 500, "bytes": 1000}])
        add, _ = gu.mysql_step(dict(my2, questions=40, uptime_s=10, bytes_in=1, bytes_out=1), st, NOW + dt.timedelta(minutes=60))
        self.assertEqual(add["days"][0]["questions"], 500 + 37)                                       # redémarrage

    def test_script_reprise(self):
        sh = gu.driver_script(["105", "101"])
        self.assertIn('DONE=" 101 105 "', sh)
        self.assertIn("rrd day week month year", sh.replace("for tf in day week month year", "rrd day week month year"))
        if shutil.which("bash"):
            self.assertEqual(subprocess.run(["bash", "-n"], input=sh, capture_output=True, text=True).returncode, 0)

    def test_build_coupe_hors_reprise(self):
        txt = "## os\nDebian\n## web\n## days\nM deep 0\nW 20261001 5 50 0 0 1 0\nW 20261015 3 30 0 0 1 0\n## login\n" + LAST + "\n## end\n"
        g = {"vmid": 101, "type": "lxc", "name": "web", "status": "running", "sections": {"exec": txt}}
        rows, _ = gu.build("pve-a", [g], {}, NOW, full=False)
        self.assertEqual([d["day"] for d in rows[0]["days"]["web"]], ["2026-10-15"])
        self.assertEqual(rows[0]["days"]["rrd_weeks"], [])
        g["sections"]["exec"] = txt.replace("M deep 0", "M deep 1")
        rows, _ = gu.build("pve-a", [g], {}, NOW, full=False)
        self.assertTrue(rows[0]["days"]["deep"])
        self.assertEqual(len(rows[0]["days"]["web"]), 2)                                               # reprise : tout
        self.assertEqual(len(rows[0]["days"]["login"]), 3)


if __name__ == "__main__":
    unittest.main()


class Interne777(unittest.TestCase):
    """#777 : activité interne -- SSH / sudo / postfix (auth.log, mail.log, .gz en reprise), fichiers de données par jour,
    journaux récents ; le script de l'invité est exécuté pour de vrai sur des fichiers factices."""

    def setUp(self):
        if not shutil.which("awk") or not shutil.which("sh") or not shutil.which("find"):
            self.skipTest("outils absents")
        import gzip
        self.d = tempfile.mkdtemp()
        lg, data = os.path.join(self.d, "log"), os.path.join(self.d, "home", "alice", "docs")
        os.makedirs(lg); os.makedirs(data); os.makedirs(os.path.join(self.d, "home", "alice", ".cache"))
        with open(os.path.join(lg, "auth.log"), "w") as fh:
            fh.write("Oct 14 08:00:01 ct sshd[100]: Accepted publickey for alice from 198.51.100.7 port 5000 ssh2: ED25519 SHA256:x\n"
                     "Oct 15 09:30:00 ct sshd[101]: Accepted password for bob from 198.51.100.8 port 5001 ssh2\n"
                     "Oct 15 09:31:00 ct sshd[102]: Accepted password for bob from 198.51.100.8 port 5002 ssh2\n"
                     "Oct 15 09:35:00 ct sudo:   bob : TTY=pts/0 ; PWD=/root ; USER=root ; COMMAND=/usr/bin/apt update\n"
                     "Oct 15 10:00:00 ct sshd[103]: Failed password for root from 203.0.113.9 port 22 ssh2\n")
        with gzip.open(os.path.join(lg, "auth.log.3.gz"), "wt") as fh:
            fh.write("Mar  2 07:00:00 ct sshd[90]: Accepted publickey for alice from 198.51.100.7 port 1 ssh2\n")
        with open(os.path.join(lg, "mail.log"), "w") as fh:
            fh.write("2026-10-15T11:00:00.123456+02:00 ct postfix/smtp[200]: 4AB: to=<x@example.org>, relay=mx.example.org, status=sent (250 ok)\n"
                     "2026-10-15T11:05:00.000000+02:00 ct postfix/smtp[201]: 4AC: to=<y@example.org>, status=deferred (timeout)\n")
        for i, age in enumerate((0, 0, 2)):
            f = os.path.join(data, "f%d.txt" % i)
            open(f, "w").close()
            t = time.time() - age * 86400
            os.utime(f, (t, t))
        open(os.path.join(self.d, "home", "alice", ".cache", "c.bin"), "w").close()   # cache : ignoré

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_guest(self, deep):
        script = gu.GUEST_SH.replace("/var/log/apache2", "/nonexistent").replace("/var/log/nginx", "/nonexistent").replace("/var/log/httpd", "/nonexistent") \
            .replace("command -v mysql", "command -v mysql_absent_pour_le_test")
        env = dict(os.environ, SI_DEEP="1" if deep else "0", SI_LOG=os.path.join(self.d, "log"), SI_DATA=os.path.join(self.d, "home"))
        out = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=60, env=env).stdout
        parts = gu.parse_guest(out)
        self.assertIn("end", parts)
        return gu.parse_internal(parts["internal"], dt.datetime(2026, 10, 15, 12, 0))

    def test_interne(self):
        res, days = self.run_guest(False)
        self.assertEqual(res["ssh_last"], {"at": "2026-10-15T09:31:00", "user": "bob", "from": "198.51.100.8"})
        self.assertEqual([(d["day"], d["logins"], d["users"]) for d in days["ssh"]], [("2026-10-14", 1, 1), ("2026-10-15", 2, 1)])
        self.assertEqual(days["sudo"], [{"day": "2026-10-15", "cmds": 1}]); self.assertEqual(res["sudo_last"], "2026-10-15T09:35:00")
        self.assertEqual(days["mail"], [{"day": "2026-10-15", "sent": 1}])   # « deferred » non compté
        self.assertEqual(sum(d["files"] for d in days["files"]), 3)           # le cache est ignoré
        self.assertEqual(res["files_last"]["dir"], os.path.join(self.d, "home", "alice"))
        self.assertTrue(any(l["path"].endswith("auth.log") for l in res["logs"]))
        self.assertNotIn("2026-03-02", [d["day"] for d in days["ssh"]])      # le .gz n'est lu qu'en reprise

    def test_reprise(self):
        _res, days = self.run_guest(True)
        self.assertIn("2026-03-02", [d["day"] for d in days["ssh"]])

    def test_lecture(self):
        res, days = gu.parse_internal("S 2026-10-15 3 2\nSL 2026-10-15 09:00:00 alice 192.0.2.1\nC 443 12 5\nC 22 1 1\nT apache2 01:02:03\nM x\n", dt.datetime(2026, 10, 15))
        self.assertEqual((res["conns"][0]["port"], res["top"][0]["comm"], days["ssh"][0]["logins"]), (443, "apache2", 3))
        self.assertEqual(gu.parse_internal("", dt.datetime(2026, 10, 15)), (None, {"ssh": [], "sudo": [], "mail": [], "files": []}))


class Pilote777(unittest.TestCase):
    """#777 : le pilote du nœud, exécuté pour de vrai avec de faux pct / pvesh, transmet bien le script à l'invité
    (régression vue sur PVE 5.4 / bash 4.4 : « sh: 0: -c requires an argument », script de l'invité vide)."""

    def test_pilote_reel(self):
        if not shutil.which("bash"):
            self.skipTest("bash absent")
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "pct"), "w") as fh:
            fh.write('#!/bin/sh\nif [ "$1" = list ]; then echo "VMID Status Lock Name"; echo "103 running ct103"; exit 0; fi\n'
                     'if [ "$1" = exec ]; then shift 3; exec "$@"; fi\n')
        with open(os.path.join(d, "pvesh"), "w") as fh:
            fh.write("#!/bin/sh\necho '[]'\n")
        for f in ("pct", "pvesh"):
            os.chmod(os.path.join(d, f), 0o755)
        env = dict(os.environ, PATH=d + ":" + os.environ["PATH"])
        out = subprocess.run(["bash", "-s"], input=gu.driver_script(), capture_output=True, text=True, timeout=120, env=env).stdout
        node, guests, done = gu.parse_driver(out)
        self.assertTrue(done)
        self.assertEqual([g["vmid"] for g in guests], [103])
        parts = gu.parse_guest(guests[0]["sections"]["exec"])
        self.assertIn("end", parts, guests[0]["sections"]["exec"][-300:])
        self.assertIn("internal", parts)


class Connexions777(unittest.TestCase):
    def test_ss_ancien_et_recent(self):
        """ss d'iproute2 2014 (Debian 9) : pas d'option -H, l'aide sortait sur la sortie standard (« C 0 34 21 »)."""
        if not shutil.which("bash"):
            self.skipTest("bash absent")
        s = gu.GUEST_SH
        part = s[s.index("if command -v ss"):s.index("ps -eo comm=")]
        fake = ("Recv-Q Send-Q Local Address:Port Peer Address:Port\n0 0 192.0.2.5:443 198.51.100.7:51000\n0 0 192.0.2.5:443 198.51.100.8:51001\n"
                "0 0 [::ffff:192.0.2.5]:22 [::ffff:198.51.100.7]:40000\n0 0 192.0.2.5:45000 192.0.2.9:3306\n0 0 127.0.0.1:3306 127.0.0.1:50000\nUsage: ss [ OPTIONS ]\n")
        out = subprocess.run(["bash", "-c", "ss() { printf '%s' \"$FAKE\"; }\n" + part], env={"FAKE": fake, "PATH": os.environ["PATH"]},
                             capture_output=True, text=True).stdout
        res, _d = gu.parse_internal(out, dt.datetime(2026, 10, 17))
        self.assertEqual(res["conns"], [{"port": 443, "n": 2, "peers": 2}, {"port": 22, "n": 1, "peers": 1}])


class HorsLigne777(unittest.TestCase):
    """#777 : CT arrêté analysé une fois hors ligne (pct mount / unmount), journaux et wtmp lus sur la racine montée."""

    def test_ct_arrete(self):
        if not shutil.which("bash"):
            self.skipTest("bash absent")
        d = tempfile.mkdtemp()
        root = os.path.join(d, "lxc", "113", "rootfs")
        os.makedirs(os.path.join(root, "var", "log")); os.makedirs(os.path.join(root, "etc"))
        open(os.path.join(root, "etc", "os-release"), "w").write('PRETTY_NAME="Debian GNU/Linux 8 (jessie)"\n')
        open(os.path.join(root, "var", "log", "auth.log"), "w").write("Mar  2 07:00:00 ct sshd[90]: Accepted publickey for alice from 198.51.100.7 port 1 ssh2\n")
        log = os.path.join(d, "pct.log")
        with open(os.path.join(d, "pct"), "w") as fh:
            fh.write('#!/bin/sh\necho "$@" >> %s\nif [ "$1" = list ]; then echo "VMID Status Lock Name"; echo "113 stopped vieux"; fi\nexit 0\n' % log)
        with open(os.path.join(d, "pvesh"), "w") as fh:
            fh.write("#!/bin/sh\necho '[]'\n")
        for f in ("pct", "pvesh"):
            os.chmod(os.path.join(d, f), 0o755)
        env = dict(os.environ, PATH=d + ":" + os.environ["PATH"], SI_LXC_ROOT=os.path.join(d, "lxc"), SI_MOUNT_MARK=os.path.join(d, "mk"))
        out = subprocess.run(["bash", "-s"], input=gu.driver_script(), capture_output=True, text=True, timeout=120, env=env).stdout
        _n, guests, done = gu.parse_driver(out)
        self.assertTrue(done)
        rows, _st = gu.build("pve-a", guests, {}, dt.datetime(2026, 10, 17))
        r = rows[0]
        self.assertTrue(r["collected"]); self.assertTrue(r["offline"]); self.assertEqual(r["os"], "Debian GNU/Linux 8 (jessie)")
        self.assertTrue(r["days"]["deep"])
        self.assertIn("2026-03-02", [x["day"] for x in r["days"]["ssh"]])
        calls = open(log).read()
        self.assertIn("mount 113", calls); self.assertIn("unmount 113", calls)
        self.assertFalse([f for f in os.listdir(d) if f.startswith("mk.")])   # marque retirée
        out2 = subprocess.run(["bash", "-s"], input=gu.driver_script(done=[113]), capture_output=True, text=True, timeout=60, env=env).stdout
        self.assertNotIn("## offline", out2)   # une seule fois


class VmArretee777(unittest.TestCase):
    """#777 : VM arrêtée lue une fois en tâche de fond (faux qm / pvesm / systemd-run exécuté sur place), Windows jamais."""

    def setUp(self):
        if not shutil.which("bash"):
            self.skipTest("bash absent")
        self.d = tempfile.mkdtemp()
        d = self.d
        open(os.path.join(d, "disk.raw"), "wb").write(b"\0" * 4096)
        self.log = os.path.join(d, "calls.log")
        self.ostype = os.path.join(d, "ostype")
        open(self.ostype, "w").write("l26")
        fakes = {
            "qm": '#!/bin/sh\necho "qm $@" >> %(log)s\ncase "$1" in list) echo "VMID NAME STATUS"; echo "120 vieille stopped";; status) echo "status: stopped";;\n'
                  '  config) echo "ostype: $(cat %(os)s)"; echo "scsi0: local:120/vm-120-disk-0.raw,size=1G"; echo "ide2: none,media=cdrom";; esac\nexit 0\n',
            "pvesm": '#!/bin/sh\necho %(d)s/disk.raw\n',
            "pct": "#!/bin/sh\nexit 0\n",
            "pvesh": "#!/bin/sh\necho '[]'\n",
            "losetup": '#!/bin/sh\necho "losetup $@" >> %(log)s\nexit 1\n',
            "systemctl": "#!/bin/sh\nexit 0\n",
            "systemd-run": '#!/bin/sh\necho "systemd-run $@" >> %(log)s\nwhile [ $# -gt 0 ]; do case "$1" in --setenv=*) export "${1#--setenv=}";; /bin/bash) shift; exec /bin/bash "$@";; esac; shift; done\n',
        }
        for n, body in fakes.items():
            with open(os.path.join(d, n), "w") as fh:
                fh.write(body % {"log": self.log, "os": self.ostype, "d": d})
            os.chmod(os.path.join(d, n), 0o755)
        self.env = dict(os.environ, PATH=d + ":" + os.environ["PATH"], SI_VMREAD_DIR=os.path.join(d, "vr"), SI_MOUNT_MARK=os.path.join(d, "mk"))

    def drive(self):
        out = subprocess.run(["bash", "-s"], input=gu.driver_script(), capture_output=True, text=True, timeout=120, env=self.env).stdout
        _n, guests, done = gu.parse_driver(out)
        self.assertTrue(done)
        return out, gu.build("pve-a", guests, {}, dt.datetime(2026, 10, 17))[0][0]

    def test_une_seule_lecture(self):
        out1, _r = self.drive()
        self.assertIn("@@info VM 120 : lecture hors ligne lancée", out1)
        calls = open(self.log).read()
        self.assertIn("qm set 120 --lock backup", calls); self.assertIn("qm unlock 120", calls); self.assertIn("losetup -r -P -f --show", calls)
        self.assertTrue(os.path.exists(os.path.join(self.d, "vr", "120.sig")))
        self.assertFalse(os.path.exists(os.path.join(self.d, "vr", "mounted.120")))   # tout défait
        out2, r = self.drive()
        self.assertNotIn("lecture hors ligne lancée", out2)                           # lue : pas de nouvelle lecture
        self.assertTrue(r["offline"]); self.assertIn("aucun système Linux lisible", r["error"])
        open(os.path.join(self.d, "disk.raw"), "ab").write(b"x")                       # la VM a tourné : disque modifié
        out3, _r = self.drive()
        self.assertIn("lecture hors ligne lancée", out3)

    def test_windows_jamais(self):
        open(self.ostype, "w").write("win10")
        self.drive()
        calls = open(self.log).read()
        self.assertNotIn("--lock", calls); self.assertNotIn("losetup", calls)
        _o, r = self.drive()
        self.assertIn("Windows : jamais lue", r["error"])
