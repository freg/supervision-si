# -*- coding: utf-8 -*-
import datetime as dt
import unittest

import rules

CAT = [{"id": 1, "name": "Office 365", "vendor": "Microsoft", "patterns": ["Microsoft 365 Apps", "Office 365"]},
       {"id": 2, "name": "DraftSight", "vendor": "Dassault Systèmes", "patterns": []},
       {"id": 3, "name": "eDraw", "vendor": "WonderShare", "patterns": ["edraw"]}]
INV = [{"agent_id": "a1", "hostname": "PC-01", "site": "siege", "users": ["alice"], "installed": [
            {"name": "Microsoft 365 Apps for business - fr-fr", "publisher": "Microsoft Corporation", "version": "16"},
            {"name": "DraftSight 2024", "publisher": "Dassault Systèmes"}, {"name": "Microsoft Update Health Tools", "publisher": "Microsoft Corporation"},
            {"name": "Zoom", "publisher": "Zoom Video Communications"}]},
       {"agent_id": "a2", "hostname": "PC-02", "site": "siege", "users": ["bob"], "installed": [{"name": "Wondershare EdrawMax", "publisher": "Wondershare"}, {"name": "vim", "publisher": "Debian", "source": "dpkg"}]}]


class Match(unittest.TestCase):
    def test_match_and_unknown(self):
        found, unknown = rules.match_installations(CAT, INV)
        self.assertEqual([i["host"] for i in found[1]], ["PC-01"])
        self.assertEqual([i["host"] for i in found[2]], ["PC-01"])
        self.assertEqual([i["host"] for i in found[3]], ["PC-02"])
        self.assertEqual([u["name"] for u in unknown], ["Zoom"])  # bruit système et paquets dpkg exclus
        self.assertTrue(rules.matches({"name": "Édraw"}, "wondershare edrawmax"))
        self.assertTrue(rules.matches({"name": "x", "patterns": ["re:^draft"]}, "DraftSight"))


class Gaps(unittest.TestCase):
    def test_gaps(self):
        today = dt.date(2026, 9, 24)
        contracts = [{"id": 10, "software_id": 1, "label": "Business Standard", "kind": "per-user", "quantity": 2, "end": "2026-11-14"},
                     {"id": 11, "software_id": 3, "label": "eDraw", "kind": "perpetual", "quantity": 1, "end": "2024-10-10"},
                     {"id": 12, "software_id": 2, "label": "DraftSight", "kind": "per-device", "quantity": 1, "end": None}]
        assignments = [{"id": 1, "contract_id": 10, "subject_kind": "user", "subject": "alice"}, {"id": 2, "contract_id": 10, "subject_kind": "user", "subject": "bob"},
                       {"id": 3, "contract_id": 10, "subject_kind": "user", "subject": "carol"}, {"id": 4, "contract_id": 12, "subject_kind": "host", "subject": "PC-09"}]
        found, _ = rules.match_installations(CAT, INV)
        g = rules.gaps(CAT, contracts, assignments, found, today=today)
        kinds = {(x["kind"], x["software"]) for x in g}
        self.assertIn(("over-assigned", "Office 365"), kinds)
        self.assertIn(("expiring", "Office 365"), kinds)   # 51 jours
        self.assertIn(("expired", "eDraw"), kinds)
        self.assertIn(("assigned-not-installed", "DraftSight"), kinds)
        self.assertIn(("installed-not-assigned", "DraftSight"), kinds)
        self.assertEqual(g[0]["severity"], "critical")
        g2 = rules.gaps([{"id": 9, "name": "Zoom", "vendor": "Zoom"}], [], [], {9: [{"host": "PC-01"}]}, today=today)
        self.assertEqual(g2[0]["kind"], "installed-no-contract")
        g3 = rules.gaps(CAT[:1], [{"id": 13, "software_id": 1, "kind": "subscription", "quantity": 5, "end": None}], [], {1: []}, today=today)
        self.assertEqual(g3[0]["kind"], "unused")


class Imports(unittest.TestCase):
    def test_matrix(self):
        rows = [[None] * 6, ["Logiciel", "Éditeur", "Licence", "Date Fin", "M. DUPONT", "Alice"], ["DraftSight", "Dassault", None, None, None, "n"],
                ["eDraw", "WonderShare", None, dt.datetime(2024, 10, 10), "n", None], [None, None, None, None, None, None]]
        out, err = rules.import_matrix(rows)
        self.assertIsNone(err)
        self.assertEqual(out[0], {"software": "DraftSight", "vendor": "Dassault", "kind_label": "", "end": None, "people": ["Alice"]})
        self.assertEqual((out[1]["end"], out[1]["people"]), ("2024-10-10", ["M. DUPONT"]))
        self.assertEqual(rules.detect_format(rows), "matrix")

    def test_m365_and_comparatif(self):
        rows = [[None, "Licences o365 Groupe"], ["Adresse e-mail de secours", "Nom complet", "Nom d'utilisateur", "Licences"],
                [None, "Alice A", "alice@ex.test", "Microsoft 365 Apps for business+Microsoft Teams"], [None, None, None, None]]
        out, err = rules.import_m365(rows)
        self.assertIsNone(err)
        self.assertEqual(out, [{"user": "Alice A", "upn": "alice@ex.test", "licenses": ["Microsoft 365 Apps for business", "Microsoft Teams"]}])
        self.assertEqual(rules.detect_format(rows), "m365")
        rows = [["Licences Office"], [None, "SL", "LB", "GN"], ["Licence Office 365 Business", None, None, "n"], ["Licence Office 365 Premium", "n", "n", None]]
        out, err = rules.import_comparatif(rows)
        self.assertEqual(out[1]["people"], ["SL", "LB"])
        self.assertEqual(rules.detect_format(rows), "comparatif")

    def test_grid(self):
        contracts = [{"id": 10, "software_id": 1, "label": "BS", "kind": "per-user", "quantity": 2}]
        assignments = [{"id": 1, "contract_id": 10, "subject_kind": "user", "subject": "Alice", "site": "siege"}]
        g = rules.grid(CAT, contracts, assignments, INV)
        self.assertEqual([c["name"] for c in g["columns"]], ["Office 365"])
        rows = {(r["kind"], r["subject"]): r for r in g["rows"]}
        self.assertEqual(rows[("user", "Alice")]["cells"][0]["assigned"], 1)
        self.assertTrue(rows[("host", "PC-01")]["cells"][0]["installed"])
        self.assertFalse(rows[("host", "PC-02")]["cells"][0]["installed"])
        self.assertIn(("user", "alice"), rows)  # utilisateur vu par l'inventaire


if __name__ == "__main__":
    unittest.main()
