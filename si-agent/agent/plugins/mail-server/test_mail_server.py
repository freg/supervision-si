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


if __name__ == "__main__":
    unittest.main()
