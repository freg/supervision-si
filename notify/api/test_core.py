# -*- coding: utf-8 -*-
import unittest

import core


class Resolve(unittest.TestCase):
    def setUp(self):
        self.groups = {
            "auto:mikrotik": {"emails": ["reseau@exemple.test"]},
            "auto:cisco": {"emails": []},
            "g:astreinte": {"emails": ["astreinte@exemple.test", "Chef@Exemple.test"]},
            "m:infra": {"kind": "meta", "members": ["auto:mikrotik", "g:astreinte", "m:boucle"]},
            "m:boucle": {"kind": "meta", "members": ["m:infra"]},
        }

    def test_validation(self):
        self.assertTrue(core.valid_action("mikrotik.nat.add"))
        for bad in ("", "nat", "Mikrotik.Nat", "a..b", "x.y z", "a." + "b" * 90):
            self.assertFalse(core.valid_action(bad), bad)
        self.assertTrue(core.valid_email("a.b@exemple.test"))
        self.assertFalse(core.valid_email("a b@exemple"))
        self.assertEqual(core.default_group_id("cisco.restore"), "auto:cisco")

    def test_default_group_and_meta(self):
        emails, why = core.resolve("mikrotik.nat.add", {}, self.groups)
        self.assertEqual((emails, why), (["reseau@exemple.test"], None))
        emails, _ = core.resolve("mikrotik.nat.add", {"mikrotik.nat.add": ["m:infra"]}, self.groups)
        self.assertEqual(emails, ["astreinte@exemple.test", "chef@exemple.test", "reseau@exemple.test"])
        emails, _ = core.resolve("mikrotik.reboot", {"mikrotik.*": ["g:astreinte"]}, self.groups)
        self.assertIn("astreinte@exemple.test", emails)

    def test_empty_and_blacklist(self):
        emails, why = core.resolve("cisco.restore", {}, self.groups)
        self.assertEqual(emails, [])
        self.assertIn("aucun destinataire", why)
        emails, why = core.resolve("inconnu.x", {}, self.groups)
        self.assertIn("aucun", why)
        bl = {"email": {"reseau@exemple.test"}, "action": {"cisco.*"}, "consumer": {"ged"}}
        self.assertEqual(core.resolve("mikrotik.nat.add", {}, self.groups, bl)[1], "aucun destinataire (groupe sans adresse ou tout en liste noire)")
        self.assertEqual(core.resolve("cisco.backup", {}, self.groups, bl)[1], "action en liste noire")
        self.assertEqual(core.resolve("mikrotik.nat.add", {}, self.groups, bl, consumer="ged")[1], "consommateur en liste noire")


class Sender(unittest.TestCase):
    def test_backoff_burst_breaker(self):
        self.assertEqual([core.backoff_seconds(n) for n in (1, 2, 3, 10)], [60, 120, 240, 3600])
        self.assertEqual(core.burst_state(29, 30), "send")
        self.assertEqual(core.burst_state(30, 30), "hold")
        self.assertEqual(core.burst_state(500, 0), "send")
        self.assertFalse(core.breaker_open(2, 3, 100, 150, 300))
        self.assertTrue(core.breaker_open(3, 3, 100, 150, 300))
        self.assertFalse(core.breaker_open(3, 3, 100, 500, 300))
        self.assertEqual(core.allowance(18, 20), 2)
        self.assertEqual(core.allowance(25, 20), 0)
        self.assertEqual(core.render_subject("[Hub SI]", "critical", " Routeur down "), "[Hub SI] [CRITIQUE] Routeur down")
        self.assertIn("31 notifications", core.summary_body("x.y", 31, "s", 300))


if __name__ == "__main__":
    unittest.main()
