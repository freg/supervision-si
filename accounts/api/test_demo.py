# -*- coding: utf-8 -*-
import unittest

import demo


class Demo(unittest.TestCase):
    def test_profiles_and_state(self):
        ps = demo.profiles(None)
        self.assertEqual([p["username"] for p in ps], ["demo-admin", "demo-technicien", "demo-lecture"])
        ps = demo.profiles('[{"username": "demo-site", "groups": ["site-alpha"]}, {"username": "vrai-compte", "groups": []}]')
        self.assertEqual([p["username"] for p in ps], ["demo-site"])  # sans préfixe demo- : ignoré
        self.assertEqual(demo.profiles("pas du json")[0]["username"], "demo-admin")
        st = demo.state(ps, [{"username": "demo-site", "id": "u1", "enabled": False, "groups": ["site-alpha"]}])
        self.assertEqual((st[0]["exists"], st[0]["enabled"], st[0]["id"]), (True, False, "u1"))
        self.assertEqual(demo.summary(st)["mode"], "off")
        st[0]["enabled"] = True
        self.assertEqual(demo.summary(st), {"profiles": 1, "active": 1, "existing": 1, "mode": "on"})

    def test_password(self):
        p = demo.generate_password()
        self.assertEqual(len(p), 15)
        self.assertTrue(all(c not in "0O1lI" for c in p))
        self.assertNotEqual(p, demo.generate_password())


if __name__ == "__main__":
    unittest.main()
