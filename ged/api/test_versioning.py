# -*- coding: utf-8 -*-
"""Tests de l'archivage versionné (#460) : graphe, voies, cycle de vie,
store SQLite, check-out/in, archive immuable -- sans Mayan."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import versioning as vg  # noqa: E402

V = [{"version_number": i, "mayan_file_id": 100 + i, "raw": {"filename": "doc-v%d.docx" % i, "timestamp": "2026-09-0%dT10:00:00Z" % i}} for i in range(1, 6)]


class TestPure(unittest.TestCase):
    def test_linear_default(self):
        g = vg.build_graph(V, [])
        self.assertEqual([n["parent"] for n in g["nodes"]], [None, 1, 2, 3, 4])
        self.assertEqual(len(g["edges"]), 4)
        self.assertIsNone(g["official"])
        self.assertEqual(g["branches"], ["principale"])

    def test_branches_and_official(self):
        metas = [{"version_number": 3, "parent_version": 1, "branch": "variante-client", "status": "draft"},
                 {"version_number": 4, "parent_version": 2, "branch": "principale", "status": "official", "author": "freg"},
                 {"version_number": 5, "parent_version": 3, "branch": "variante-client", "status": "draft"}]
        g = vg.build_graph(V, metas, checkout={"user": "freg"}, archives=[{"version_number": 4, "sha256": "ab", "archived_at": "t", "size": 3}])
        self.assertEqual([(e["from"], e["to"]) for e in g["edges"]], [(1, 2), (1, 3), (2, 4), (3, 5)])
        self.assertEqual(g["official"], 4)
        self.assertEqual(g["branches"], ["principale", "variante-client"])
        self.assertTrue(g["nodes"][3]["archived"])
        lanes = vg.assign_lanes(g["nodes"])
        self.assertEqual(lanes, {1: 0, 2: 0, 3: 1, 4: 0, 5: 1})

    def test_lifecycle(self):
        nodes = [{"version": 1, "status": "official"}, {"version": 2, "status": "draft"}, {"version": 3, "status": "archived"}]
        self.assertEqual(vg.lifecycle_transition(nodes, 2, "official"), {2: "official", 1: "superseded"})
        self.assertEqual(vg.lifecycle_transition(nodes, 2, "draft"), {2: "draft"})
        with self.assertRaises(ValueError):
            vg.lifecycle_transition(nodes, 3, "draft")
        with self.assertRaises(ValueError):
            vg.lifecycle_transition(nodes, 9, "draft")
        with self.assertRaises(ValueError):
            vg.lifecycle_transition(nodes, 1, "nimp")


class TestStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.db = os.path.join(self.d, "ged.db")
        vg.ensure_schema(self.db)

    def test_meta_and_statuses(self):
        vg.upsert_meta(self.db, 7, 2, parent_version=1, branch="b", author="freg", comment="c")
        vg.upsert_meta(self.db, 7, 2, status="official")
        m = vg.list_meta(self.db, 7)
        self.assertEqual((m[0]["version_number"], m[0]["parent_version"], m[0]["branch"], m[0]["status"], m[0]["author"]), (2, 1, "b", "official", "freg"))
        vg.set_statuses(self.db, 7, {2: "superseded", 3: "official"})
        self.assertEqual({x["version_number"]: x["status"] for x in vg.list_meta(self.db, 7)}, {2: "superseded", 3: "official"})

    def test_checkout(self):
        ok, holder = vg.checkout(self.db, 7, "freg", 2)
        self.assertTrue(ok)
        ok, holder = vg.checkout(self.db, 7, "eve")
        self.assertFalse(ok); self.assertEqual(holder["user"], "freg")
        ok, _ = vg.checkout(self.db, 7, "freg")          # re-sortie par le même : ok
        self.assertTrue(ok)
        self.assertEqual(vg.list_checkouts(self.db)[0]["document_id"], 7)
        ok, why = vg.checkin(self.db, 7, "eve")
        self.assertFalse(ok); self.assertIn("freg", why)
        ok, _ = vg.checkin(self.db, 7, "eve", force=True)
        self.assertTrue(ok)
        self.assertIsNone(vg.get_checkout(self.db, 7))
        self.assertEqual(vg.checkin(self.db, 7, "freg"), (False, "document non sorti"))

    def test_archive_worm(self):
        arch = os.path.join(self.d, "archive")
        e, err = vg.archive_version(self.db, arch, 7, 2, b"contenu", "rapport final.docx", document_name="Rapport", archived_by="freg")
        self.assertIsNone(err)
        self.assertTrue(os.path.exists(e["path"]))
        self.assertIn("v2-", os.path.basename(e["path"]))
        self.assertTrue(vg.verify_archive(vg.get_archive(self.db, 7, 2)))
        e2, err2 = vg.archive_version(self.db, arch, 7, 2, b"autre", "x", archived_by="freg")
        self.assertIsNone(e2); self.assertIn("immuable", err2)
        self.assertEqual(len(vg.list_archives(self.db)), 1)
        self.assertTrue(os.path.exists(os.path.join(arch, "7", "catalogue.jsonl")))
        os.chmod(e["path"], 0o600); open(e["path"], "wb").write(b"altere")
        self.assertFalse(vg.verify_archive(vg.get_archive(self.db, 7, 2)))

if __name__ == "__main__":
    unittest.main()
