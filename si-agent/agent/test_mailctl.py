# -*- coding: utf-8 -*-
"""Tests #697 : commande `mail` (tuile Serveur de messagerie) -- lignes au format
réel Postfix 3.1 / amavisd-new (filtre avant file), sorties doveadm et mysql
simulées, valeurs fictives."""
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import mailctl as mc  # noqa: E402

NOW = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()


def L(min_ago, rest):
    t = datetime.fromtimestamp(NOW - min_ago * 60)
    return "%s %2d %s mx-alpha %s" % (t.strftime("%b"), t.day, t.strftime("%H:%M:%S"), rest)


LOG = [
    L(30, "postfix/postscreen[10]: CONNECT from [192.0.2.10]:4000 to [198.51.100.1]:25"),
    L(30, "postfix/postscreen[10]: PASS OLD [192.0.2.10]:4000"),
    L(30, "postfix/smtpd[11]: connect from mx.exemple.org[192.0.2.10]"),
    L(29, "amavis[20]: (00020-01) Passed CLEAN {RelayedInbound}, [192.0.2.10]:4000 [192.0.2.10] <alice@exemple.org> -> <bob@exemple.fr>,<carol@exemple.fr>, Queue-ID: 0, Message-ID: <m1@exemple.org>, mail_id: AbC123dEf_x, Hits: -1.2, size: 900, queued_as: 4A1B2C3D4E, 1000 ms"),
    L(29, "postfix/smtpd[11]: NOQUEUE: proxy-accept: END-OF-MESSAGE: 250 2.0.0 from MTA(smtp:[127.0.0.1]:10025): 250 2.0.0 Ok: queued as 4A1B2C3D4E; from=<alice@exemple.org> to=<bob@exemple.fr> proto=ESMTP helo=<mx.exemple.org>"),
    L(29, "postfix/smtpd[12]: 4A1B2C3D4E: client=localhost[127.0.0.1]"),
    L(29, "postfix/cleanup[13]: 4A1B2C3D4E: message-id=<m1@exemple.org>"),
    L(29, "postfix/qmgr[14]: 4A1B2C3D4E: from=<alice@exemple.org>, size=1200, nrcpt=2 (queue active)"),
    L(29, "postfix/lmtp[15]: 4A1B2C3D4E: to=<bob@exemple.fr>, relay=mx-alpha[private/dovecot-lmtp], delay=0.1, status=sent (250 2.0.0 Saved)"),
    L(29, "postfix/lmtp[15]: 4A1B2C3D4E: to=<carol@exemple.fr>, relay=mx-alpha[private/dovecot-lmtp], delay=0.1, status=sent (250 2.0.0 Saved)"),
    L(29, "postfix/qmgr[14]: 4A1B2C3D4E: removed"),
    L(20, "amavis[21]: (00021-01) Blocked SPAM {DiscardedInbound,Quarantined}, [203.0.113.5]:4000 [203.0.113.5] <promo@spam.example> -> <bob@exemple.fr>, quarantine: Zz9yX8wV7u, Message-ID: <s@spam.example>, mail_id: Zz9yX8wV7u, Hits: 12.3, size: 7000, 1500 ms"),
    L(15, "postfix/smtpd[16]: NOQUEUE: reject: RCPT from unknown[203.0.113.9]: 550 5.1.1 <old@exemple.fr>: Recipient address rejected: unknown user; from=<x@spam.example> to=<old@exemple.fr> proto=ESMTP helo=<h>"),
    L(10, "dovecot: imap-login: Login: user=<bob@exemple.fr>, method=PLAIN, rip=192.0.2.50"),
    L(9, "dovecot: auth-worker(17): sql(eve@exemple.fr,192.0.2.66): Password mismatch"),
    L(500, "postfix/smtpd[1]: connect from vieux[192.0.2.1]"),            # hors fenêtre d'une heure
    "ligne illisible",
]


class Journal(unittest.TestCase):
    def test_arbre(self):
        t = mc.log_tree(LOG, NOW, minutes=60)
        tree = t["tree"]
        self.assertEqual(tree["amavis"]["Passed CLEAN"]["count"], 1)
        self.assertEqual(tree["amavis"]["Blocked SPAM"]["count"], 1)
        self.assertEqual(tree["smtpd"]["refus"]["count"], 1)
        self.assertEqual(tree["smtpd"]["accepté par le filtre"]["count"], 1)
        self.assertEqual(tree["remise (lmtp)"]["status=sent"]["count"], 2)
        self.assertEqual(tree["postscreen"]["PASS OLD"]["count"], 1)
        self.assertEqual(tree["dovecot"]["connexions"]["count"], 1)
        self.assertEqual(t["lines"], 15)                                     # 500 min et ligne illisible écartées
        leaf = tree["qmgr"]["retirés de la file"]["lines"][0]
        self.assertIn("removed", leaf["line"]); self.assertIsInstance(leaf["at"], int)

    def test_borne_globale(self):
        many = [L(1, "postfix/smtpd[1]: connect from h%d[192.0.2.1]" % i) for i in range(500)]
        t = mc.log_tree(many, NOW, 60, per_leaf=1000, total=100)
        self.assertLessEqual(len(t["tree"]["smtpd"]["connexions"]["lines"]), 100)
        self.assertEqual(t["tree"]["smtpd"]["connexions"]["count"], 500)

    def test_messages(self):
        items = mc.log_messages(LOG, NOW, hours=1)
        by = {m["key"]: m for m in items}
        m = by["4A1B2C3D4E"]
        self.assertEqual((m["from"], m["message_id"], m["size"]), ("alice@exemple.org", "m1@exemple.org", 1200))
        self.assertEqual(sorted(m["to"]), ["bob@exemple.fr", "carol@exemple.fr"])
        self.assertEqual(m["amavis"]["verdict"], "Passed CLEAN"); self.assertEqual(m["amavis"]["mail_id"], "AbC123dEf_x")
        self.assertEqual(m["states"].count("sent"), 2); self.assertIn("retiré de la file", m["states"])
        self.assertGreaterEqual(len(m["lines"]), 8)
        q = by["amavis-Zz9yX8wV7u"]
        self.assertEqual((q["amavis"]["quarantine"], q["amavis"]["hits"]), ("Zz9yX8wV7u", 12.3))
        self.assertIn("bloqué (SPAM)", q["states"])
        r = by["noqueue-1"]
        self.assertEqual((r["from"], r["to"]), ("x@spam.example", ["old@exemple.fr"])); self.assertIn("refusé 550 5.1.1", r["states"])

    def test_filtres(self):
        items = mc.log_messages(LOG, NOW, hours=1)
        f = lambda **p: [m["key"] for m in mc.filter_messages(items, p)]
        self.assertEqual(f(**{"from": "*@spam.example"}), ["noqueue-1", "amavis-Zz9yX8wV7u"])
        self.assertEqual(f(to="carol"), ["4A1B2C3D4E"])
        self.assertEqual(f(to="*@EXEMPLE.FR", status="refus*"), ["noqueue-1"])
        self.assertEqual(f(queue_id="AbC123dEf_x"), ["4A1B2C3D4E"])
        self.assertEqual(f(message_id="s@spam*"), ["amavis-Zz9yX8wV7u"])
        self.assertEqual(f(status="Blocked*"), ["amavis-Zz9yX8wV7u"])


class Quarantaine(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "50-user"), "w") as fh:
            fh.write("# @storage_sql_dsn = ( ['DBI:mysql:database=faux', 'x', 'y']);\n"
                     "@lookup_sql_dsn = ( ['DBI:mysql:database=amavis;host=127.0.0.1;port=3306', 'amavis', 'S3cret'] );\n"
                     "@storage_sql_dsn = @lookup_sql_dsn;\n")

    def test_dsn(self):
        d = mc.amavis_dsn((self.d,))
        self.assertEqual((d["driver"], d["database"], d["host"], d["port"], d["user"], d["password"]),
                         ("mysql", "amavis", "127.0.0.1", "3306", "amavis", "S3cret"))

    def test_sql_sans_injection(self):
        sql = mc.quarantine_sql({"from": "a'; DROP TABLE msgs; --", "to": "*@exemple.fr", "subject": "fac?ure", "content": "S", "days": 7}, NOW)
        self.assertNotIn("DROP", sql); self.assertNotIn("'; ", sql)
        self.assertIn("X'%s'" % "%@exemple.fr".encode().hex(), sql)          # joker * -> %
        self.assertIn("X'%s'" % "fac_ure".encode().hex(), sql)               # joker ? -> _
        self.assertIn("X'%s'" % "%a''; DROP TABLE msgs; --%".replace("''", "'").encode().hex(), sql)  # sans joker : contient
        self.assertIn("m.quar_type = 'Q'", sql)
        self.assertEqual(mc.like_pattern("100%_net"), "%100\\%\\_net%")

    def test_recherche_et_mot_de_passe(self):
        seen = {}

        def runner(argv, timeout=120, stdin=None):
            cnf = argv[1].split("=", 1)[1]
            seen["cnf"] = open(cnf).read(); seen["mode"] = oct(os.stat(cnf).st_mode & 0o777); seen["argv"] = argv; seen["path"] = cnf
            h = lambda s: s.encode().hex().upper()
            row = [h("Zz9yX8wV7u"), str(int(NOW - 600)), h("S"), h("Q"), "12.3", "7000", h("promo@spam.example"),
                   h("Offre spéciale"), h("bob@exemple.fr,carol@exemple.fr"), h("203.0.113.5"), h("<s@spam.example>")]
            return 0, "\t".join(row) + "\n", ""
        r = mc.run_action({"action": "quarantine_search", "to": "bob"}, NOW, runner, dsn_dirs=(self.d,), audit_path=os.path.join(self.d, "a.log"))
        self.assertTrue(r["ok"], r)
        q = r["rows"][0]
        self.assertEqual((q["mail_id"], q["subject"], q["to"], q["content_label"], q["score"], q["message_id"]),
                         ("Zz9yX8wV7u", "Offre spéciale", ["bob@exemple.fr", "carol@exemple.fr"], "spam", 12.3, "s@spam.example"))
        self.assertIn("password=S3cret", seen["cnf"]); self.assertEqual(seen["mode"], "0o600")
        self.assertNotIn("S3cret", " ".join(seen["argv"])); self.assertFalse(os.path.exists(seen["path"]))
        self.assertNotIn("S3cret", json.dumps(r))

    def test_source_et_liberation(self):
        audit = os.path.join(self.d, "audit.log")
        raw = b"From: promo@spam.example\r\nSubject: =?utf-8?B?T2ZmcmU=?=\r\n\r\nCorps\r\n"

        def runner(argv, timeout=120, stdin=None):
            if argv[0] == "mysql":
                sql = argv[-1]
                if "quarantine" in sql:
                    return 0, raw[:20].hex().upper() + "\n" + raw[20:].hex().upper() + "\n", ""
                return 0, b"s3cr3tId".hex().upper() + "\n", ""
            self.assertEqual(argv[:3], ["amavisd-release", "Zz9yX8wV7u", "s3cr3tId"])
            return 0, "250 2.0.0 Ok, id=rel-Zz9yX8wV7u, from MTA([127.0.0.1]:10025): 250 2.0.0 Ok: queued as 9F8E7D6C5B\n", ""
        kw = dict(runner=runner, dsn_dirs=(self.d,), audit_path=audit)
        self.assertFalse(mc.run_action({"action": "quarantine_get", "mail_id": "Zz9yX8wV7u"}, NOW, **kw)["ok"])     # sans motif
        g = mc.run_action({"action": "quarantine_get", "mail_id": "Zz9yX8wV7u", "reason": "réclamation client", "actor": "admin"}, NOW, **kw)
        self.assertEqual(g["raw"], raw.decode()); self.assertFalse(g["truncated"])
        self.assertFalse(mc.run_action({"action": "quarantine_get", "mail_id": "x' OR 1=1", "reason": "test test"}, NOW, **kw)["ok"])
        rel = mc.run_action({"action": "quarantine_release", "mail_id": "Zz9yX8wV7u", "reason": "faux positif"}, NOW, **kw)
        self.assertTrue(rel["ok"], rel); self.assertNotIn("s3cr3tId", json.dumps(rel))
        with open(audit) as fh:
            lines = [json.loads(l) for l in fh]
        self.assertEqual([l["action"] for l in lines], ["quarantine_get"] * 3 + ["quarantine_release"])
        self.assertTrue(lines[0]["refused"])                                 # tentative sans motif journalisée
        self.assertEqual((lines[1]["actor"], lines[1]["reason"]), ("admin", "réclamation client"))
        self.assertNotIn("reason", lines[1]["params"])


PAGER = ("username: bob@exemple.fr\nmailbox: INBOX\nmailbox-guid: 0123456789abcdef0123456789abcdef\nuid: 42\n"
         "date.received: 2026-10-07 10:00:00\nsize.physical: 5120\nhdr.from: Alice <alice@exemple.org>\nhdr.to: bob@exemple.fr\nhdr.cc: \n"
         "hdr.subject: =?utf-8?Q?Facture_d=C3=A9cembre?=\nhdr.message-id: <m1@exemple.org>\n\f\n"
         "username: carol@exemple.fr\nmailbox: Junk\nmailbox-guid: fedcba9876543210fedcba9876543210\nuid: 7\n"
         "date.received: 2026-10-06 09:00:00\nsize.physical: 900\nhdr.from: promo@spam.example\nhdr.to: carol@exemple.fr\nhdr.cc: \n"
         "hdr.subject: Promo\nhdr.message-id: <p@spam.example>\n\f\n")


class Boites(unittest.TestCase):
    def test_recherche(self):
        calls = []

        def runner(argv, timeout=120, stdin=None):
            calls.append(argv)
            return 0, PAGER, ""
        r = mc.run_action({"action": "mailbox_search", "subject": "*décembre*", "from": "alice", "since": "2026-10-01"}, NOW, runner,
                          audit_path=os.path.join(tempfile.mkdtemp(), "a.log"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(calls[0][:5], ["doveadm", "-f", "pager", "fetch", "-A"])
        self.assertEqual(calls[0][6:], ["from", "alice", "subject", "décembre", "since", "2026-10-01"])
        self.assertEqual(len(r["rows"]), 1)
        row = r["rows"][0]
        self.assertEqual((row["user"], row["subject"], row["guid"], row["uid"], row["size"], row["message_id"]),
                         ("bob@exemple.fr", "Facture décembre", "0123456789abcdef0123456789abcdef", "42", 5120, "m1@exemple.org"))
        r = mc.run_action({"action": "mailbox_search", "user": "*@exemple.fr"}, NOW, runner, audit_path=os.path.join(tempfile.mkdtemp(), "a.log"))
        self.assertEqual(calls[1][4:6], ["-u", "*@exemple.fr"]); self.assertEqual(calls[1][7], "since")   # jamais « tout »
        self.assertEqual(r["total"], 2)

    def test_lecture(self):
        body = "Return-Path: <a@b>\nFrom: a@b\ntext: piège dans le corps\n\nBonjour\n"

        def runner(argv, timeout=120, stdin=None):
            self.assertEqual(argv[4:], ["-u", "bob@exemple.fr", "text", "mailbox-guid", "0123456789abcdef0123456789abcdef", "uid", "42"])
            return 0, "text:\n" + body + "\f\n", ""
        kw = dict(runner=runner, audit_path=os.path.join(tempfile.mkdtemp(), "a.log"))
        p = {"action": "mailbox_get", "user": "bob@exemple.fr", "guid": "0123456789abcdef0123456789abcdef", "uid": "42", "reason": "demande de l'utilisateur"}
        r = mc.run_action(p, NOW, **kw)
        self.assertTrue(r["ok"], r); self.assertEqual(r["raw"].rstrip("\n"), body.rstrip("\n"))
        self.assertFalse(mc.run_action(dict(p, user="*"), NOW, **kw)["ok"])
        self.assertFalse(mc.run_action(dict(p, reason=""), NOW, **kw)["ok"])

    def test_jokers(self):
        self.assertEqual(mc.longest_literal("*credit*agricole?"), "agricole")
        self.assertTrue(mc.match(mc.wild("BNP*@*.plus"), "bnpparibas1@mailto.plus"))
        self.assertTrue(mc.match(mc.wild("Paribas"), "bnpparibas1@mailto.plus"))
        self.assertIsNone(mc.wild("  "))

    def test_journaux_tournants(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, "mail.log")
        import gzip
        with gzip.open(p + ".2.gz", "wt") as fh:
            fh.write(L(200, "postfix/smtpd[1]: connect from a[192.0.2.1]") + "\n")
        with open(p + ".1", "w") as fh:
            fh.write(L(100, "postfix/smtpd[1]: connect from b[192.0.2.2]") + "\n")
        with open(p, "w") as fh:
            fh.write(L(1, "postfix/smtpd[1]: connect from c[192.0.2.3]") + "\n")
        lines = mc.read_logs(p, NOW - 6 * 3600, NOW)
        self.assertEqual([l.split()[-1] for l in lines], ["a[192.0.2.1]", "b[192.0.2.2]", "c[192.0.2.3]"])   # ancien -> récent

    def test_action_inconnue(self):
        self.assertFalse(mc.run_action({"action": "rm"}, NOW, audit_path=os.path.join(tempfile.mkdtemp(), "a.log"))["ok"])


class QuarantaineNiveaux(unittest.TestCase):
    """#704 : niveaux (récupérable / dépassée / historique), statistiques, libération groupée, règles wblist."""
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "50-user"), "w") as fh:
            fh.write("@lookup_sql_dsn = ( ['DBI:mysql:database=amavis;host=127.0.0.1', 'amavis', 'S3cret'] );\n@storage_sql_dsn = @lookup_sql_dsn;\n")
        self.kw = dict(dsn_dirs=(self.d,), audit_path=os.path.join(self.d, "a.log"))

    def test_niveaux(self):
        q = lambda **p: mc.quarantine_sql(p, NOW)
        self.assertIn("m.quar_type = 'Q' AND EXISTS (SELECT 1 FROM quarantine", q(level="recoverable"))
        self.assertIn("NOT EXISTS (SELECT 1 FROM quarantine qq", q(level="expired"))
        h = q(level="history", days=99999)
        self.assertNotIn("m.quar_type = 'Q'", h.split("WHERE", 1)[1]); self.assertIn("m.time_num >= %d" % int(NOW - 3650 * 86400), h)
        self.assertIn("m.quar_type = 'Q'", q()); self.assertNotIn("m.quar_type = 'Q'", q(only_quarantined=False).split("WHERE", 1)[1])   # compatibilité #697
        self.assertIn("m.content IN (X'53', X'56')", q(content="SV")); self.assertNotIn("content IN", q(content="S'; --"))
        self.assertIn("xr.rs = 'R'", q(hide_released=True))

    def test_statistiques(self):
        for by in mc.STAT_KEYS:
            sql = mc.stats_sql({"level": "history", "from": "*@banque.example"}, NOW, by)
            self.assertIn("GROUP BY k", sql); self.assertEqual("JOIN maddr r" in sql, mc.STAT_KEYS[by][1], by)
        h = lambda s: s.encode().hex().upper()

        def runner(argv, timeout=120, stdin=None):
            sql = argv[-1]
            if sql.startswith("SELECT COUNT(*), IFNULL(MIN"):
                return 0, "981\t1700000000\t120\t1750000000\t861\t981\t40\t12\n", ""
            if "SUBSTRING_INDEX" in sql and "s.email" in sql:
                return 0, "%s\t17\t5\t0\t2\t1750000000\t1760000000\t8.4\n%s\t3\t0\t1\t0\t1750000000\t1750000000\tNULL\n" % (h("phish.example"), h("")), ""
            if "IFNULL(m.content" in sql.split("FROM")[0]:
                return 0, "%s\t900\t100\t3\t4\t1\t2\t9.9\n" % h("S"), ""
            return 0, "", ""
        r = mc.run_action({"action": "quarantine_stats", "by": ["sender_domain", "content", "faux"]}, NOW, runner, **self.kw)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["overview"]["recoverable"], {"count": 120, "since": 1750000000})
        self.assertEqual((r["overview"]["expired"]["count"], r["overview"]["last24h"]["quarantined"]), (861, 12))
        self.assertEqual(sorted(r["groups"]), ["content", "sender_domain"])
        d = r["groups"]["sender_domain"][0]
        self.assertEqual((d["key"], d["count"], d["recoverable"], d["released"], d["avg_score"]), ("phish.example", 17, 5, 2, 8.4))
        self.assertIsNone(r["groups"]["sender_domain"][1]["avg_score"])
        self.assertEqual(r["groups"]["content"][0]["label"], "spam")

    def test_liberation_groupee(self):
        seen = []

        def runner(argv, timeout=120, stdin=None):
            seen.append(argv[-1] if argv[0] == "mysql" else " ".join(argv))
            if argv[0] == "mysql":
                if "secret_id" in argv[-1]:
                    return (0, b"sec".hex() + "\n", "") if "4161414161" in argv[-1] or "41616161" in argv[-1] else (0, "", "")
                return 0, "", ""
            return 0, "250 2.0.0 Ok, id=rel, from MTA: 250 2.0.0 Ok: queued as 1A2B3C4D5E\n", ""
        self.assertFalse(mc.run_action({"action": "quarantine_release", "mail_ids": ["Aaaa1111"]}, NOW, runner, **self.kw)["ok"])   # sans motif
        r = mc.run_action({"action": "quarantine_release", "mail_ids": ["AaAAa1", "Inconnu1", "x' OR 1"], "reason": "faux positifs"}, NOW, runner, **self.kw)
        self.assertTrue(r["ok"], r); self.assertEqual((r["released"], r["failed"]), (1, 2))
        self.assertIn("UPDATE msgrcpt SET rs = 'R' WHERE mail_id = X'%s'" % "AaAAa1".encode().hex(), "\n".join(seen))
        self.assertNotIn("sec", json.dumps(r).replace("secret", ""))

    def test_regles(self):
        db = {"users": {"@exemple.fr": 1, "bob@exemple.fr": 2}, "sql": []}
        h = lambda s: s.encode().hex().upper()

        def runner(argv, timeout=120, stdin=None):
            sql = argv[-1]; db["sql"].append(sql)
            if "information_schema" in sql:
                return 0, "3\n", ""
            if sql.startswith("SELECT id FROM users"):
                for e, i in db["users"].items():
                    if "X'%s'" % e.encode().hex() in sql:
                        return 0, "%d\n" % i, ""
                return 0, "", ""
            if sql.startswith("SELECT HEX(u.email)"):
                return 0, "%s\t%s\t%s\t7\t10\n" % (h("@exemple.fr"), h("factures@fournisseur.example"), h("-5")), ""
            if sql.startswith("SELECT HEX(email), priority FROM users"):
                return 0, "%s\t7\n%s\t10\n" % (h("@exemple.fr"), h("bob@exemple.fr")), ""
            return 0, "", ""
        run = lambda p: mc.run_action(dict(p, action="wblist_set"), NOW, runner, **self.kw)
        self.assertIn("motif", run({"sender": "a@b.example", "recipient": "@exemple.fr", "wb": "W"})["error"])
        self.assertIn("expéditeur invalide", run({"sender": "x'); DROP--", "recipient": "@exemple.fr", "wb": "W", "reason": "test"})["error"])
        self.assertIn("règle invalide", run({"sender": "a@b.example", "recipient": "@exemple.fr", "wb": "X; --", "reason": "test"})["error"])
        self.assertIn("absent de la table users", run({"sender": "a@b.example", "recipient": "@autre.example", "wb": "B", "reason": "test"})["error"])
        r = run({"sender": "Factures@Fournisseur.example", "recipient": "@exemple.fr", "wb": "-5", "reason": "faux positifs récurrents"})
        self.assertTrue(r["ok"], r); self.assertTrue(r["lookup_sql"]); self.assertNotIn("warning", r)
        ins = [x for x in db["sql"] if x.startswith("INSERT IGNORE")][0]
        self.assertIn("VALUES (10, X'%s')" % "factures@fournisseur.example".encode().hex(), ins)
        self.assertIn("SELECT 1, id, X'%s'" % b"-5".hex(), ins)
        self.assertEqual(r["rules"][0], {"recipient": "@exemple.fr", "sender": "factures@fournisseur.example", "wb": "-5", "rcpt_priority": 7, "sender_priority": 10})
        self.assertEqual(r["recipients"][1]["email"], "bob@exemple.fr")
        self.assertTrue(run({"sender": "@phish.example", "recipient": "bob@exemple.fr", "wb": "delete", "reason": "nettoyage"})["ok"])
        self.assertTrue(db["sql"][-4].startswith("DELETE w FROM wblist w"))
        self.assertEqual((mc.sender_priority("@.") , mc.sender_priority("@a.example"), mc.sender_priority("@x.a.example"), mc.sender_priority("u@a.example")), (0, 4, 5, 10))
        with open(os.path.join(self.d, "50-user"), "w") as fh:
            fh.write("# @lookup_sql_dsn = ( ['DBI:mysql:database=amavis', 'a', 'b'] );\n@storage_sql_dsn = ( ['DBI:mysql:database=amavis', 'amavis', 'S3cret'] );\n")
        r = run({"sender": "a@b.example", "recipient": "@exemple.fr", "wb": "W", "reason": "test"})
        self.assertFalse(r["lookup_sql"]); self.assertIn("@lookup_sql_dsn", r["warning"])
        l = mc.run_action({"action": "wblist_list"}, NOW, runner, **self.kw)
        self.assertTrue(l["available"]); self.assertEqual(len(l["rules"]), 1)


if __name__ == "__main__":
    unittest.main()
