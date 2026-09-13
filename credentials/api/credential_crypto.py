# -*- coding: utf-8 -*-
"""Chiffrement des mots de passe des accès d'équipements (livraison #498)
-- enveloppe `shared/secret_crypto.py`, même motif que ups-monitor (#415),
snmp (#213) et ssh-tunnels (#210) : phrase de passe fournie EN CONTINU au
conteneur (`CREDENTIALS_PASSPHRASE`), un mot de passe devant être révélé
à chaque relevé d'un consommateur, bien après le lancement.

Différence avec ups-monitor : ce service EST le coffre des accès du hub,
donc **sans phrase de passe il refuse d'enregistrer un mot de passe**
(503 « chiffrement non configuré ») plutôt que de le stocker en clair.
`sync-env.py` génère la phrase (placeholder `change-me`) au déploiement.

Le SEL est généré une fois et conservé à côté de la base
(`/data/salt.b64`, sauvegardé avec elle, jamais régénéré) ; `CREDENTIALS_SALT`
(base64) le surcharge si la personne préfère le garder dans .env.

Règle absolue : jamais la phrase de passe ni un mot de passe en clair dans
un log.
"""
import base64
import logging
import os

try:
    import secret_crypto as sc
except ImportError:  # dépôt de développement : shared/ n'est pas sur le chemin
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared"))
    try:
        import secret_crypto as sc
    except ImportError:
        sc = None

_log = logging.getLogger("credentials.crypto")

PREFIX = "enc:"


def _passphrase():
    return os.environ.get("CREDENTIALS_PASSPHRASE", "").strip()


def _salt_path():
    return os.path.join(os.environ.get("CREDENTIALS_DATA_DIR", "/data"), "salt.b64")


def _salt():
    """Sel : CREDENTIALS_SALT (base64) sinon fichier /data/salt.b64, créé
    au premier besoin (16 octets aléatoires)."""
    env = os.environ.get("CREDENTIALS_SALT", "").strip()
    if env:
        try:
            return base64.b64decode(env)
        except (ValueError, TypeError) as exc:
            raise ValueError("CREDENTIALS_SALT invalide (pas du base64) : %s" % exc)
    path = _salt_path()
    try:
        with open(path, "rb") as fh:
            return base64.b64decode(fh.read().strip())
    except FileNotFoundError:
        salt = sc.generate_salt() if sc else os.urandom(16)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(base64.b64encode(salt))
        os.chmod(path, 0o600)
        _log.info("sel de chiffrement généré dans %s (à sauvegarder avec la base, jamais régénérer)", path)
        return salt


def is_configured():
    return bool(sc) and bool(_passphrase())


def is_protected(stored):
    return bool(stored) and stored.startswith(PREFIX)


def protect(plaintext):
    """`enc:<jeton>` ; lève ValueError si le chiffrement n'est pas
    configuré (jamais de stockage en clair ici). Vide reste vide."""
    if not plaintext:
        return ""
    if not is_configured():
        raise ValueError("chiffrement non configuré (CREDENTIALS_PASSPHRASE absente ou module cryptography indisponible)")
    return PREFIX + sc.encrypt_value(plaintext, _passphrase(), _salt())


def reveal(stored):
    if not stored:
        return ""
    if not is_protected(stored):
        return stored  # base antérieure / import manuel : toléré en lecture, rechiffré par /reencrypt
    if not is_configured():
        raise ValueError("mot de passe chiffré mais CREDENTIALS_PASSPHRASE absente")
    try:
        return sc.decrypt_value(stored[len(PREFIX):], _passphrase(), _salt())
    except sc.SecretCryptoError as exc:
        raise ValueError("déchiffrement échoué (phrase de passe ou sel changés ?) : %s" % exc)
