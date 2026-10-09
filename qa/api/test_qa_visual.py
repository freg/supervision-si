"""Tests #727 : différences visuelles (images générées)."""
import os, tempfile, unittest
from PIL import Image, ImageDraw
import qa_visual as qv


class Visuel(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def img(self, name, box=None, size=(200, 100), color=(255, 255, 255)):
        im = Image.new("RGB", size, color)
        if box:
            ImageDraw.Draw(im).rectangle(box, fill=(0, 0, 200))
        p = os.path.join(self.d, name); im.save(p); return p

    def test_compare(self):
        a, b = self.img("a.png"), self.img("b.png", box=(10, 10, 29, 19))
        r = qv.compare(a, a)
        self.assertEqual((r["ratio"], r["bbox"], r["significant"]), (0.0, None, False))
        r = qv.compare(a, b, os.path.join(self.d, "d.png"))
        self.assertEqual((r["changed_px"], r["bbox"], r["significant"]), (200, [10, 10, 30, 20], True))
        self.assertTrue(os.path.exists(os.path.join(self.d, "d.png")))
        c = self.img("c.png", color=(250, 250, 250))                  # écart sous le seuil (anticrénelage, gamma)
        self.assertEqual(qv.compare(a, c)["changed_px"], 0)
        r = qv.compare(a, self.img("e.png", size=(200, 120)))
        self.assertTrue(r["size_changed"] and r["significant"])

    def test_pairs(self):
        ref = [{"index": -1, "login": True, "shot": "step1.png"}, {"index": 1, "shot": "step2.png", "action": "goto"}, {"index": 2, "shot": "", "action": "click"}]
        new = [{"index": 1, "shot": "step2.png", "action": "goto"}, {"index": 2, "shot": "step3.png", "action": "click"}]
        self.assertEqual(qv.pairs(ref, new), [(1, "goto", "step2.png", "step2.png")])


if __name__ == "__main__":
    unittest.main()
