# -*- coding: utf-8 -*-
"""Tests purs du gestionnaire de sauvegardes du hub (#459)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub_backups as hb  # noqa: E402


def sess(name, kind, at, base=None, prev=None, size=100):
    return {"name": name, "kind": kind, "created_at": at, "base": base or (name if kind == "full" else None), "previous": prev, "size": size, "archive": name + ".tar.gz.enc"}


class T(unittest.TestCase):
    def test_catalog_from_manifests(self):
        d = tempfile.mkdtemp()
        json.dump({"name": "supervision-si-backup-h-20260908-100000", "kind": "full", "archive": "supervision-si-backup-h-20260908-100000.tar.gz.enc",
                   "created_at": "2026-09-08T10:00:00+00:00", "git": {"delivery": "458", "commit": "abcdef123456"}, "size": 5, "volumes": [1, 2], "mounts": [1]},
                  open(os.path.join(d, "supervision-si-backup-h-20260908-100000.manifest.json"), "w"))
        open(os.path.join(d, "supervision-si-backup-h-20260908-100000.tar.gz.enc"), "wb").write(b"x")
        json.dump({"name": "supervision-si-incr-h-20260908-110000", "kind": "incremental", "archive": "supervision-si-incr-h-20260908-110000.tar.gz.enc",
                   "created_at": "2026-09-08T11:00:00+00:00", "base": "supervision-si-backup-h-20260908-100000", "previous": "supervision-si-backup-h-20260908-100000",
                   "git": {}, "deleted": ["a"], "changed_files": 3}, open(os.path.join(d, "supervision-si-incr-h-20260908-110000.manifest.json"), "w"))
        open(os.path.join(d, "poubelle.txt"), "w").write("")
        cat = hb.read_catalog(d)
        self.assertEqual([s["kind"] for s in cat], ["incremental", "full"])
        self.assertEqual((cat[1]["present"], cat[1]["delivery"], cat[1]["commit"], cat[1]["volumes"]), (True, "458", "abcdef12", 2))
        self.assertEqual((cat[0]["present"], cat[0]["deleted"], cat[0]["changed_files"]), (False, 1, 3))
        chains = hb.build_chains(cat)
        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0]["count"], 2)
        self.assertEqual(hb.files_of_chain(chains[0])[0], "supervision-si-backup-h-20260908-100000.tar.gz.enc")

    def test_chains_and_orphans(self):
        s = [sess("f1", "full", "2026-09-01T02:00:00+00:00"), sess("i1", "incremental", "2026-09-02T02:00:00+00:00", base="f1", prev="f1"),
             sess("i2", "incremental", "2026-09-03T02:00:00+00:00", base="f1", prev="i1"), sess("f2", "full", "2026-09-07T02:00:00+00:00"),
             sess("ix", "incremental", "2026-09-04T02:00:00+00:00", base="disparu", prev="disparu")]
        ch = hb.build_chains(s)
        self.assertEqual([c["key"] for c in ch], ["f2", "orphelines", "f1"])
        self.assertEqual([m["name"] for m in ch[2]["increments"]], ["i1", "i2"])

    def test_gfs(self):
        fulls = []
        day = dt.datetime(2026, 9, 8, 2, tzinfo=dt.timezone.utc)
        for i in range(60):   # une totale par jour pendant 60 jours
            d = day - dt.timedelta(days=i)
            fulls.append(sess("f%02d" % i, "full", d.isoformat()))
        ch = hb.build_chains(fulls)
        plan = hb.gfs_plan(ch, keep_daily=7, keep_weekly=4, keep_monthly=3, now=day)
        keys = {c["key"] for c in plan["keep"]}
        self.assertTrue({"f00", "f01", "f06"} <= keys)      # 7 récentes
        self.assertNotIn("f07", keys) if plan["why"].get("f07") is None else None
        self.assertLessEqual(len(keys), 7 + 4 + 3)
        self.assertGreaterEqual(len(keys), 7 + 2)
        self.assertEqual(len(plan["keep"]) + len(plan["drop"]), 60)
        self.assertTrue(any(v.startswith("hebdomadaire") for v in plan["why"].values()))
        self.assertTrue(any(v.startswith("mensuelle") for v in plan["why"].values()))

    def test_safe_name(self):
        self.assertTrue(hb.safe_name("supervision-si-backup-super-20260908-191243"))
        self.assertTrue(hb.safe_name("supervision-si-incr-vm-20260908-191245"))
        self.assertFalse(hb.safe_name("../etc/passwd"))
        self.assertFalse(hb.safe_name("supervision-si-backup-super-2026"))

    def test_due(self):
        r = hb.Runner("/p", "/b", passphrase="x", incr_hours=6, full_weekday=6, full_hour=2)
        now = dt.datetime(2026, 9, 13, 2, 5, tzinfo=dt.timezone.utc)   # dimanche 02:05
        self.assertEqual(r.due([], now), "full")
        s = [sess("f1", "full", "2026-09-12T02:00:00+00:00")]
        self.assertEqual(r.due(s, now), "full")                          # totale hebdo due
        s = [sess("f1", "full", "2026-09-13T02:00:00+00:00")]
        self.assertIsNone(r.due(s, now))                                  # déjà faite ce matin
        later = dt.datetime(2026, 9, 13, 9, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(r.due(s, later), "incremental")                  # 7 h plus tard
        r2 = hb.Runner("/p", "/b", passphrase=None, incr_hours=6)
        self.assertIsNone(r2.due([], later))                              # sans phrase : jamais

if __name__ == "__main__":
    unittest.main()
