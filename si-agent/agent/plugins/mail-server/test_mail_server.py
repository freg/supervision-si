"""Tests #692 : sonde « serveur de messagerie » -- lignes au format réel (Postfix 3.1 / amavisd-new, Debian 9), valeurs fictives."""
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mail_server as ms  # noqa: E402

NOW = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)


def L(minutes_ago, rest):
    t = datetime.fromtimestamp(NOW.timestamp() - minutes_ago * 60)
    return "%s %2d %s mx-alpha %s" % (t.strftime("%b"), t.day, t.strftime("%H:%M:%S"), rest)


LINES = [
    L(30, "amavis[1]: (00001-01) Passed CLEAN {RelayedInbound}, [192.0.2.10]:4000 [192.0.2.10] <alice@exemple.org> -> <bob@exemple.fr>, Message-ID: <a@b>, mail_id: AAAA, Hits: -1.2, size: 900, queued_as: 1, 1000 ms"),
    L(25, "amavis[1]: (00001-02) Blocked SPAM {DiscardedInbound,Quarantined}, [198.51.100.7]:4000 [198.51.100.7] <info@partenaire.exemple> -> <accueil@exemple.fr>,<carol@exemple.fr>, quarantine: QQQ1, Message-ID: <c@d>, mail_id: QQQ1, Hits: 4.41, size: 7000, 1500 ms"),
    L(20, "amavis[1]: (00001-03) Blocked SPAM {DiscardedInbound,Quarantined}, [203.0.113.5]:4000 [203.0.113.5] <x@spam.example> -> <accueil@exemple.fr>, quarantine: QQQ2, Message-ID: <e@f>, mail_id: QQQ2, Hits: 26.9, size: 7000, 1500 ms"),
    L(15, "amavis[2]: (00002-01) (!)ClamAV-clamd: Can't connect to UNIX socket /var/run/clamav/clamd.ctl: No such file or directory, retrying (2)"),
    L(14, "postfix/smtpd[9]: proxy-reject: END-OF-MESSAGE: 451 4.3.0 Error: queue file write error; from=<n@exemple.org> to=<d@exemple.fr>"),
    L(13, "postfix/smtpd[9]: NOQUEUE: reject: RCPT from unknown[203.0.113.9]: 550 5.1.1 <old@exemple.fr>: Recipient address rejected: unknown user; from=<s@spam.example> to=<old@exemple.fr> proto=ESMTP helo=<h>"),
    L(12, "postfix/postscreen[3]: DNSBL rank 3 for [203.0.113.9]:5555"),
    L(12, "postfix/postscreen[3]: PASS OLD [192.0.2.10]:4001"),
    L(5, "postfix/lmtp[7]: 1A2B: to=<bob@exemple.fr>, relay=mx-alpha[private/dovecot-lmtp], delay=0.1, status=sent (250 2.0.0 Saved)"),
    L(400, "amavis[1]: (00009-09) Blocked SPAM {DiscardedInbound,Quarantined}, [192.0.2.99]:1 [192.0.2.99] <vieux@exemple.org> -> <z@exemple.fr>, quarantine: OLD, mail_id: OLD, Hits: 3.1, size: 1, 1 ms"),  # hors fenêtre
    "ligne illisible",
]


class Analyse(unittest.TestCase):
    def setUp(self):
        self.s = ms.analyse(LINES, NOW.timestamp(), minutes=60, fp_below=8)

    def test_verdicts_et_faux_positifs(self):
        self.assertEqual(self.s["amavis"], {"Passed CLEAN": 1, "Blocked SPAM": 2})
        fp = self.s["false_positive_candidates"]
        self.assertEqual(len(fp), 1)
        self.assertEqual((fp[0]["from"], fp[0]["to"], fp[0]["hits"], fp[0]["quarantine"]),
                         ("info@partenaire.exemple", ["accueil@exemple.fr", "carol@exemple.fr"], 4.41, "QQQ1"))
        self.assertEqual(self.s["blocked_by_recipient"]["accueil@exemple.fr"], 2)

    def test_incidents(self):
        self.assertEqual(self.s["queue_write_errors"], 1)
        self.assertIn("Can't connect", self.s["amavis_trouble"][0])
        self.assertEqual(self.s["smtpd_rejects"], {"550 5.1.1 Recipient address rejected": 1})
        self.assertEqual(self.s["postscreen"], {"DNSBL rank": 1, "PASS OLD": 1})
        self.assertEqual(self.s["delivery"], {"sent": 1})

    def test_format_iso(self):
        t = ms.parse_time("2026-10-07T08:28:07.123456+02:00 mx-alpha postfix/smtpd[1]: connect from x", time.time())
        self.assertEqual((t[1], t[2]), ("postfix/smtpd", "connect from x"))


class Constats(unittest.TestCase):
    def full(self, **over):
        s = {"log": ms.analyse(LINES, NOW.timestamp(), 60, 8),
             "services": {"postfix": "active", "amavis": "active", "dovecot": "active", "clamav-daemon": "failed", "mysql": "inactive", "mariadb": "active"},
             "queue": {"count": 3, "oldest_seconds": 7200}, "postconf": {"dnsbl_sites": True, "dnsbl_action": "ignore"},
             "blacklist_to": [{"file": "custom.cf", "line": 55, "address": "accueil@exemple.fr"}],
             "antivirus": {"databases": ["main.cvd"], "age_days": 800, "update_refused": True}, "os": {"debian": "9.13", "eol": "2022-06"}}
        s.update(over)
        return {a["code"]: a for a in ms.alerts_from(s)}

    def test_tous_les_constats(self):
        a = self.full()
        self.assertEqual(set(a), {"queue-write-error", "amavis-trouble", "service-down", "queue-backlog", "spam-false-positive",
                                  "blacklist-to", "antivirus-outdated", "dnsbl-ignored", "os-eol"})
        self.assertIn("clamav-daemon (failed)", a["service-down"]["message"])
        self.assertNotIn("mysql", a["service-down"]["message"])        # mariadb active suffit
        self.assertIn("info@partenaire.exemple ×1", a["spam-false-positive"]["message"])
        self.assertEqual(a["queue-write-error"]["severity"], "critical")

    def test_serveur_sain(self):
        a = self.full(log=ms.analyse(LINES[:1], NOW.timestamp(), 60, 8),
                      services={"postfix": "active", "amavis": "active", "mariadb": "active"}, queue={"count": 0, "oldest_seconds": 0},
                      postconf={"dnsbl_sites": True, "dnsbl_action": "enforce"}, blacklist_to=[],
                      antivirus={"databases": [], "age_days": None, "update_refused": False}, os={"debian": "12.7", "eol": None})
        self.assertEqual(a, {})

    def test_base_absente(self):
        a = self.full(services={"postfix": "active", "mysql": "failed"})
        self.assertIn("mysql (failed)", a["service-down"]["message"])


class Retours694(unittest.TestCase):
    """#694 : retours du premier passage réel (clamd désactivé, spamd inactif, blacklist_to anti-hameçonnage)."""

    def test_domaines_locaux(self):
        self.assertEqual(ms.analyse(LINES, NOW.timestamp(), 60, 8)["local_domains"], ["exemple.fr"])

    def test_blacklist_to_etrangere_ignoree(self):
        e = [{"address": a} for a in ("bnp*@jetable.example", "*credit*@jetable.example", "*credit*@jetable.example", "Accueil@exemple.fr", "*@exemple.*")]
        self.assertEqual(ms.local_blacklist_to(e, ["exemple.fr"]), ["accueil@exemple.fr", "*@exemple.*"])
        self.assertEqual(len(ms.local_blacklist_to(e, [])), 4)          # domaines inconnus : tout, dédoublonné
        s = {"log": {"local_domains": ["exemple.fr"]}, "blacklist_to": e[:3]}
        self.assertEqual([a["code"] for a in ms.alerts_from(s)], [])

    def test_service_desactive_et_spamd(self):
        def runner(argv, timeout=20):
            st = {"postfix": ("enabled", "active"), "amavis": ("enabled", "active"), "clamav-daemon": ("disabled", "failed"),
                  "spamassassin": ("enabled", "inactive")}.get(argv[-1])
            if st is None:
                return 0, "LoadState=not-found", ""
            return 0, ("LoadState=loaded\nUnitFileState=%s\n" % st[0]) if argv[1] == "show" else st[1], ""
        ms.shutil.which = lambda b: "/bin/systemctl"
        svcs = ms.services_state(runner)
        self.assertEqual(svcs, {"postfix": "active", "amavis": "active", "clamav-daemon": "disabled", "spamassassin": "inactive"})
        s = {"services": svcs, "antivirus": {"databases": ["main.cvd"], "age_days": 900, "update_refused": True}}
        self.assertEqual(ms.alerts_from(s), [])                        # clamd désactivé : ni panne ni signatures
        s["services"] = dict(svcs, amavis="failed")
        self.assertIn("spamassassin (inactive)", ms.alerts_from(s)[0]["message"])


class Hote(unittest.TestCase):
    def test_blacklist_to_et_antivirus(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "custom.cf"), "w") as fh:
            fh.write("whitelist_from a@b\n# blacklist_to commente@exemple.fr\nblacklist_to accueil@exemple.fr\n")
        self.assertEqual(ms.blacklist_to_entries((d,)), [{"file": os.path.join(d, "custom.cf"), "line": 3, "address": "accueil@exemple.fr"}])
        db = tempfile.mkdtemp(); f = os.path.join(db, "main.cvd"); open(f, "w").close()
        os.utime(f, (time.time() - 10 * 86400,) * 2)
        log = os.path.join(db, "freshclam.log")
        with open(log, "w") as fh:
            fh.write("FreshClam received error code 403 from the ClamAV Content Delivery Network (CDN).\n")
        av = ms.antivirus_state(db_dir=db, fresh_log=log)
        self.assertEqual((av["databases"], round(av["age_days"]), av["update_refused"]), (["main.cvd"], 10, True))

    def test_file_postfix(self):
        now = 1_000_000.0
        out = '{"queue_name": "deferred", "arrival_time": 996400}\n{"queue_name": "active", "arrival_time": 999990}\n'
        q = ms.queue_state(runner=lambda argv, timeout=20: (0, out, ""), now=now)
        self.assertEqual(q, {"count": 2, "deferred": 1, "oldest_seconds": 3600})
        q = ms.queue_state(runner=lambda argv, timeout=20: (1, "", "") if "-j" in argv else (0, "-- 12 Kbytes in 4 Requests.", ""), now=now)
        self.assertEqual(q["count"], 4)

    def test_postconf(self):
        pc = ms.postconf_checks(runner=lambda argv, timeout=20: (0, "zen.exemple*3\nignore\n", "postconf: warning: master.cf: undefined parameter: mua_helo_restrictions"))
        self.assertEqual(pc, {"dnsbl_sites": True, "dnsbl_action": "ignore", "undefined_parameters": ["mua_helo_restrictions"]})

    def test_services(self):
        calls = {"postfix": ("LoadState=loaded", "active"), "amavis": ("LoadState=loaded", "active"), "clamav-daemon": ("LoadState=loaded", "failed")}

        def runner(argv, timeout=20):
            svc = argv[-1]
            if svc not in calls:
                return 0, "LoadState=not-found", ""
            return 0, calls[svc][0] if argv[1] == "show" else calls[svc][1], ""
        ms.shutil.which = lambda b: "/bin/systemctl"
        self.assertEqual(ms.services_state(runner), {"postfix": "active", "amavis": "active", "clamav-daemon": "failed"})
        self.assertEqual(ms.services_state(runner, ignore=("clamav-daemon",)), {"postfix": "active", "amavis": "active"})


class Politiques708(unittest.TestCase):
    """#708 : supprimés sans quarantaine, authentification des expéditeurs, politiques Amavis, conservation."""
    def test_journal(self):
        lines = [
            L(30, "amavis[1]: (00001-04) Blocked SPAM {DiscardedInbound}, [192.0.2.20]:4000 [192.0.2.20] <factures@fournisseur.example> -> <compta@exemple.fr>, Message-ID: <g@h>, mail_id: RRR1, Hits: 5.2, size: 900, 800 ms"),
            L(29, "amavis[1]: (00001-05) Blocked SPAM {DiscardedInbound,Quarantined}, [192.0.2.20]:4000 [192.0.2.20] <factures@fournisseur.example> -> <compta@exemple.fr>, quarantine: RRR2, Message-ID: <i@j>, mail_id: RRR2, Hits: 5.4, size: 900, 800 ms"),
            L(28, "policyd-spf[5]: prepend Received-SPF: Softfail (mailfrom) identity=mailfrom; client-ip=192.0.2.20; helo=mx; envelope-from=factures@fournisseur.example; receiver=<UNKNOWN>"),
            L(27, "amavis[1]: (00001-06) Passed CLEAN {RelayedInbound}, [192.0.2.30]:4000 [192.0.2.30] <bob@mail.partenaire.example> -> <compta@exemple.fr>, Message-ID: <k@l>, mail_id: RRR3, Hits: -0.1, size: 900, queued_as: 2, dkim_sd=s1:partenaire.example,s2:esp.example, 300 ms"),
            L(26, "policyd-spf[5]: prepend Received-SPF: Pass (mailfrom) identity=mailfrom; client-ip=192.0.2.30; envelope-from=<bob@mail.partenaire.example>; receiver=<UNKNOWN>"),
        ]
        r = ms.analyse(lines, NOW.timestamp(), 60)
        self.assertEqual(r["discarded_without_quarantine"], 1)
        a = {x["domain"]: x for x in r["sender_auth"]}
        self.assertEqual((a["fournisseur.example"]["blocked"], a["fournisseur.example"]["authenticated"], a["fournisseur.example"]["spf"]), (2, False, {"softfail": 1}))
        self.assertEqual((a["mail.partenaire.example"]["dkim_aligned"], a["mail.partenaire.example"]["spf_pass"]), (1, 1))
        self.assertEqual(ms.dkim_domains("x, dkim_sd=a:b.example, 3 ms"), ["b.example"])
        al = {x["code"] for x in ms.alerts_from({"log": r})}
        self.assertTrue({"spam-discard-silent", "sender-unauth-blocked"} <= al)

    def test_config_et_sql(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "20-debian_defaults"), "w") as fh:
            fh.write("$final_spam_destiny       = D_BOUNCE;\n$sa_kill_level_deflt = 6.31;\n")
        with open(os.path.join(d, "50-user"), "w") as fh:
            fh.write("$final_spam_destiny = D_DISCARD;\n# $sa_kill_level_deflt = 1;\n$spam_quarantine_method = undef;\n"
                     "@lookup_sql_dsn = ( ['DBI:mysql:database=amavis;host=127.0.0.1', 'amavis', 'S3cret'] );\n")
        vals, dsn = ms.amavis_config((d,))
        self.assertEqual((vals["final_spam_destiny"], vals["sa_kill_level_deflt"], vals["spam_quarantine_method"]), ("D_DISCARD", "6.31", "undef"))
        self.assertEqual((dsn["user"], dsn["database"]), ("amavis", "amavis"))
        h = lambda x: x.encode().hex().upper()
        seen = {}

        def runner(argv, timeout=20):
            seen["argv"] = argv
            seen["cnf"] = open(argv[1].split("=", 1)[1]).read()
            if "FROM users" in argv[-1]:
                return 0, "\n".join(["%s\t7\t%s\t2\t3\t%s\tN\tN" % (h("@exemple.fr"), h("Défaut"), h("spam-quarantine")),
                                     "%s\t10\t%s\t2\t3\t%s\tN\tN" % (h("bob@exemple.fr"), h("Défaut"), h("spam-quarantine")),
                                     "%s\t7\t%s\t6\t10\t\tN\tN" % (h("@autre.example"), h("Normal"))]) + "\n", ""
            return 0, "%d\t%d\t40\n" % (NOW.timestamp() - 200 * 86400, NOW.timestamp() - 3 * 86400), ""
        st = ms.amavis_state(NOW.timestamp(), runner, (d,))
        self.assertNotIn("S3cret", " ".join(seen["argv"])); self.assertIn("password=S3cret", seen["cnf"])
        g = st["policies"][0]
        self.assertEqual((g["policy"], g["kill"], g["domains"], g["mailboxes"]), ("Défaut", 3.0, ["@exemple.fr"], 1))
        self.assertEqual((st["retention"]["history_days"], st["retention"]["quarantine_days"]), (200.0, 3.0))
        s = {"log": {"local_domains": ["exemple.fr"], "window_minutes": 60}, "amavis": st, "log_retention_days": 28,
             "limits": {"kill_min": 5, "quarantine_min_days": 14, "log_min_days": 30}}
        al = {x["code"]: x["message"] for x in ms.alerts_from(s)}
        self.assertIn("3.0 (@exemple.fr + 1 boîte(s))", al["spam-threshold-low"]); self.assertNotIn("autre.example", al["spam-threshold-low"])
        self.assertIn("D_DISCARD", al["spam-discard-silent"])
        self.assertIn("3.0 jour(s)", al["quarantine-short"]); self.assertIn("28 jour(s)", al["log-retention-short"])
        self.assertIsNone(ms.amavis_state(NOW.timestamp(), runner, (tempfile.mkdtemp(),))["policies"])   # sans SQL

    def test_logrotate(self):
        d = tempfile.mkdtemp()
        conf = os.path.join(d, "logrotate.conf")
        with open(conf, "w") as fh:
            fh.write("weekly\nrotate 4\ncreate\ninclude /etc/logrotate.d\n")
        os.makedirs(os.path.join(d, "d"))
        with open(os.path.join(d, "d", "rsyslog"), "w") as fh:
            fh.write("/var/log/syslog\n{\n\trotate 7\n\tdaily\n}\n\n/var/log/mail.info\n/var/log/mail.warn\n/var/log/mail.err\n/var/log/mail.log\n/var/log/daemon.log\n{\n\trotate 4\n\tweekly\n\tcompress\n}\n")
        self.assertEqual(ms.logrotate_days("/var/log/mail.log", (os.path.join(d, "d"),), conf), 28)
        self.assertEqual(ms.logrotate_days("/var/log/syslog", (os.path.join(d, "d"),), conf), 7)
        self.assertIsNone(ms.logrotate_days("/var/log/autre.log", (os.path.join(d, "d"),), os.path.join(d, "absent")))


if __name__ == "__main__":
    unittest.main()
