# -*- coding: utf-8 -*-
"""Tests #868 : test de connectivité depuis le hub (validation, analyse ping, repli TCP, lot)."""
import socket
import threading
import unittest

import ping


class Ping(unittest.TestCase):
    def setUp(self):
        ping._cache.clear()

    def test_clean_host(self):
        self.assertEqual(ping.clean_host("192.0.2.4"), "192.0.2.4")
        self.assertEqual(ping.clean_host(" 192.0.2.4:22 "), "192.0.2.4")
        self.assertEqual(ping.clean_host("192.0.2.4/24"), "192.0.2.4")
        self.assertEqual(ping.clean_host("[2001:db8::1]:443"), "2001:db8::1")
        self.assertEqual(ping.clean_host("2001:db8::1"), "2001:db8::1")
        self.assertEqual(ping.clean_host("srv-1.exemple.fr"), "srv-1.exemple.fr")
        for bad in ("", "-c 99 x", "a;rm -rf /", "$(id)", "a b", None, "x" * 300):
            self.assertIsNone(ping.clean_host(bad), bad)

    def test_parse_ping(self):
        out = "2 packets transmitted, 2 received, 0% packet loss, time 1001ms\nrtt min/avg/max/mdev = 0.4/0.52/0.6/0.1 ms"
        self.assertEqual(ping.parse_ping(out), (2, 2, 0.5))
        self.assertEqual(ping.parse_ping("2 packets transmitted, 0 received, 100% packet loss")[:2], (0, 2))
        self.assertEqual(ping.parse_ping(""), (0, 0, None))

    def test_invalide_sans_appel(self):
        r = ping.ping("a;id")
        self.assertEqual(r["state"], "invalide")

    def test_tcp_ouvert_et_ferme(self):
        srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
        port = srv.getsockname()[1]
        threading.Thread(target=lambda: srv.accept(), daemon=True).start()
        r = ping.tcp("127.0.0.1", ports=(port,))
        self.assertTrue(r["ok"]); self.assertEqual(r["port"], port)
        srv.close()
        r = ping.tcp("127.0.0.1", ports=(port,))   # fermé -> RST : hôte vivant
        self.assertTrue(r["ok"]); self.assertIsNone(r["port"])

    def test_icmp_absent_repli_tcp(self):
        orig = ping.icmp
        ping.icmp = lambda ip: {"ok": None, "error": "commande ping absente"}
        try:
            r = ping.ping("127.0.0.1")
        finally:
            ping.icmp = orig
        self.assertTrue(r["ok"]); self.assertTrue(r["via"].startswith("tcp"))

    def test_lot_dedoublonne_et_borne(self):
        ping.ping = ping.ping  # noqa
        orig = ping.ping
        ping.ping = lambda h, now=None: {"host": h}
        try:
            r = ping.ping_many(["a", "a", "b"] + ["h%d" % i for i in range(100)])
        finally:
            ping.ping = orig
        self.assertEqual(len(r), ping.MAX_BATCH)
        self.assertEqual([x["host"] for x in r[:2]], ["a", "b"])

    def test_limite_par_client(self):
        ping._rate.clear()
        self.assertTrue(ping.allow("c1", 100, now=1000))
        self.assertFalse(ping.allow("c1", 30, now=1010))
        self.assertTrue(ping.allow("c2", 30, now=1010))
        self.assertTrue(ping.allow("c1", 30, now=1061))   # fenêtre d'une minute écoulée


if __name__ == "__main__":
    unittest.main()
