"""
Chiffrement des mots de passe SSH stockés (livraison #210, backlog
item 12 -- "gestion SÉCURISÉE de couples utilisateur/mot de passe,
jamais en clair"). Enveloppe `secret_crypto.py` (copié dans cette
image au même titre que `log_buffer.py`/`version_endpoint.py`, voir
Dockerfile) -- phrase de passe et sel fournis à CE CONTENEUR via des
variables d'environnement (`SSH_TUNNELS_CRED_PASSPHRASE`,
`SSH_TUNNELS_CRED_SALT` en base64), conservés en mémoire pour toute la
durée de vie du conteneur.

**Différence assumée avec le chantier de chiffrement des secrets de
démarrage (#202-206)** : ces mots de passe SSH doivent pouvoir être
déchiffrés BIEN APRÈS le déploiement -- au moment où quelqu'un démarre
effectivement un tunnel/montage par mot de passe, potentiellement des
heures ou des jours après `docker compose up` -- contrairement aux
secrets de démarrage (`.env.encrypted`) qui ne sont déchiffrés QU'UNE
FOIS, au lancement, jamais conservés ensuite. Ce module a donc besoin
de la phrase de passe DISPONIBLE EN CONTINU dans l'environnement de ce
conteneur, pas seulement au démarrage. Choix cohérent avec le reste de
ce projet : d'autres secrets (mots de passe de base de données, clés
d'API...) persistent déjà dans l'environnement d'un conteneur pour
toute sa durée de vie -- cette propriété n'est donc pas une régression
par rapport à ce qui existe déjà ailleurs, seulement étendue à ce
nouveau cas d'usage précis.
"""
import base64
import logging
import os

import secret_crypto as sc

# Traces DEBUG (livraison #215) -- même RÈGLE ABSOLUE que
# secret_crypto.py : jamais la phrase de passe, jamais le mot de
# passe en clair dans un log.
_log = logging.getLogger("ssh_tunnels_credential_crypto")


class CredentialCryptoNotConfigured(Exception):
    pass


def _get_passphrase_and_salt():
    passphrase = os.environ.get("SSH_TUNNELS_CRED_PASSPHRASE", "").strip()
    salt_b64 = os.environ.get("SSH_TUNNELS_CRED_SALT", "").strip()
    if not passphrase or not salt_b64:
        _log.debug("_get_passphrase_and_salt : NON CONFIGURÉ -- SSH_TUNNELS_CRED_PASSPHRASE ou SSH_TUNNELS_CRED_SALT manquant")
        raise CredentialCryptoNotConfigured(
            "SSH_TUNNELS_CRED_PASSPHRASE et SSH_TUNNELS_CRED_SALT doivent être configurés "
            "pour utiliser l'authentification par mot de passe -- voir ssh-tunnels/README.md"
        )
    try:
        salt = base64.b64decode(salt_b64)
    except (ValueError, TypeError) as exc:
        _log.debug("_get_passphrase_and_salt : SSH_TUNNELS_CRED_SALT invalide (pas du base64 valide) -- %s", exc)
        raise CredentialCryptoNotConfigured(f"SSH_TUNNELS_CRED_SALT invalide (pas du base64 valide) : {exc}")
    _log.debug("_get_passphrase_and_salt : configuration trouvée (sel de %d octets, jamais la phrase de passe elle-même ici)", len(salt))
    return passphrase, salt


def encrypt_password(plaintext_password):
    """Lève CredentialCryptoNotConfigured si les variables
    d'environnement ne sont pas prêtes -- JAMAIS un mot de passe
    stocké en clair faute de configuration (voir app.py, qui refuse
    la création d'une connexion par mot de passe dans ce cas plutôt
    que de se rabattre silencieusement sur du texte en clair)."""
    _log.debug("encrypt_password : démarré")
    passphrase, salt = _get_passphrase_and_salt()
    result = sc.encrypt_value(plaintext_password, passphrase, salt)
    _log.debug("encrypt_password : terminé (jeton produit)")
    return result


def decrypt_password(encrypted_token):
    _log.debug("decrypt_password : démarré")
    passphrase, salt = _get_passphrase_and_salt()
    try:
        result = sc.decrypt_value(encrypted_token, passphrase, salt)
    except sc.SecretCryptoError:
        _log.debug("decrypt_password : ÉCHEC -- voir secret_crypto pour le détail (phrase de passe incorrecte ou jeton corrompu)")
        raise
    _log.debug("decrypt_password : succès")
    return result
