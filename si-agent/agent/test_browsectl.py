"""Tests #627 : parcours de l'arborescence (lecteurs, sous-dossiers, parent, bornes)."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import browsectl  # noqa: E402


class FakeEntry:
    def __init__(self, name, d=True, err=False):
        self.name, self._d, self._err = name, d, err

    def is_dir(self, follow_symlinks=False):
        if self._err:
            raise OSError("x")
        return self._d


class FakeScan:
    def __init__(self, entries):
        self.entries = entries

    def __enter__(self):
        return iter(self.entries)

    def __exit__(self, *a):
        return False


class BrowseTests(unittest.TestCase):
    def test_normalize_et_parent(self):
        self.assertEqual(browsectl.normalize("c:"), "c:\\"); self.assertEqual(browsectl.normalize(" D:/images "), "D:\\images")
        self.assertIsNone(browsectl.normalize("C:\\a\\..\\b")); self.assertIsNone(browsectl.normalize(""))
        self.assertEqual(browsectl.parent_of("C:\\images\\p2v"), "C:\\images"); self.assertEqual(browsectl.parent_of("C:\\images"), "C:\\")
        self.assertIsNone(browsectl.parent_of("C:\\")); self.assertIsNone(browsectl.parent_of("\\\\nas\\images"))
        self.assertEqual(browsectl.parent_of("\\\\nas\\images\\p2v"), "\\\\nas\\images")

    def test_lecteurs(self):
        d = browsectl.list_drives(exists=lambda p: p in ("C:\\", "D:\\"), usage=lambda p: NS(free=10, total=100), fstype=lambda p: "NTFS")
        self.assertEqual([x["path"] for x in d], ["C:\\", "D:\\"]); self.assertEqual(d[0]["free"], 10); self.assertEqual(d[1]["fs"], "NTFS")
        r = browsectl.run({}, exists=lambda p: p == "C:\\")
        self.assertTrue(r["ok"]); self.assertIsNone(r["path"]); self.assertEqual(len(r["drives"]), 1)

    def test_dossiers(self):
        scan = lambda p: FakeScan([FakeEntry("zeta"), FakeEntry("fichier.txt", d=False), FakeEntry("Alpha"), FakeEntry("bad", err=True)])
        r = browsectl.run({"path": "D:\\images"}, scandir=scan, usage=lambda p: NS(free=5, total=9))
        self.assertTrue(r["ok"]); self.assertEqual([e["name"] for e in r["entries"]], ["Alpha", "zeta"])
        self.assertEqual(r["entries"][0]["path"], os.path.join("D:\\images", "Alpha")); self.assertEqual(r["parent"], "D:\\"); self.assertEqual(r["free"], 5)

        def missing(p):
            raise FileNotFoundError(p)
        self.assertIn("introuvable", browsectl.run({"path": "Z:\\x"}, scandir=missing)["error"])

        def denied(p):
            raise PermissionError(p)
        self.assertIn("refusé", browsectl.run({"path": "\\\\nas\\prive"}, scandir=denied)["error"])
        self.assertFalse(browsectl.run({"path": "C:\\..\\x"})["ok"])
        big = lambda p: FakeScan([FakeEntry("d%04d" % i) for i in range(500)])
        r = browsectl.run({"path": "C:\\big"}, scandir=big)
        self.assertEqual(len(r["entries"]), browsectl.MAX_ENTRIES); self.assertTrue(r["truncated"])


if __name__ == "__main__":
    unittest.main()
