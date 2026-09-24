# -*- coding: utf-8 -*-
import unittest

import vendors


class Graph(unittest.TestCase):
    def test_sync(self):
        calls = []

        def http(url, headers=None, data=None, timeout=20):
            calls.append(url)
            if "oauth2" in url:
                return {"access_token": "T"}
            if "subscribedSkus" in url:
                return {"value": [{"skuId": "s1", "skuPartNumber": "O365_BUSINESS_PREMIUM", "prepaidUnits": {"enabled": 7, "suspended": 0, "warning": 0}, "consumedUnits": 7, "capabilityStatus": "Enabled"},
                                  {"skuId": "s2", "skuPartNumber": "POWER_BI_STANDARD", "prepaidUnits": {"enabled": 4}, "consumedUnits": 3}]}
            if "users" in url and "skip" not in url:
                return {"value": [{"userPrincipalName": "b@ex.test", "assignedLicenses": [{"skuId": "s1"}, {"skuId": "s2"}]}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?skip=1"}
            return {"value": [{"userPrincipalName": "a@ex.test", "assignedLicenses": [{"skuId": "s1"}]}]}
        out = vendors.sync_microsoft_graph({"tenant": "t", "client_id": "c"}, "secret", http)
        self.assertEqual([o["label"] for o in out], ["Microsoft 365 Business Standard", "Microsoft Fabric (Free)"])
        self.assertEqual((out[0]["quantity"], out[0]["assigned"], out[0]["users"]), (7, 7, ["a@ex.test", "b@ex.test"]))
        self.assertEqual(out[1]["users"], ["b@ex.test"])
        self.assertEqual(len([c for c in calls if "users" in c]), 2)  # pagination suivie
        with self.assertRaises(RuntimeError):
            vendors.sync_microsoft_graph({"tenant": "t"}, "s", http)
        with self.assertRaises(RuntimeError):
            vendors.graph_token("t", "c", "s", lambda *a, **k: {"error": "invalid_client"})


if __name__ == "__main__":
    unittest.main()


class Account(unittest.TestCase):  # #602
    def test_ropc_and_device_code(self):
        seen, polls = [], []

        def http(url, headers=None, data=None, timeout=20):
            seen.append(data.decode() if data else url)
            if "devicecode" in url:
                return {"device_code": "D", "user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin", "expires_in": 900, "interval": 5, "message": "..."}
            if "grant_type=password" in (data or b"").decode():
                if "password=bad" in data.decode():
                    return {"error": "invalid_grant", "error_description": "AADSTS50076: Due to a configuration change made by your administrator, you must use multi-factor authentication"}
                return {"access_token": "A", "refresh_token": "R"}
            if "device_code" in (data or b"").decode():
                polls.append(1)
                return {"error": "authorization_pending"} if len(polls) < 2 else {"access_token": "A2", "refresh_token": "R2"}
            if "refresh_token" in (data or b"").decode():
                return {"access_token": "A3", "refresh_token": "R3"}
            return {}
        tok = vendors.ropc_token("t", "admin@exemple.test", "pw", http=http)
        self.assertEqual((tok["access_token"], tok["refresh_token"]), ("A", "R"))
        self.assertIn("client_id=" + vendors.PUBLIC_CLIENT_ID, seen[-1])
        with self.assertRaises(RuntimeError) as cm:
            vendors.ropc_token("t", "admin@exemple.test", "bad", http=http)
        self.assertIn("connexion par code", str(cm.exception))
        self.assertIn("AADSTS50076", str(cm.exception))
        dc = vendors.device_code_start("t", http=http)
        self.assertEqual(dc["user_code"], "ABCD-EFGH")
        self.assertEqual(vendors.device_code_poll("t", "D", http=http), ("pending", None))
        st, tok = vendors.device_code_poll("t", "D", http=http)
        self.assertEqual((st, tok["refresh_token"]), ("ok", "R2"))
        self.assertEqual(vendors.refresh_token("t", "R2", http=http)["access_token"], "A3")
        self.assertEqual(vendors.portal_url("microsoft-account", {}), "https://admin.microsoft.com/#/licenses")
