# -*- coding: utf-8 -*-
import unittest

import alertfilters as af


class Filters(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(af.category_of("agent-offline"), "availability")
        self.assertEqual(af.category_of("plugin-assigned"), "plugins")
        self.assertEqual(af.category_of("command-software"), "commands")
        self.assertEqual(af.category_of("smb1_enabled"), "risks")
        self.assertEqual(af.category_of("bizarre"), "other")

    def test_hours_paris(self):
        rule = {"when": "outside", "days": [0, 1, 2, 3, 4], "start": "08:30", "end": "18:00"}
        # mardi 22/09/2026 07:00 UTC = 09:00 Paris (heure d'été) -> dans la plage
        self.assertTrue(af.in_hours("2026-09-22T07:00:00Z", rule))
        # 16:30 UTC = 18:30 Paris -> hors plage ; samedi -> hors plage
        self.assertFalse(af.in_hours("2026-09-22T16:30:00Z", rule))
        self.assertFalse(af.in_hours("2026-09-26T10:00:00Z", rule))
        # hiver : 08:00 UTC = 09:00 Paris
        self.assertTrue(af.in_hours("2026-12-15T08:00:00Z", rule))

    def test_evaluate_workstations(self):
        groups = af.DEFAULT_GROUPS
        agent = {"filter_enabled": 1, "filter_group": "postes-travail"}
        night = {"kind": "agent-offline", "at": "2026-09-22T20:00:00Z"}
        day = {"kind": "agent-offline", "at": "2026-09-22T09:00:00Z"}
        self.assertEqual(af.evaluate(night, groups, agent)[0], True)
        self.assertIn("Postes de travail", af.evaluate(night, groups, agent)[1])
        self.assertEqual(af.evaluate(day, groups, agent), (False, ""))
        self.assertEqual(af.evaluate({"kind": "auth-refused", "at": "2026-09-22T20:00:00Z"}, groups, agent), (False, ""))  # autre catégorie : jamais filtrée
        self.assertEqual(af.evaluate(night, groups, {"filter_enabled": 0, "filter_group": "postes-travail"}), (False, ""))
        self.assertEqual(af.evaluate(night, groups, {"filter_enabled": 1, "filter_group": "inconnu"}), (False, ""))
        self.assertTrue(af.evaluate({"kind": "auth-refused", "at": "2026-09-22T09:00:00Z"}, groups, {"filter_enabled": 1, "filter_group": "silencieux"})[0])

    def test_normalize(self):
        g = af.normalize_groups([{"id": "Nuit Serveurs", "label": "Serveurs la nuit", "rules": [{"categories": ["availability", "nope"], "when": "outside", "days": [0, 6, 9], "start": "22h00", "end": "6:00"}]}])
        self.assertEqual(g[0]["id"], "nuit-serveurs")
        self.assertEqual(g[0]["rules"][0], {"categories": ["availability"], "kinds": [], "when": "outside", "days": [0, 6], "start": "22:00", "end": "06:00", "action": "mute", "label": ""})
        with self.assertRaises(ValueError):
            af.normalize_groups([{"id": "x", "rules": [{"categories": []}]}])
        with self.assertRaises(ValueError):
            af.normalize_groups([{"id": "x", "rules": []}, {"id": "x", "rules": []}])


if __name__ == "__main__":
    unittest.main()
