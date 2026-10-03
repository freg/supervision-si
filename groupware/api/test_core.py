# -*- coding: utf-8 -*-
"""#664 : noyau groupware -- droits (lettres, masque, effectifs avec groupes), validation des partages, préférences à
quatre niveaux, fichier de droits Radicale, URLs DAV."""
import unittest
import core

class Core(unittest.TestCase):
    def test_rights(self):
        self.assertEqual(core.parse_rights("rae"), 7); self.assertEqual(core.parse_rights("write"), 15); self.assertEqual(core.parse_rights("all"), 31); self.assertEqual(core.parse_rights(3), 3)
        self.assertEqual(core.rights_text(5), "re")
        with self.assertRaises(ValueError):
            core.parse_rights("rx")

    def test_effective(self):
        grants = [{"owner": "alice", "app": "calendar", "grantee_kind": "user", "grantee": "bob", "rights": 1},
                  {"owner": "alice", "app": "calendar", "grantee_kind": "group", "grantee": "secretariat", "rights": 15},
                  {"owner": "carol", "app": "calendar", "grantee_kind": "all", "grantee": "*", "rights": 1},
                  {"owner": "carol", "app": "addressbook", "grantee_kind": "user", "grantee": "bob", "rights": 1}]
        self.assertEqual(core.effective(grants, "calendar", "bob", []), {"bob": 31, "alice": 1, "carol": 1})
        self.assertEqual(core.effective(grants, "calendar", "bob", ["secretariat"]), {"bob": 31, "alice": 15, "carol": 1})
        self.assertEqual(core.effective(grants, "addressbook", "dave", []), {"dave": 31})

    def test_validate_grant(self):
        g, err = core.validate_grant({"owner": "alice", "app": "calendar", "grantee": "bob", "rights": "rae"})
        self.assertIsNone(err); self.assertEqual(g["rights"], 7); self.assertEqual(g["grantee_kind"], "user")
        self.assertIn("app", core.validate_grant({"owner": "alice", "app": "x", "grantee": "bob"})[1])
        self.assertIn("tous les droits", core.validate_grant({"owner": "alice", "app": "calendar", "grantee": "alice"})[1])
        self.assertEqual(core.validate_grant({"owner": "alice", "app": "calendar", "grantee_kind": "all"})[0]["grantee"], "*")
        self.assertIn("droit inconnu", core.validate_grant({"owner": "alice", "app": "calendar", "grantee": "bob", "rights": "z"})[1])

    def test_prefs(self):
        rows = [{"level": "default", "subject": "", "app": "*", "key": "lang", "value": "fr"}, {"level": "default", "subject": "", "app": "calendar", "key": "view", "value": "week"},
                {"level": "group", "subject": "secretariat", "app": "calendar", "key": "view", "value": "day"}, {"level": "user", "subject": "bob", "app": "calendar", "key": "view", "value": "month"},
                {"level": "forced", "subject": "", "app": "*", "key": "tz", "value": "Europe/Paris"}, {"level": "user", "subject": "bob", "app": "*", "key": "tz", "value": "UTC"}]
        self.assertEqual(core.resolve_prefs(rows, "calendar", "bob", ["secretariat"]), {"lang": "fr", "view": "month", "tz": "Europe/Paris"})
        self.assertEqual(core.resolve_prefs(rows, "calendar", "eve", ["secretariat"]), {"lang": "fr", "view": "day", "tz": "Europe/Paris"})
        self.assertEqual(core.resolve_prefs(rows, "infolog", "eve", [])["lang"], "fr"); self.assertNotIn("view", core.resolve_prefs(rows, "infolog", "eve", []))

    def test_radicale_rights(self):
        grants = [{"owner": "alice", "app": "calendar", "grantee_kind": "user", "grantee": "bob", "rights": 1},
                  {"owner": "alice", "app": "addressbook", "grantee_kind": "group", "grantee": "secretariat", "rights": 15},
                  {"owner": "alice", "app": "infolog", "grantee_kind": "user", "grantee": "bob", "rights": 15},
                  {"owner": "carol", "app": "calendar", "grantee_kind": "all", "grantee": "*", "rights": 1}]
        txt = core.radicale_rights(grants, lambda g: ["dave", "alice", "eve"] if g == "secretariat" else [])
        self.assertIn("user: ^bob$\ncollection: ^alice/(agenda|cal|calendar)[^/]*(/.*)?$\npermissions: rR", txt)
        self.assertIn("user: ^dave$\ncollection: ^alice/(contacts|carnet|ab|addressbook)[^/]*(/.*)?$\npermissions: rRwW", txt); self.assertIn("user: ^eve$", txt)
        self.assertNotIn("user: ^alice$", txt)                     # membre du groupe mais propriétaire : pas de règle
        self.assertNotIn("infolog", txt)
        self.assertIn("user: ^.+$\ncollection: ^carol/", txt)       # all
        self.assertTrue(txt.rstrip().endswith("[root]\nuser: .+\ncollection: ^$\npermissions: R")); self.assertIn("[owner-write]\nuser: .+\ncollection: ^{user}(/.*)?$\npermissions: RW", txt)
        self.assertLess(txt.index("[grant-1]"), txt.index("[owner-write]")); self.assertEqual(txt.count("[grant-"), 4)

    def test_dav_urls(self):
        u = core.dav_urls("https://hub.exemple.fr:6443/dav/", "bob")
        self.assertEqual(u["principal"], "https://hub.exemple.fr:6443/dav/bob/"); self.assertIn("/.web/", u["note"])

if __name__ == "__main__":
    unittest.main()
