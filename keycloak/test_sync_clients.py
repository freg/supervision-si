"""Tests de la logique pure de sync_clients.py (fusion des URL, jamais de retrait)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_clients import missing_clients, plan_changes  # noqa: E402

LIVE = [
    {"id": "u1", "clientId": "hub", "redirectUris": ["https://192.0.2.10:6443/*", "https://ajout-main/*"],
     "webOrigins": ["https://192.0.2.10:6443"]},
    {"id": "u2", "clientId": "portal", "redirectUris": ["https://192.0.2.10:6443/portal/*"], "webOrigins": ["https://192.0.2.10:6443"]},
]


class PlanTests(unittest.TestCase):
    def test_ajoute_seulement_le_manquant_et_garde_les_ajouts_manuels(self):
        rendered = [{"clientId": "hub",
                     "redirectUris": ["https://192.0.2.10:6443/*", "https://hub.exemple.fr/*"],
                     "webOrigins": ["https://192.0.2.10:6443", "https://hub.exemple.fr"]}]
        plan = plan_changes(rendered, LIVE)
        self.assertEqual(len(plan), 1)
        cid, live_id, updates = plan[0]
        self.assertEqual((cid, live_id), ("hub", "u1"))
        self.assertEqual(updates["redirectUris"], ["https://192.0.2.10:6443/*", "https://ajout-main/*", "https://hub.exemple.fr/*"])
        self.assertEqual(updates["webOrigins"], ["https://192.0.2.10:6443", "https://hub.exemple.fr"])

    def test_rien_a_faire_quand_tout_est_deja_present(self):
        rendered = [{"clientId": "portal", "redirectUris": ["https://192.0.2.10:6443/portal/*"], "webOrigins": ["https://192.0.2.10:6443"]}]
        self.assertEqual(plan_changes(rendered, LIVE), [])

    def test_client_absent_du_realm_vivant_ignore_et_signale(self):
        rendered = [{"clientId": "nouveau", "redirectUris": ["https://x/*"]}]
        self.assertEqual(plan_changes(rendered, LIVE), [])
        self.assertEqual(missing_clients(rendered, LIVE), ["nouveau"])

    def test_champ_absent_cote_vivant(self):
        rendered = [{"clientId": "portal", "webOrigins": ["https://192.0.2.10:6443", "+"]}]
        live = [{"id": "u2", "clientId": "portal"}]
        plan = plan_changes(rendered, live)
        self.assertEqual(plan[0][2], {"webOrigins": ["https://192.0.2.10:6443", "+"]})


if __name__ == "__main__":
    unittest.main()
