# -*- coding: utf-8 -*-
"""Tests #884 : reconstitution des sessions VPN à partir des relevés wireguard."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vpn  # noqa: E402


def rel(at, *peers):
    return ("ag1", at, {"interfaces": [{"interface": "wg0", "peers": [dict(public_key=k, name=n, endpoint=e, allowed_ips=["10.8.0.2/32"],
                                                                                 handshake_at=h, connected=c, rx=rx, tx=tx) for k, n, e, h, c, rx, tx in peers]}]})


class Sessions(unittest.TestCase):
    def test_sessions(self):
        r = [rel("2026-10-28T08:00:00Z", ("A", "Alice", "198.51.100.7:1", "2026-10-28T07:59:30Z", True, 100, 50)),
             rel("2026-10-28T08:02:00Z", ("A", "Alice", "198.51.100.7:1", "2026-10-28T08:01:40Z", True, 600, 250)),
             rel("2026-10-28T08:10:00Z", ("A", "Alice", "198.51.100.7:1", "2026-10-28T08:01:40Z", False, 600, 250)),
             rel("2026-10-28T09:00:00Z", ("A", "Alice", "203.0.113.5:9", "2026-10-28T08:59:50Z", True, 10, 5)),
             rel("2026-10-28T09:02:00Z", ("A", "Alice", "203.0.113.5:9", "2026-10-28T09:01:50Z", True, 30, 15))]
        s = vpn.sessions(r)
        self.assertEqual(len(s), 2)
        recente, ancienne = s
        self.assertTrue(recente["en_cours"])
        self.assertEqual((recente["origine"], recente["rx"], recente["tx"]), ("203.0.113.5:9", 20, 10))
        self.assertFalse(ancienne["en_cours"])
        self.assertEqual((ancienne["debut"], ancienne["fin"], ancienne["duree_s"], ancienne["rx"]),
                         ("2026-10-28T07:59:30Z", "2026-10-28T08:01:40Z", 130, 500))
        self.assertNotIn("rx0", ancienne)

    def test_retrait_et_remise_a_zero(self):
        r = [rel("2026-10-28T08:00:00Z", ("B", "", None, "2026-10-28T07:59:59Z", True, 900, 900)),
             rel("2026-10-28T08:02:00Z", ("B", "", None, "2026-10-28T08:01:59Z", True, 40, 30)),
             rel("2026-10-28T08:04:00Z")]
        s = vpn.sessions(r)
        self.assertEqual((len(s), s[0]["rx"], s[0]["en_cours"]), (1, 40, False))


if __name__ == "__main__":
    unittest.main()
