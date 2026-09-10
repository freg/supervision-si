# -*- coding: utf-8 -*-
"""Tests purs du protocole du bastion si-proxy (#452)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from siproxy import proto  # noqa: E402


class TestHello(unittest.TestCase):
    def test_roundtrip(self):
        obj = {"role": "client", "type": "data", "token": "t", "kind": "connect", "target": "192.168.1.1:443"}
        self.assertEqual(proto.decode_line(proto.encode_line(obj).rstrip(b"\n")), obj)
        self.assertIsNone(proto.decode_line(b"pas du json"))
        self.assertIsNone(proto.decode_line(b"[1,2,3]"))  # pas un objet

    def test_valid_hello(self):
        ok, _ = proto.valid_hello({"role": "host", "type": "control", "token": "s"}, "s", roles=("host",))
        self.assertTrue(ok)
        self.assertEqual(proto.valid_hello({"role": "host", "type": "control", "token": "x"}, "s", roles=("host",))[1], "jeton refusé")
        self.assertEqual(proto.valid_hello({"role": "client", "type": "control", "token": "s"}, "s", roles=("host",))[1], "role inconnu")
        ok, why = proto.valid_hello({"role": "client", "type": "data", "token": "s", "kind": "connect", "target": "nope"}, "s", roles=("client",))
        self.assertFalse(ok)
        self.assertIn("mal formée", why)
        ok, _ = proto.valid_hello({"role": "client", "type": "data", "token": "s", "kind": "shell"}, "s", roles=("client",))
        self.assertTrue(ok)
        self.assertEqual(proto.valid_hello({"role": "client", "type": "data", "token": "s", "kind": "sftp"}, "s", roles=("client",))[1], "kind inconnu")

    def test_empty_token_refused(self):
        self.assertFalse(proto.valid_hello({"role": "host", "type": "control", "token": ""}, "", roles=("host",))[0])


class TestTarget(unittest.TestCase):
    def test_split(self):
        self.assertEqual(proto.split_target("192.168.1.10:443"), ("192.168.1.10", 443, None))
        self.assertEqual(proto.split_target("hub.local:8443"), ("hub.local", 8443, None))
        self.assertEqual(proto.split_target("[fe80::1]:22")[0], "fe80::1")
        self.assertEqual(proto.split_target("[fe80::1]:22")[1], 22)
        self.assertIsNotNone(proto.split_target("x:99999")[2])
        self.assertIsNotNone(proto.split_target("noport")[2])
        self.assertIsNotNone(proto.split_target(None)[2])

    def test_allowed(self):
        self.assertTrue(proto.target_allowed("192.168.1.10")[0])
        self.assertTrue(proto.target_allowed("hub.local")[0])
        self.assertFalse(proto.target_allowed("127.0.0.1")[0])
        self.assertFalse(proto.target_allowed("169.254.169.254")[0])   # métadonnées cloud
        self.assertFalse(proto.target_allowed("::1")[0])
        # liste de refus par configuration
        ok, why = proto.target_allowed("10.9.9.9", extra_deny=["10.0.0.0/8"])
        self.assertFalse(ok)
        self.assertIn("configuration", why)
        self.assertTrue(proto.target_allowed("192.168.1.10", extra_deny=["10.0.0.0/8"])[0])


class TestProxyParse(unittest.TestCase):
    def test_connect(self):
        m, t, v, is_c = proto.parse_proxy_request(b"CONNECT hub.local:443 HTTP/1.1\r\nHost: hub.local\r\n\r\n")
        self.assertTrue(is_c)
        self.assertEqual((m, t), ("CONNECT", "hub.local:443"))

    def test_absolute_get(self):
        m, t, v, is_c = proto.parse_proxy_request(b"GET http://192.168.1.5/x HTTP/1.1\r\n\r\n")
        self.assertFalse(is_c)
        self.assertEqual(m, "GET")
        hostport, path = proto.absolute_uri_target(t)
        self.assertEqual((hostport, path), ("192.168.1.5:80", "/x"))
        self.assertEqual(proto.absolute_uri_target("http://h:8080/a/b")[0], "h:8080")
        self.assertEqual(proto.absolute_uri_target("https://x/")[0], None)

    def test_garbage(self):
        self.assertEqual(proto.parse_proxy_request(b"\r\n\r\n")[0], None)


class TestRedact(unittest.TestCase):
    def test_redact(self):
        self.assertEqual(proto.redact({"cmd": "open", "token": "secret", "session": 3}), {"cmd": "open", "token": "***", "session": 3})


if __name__ == "__main__":
    unittest.main()
