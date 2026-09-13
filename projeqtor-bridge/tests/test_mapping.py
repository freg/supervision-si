# -*- coding: utf-8 -*-
"""Tests purs du marqueur configurable du pont (livraison #494) :
PROJEQTOR_BRIDGE_LABEL pilote la ligne récap et l'externalReference,
l'export relit ce que l'import a écrit, et un autre libellé n'est pas
relu (ce qui documente le « choisir une fois »).
    python3 projeqtor-bridge/tests/test_mapping.py
"""
import importlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


def _load(label):
    if label is None:
        os.environ.pop("PROJEQTOR_BRIDGE_LABEL", None)
    else:
        os.environ["PROJEQTOR_BRIDGE_LABEL"] = label
    sys.modules.pop("mapping", None)
    return importlib.import_module("mapping")


class LabelTests(unittest.TestCase):
    def test_default_label(self):
        m = _load(None)
        self.assertEqual(m.RECAP_PREFIX, "[SUIVI]")
        self.assertEqual(m.REF_PREFIX, "SUIVI:")

    def test_blank_label_falls_back(self):
        m = _load("   ")
        self.assertEqual(m.RECAP_PREFIX, "[SUIVI]")

    def test_roundtrip_with_custom_label(self):
        m = _load("ACME")
        demand = {m.COL_ID: 42, m.COL_REQUESTER: "alice", m.COL_PRIORITY: "Haute",
                  m.COL_CATEGORY: "SAV", m.COL_DURATION: 3, m.COL_PROGRESS: 0.5,
                  m.COL_SUBJECT: "Imprimante", m.COL_COMMENT: "bac 2 bloqué"}
        line = m.build_recap(demand)
        self.assertTrue(line.startswith("[ACME] Demandeur: alice | "))
        parsed = m.parse_recap("bac 2 bloqué\n" + line)
        self.assertEqual(parsed["demandeur"], "alice")
        self.assertEqual(parsed["avancement"], "0.5")
        # externalReference porte le même marqueur
        fields, unresolved = m.demand_to_ticket(demand, {"contacts": {}, "urgencies": {}, "types": {}})
        self.assertEqual(fields["externalReference"], "ACME:42")
        # relecture à l'export
        ticket = {"id": 7, "name": "Imprimante", "description": fields["description"],
                  "externalReference": fields["externalReference"]}
        back = m.ticket_to_demand(ticket, {"contacts": {}, "urgencies": {}, "types": {}})
        self.assertEqual(str(back[m.COL_ID]), "42")
        self.assertEqual(back[m.COL_DURATION], 3)
        self.assertEqual(back[m.COL_PROGRESS], 0.5)
        self.assertEqual(back[m.COL_COMMENT], "bac 2 bloqué")

    def test_other_label_is_not_reread(self):
        m = _load("ACME")
        demand = {m.COL_ID: 1, m.COL_SUBJECT: "Écran", m.COL_REQUESTER: "bob", m.COL_DURATION: 1, m.COL_PROGRESS: 0}
        fields, _ = m.demand_to_ticket(demand, {"contacts": {}, "urgencies": {}, "types": {}})
        m2 = _load("AUTRE")
        back = m2.ticket_to_demand({"id": 9, "description": fields["description"],
                                    "externalReference": fields["externalReference"]},
                                   {"contacts": {}, "urgencies": {}, "types": {}})
        self.assertEqual(back[m2.COL_ID], 9, "id ProjeQtOr faute de marqueur relu")
        self.assertIsNone(back[m2.COL_DURATION])


if __name__ == "__main__":
    unittest.main(verbosity=1)
