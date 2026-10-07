# -*- coding: utf-8 -*-
"""Tests #710 : index local de l'historique du courrier -- rattrapage, suite incrémentale, rotation, recyclage des
n° de file, conservation, recherche (jokers, plein texte FTS5), branchement dans la commande `mail`."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import maillogidx as ix  # noqa: E402
from si_agent import mailctl as mc  # noqa: E402
from test_mailctl import LOG, NOW, L  # noqa: E402


class Index(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.log = os.path.join(self.d, "mail.log")
        self.db = os.path.join(self.d, "idx.db")
        with open(self.log, "w") as fh:
            fh.write("\n".join(LOG[:9]) + "\n")

    def append(self, lines, path=None):
        with open(path or self.log, "a") as fh:
            fh.write("\n".join(lines) + "\n")

    def s(self, **p):
        return ix.search(p, self.db, now=NOW)

    def test_cycle(self):
        r = ix.update(self.log, self.db, now=NOW)
        self.assertTrue(r["ok"], r); self.assertEqual(oct(os.stat(self.db).st_mode & 0o777), "0o600")
        self.assertEqual([m["key"] for m in self.s(to="carol")["rows"]], ["4A1B2C3D4E"])
        # suite incrémentale : fin du même message + blocage Amavis + refus + lignes sans rapport
        self.append(LOG[9:])
        r = ix.update(self.log, self.db, now=NOW)
        self.assertEqual(r["added_lines"], len(LOG) - 9)
        m = self.s(to="carol")["rows"][0]
        self.assertIn("retiré de la file", m["states"]); self.assertEqual(m["states"].count("sent"), 2)
        self.assertEqual(self.s(q="Zz9yX8wV7u")["rows"][0]["amavis"]["verdict"], "Blocked SPAM")           # plein texte
        self.assertEqual(self.s(status="Blocked*")["rows"][0]["key"], "amavis-Zz9yX8wV7u")
        self.assertEqual(self.s(queue_id="AbC123dEf_x")["rows"][0]["key"], "4A1B2C3D4E")
        self.assertTrue(self.s(to="*@EXEMPLE.FR")["total"] >= 2)
        self.assertEqual(ix.update(self.log, self.db, now=NOW)["added_lines"], 0)                          # rien de neuf
        # rotation : fin de l'ancien fichier puis le nouveau ; refus NOQUEUE de lots différents : clés distinctes
        refus = "postfix/smtpd[16]: NOQUEUE: reject: RCPT from unknown[203.0.113.9]: 550 5.1.1 <x@exemple.fr>: Recipient address rejected: unknown user; from=<a@b.example> to=<x@exemple.fr> proto=ESMTP helo=<h>"
        self.append([L(3, refus)])
        os.rename(self.log, self.log + ".1")
        with open(self.log, "w") as fh:
            fh.write(L(2, refus.replace("x@exemple", "y@exemple")) + "\n")
        r = ix.update(self.log, self.db, now=NOW)
        self.assertEqual(r["added_lines"], 2)
        self.assertEqual(len([m for m in self.s(status="refusé*")["rows"]]), 3)
        # n° de file recyclé plus d'un jour après : nouveau message
        later = NOW + 3 * 86400
        self.append(["%s" % L(-3 * 24 * 60, "postfix/qmgr[14]: 4A1B2C3D4E: from=<zed@autre.example>, size=10, nrcpt=1 (queue active)")])
        ix.update(self.log, self.db, now=later)
        rows = ix.search({"queue_id": "4A1B2C3D4E", "days": 10}, self.db, now=later)["rows"]
        self.assertEqual(sorted(m["from"] for m in rows), ["alice@exemple.org", "zed@autre.example"])
        # conservation
        ix.update(self.log, self.db, now=NOW + 400 * 86400, retention_days=183)
        self.assertEqual(ix.search({"days": 3650}, self.db, now=NOW + 400 * 86400)["index"]["rows"], 0)

    def test_commande_mail(self):
        self.append(LOG[9:])
        kw = dict(log_path=self.log, audit_path=os.path.join(self.d, "a.log"), index_db=self.db)
        r = mc.run_action({"action": "log_search", "to": "carol", "hours": 24}, NOW, **kw)
        self.assertTrue(r["indexed"]); self.assertEqual(r["rows"][0]["key"], "4A1B2C3D4E")
        self.assertIn("last_update", r["index"])
        r = mc.run_action({"action": "log_search", "to": "carol", "hours": 24, "source": "log"}, NOW, **kw)
        self.assertNotIn("indexed", r)                                                                     # relecture du journal demandée
        self.assertTrue(mc.run_action({"action": "log_index"}, NOW, **kw)["indexed"])
        self.assertNotIn("indexed", mc.run_action({"action": "log_search", "to": "carol"}, NOW, log_path=self.log, audit_path=kw["audit_path"]))

    def test_pur(self):
        self.assertEqual(ix.like("*@Exemple.fr"), "%@exemple.fr"); self.assertEqual(ix.like("100%"), "%100\\%%")
        self.assertEqual(ix.fts_query('facture* "x" OR -y'), '"facture"* "x" "OR" "-y"')
        m = ix.merge({"first": 5, "last": 6, "to": ["a"], "states": ["x"], "from": None, "lines": [1]},
                     {"first": 4, "last": 9, "to": ["a", "b"], "states": ["y"], "from": "f", "lines": [2]})
        self.assertEqual((m["first"], m["last"], m["to"], m["states"], m["from"], m["lines"]), (4, 9, ["a", "b"], ["x", "y"], "f", [1, 2]))


if __name__ == "__main__":
    unittest.main()
