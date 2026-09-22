"""Règles lisibles (livraison #556)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import rules  # noqa: E402

RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rules")
TEXT = """# Titre
## R-T-01 · Première règle
- Quand : link_missing_vlan
- Gravité : haute
- Action : Ajouter le VLAN {vlans} sur le port {missing_port} de {missing_on} ({inconnu}).
- Applicable : oui
- Pourquoi : Parce que.
  Suite du pourquoi.
## R-T-02 · Sans type (ignorée)
- Gravité : basse
## R-T-03 · Gravité inconnue
- Quand : link_bare
- Gravité : énorme
- Action : Rien.
"""


class Rules(unittest.TestCase):
    def test_parse(self):
        r = rules.parse_rules(TEXT, "t.md")
        self.assertEqual([x["id"] for x in r], ["R-T-01", "R-T-03"])
        self.assertEqual(r[0]["severity"], "haute"); self.assertTrue(r[0]["applicable"]); self.assertEqual(r[0]["why"], "Parce que. Suite du pourquoi.")
        self.assertEqual(r[1]["severity"], "info"); self.assertFalse(r[1]["applicable"])

    def test_apply(self):
        r = rules.parse_rules(TEXT)
        out = rules.apply_rules([{"kind": "link_bare", "element": "x", "message": "m", "details": {}},
                                 {"kind": "link_missing_vlan", "element": "y", "message": "n", "details": {"vlans": [30, 40], "missing_port": 49, "missing_on": "GS2220-1"}},
                                 {"kind": "autre", "element": "z", "message": "o", "details": {}}], r)
        self.assertEqual([o["kind"] for o in out], ["link_missing_vlan", "link_bare", "autre"])  # tri par gravité
        self.assertEqual(out[0]["action"], "Ajouter le VLAN 30, 40 sur le port 49 de GS2220-1 ({inconnu}).")
        self.assertTrue(out[0]["applicable"]); self.assertEqual(out[0]["rule_id"], "R-T-01")
        self.assertIn("À qualifier", out[2]["action"]); self.assertIsNone(out[2]["rule_id"])

    def test_fichiers_du_depot(self):
        r, errors = rules.load_rules(RULES_DIR)
        self.assertEqual(errors, [])
        whens = {x["when"] for x in r}
        for kind in ("link_missing_vlan", "ssid_vlan_not_on_link", "ssid_vlan_no_port", "vlan_no_gateway", "link_bare"):
            self.assertIn(kind, whens)
        self.assertTrue(next(x for x in r if x["when"] == "link_missing_vlan")["applicable"])
        self.assertEqual(sum(1 for x in r if x["when"] == "link_bare" and x["applicable"]), 0)


if __name__ == "__main__":
    unittest.main()
