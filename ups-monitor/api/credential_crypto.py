"""
Chiffrement des mots de passe des onduleurs stockés (livraison #415) --
enveloppe `shared/secret_crypto.py`, même motif que
`snmp/api/credential_crypto.py` (#213) et `ssh-tunnels/api/credential_crypto.py`
(#210) : phrase de passe et sel (base64) fournis EN CONTINU au conteneur
(`UPS_CRED_PASSPHRASE`, `UPS_CRED_SALT`), un mot de passe devant être
déchiffré à chaque relevé, bien après le lancement.

Différence ASSUMÉE avec snmp : tuile demandée en urgence, donc si les
deux variables sont absentes, les mots de passe sont stockés EN CLAIR
dans la base (volume /data) et `/status` le signale (`secrets_encrypted:
false`) -- jamais un refus d'enregistrer qui bloquerait la mise en route.
Dès que les variables sont fournies, les nouveaux enregistrements sont
chiffrés ; les anciens sont rechiffrés à leur prochaine modification
(voir README pour rechiffrer d'un coup).

Règle absolue reprise de secret_crypto : jamais la phrase de passe ni un
mot de passe en clair dans un log.
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
    except ImportError:  # `cryptography` absent : chiffrement indisponible, clair signalé
        sc = None

_log = logging.getLogger("ups_credential_crypto")

PREFIX = "enc:"


def is_configured():
    return bool(sc) and bool(os.environ.get("UPS_CRED_PASSPHRASE", "").strip()) and bool(os.environ.get("UPS_CRED_SALT", "").strip())


def _passphrase_and_salt():
    passphrase = os.environ.get("UPS_CRED_PASSPHRASE", "").strip()
    salt_b64 = os.environ.get("UPS_CRED_SALT", "").strip()
    try:
        salt = base64.b64decode(salt_b64)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"UPS_CRED_SALT invalide (pas du base64 valide) : {exc}")
    return passphrase, salt


def protect(plaintext):
    """Valeur à stocker : `enc:<jeton>` si le chiffrement est configuré,
    sinon la valeur telle quelle. Une valeur vide reste vide."""
    if not plaintext:
        return ""
    if not is_configured():
        return plaintext
    passphrase, salt = _passphrase_and_salt()
    return PREFIX + sc.encrypt_value(plaintext, passphrase, salt)


def reveal(stored):
    """Valeur en clair depuis la base. Un jeton chiffré sans configuration
    (phrase de passe retirée) lève ValueError -- le relevé échouera avec un
    message explicite plutôt qu'avec un mot de passe faux."""
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        return stored
    if not sc:
        raise ValueError("mot de passe chiffré mais module cryptography indisponible")
    if not is_configured():
        raise ValueError("mot de passe chiffré mais UPS_CRED_PASSPHRASE / UPS_CRED_SALT absents")
    passphrase, salt = _passphrase_and_salt()
    try:
        return sc.decrypt_value(stored[len(PREFIX):], passphrase, salt)
    except sc.SecretCryptoError as exc:
        raise ValueError(f"déchiffrement du mot de passe échoué (phrase de passe changée ?) : {exc}")


def is_protected(stored):
    return bool(stored) and stored.startswith(PREFIX)
