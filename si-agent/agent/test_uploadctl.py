"""Tests #634 : transfert d'image vers le central (découpage, reprise, condensé, progression)."""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import uploadctl  # noqa: E402


class UploadTests(unittest.TestCase):
    def test_nom(self):
        self.assertEqual(uploadctl.safe_name("d:\\papa\\PC-01-20260926-1256.vhdx"), "PC-01-20260926-1256.vhdx")
        self.assertEqual(uploadctl.safe_name("/mnt/x/a b.vhdx"), "a-b.vhdx"); self.assertIsNone(uploadctl.safe_name("")); self.assertIsNone(uploadctl.safe_name("d:\\.hidden"))

    def test_decoupage_et_reprise(self):
        self.assertEqual(list(uploadctl.plan_chunks(10, 0, 4)), [(0, 4), (4, 4), (8, 2)])
        self.assertEqual(list(uploadctl.plan_chunks(10, 8, 4)), [(8, 2)]); self.assertEqual(list(uploadctl.plan_chunks(10, 10, 4)), [])
        data = bytes(range(256)) * 40
        h = uploadctl.prefix_digest(lambda pos, n: data[pos:pos + n], 1000, chunk=300)
        self.assertEqual(h.hexdigest(), hashlib.sha256(data[:1000]).hexdigest())
        h.update(data[1000:]); self.assertEqual(h.hexdigest(), hashlib.sha256(data).hexdigest())

    def test_progression_et_offset(self):
        p = uploadctl.progress(50_000_000, 100_000_000, 1000, 1010)
        self.assertEqual(p["percent"], 50.0); self.assertEqual(p["rate_mbps"], 40.0); self.assertEqual(p["eta_seconds"], 10)
        self.assertIsNone(uploadctl.check_offset(8, "8")); self.assertIn("attendu", uploadctl.check_offset(8, 0)); self.assertIn("entier", uploadctl.check_offset(8, "x"))


if __name__ == "__main__":
    unittest.main()
