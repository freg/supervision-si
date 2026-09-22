# -*- coding: utf-8 -*-
"""Sondeur Nebula (livraison #546) : relevé, transitions en base, tableau de santé -- client Nebula simulé."""
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))
TMP = tempfile.mkdtemp()
os.environ["NEBULA_DB_PATH"] = os.path.join(TMP, "nebula.db")
os.environ["NEBULA_POLL_DISABLED"] = "1"
os.environ["NEBULA_API_KEY"] = "x"
import app as app_mod  # noqa: E402


class Fake:
    def __init__(self):
        self.status = [{"devId": "d1", "currentStatus": "online"}, {"devId": "d2", "currentStatus": "online"}]
    def list_organizations(self): return [{"orgId": "o" * 16, "mode": "PRO"}]
    def list_sites(self, org): return [{"siteId": "s" * 16, "name": "Site test"}]
    def list_devices_from_org(self, org): return [{"siteId": "s" * 16, "devices": [{"devId": "d1", "name": "Borne 1", "model": "WBE660S", "type": "AP"}, {"devId": "d2", "name": "Coeur", "model": "XS3800-28", "type": "SW"}]}]
    def get_online_status(self, site, device_type=None): return self.status


class Poll(unittest.TestCase):
    def test_poll_and_board(self):
        fake = Fake()
        t0 = int(time.time()) - 600
        r = app_mod.poll_once(fake, now=t0)
        self.assertEqual(r, {"sites": 1, "devices": 2, "transitions": 2})  # premiers relevés = transitions depuis None
        r = app_mod.poll_once(fake, now=t0 + 60)
        self.assertEqual(r["transitions"], 0)
        fake.status[0]["currentStatus"] = "offline"
        r = app_mod.poll_once(fake, now=t0 + 120)
        self.assertEqual(r["transitions"], 1)
        c = app_mod.app.test_client()
        b = c.get("/sites/%s/health-board?hours=1" % ("s" * 16)).get_json()
        self.assertEqual(b["offline"], 1)
        self.assertEqual(b["phrases"][0][:22], "Borne 1 (WBE660S) : ho")
        self.assertEqual(b["devices"][0]["status"], "offline")
        t = c.get("/sites/%s/transitions?hours=1" % ("s" * 16)).get_json()["transitions"]
        self.assertEqual(t[0]["name"], "Borne 1"); self.assertEqual(t[0]["to_status"], "offline")
        st = c.get("/poll/status").get_json()
        self.assertEqual(len(st["runs"]), 3)
        all_ = c.get("/health-board").get_json()
        self.assertEqual(all_["sites"][0]["site_name"], "Site test")


if __name__ == "__main__":
    unittest.main()
