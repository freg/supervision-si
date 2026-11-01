# -*- coding: utf-8 -*-
"""#796 : Web Push -- chiffrement RFC 8291 (vecteur de test de l'annexe A), VAPID, seuils, envoi simulé."""
import json
import os
import tempfile
import unittest
import urllib.error

from cryptography.hazmat.primitives.asymmetric import ec

import push as P

# RFC 8291, annexe A
PLAIN = b"When I grow up, I want to be a watermelon"
AS_PRIV = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
UA_PUB = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
SALT = "DGv6ra1nlYgDCS1FRnbzlw"
EXPECTED = ("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_y"
            "l95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")


class Pur(unittest.TestCase):
    def test_vecteur_rfc8291(self):
        priv = ec.derive_private_key(int.from_bytes(P.b64u_dec(AS_PRIV), "big"), ec.SECP256R1())
        out = P.encrypt(PLAIN, UA_PUB, AUTH, sender_private=priv, salt=P.b64u_dec(SALT))
        self.assertEqual(P.b64u(out), EXPECTED)

    def test_vapid_et_seuils(self):
        import jwt
        keys = P.Keys(os.path.join(tempfile.mkdtemp(), "vapid.pem"))
        pub = keys.public_raw()
        self.assertEqual((len(pub), pub[0]), (65, 4))
        self.assertEqual(oct(os.stat(keys.path).st_mode & 0o777), "0o600")
        h = P.vapid_headers("https://fcm.googleapis.com/fcm/send/abc", keys.private_pem(), pub, "mailto:admin@example.org", now=1000)
        t = h["Authorization"].split("t=")[1].split(",")[0]
        claims = jwt.decode(t, keys.private().public_key(), algorithms=["ES256"], audience="https://fcm.googleapis.com", options={"verify_exp": False})
        self.assertEqual((claims["aud"], claims["exp"], claims["sub"]), ("https://fcm.googleapis.com", 1000 + 43200, "mailto:admin@example.org"))
        self.assertTrue(P.should_push("critical", "critical"))
        self.assertFalse(P.should_push("warning", "critical"))
        self.assertTrue(P.should_push("warning", "warning"))
        self.assertFalse(P.should_push(None, "warning"))
        self.assertEqual(P.Keys(keys.path).public_raw(), pub)          # clé relue, pas régénérée

    def test_envoi_simule(self):
        keys = P.Keys(os.path.join(tempfile.mkdtemp(), "vapid.pem"))
        ua = ec.generate_private_key(ec.SECP256R1())
        sub = {"endpoint": "https://push.example.org/x", "p256dh": P.b64u(P._pub_bytes(ua.public_key())), "auth": P.b64u(os.urandom(16))}
        seen = {}

        class R(object):
            status = 201
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def ok(req, timeout=20):
            seen["h"] = dict(req.header_items())
            seen["len"] = len(req.data)
            return R()
        self.assertEqual(P.send(sub, {"title": "t", "body": "b"}, keys, "mailto:a@example.org", opener=ok), ("ok", ""))
        self.assertEqual(seen["h"]["Content-encoding"], "aes128gcm")
        self.assertTrue(seen["h"]["Authorization"].startswith("vapid t="))

        def gone(req, timeout=20):
            raise urllib.error.HTTPError(sub["endpoint"], 410, "Gone", {}, None)
        self.assertEqual(P.send(sub, {"title": "t"}, keys, "mailto:a@example.org", opener=gone)[0], "gone")


if __name__ == "__main__":
    unittest.main()
