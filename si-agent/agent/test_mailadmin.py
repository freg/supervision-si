# -*- coding: utf-8 -*-
"""Tests #752 : exploitation du serveur de messagerie -- file, échecs de distribution, listes, réglages (valeurs fictives,
sorties postqueue / postconf / journal au format réel Postfix 3)."""
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import mailadmin as ma  # noqa: E402
from si_agent import mailctl as mc  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, 0).timestamp()
PQ = "\n".join(json.dumps(o) for o in [
    {"queue_name": "deferred", "queue_id": "4B2C61A0F2", "arrival_time": int(NOW - 7200), "message_size": 2048, "sender": "alice@exemple.fr",
     "recipients": [{"address": "bob@mail.exemple.net", "delay_reason": "connect to mx.exemple.net[203.0.113.7]:25: Connection timed out"}]},
    {"queue_name": "deferred", "queue_id": "5C3D72B1A3", "arrival_time": int(NOW - 600), "message_size": 1024, "sender": "carol@exemple.fr",
     "recipients": [{"address": "dave@mail.exemple.net", "delay_reason": "connect to mx.exemple.net[203.0.113.9]:25: Connection timed out"}]},
    {"queue_name": "active", "queue_id": "6D4E83C2B4", "arrival_time": int(NOW - 5), "message_size": 512, "sender": "", "recipients": [{"address": "eve@exemple.org"}]},
]) + "\n"
LOG = """Oct 14 10:00:01 mx postfix/smtp[100]: 4B2C61A0F2: to=<bob@mail.exemple.net>, relay=none, delay=3600, dsn=4.4.1, status=deferred (connect to mx.exemple.net[203.0.113.7]:25: Connection timed out)
Oct 14 10:30:01 mx postfix/smtp[101]: 5C3D72B1A3: to=<dave@mail.exemple.net>, relay=none, delay=60, dsn=4.4.1, status=deferred (connect to mx.exemple.net[203.0.113.9]:25: Connection timed out)
Oct 14 11:00:00 mx postfix/smtp[102]: 7E5F94D3C5: to=<x@grand.exemple>, relay=mx.grand.exemple[198.51.100.4]:25, delay=1, dsn=5.7.1, status=bounced (host mx.grand.exemple[198.51.100.4] said: 550 5.7.1 Service unavailable; client [192.0.2.10] blocked using Spamhaus (in reply to RCPT TO command))
Oct 14 11:10:00 mx postfix/smtp[103]: 8F6A05E4D6: to=<y@grand.exemple>, relay=mx.grand.exemple[198.51.100.4]:25, delay=1, dsn=5.1.1, status=bounced (host mx.grand.exemple[198.51.100.4] said: 550 5.1.1 User unknown (in reply to RCPT TO command))
Oct 13 08:00:00 mx postfix/smtp[104]: 9A7B16F5E7: to=<z@vieux.exemple>, relay=none, dsn=4.4.1, status=deferred (too old)
"""
POSTCONF = """smtpd_recipient_restrictions = permit_mynetworks, check_sender_access hash:%(d)s/sender_access, reject_unauth_destination, reject_rbl_client zen.spamhaus.org, check_client_access cidr:%(d)s/client.cidr
smtpd_client_restrictions = check_client_access pcre:%(d)s/client.pcre
postscreen_access_list = permit_mynetworks, cidr:%(d)s/postscreen_access.cidr
postscreen_dnsbl_sites = zen.spamhaus.org*3 b.barracudacentral.org*2
postscreen_dnsbl_action = enforce
postscreen_dnsbl_threshold = 3
"""


class Runner:
    def __init__(self, outs=None, fail=()):
        self.calls, self.outs, self.fail = [], outs or {}, fail

    def __call__(self, argv, timeout=120, stdin=None):
        self.calls.append((argv, stdin))
        key = " ".join(argv[:2])
        if any(" ".join(argv).startswith(f) for f in self.fail):
            return 1, "", "fatal: erreur simulée"
        return 0, self.outs.get(key, self.outs.get(argv[0], "")), ""


class QueueTest(unittest.TestCase):
    def test_parse_and_summary(self):
        items = ma.parse_postqueue_json(PQ + "pas du json\n")
        self.assertEqual(len(items), 3)
        s = ma.queue_summary(items, NOW)
        self.assertEqual(s["by_queue"], {"deferred": 2, "active": 1}); self.assertEqual(s["oldest_age_s"], 7200)
        self.assertEqual(s["domains"][0]["domain"], "mail.exemple.net"); self.assertEqual(s["domains"][0]["messages"], 2)
        self.assertEqual(len(s["domains"][0]["reasons"]), 1)                       # IP différentes -> même motif
        self.assertIn("[ip]", s["reasons"][0]["reason"])

    def test_queue_argv(self):
        self.assertEqual(ma.queue_argv("flush", [])[0], [["postqueue", "-f"]])
        self.assertEqual(ma.queue_argv("requeue", ["ALL deferred"])[0], [["postsuper", "-r", "ALL", "deferred"]])
        self.assertEqual(ma.queue_argv("delete", ["4B2C61A0F2"])[0], [["postsuper", "-d", "-"]])
        self.assertIn("invalides", ma.queue_argv("delete", ["ALL"])[1])
        self.assertIn("invalides", ma.queue_argv("hold", ["x; rm"])[1])
        self.assertIn("op", ma.queue_argv("purge", ["4B2C61A0F2"])[1])
        self.assertEqual(ma.queue_argv("deliver", ["4B2C61A0F2"])[0], [["postqueue", "-i", "4B2C61A0F2"]])

    def test_run_queue(self):
        r = Runner({"postqueue -j": PQ})
        res = ma.run_admin("queue_list", {"domain": "mail.exemple.net"}, NOW, r)
        self.assertEqual(res["total"], 2); self.assertEqual(res["summary"]["total"], 3)
        res = ma.run_admin("queue_action", {"op": "delete", "ids": ["4B2C61A0F2", "5C3D72B1A3"]}, NOW, r)
        self.assertTrue(res["ok"]); self.assertEqual(r.calls[-1], (["postsuper", "-d", "-"], b"4B2C61A0F2\n5C3D72B1A3\n"))
        self.assertFalse(ma.run_admin("queue_action", {"op": "delete", "ids": ["4B2C61A0F2"]}, NOW, Runner(fail=("postsuper",)))["ok"])

    def test_motif_obligatoire(self):
        with tempfile.TemporaryDirectory() as d:
            res = mc.run_action({"action": "queue_action", "op": "flush"}, now=NOW, runner=Runner(), audit_path=os.path.join(d, "a.log"))
            self.assertIn("motif", res["error"])
            res = mc.run_action({"action": "queue_action", "op": "flush", "reason": "relance après panne DNS"}, now=NOW, runner=Runner(), audit_path=os.path.join(d, "a.log"))
            self.assertTrue(res["ok"], res)


class FailuresTest(unittest.TestCase):
    def test_groups(self):
        r = ma.delivery_failures(LOG.splitlines(), NOW, 24, mc.parse_time)
        self.assertEqual((r["deferred"], r["bounced"]), (2, 2))                      # la ligne du 13/10 08:00 est hors période
        first = r["groups"][0]
        self.assertEqual(first["status"], "bounced")
        kinds = {g["dsn"]: g["kind"] for g in r["groups"]}
        self.assertEqual(kinds["5.7.1"], "réputation / liste noire"); self.assertEqual(kinds["5.1.1"], "boîte inexistante")
        self.assertEqual(kinds["4.4.1"], "serveur injoignable / DNS")
        deferred = [g for g in r["groups"] if g["status"] == "deferred"][0]
        self.assertEqual(deferred["count"], 2); self.assertEqual(deferred["domain"], "mail.exemple.net")

    def test_via_mailctl(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "mail.log")
            with open(log, "w") as fh:
                fh.write(LOG)
            res = mc.run_action({"action": "delivery_failures", "hours": 24}, now=NOW, runner=Runner(), log_path=log, audit_path=os.path.join(d, "a.log"))
            self.assertTrue(res["ok"], res); self.assertEqual(res["bounced"], 2)


class ListsTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "sender_access"), "w") as fh:
            fh.write("# expéditeurs\nami@exemple.fr OK\n@spam.exemple REJECT pas de spam\n")
        with open(os.path.join(self.d, "client.cidr"), "w") as fh:
            fh.write("192.0.2.0/24 OK\n")
        with open(os.path.join(self.d, "postscreen_access.cidr"), "w") as fh:
            fh.write("198.51.100.0/24 reject\n")
        self.pg = os.path.join(self.d, "whitelist_clients.local")
        with open(self.pg, "w") as fh:
            fh.write("# local\nexemple.org\n")
        self.r = Runner({"postconf": POSTCONF % {"d": self.d}})

    def test_discover_and_list(self):
        disc = ma.discover(ma.parse_postconf(POSTCONF % {"d": self.d}))
        self.assertEqual([m["type"] for m in disc["maps"]], ["pcre", "hash", "cidr", "cidr"])
        self.assertEqual(disc["dnsbl"]["smtpd"], [{"check": "reject_rbl_client", "zone": "zen.spamhaus.org"}])
        self.assertEqual(disc["dnsbl"]["postscreen_sites"], ["zen.spamhaus.org*3", "b.barracudacentral.org*2"])
        res = ma.run_admin("lists", {}, NOW, self.r, postgrey_files=(self.pg,))
        sender = [m for m in res["maps"] if m["path"].endswith("sender_access")][0]
        self.assertEqual([(e["key"], e["list"]) for e in sender["entries"]], [("ami@exemple.fr", "blanche"), ("@spam.exemple", "noire")])
        self.assertFalse([m for m in res["maps"] if m["type"] == "pcre"][0]["editable"])
        self.assertEqual(res["postgrey"][0]["entries"][0]["key"], "exemple.org")

    def test_set_entry(self):
        t = ma.set_entry("# c\na OK\nb REJECT\n", "a", "REJECT non")
        self.assertEqual(t, "# c\na REJECT non\nb REJECT\n")
        self.assertEqual(ma.set_entry(t, "b", None), "# c\na REJECT non\n")
        self.assertEqual(ma.set_entry("", "c", "OK"), "c OK\n")

    def test_list_set(self):
        p = os.path.join(self.d, "sender_access")
        res = ma.run_admin("list_set", {"path": p, "key": "@nouveau.exemple", "value": "REJECT expéditeur indésirable"}, NOW, self.r, postgrey_files=(self.pg,))
        self.assertTrue(res["ok"], res); self.assertTrue(os.path.exists(res["backup"]))
        self.assertIn(["postmap", "hash:%s" % p], [c[0] for c in self.r.calls]); self.assertEqual(self.r.calls[-1][0], ["postfix", "reload"])
        self.assertIn("@nouveau.exemple", [e["key"] for e in res["entries"]])
        res = ma.run_admin("list_set", {"path": p, "key": "ami@exemple.fr", "remove": True}, NOW, self.r, postgrey_files=(self.pg,))
        self.assertNotIn("ami@exemple.fr", [e["key"] for e in res["entries"]])
        bad = ma.run_admin("list_set", {"path": "/etc/passwd", "key": "x", "value": "OK"}, NOW, self.r, postgrey_files=(self.pg,))
        self.assertIn("table inconnue", bad["error"])
        self.assertIn("action", ma.run_admin("list_set", {"path": p, "key": "x@y.fr", "value": "rm -rf"}, NOW, self.r, postgrey_files=(self.pg,))["error"])
        self.assertIn("cidr", ma.run_admin("list_set", {"path": os.path.join(self.d, "client.cidr"), "key": "pas-une-ip", "value": "OK"}, NOW, self.r, postgrey_files=(self.pg,))["error"])
        self.assertIn("non modifiable", ma.run_admin("list_set", {"path": os.path.join(self.d, "client.pcre"), "key": "/x/", "value": "OK"}, NOW, self.r, postgrey_files=(self.pg,))["error"])
        res = ma.run_admin("list_set", {"path": self.pg, "key": "partenaire.exemple", "value": ""}, NOW, self.r, postgrey_files=(self.pg,))
        self.assertTrue(res["ok"], res); self.assertEqual(self.r.calls[-1][0], ["systemctl", "reload", "postgrey"])
        with open(self.pg) as fh:
            self.assertIn("partenaire.exemple\n", fh.read())

    def test_list_set_rollback(self):
        p = os.path.join(self.d, "sender_access")
        with open(p) as fh:
            before = fh.read()
        r = Runner({"postconf": POSTCONF % {"d": self.d}}, fail=("postfix reload",))
        res = ma.run_admin("list_set", {"path": p, "key": "@x.exemple", "value": "OK"}, NOW, r, postgrey_files=(self.pg,))
        self.assertFalse(res["ok"]); self.assertIn("rétabli", res["error"])
        with open(p) as fh:
            self.assertEqual(fh.read(), before)


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f1, self.f2 = os.path.join(self.d, "20-debian_defaults"), os.path.join(self.d, "50-user")
        with open(self.f1, "w") as fh:
            fh.write("$sa_tag2_level_deflt = 6.31;\n$final_spam_destiny = D_BOUNCE;\n1;\n")
        with open(self.f2, "w") as fh:
            fh.write("use strict;\n$max_servers = 4;\n#------------ Do not modify anything below this line -------------\n1;  # ensure a defined return\n")
        self.pf = os.path.join(self.d, "main.cf")
        with open(self.pf, "w") as fh:
            fh.write("smtpd_proxy_timeout = 300s\n")

    def test_get(self):
        r = Runner({"postconf message_size_limit": "message_size_limit = 10240000\nsmtpd_proxy_timeout = 300s\n"})
        res = ma.run_admin("settings_get", {}, NOW, r, amavis_dirs=(self.d,))
        pf = {x["key"]: x["value"] for x in res["postfix"]}; am = {x["key"]: x for x in res["amavis"]}
        self.assertEqual(pf["smtpd_proxy_timeout"], "300s"); self.assertEqual(am["max_servers"]["value"], "4")
        self.assertEqual(am["final_spam_destiny"]["value"], "D_BOUNCE"); self.assertTrue(am["sa_tag2_level_deflt"]["file"].endswith("20-debian_defaults"))

    def test_check_and_set_amavis_var(self):
        self.assertEqual(ma.check_settings({"smtpd_proxy_timeout": "600s"}, {"sa_kill_level_deflt": "8.5"}), [])
        self.assertEqual(len(ma.check_settings({"mydestination": "x"}, {"sa_kill_level_deflt": "huit", "dangerous": 1})), 3)
        t = ma.set_amavis_var("$max_servers = 4;\n1;  # ensure\n", "sa_kill_level_deflt", "8.5")
        self.assertEqual(t, "$max_servers = 4;\n$sa_kill_level_deflt = 8.5;   # si-agent (hub)\n1;  # ensure\n")
        self.assertIn("$max_servers = 6;", ma.set_amavis_var(t, "max_servers", "6"))
        self.assertIn("$sa_spam_subject_tag = '***SPAM*** ';", ma.set_amavis_var(t, "sa_spam_subject_tag", "***SPAM*** "))

    def test_set(self):
        r = Runner({"postconf -h": self.d + "\n", "systemctl is-active": "active\n"})
        res = ma.run_admin("settings_set", {"postfix": {"smtpd_proxy_timeout": "600s"}, "amavis": {"sa_kill_level_deflt": "8.5", "max_servers": "6"}}, NOW, r, amavis_dirs=(self.d,))
        self.assertTrue(res["ok"], res)
        self.assertIn(["postconf", "-e", "smtpd_proxy_timeout=600s"], [c[0] for c in r.calls]); self.assertIn(["postfix", "check"], [c[0] for c in r.calls])
        with open(self.f2) as fh:
            t = fh.read()
        self.assertIn("$max_servers = 6;", t); self.assertIn("$sa_kill_level_deflt = 8.5;", t); self.assertTrue(t.rstrip().endswith("1;  # ensure a defined return"))

    def test_set_rollback(self):
        with open(self.f2) as fh:
            before = fh.read()
        r = Runner({"postconf -h": self.d + "\n", "systemctl is-active": "failed\n"})
        res = ma.run_admin("settings_set", {"amavis": {"max_servers": "6"}}, NOW, r, amavis_dirs=(self.d,))
        self.assertFalse(res["ok"]); self.assertIn("rétablie", res["error"])
        with open(self.f2) as fh:
            self.assertEqual(fh.read(), before)
        r = Runner({"postconf -h": self.d + "\n"}, fail=("postfix check",))
        res = ma.run_admin("settings_set", {"postfix": {"message_size_limit": "52428800"}}, NOW, r, amavis_dirs=(self.d,))
        self.assertFalse(res["ok"]); self.assertIn("main.cf rétabli", res["error"])


if __name__ == "__main__":
    unittest.main()
