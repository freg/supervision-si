import unittest
import events as ev

RAW = [
    {"time": 1758799386430, "type": "LOGIN_ERROR", "clientId": "supervision-hub", "ipAddress": "203.0.113.9", "error": "invalid_redirect_uri", "details": {"redirect_uri": "https://hub.exemple.fr/"}},
    {"time": 1758799486430, "type": "LOGIN", "clientId": "supervision-hub", "userId": "u-1", "ipAddress": "192.0.2.20", "details": {"username": "francois", "auth_method": "openid-connect"}},
    {"time": 1758799286430, "type": "CLIENT_LOGIN_ERROR", "clientId": "supervision-si-service", "ipAddress": "192.0.2.31", "error": "client_not_found"},
]


class EventsTests(unittest.TestCase):
    def test_normalize_trie_et_traduit(self):
        rows = ev.normalize(RAW)
        self.assertEqual([r["type"] for r in rows], ["LOGIN", "LOGIN_ERROR", "CLIENT_LOGIN_ERROR"])
        self.assertEqual(rows[0]["user"], "francois"); self.assertTrue(rows[0]["ok"])
        self.assertIn("origine du hub", rows[1]["reason"]); self.assertFalse(rows[1]["ok"])
        self.assertEqual(rows[2]["reason"], "client inconnu")
        self.assertTrue(rows[0]["at"].startswith("2025-09-25") or rows[0]["at"].startswith("2025-09-2"))

    def test_filter_debut_de_mot_et_erreurs(self):
        rows = ev.normalize(RAW)
        self.assertEqual(len(ev.filter_rows(rows, "errors")), 2)
        self.assertEqual(len(ev.filter_rows(rows, "LOGIN")), 1)
        self.assertEqual([r["user"] for r in ev.filter_rows(rows, "", "fran")], ["francois"])
        self.assertEqual(len(ev.filter_rows(rows, "", "203.0")), 1)
        self.assertEqual(len(ev.filter_rows(rows, "", "ncois")), 0)

    def test_summary(self):
        s = ev.summary(ev.normalize(RAW))
        self.assertEqual((s["total"], s["logins"], s["errors"], s["users"], s["ips"]), (3, 1, 2, 1, 3))
        self.assertEqual(s["last_error"]["type"], "LOGIN_ERROR")

    def test_config_plan(self):
        cfg, changed = ev.config_plan({"eventsEnabled": False, "enabledEventTypes": ["LOGIN"], "adminEventsEnabled": False})
        self.assertTrue(changed); self.assertTrue(cfg["eventsEnabled"]); self.assertIn("LOGIN_ERROR", cfg["enabledEventTypes"])
        self.assertEqual(cfg["eventsExpiration"], 30 * 86400); self.assertFalse(cfg["adminEventsEnabled"])
        cfg2, changed2 = ev.config_plan(cfg)
        self.assertFalse(changed2)
        st = ev.config_state({"eventsEnabled": True, "eventsExpiration": 86400 * 7})
        self.assertEqual((st["enabled"], st["expiration_days"], st["types_all"]), (True, 7, True))


if __name__ == "__main__":
    unittest.main()
