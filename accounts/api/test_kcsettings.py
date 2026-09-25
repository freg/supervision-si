import unittest
import kcsettings as ks

REALM = {"realm": "supervision-si", "displayName": "Hub", "ssoSessionIdleTimeout": 1800, "bruteForceProtected": False,
         "failureFactor": 30, "passwordPolicy": "", "clients": [], "smtpServer": {"password": "x"}, "loginTheme": "hub-dark"}


class KcSettingsTests(unittest.TestCase):
    def test_current_ne_garde_que_la_liste_blanche(self):
        cur = ks.current(REALM)
        self.assertNotIn("smtpServer", cur); self.assertNotIn("realm", cur); self.assertEqual(cur["loginTheme"], "hub-dark")

    def test_plan_changements_bornes_et_refus(self):
        changes, errors = ks.plan(REALM, {"ssoSessionIdleTimeout": "3600", "bruteForceProtected": "oui", "failureFactor": 30,
                                          "realm": "autre", "accessTokenLifespan": 5, "passwordPolicy": "length(12) and digits(1)"})
        self.assertEqual(set(changes), {"ssoSessionIdleTimeout", "bruteForceProtected", "passwordPolicy"})
        self.assertEqual(changes["ssoSessionIdleTimeout"], {"before": 1800, "after": 3600})
        self.assertTrue(changes["bruteForceProtected"]["after"])
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("non modifiable" in e for e in errors)); self.assertTrue(any("entre 60" in e for e in errors))
        self.assertEqual(ks.apply_body(changes)["passwordPolicy"], "length(12) and digits(1)")

    def test_policy_et_html_filtres(self):
        _, errors = ks.plan(REALM, {"passwordPolicy": "length(8); rm -rf", "displayNameHtml": "<script>x</script>"})
        self.assertEqual(len(errors), 2)

    def test_origin_plan(self):
        clients = [{"clientId": "hub", "id": "u1", "redirectUris": ["https://192.0.2.10:6443/*", "https://192.0.2.10:6443"], "webOrigins": ["https://192.0.2.10:6443"]},
                   {"clientId": "autre", "id": "u2", "redirectUris": ["https://x/*"], "webOrigins": []}]
        out, err = ks.origin_plan(clients, "https://192.0.2.10:6443", "https://hub.exemple.fr/")
        self.assertIsNone(err); self.assertEqual(len(out), 1)
        self.assertEqual(out[0][2]["redirectUris"][-2:], ["https://hub.exemple.fr/*", "https://hub.exemple.fr"])
        self.assertEqual(out[0][2]["webOrigins"], ["https://192.0.2.10:6443", "https://hub.exemple.fr"])
        out2, _ = ks.origin_plan([{"clientId": "hub", "id": "u1", **out[0][2]}], "https://192.0.2.10:6443", "https://hub.exemple.fr")
        self.assertEqual(out2, [])
        self.assertIsNotNone(ks.origin_plan(clients, "x", "https://hub.exemple.fr/chemin")[1])

    def test_ldap_providers_sans_secret(self):
        comps = [{"id": "c1", "name": "ldap", "providerId": "ldap", "config": {"connectionUrl": ["ldap://ldap.exemple.local:389"], "bindDn": ["cn=ro,dc=x"], "bindCredential": ["**********"], "enabled": ["true"]}},
                 {"id": "c2", "providerId": "kerberos", "config": {}}]
        out = ks.ldap_providers(comps)
        self.assertEqual(len(out), 1); self.assertEqual(out[0]["url"], "ldap://ldap.exemple.local:389")
        self.assertNotIn("bindCredential", str(out)); self.assertTrue(out[0]["enabled"])


if __name__ == "__main__":
    unittest.main()
