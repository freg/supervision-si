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
