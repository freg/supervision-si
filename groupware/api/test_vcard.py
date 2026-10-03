import unittest, vcard
class V(unittest.TestCase):
    def test_roundtrip(self):
        c = {"uid": "u1", "last": "Martin", "first": "Alice", "org": "Société Alpha", "title": "Directrice", "tels": [{"type": "work", "value": "+33 1 23 45 67 89"}, {"type": "cell", "value": "06 00 00 00 00"}],
             "emails": [{"type": "work", "value": "alice@exemple.fr"}], "adr": {"type": "work", "street": "5 rue de l'Exemple", "city": "Villexemple", "region": "", "zip": "86000", "country": "France"},
             "url": "https://exemple.fr", "note": "ligne 1\nligne 2, avec virgule; et point-virgule", "categories": ["client", "VIP"]}
        txt = vcard.serialize(c); self.assertTrue(txt.startswith("BEGIN:VCARD\r\nVERSION:3.0")); self.assertIn("FN:Alice Martin", txt); self.assertIn("NOTE:ligne 1\\nligne 2\\, avec virgule\; et point-virgule", txt)
        p = vcard.parse(txt)
        for k in ("uid", "last", "first", "org", "title", "url", "note", "categories"): self.assertEqual(p[k], c[k], k)
        self.assertEqual(p["fn"], "Alice Martin"); self.assertEqual(p["tels"][1], {"type": "cell", "value": "06 00 00 00 00"}); self.assertEqual(p["adr"]["city"], "Villexemple"); self.assertEqual(p["adr"]["zip"], "86000"); self.assertTrue(p["rev"])
    def test_foreign_card_preserved(self):
        txt = "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:x\r\nFN:Bob\r\nN:;Bob;;;\r\nPHOTO;ENCODING=b;TYPE=JPEG:" + "A" * 200 + "\r\nX-FOO:bar\r\nEND:VCARD\r\n"
        p = vcard.parse(txt); self.assertEqual(len(p["extra"]), 2); self.assertTrue(p["extra"][0].startswith("PHOTO"))
        out = vcard.serialize(p); self.assertIn("X-FOO:bar", out); self.assertIn("PHOTO;ENCODING=b;TYPE=JPEG:AAAA", out.replace("\r\n ", ""))
        self.assertTrue(all(len(l.encode()) <= 75 for l in out.split("\r\n")))
        self.assertEqual(vcard.parse("BEGIN:VCARD\r\nVERSION:3.0\r\nUID:y\r\nN:Durand;;;;\r\nEND:VCARD\r\n")["fn"], "Durand")
    def test_matches(self):
        c = vcard.parse(vcard.serialize({"uid": "1", "first": "Alice", "last": "Martin", "org": "Alpha", "emails": [{"value": "a@exemple.fr"}]}))
        self.assertTrue(vcard.matches(c, "alice alpha")); self.assertTrue(vcard.matches(c, "exemple.fr")); self.assertFalse(vcard.matches(c, "bob")); self.assertTrue(vcard.matches(c, ""))
if __name__ == "__main__": unittest.main()
