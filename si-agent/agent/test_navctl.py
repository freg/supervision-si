"""Tests #798 : commande « navigateur » de l'agent (relais vers l'automate local, jeton, allègement)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import navctl  # noqa: E402


class Navctl(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        open(os.path.join(self.d, "jeton"), "w").write("j" * 32 + "\n")
        open(os.path.join(self.d, "port"), "w").write("8095\n")
        self.appels = []

    def http(self, rep):
        def f(m, chemin, corps, cfg):
            self.appels.append((m, chemin, corps, cfg))
            return rep
        return f

    def test_relais(self):
        r = navctl.run({"action": "aller", "url": "https://www.example.org/"}, self.http((200, {"ok": True, "url": "https://www.example.org/"})), self.d)
        self.assertTrue(r["ok"])
        self.assertEqual(self.appels[0][:3], ("POST", "/aller", {"url": "https://www.example.org/"}))
        self.assertEqual(self.appels[0][3], {"jeton": "j" * 32, "port": 8095})
        self.assertFalse(navctl.run({"action": "aller", "url": "file:///etc/passwd"}, self.http((200, {})), self.d)["ok"])
        self.assertFalse(navctl.run({"action": "formater"}, self.http((200, {})), self.d)["ok"])
        r = navctl.run({"action": "etapes", "etapes": [{"action": "goto", "value": "/"}], "base_url": "https://x.example"},
                       self.http((200, {"ok": False, "statut": "ko", "resultats": []})), self.d)
        self.assertEqual((r["ok"], r["error"]), (False, "parcours en échec"))
        self.assertEqual(self.appels[-1][2], {"etapes": [{"action": "goto", "value": "/"}], "base_url": "https://x.example"})
        r = navctl.run({"action": "enregistrer", "etape": "fin"}, self.http((200, {"ok": True, "etapes": []})), self.d)
        self.assertEqual((r["ok"], self.appels[-1][1], self.appels[-1][2]), (True, "/enregistrer", {"etape": "fin"}))
        self.assertFalse(navctl.run({"action": "enregistrer", "etape": "pause"}, self.http((200, {})), self.d)["ok"])
        r = navctl.run({"action": "etat"}, self.http((502, {"error": "automate injoignable"})), self.d)
        self.assertEqual(r["error"], "automate injoignable")

    def test_non_installe_et_allegement(self):
        self.assertIn("non installé", navctl.run({"action": "etat"}, self.http((200, {})), tempfile.mkdtemp())["error"])
        gros = {"ok": True, "capture": "A" * 2000, "resultats": [{"index": 1, "capture": "B" * 2000}]}
        x = navctl.alleger(json.loads(json.dumps(gros)), limite=3000)
        self.assertNotIn("capture", x["resultats"][0])
        self.assertIn("capture", x)
        y = navctl.alleger(json.loads(json.dumps(gros)), limite=500)
        self.assertTrue(y["capture_retiree"])


if __name__ == "__main__":
    unittest.main()
