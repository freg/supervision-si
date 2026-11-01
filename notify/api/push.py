# -*- coding: utf-8 -*-
"""#796 : notifications poussées (Web Push) vers les téléphones et navigateurs abonnés au hub.

- clés VAPID (P-256) créées au premier usage dans NOTIFY_VAPID_FILE (défaut : à côté de la base, mode 0600), ou fournies par
  NOTIFY_VAPID_PRIVATE_PEM ; la clé publique est donnée au navigateur (applicationServerKey) ;
- chiffrement du message : RFC 8291 (aes128gcm, RFC 8188), signature VAPID : RFC 8292 (JWT ES256) -- sans dépendance
  en plus de cryptography et PyJWT, déjà présents ;
- envoi : POST sur l'adresse de l'abonnement (service de push du navigateur), 201 = remis ; 404 / 410 = abonnement
  périmé, supprimé.
Pur : b64u, b64u_dec, encrypt, vapid_headers, should_push."""
import base64
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SEV_RANK = {"info": 0, "warning": 1, "critical": 2}


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def b64u_dec(s):
    s = str(s or "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hmac(key, data):
    return hmac.new(key, data, hashlib.sha256).digest()


def _pub_bytes(pub):
    return pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def encrypt(plaintext, ua_public_b64, auth_b64, sender_private=None, salt=None, rs=4096):
    """Corps chiffré aes128gcm (RFC 8291) pour un abonnement ; sender_private / salt fixés seulement pour les tests."""
    ua_pub_raw = b64u_dec(ua_public_b64)
    auth = b64u_dec(auth_b64)
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_raw)
    priv = sender_private or ec.generate_private_key(ec.SECP256R1())
    as_pub_raw = _pub_bytes(priv.public_key())
    salt = salt or os.urandom(16)
    ecdh = priv.exchange(ec.ECDH(), ua_pub)
    prk_key = _hmac(auth, ecdh)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_pub_raw + as_pub_raw + b"\x01")
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    body = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    return salt + struct.pack("!IB", rs, len(as_pub_raw)) + as_pub_raw + body


def vapid_headers(endpoint, private_pem, public_raw, subject, now=None):
    import jwt
    u = urllib.parse.urlsplit(endpoint)
    token = jwt.encode({"aud": "%s://%s" % (u.scheme, u.netloc), "exp": int((now or time.time()) + 12 * 3600), "sub": subject},
                       private_pem, algorithm="ES256")
    return {"Authorization": "vapid t=%s, k=%s" % (token, b64u(public_raw))}


def should_push(severity, min_severity):
    return SEV_RANK.get(severity or "info", 0) >= SEV_RANK.get(min_severity or "critical", 2)


class Keys(object):
    """Paire VAPID : fichier PEM (créé au premier usage) ou variable d'environnement."""
    def __init__(self, path):
        self.path = path
        self._priv = None

    def private(self):
        if self._priv is None:
            pem = os.environ.get("NOTIFY_VAPID_PRIVATE_PEM", "").encode()
            if not pem and os.path.exists(self.path):
                with open(self.path, "rb") as fh:
                    pem = fh.read()
            if pem:
                self._priv = serialization.load_pem_private_key(pem, password=None)
            else:
                priv = ec.generate_private_key(ec.SECP256R1())
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                try:   # création exclusive : deux processus ne peuvent pas s'écraser la clé (les abonnements en dépendent)
                    fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    with open(self.path, "rb") as fh:
                        priv = serialization.load_pem_private_key(fh.read(), password=None)
                else:
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                self._priv = priv
        return self._priv

    def private_pem(self):
        return self.private().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())

    def public_raw(self):
        return _pub_bytes(self.private().public_key())


def send(sub, payload, keys, subject, ttl=86400, urgency="high", opener=urllib.request.urlopen):
    """Envoie un message à un abonnement -> (statut, erreur) ; statut 'ok', 'gone' (abonnement à supprimer) ou 'error'."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")[:3800]
    body = encrypt(data, sub["p256dh"], sub["auth"])
    headers = {"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": str(ttl), "Urgency": urgency}
    headers.update(vapid_headers(sub["endpoint"], keys.private_pem(), keys.public_raw(), subject))
    req = urllib.request.Request(sub["endpoint"], data=body, headers=headers, method="POST")
    try:
        with opener(req, timeout=20) as r:
            return ("ok", "") if r.status in (200, 201, 202) else ("error", "HTTP %d" % r.status)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return "gone", "abonnement expiré (HTTP %d)" % exc.code
        return "error", "service de push : HTTP %d %s" % (exc.code, exc.read(200).decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError) as exc:
        return "error", "service de push injoignable : %s" % str(getattr(exc, "reason", exc))[:150]
