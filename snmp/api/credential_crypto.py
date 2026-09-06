"""
Chiffrement des communautés SNMP stockées (livraison #213, backlog
item 13, volet 2 -- "gestion des paramètres d'accès sécurisés").
Enveloppe `secret_crypto.py` (#202-206) -- même motif que
`ssh-tunnels/api/credential_crypto.py` (#210), adapté à ce module :
phrase de passe et sel fournis à CE CONTENEUR via des variables
d'environnement (`SNMP_CRED_PASSPHRASE`, `SNMP_CRED_SALT` en base64),
conservés en mémoire pour toute la durée de vie du conteneur -- une
communauté stockée doit pouvoir être déchiffrée BIEN APRÈS le
déploiement (au moment où quelqu'un interroge effectivement une
cible), pas seulement au lancement (voir le raisonnement complet dans
ssh-tunnels/README.md, section authentification par mot de passe --
même différence assumée ici avec les secrets de démarrage).
"""
import base64
import logging
import os

import secret_crypto as sc

# Traces DEBUG (livraison #215) -- même RÈGLE ABSOLUE que
# secret_crypto.py et ssh-tunnels/api/credential_crypto.py : jamais
# la phrase de passe, jamais la communauté en clair dans un log.
_log = logging.getLogger("snmp_credential_crypto")


class CredentialCryptoNotConfigured(Exception):
    pass


def _get_passphrase_and_salt():
    passphrase = os.environ.get("SNMP_CRED_PASSPHRASE", "").strip()
    salt_b64 = os.environ.get("SNMP_CRED_SALT", "").strip()
    if not passphrase or not salt_b64:
        _log.debug("_get_passphrase_and_salt : NON CONFIGURÉ -- SNMP_CRED_PASSPHRASE ou SNMP_CRED_SALT manquant")
        raise CredentialCryptoNotConfigured(
            "SNMP_CRED_PASSPHRASE et SNMP_CRED_SALT doivent être configurés "
            "pour enregistrer des cibles SNMP -- voir snmp/README.md"
        )
    try:
        salt = base64.b64decode(salt_b64)
    except (ValueError, TypeError) as exc:
        _log.debug("_get_passphrase_and_salt : SNMP_CRED_SALT invalide (pas du base64 valide) -- %s", exc)
        raise CredentialCryptoNotConfigured(f"SNMP_CRED_SALT invalide (pas du base64 valide) : {exc}")
    _log.debug("_get_passphrase_and_salt : configuration trouvée (sel de %d octets, jamais la phrase de passe elle-même ici)", len(salt))
    return passphrase, salt


def encrypt_community(plaintext_community):
    _log.debug("encrypt_community : démarré")
    passphrase, salt = _get_passphrase_and_salt()
    result = sc.encrypt_value(plaintext_community, passphrase, salt)
    _log.debug("encrypt_community : terminé (jeton produit)")
    return result


def decrypt_community(encrypted_token):
    _log.debug("decrypt_community : démarré")
    passphrase, salt = _get_passphrase_and_salt()
    try:
        result = sc.decrypt_value(encrypted_token, passphrase, salt)
    except sc.SecretCryptoError:
        _log.debug("decrypt_community : ÉCHEC -- voir secret_crypto pour le détail (phrase de passe incorrecte ou jeton corrompu)")
        raise
    _log.debug("decrypt_community : succès")
    return result
