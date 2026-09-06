"""
Chiffrement des secrets de DÉMARRAGE (livraison #202, "urgence"
matrice de risque, points 2/3 -- "mots de passe stockés en clair ->
chiffrer et imposer une réinjection de la clé à chaque déploiement",
"clés de connexion SSH non chiffrées : chiffrer avec la clé d'admin").

**Conclusion du point 4 de la même urgence (déjà actée avec la
personne, #198)** : ces secrets de DÉMARRAGE (mots de passe .env,
clés SSH) restent INDÉPENDANTS du coffre-fort et de Keycloak, pour
éviter la boucle identifiée (coffre-fort accessible seulement via
Keycloak déjà démarré -- si un secret nécessaire à DÉMARRER Keycloak
lui-même était dans le coffre-fort, blocage total). Une clé maître,
fournie fraîchement à CHAQUE déploiement (jamais stockée sur disque,
jamais dans le coffre-fort), sert à chiffrer/déchiffrer :
- les mots de passe/secrets du `.env` (point 2)
- les clés privées SSH de `ssh-tunnels` (point 3)

**Algorithme** : PBKDF2-HMAC-SHA256, 600 000 itérations -- valeur
vérifiée via l'OWASP Password Storage Cheat Sheet (recommandation
actuelle pour PBKDF2-HMAC-SHA256, https://cheatsheetseries.owasp.org/
cheatsheets/Password_Storage_Cheat_Sheet.html, consultée le jour de
cette livraison -- jamais un nombre choisi de mémoire) dérive une clé
de chiffrement à partir de la phrase de passe fournie + un SEL (non
secret, peut être stocké en clair aux côtés des données chiffrées --
son rôle est d'empêcher une attaque par table précalculée, pas de
protéger la confidentialité à lui seul -- LA phrase de passe reste le
seul secret réel). Fernet (implémentation `cryptography`, AES-128-CBC
+ HMAC-SHA256 authentifié -- jamais de padding oracle, contrairement
à un AES-CBC "nu") pour le chiffrement symétrique effectif.

**⚠️ Portée VOLONTAIREMENT LIMITÉE de cette livraison** : uniquement
les primitives de chiffrement elles-mêmes, testées de façon
exhaustive ci-après. PAS ENCORE le câblage dans `scripts/run.sh`, PAS
ENCORE la migration des secrets RÉELS déjà en place (`.env`, clés SSH
existantes). Un sujet où une erreur peut rendre des secrets
définitivement inaccessibles mérite d'être validé étape par étape,
jamais livré d'un bloc en fin de session -- ces primitives sont la
fondation sur laquelle les étapes suivantes s'appuieront, une fois
CELLE-CI éprouvée.

**Rappel important, à ne jamais perdre de vue pour les étapes
suivantes** : si la phrase de passe maître est perdue, TOUT ce qui a
été chiffré avec devient DÉFINITIVEMENT irrécupérable -- aucune
porte dérobée n'existe ni ne doit exister dans ce module. La
procédure de sauvegarde/récupération de cette phrase de passe (PRA)
reste à documenter dans le volet Cyber (voir point 4, toujours pas
transcrit en documentation -- prochaine étape logique après celle-ci).
"""
import base64
import logging
import os
import time

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITERATIONS = 600_000
SALT_SIZE_BYTES = 16

# Traces DEBUG à chaque étape sensible (livraison #215, demandé
# explicitement -- "rien ne doit être silencieux... identifier vite
# les points de blocage"). RÈGLE ABSOLUE, jamais transgressée dans ce
# module : ni la phrase de passe, ni le texte en clair, ni le
# contenu déchiffré n'apparaissent JAMAIS dans un message de log, à
# AUCUN niveau -- seules la LONGUEUR, la DURÉE et l'ISSUE (succès/
# échec) de chaque étape sont tracées. Voir shared/log_buffer.py
# (correctif du même numéro) pour l'infrastructure qui rend ces
# traces effectivement visibles (le logger racine était jusqu'ici
# trop strict pour laisser passer le moindre appel debug()).
_log = logging.getLogger("secret_crypto")


class SecretCryptoError(Exception):
    pass


def generate_salt():
    """Un sel ALÉATOIRE par installation -- NON secret, stockable en
    clair à côté des données chiffrées (ex. un fichier `.salt`,
    versionnable). Généré UNE FOIS par déploiement, jamais régénéré
    ensuite (le régénérer invaliderait tout ce qui a déjà été
    chiffré avec l'ancien sel, y compris avec la bonne phrase de
    passe)."""
    salt = os.urandom(SALT_SIZE_BYTES)
    _log.debug("generate_salt : nouveau sel généré (%d octets)", SALT_SIZE_BYTES)
    return salt


def derive_key(passphrase, salt):
    """Dérive une clé Fernet (32 octets, encodée base64 urlsafe,
    format attendu par `Fernet(...)`) à partir d'une phrase de passe
    + un sel. Deterministe : mêmes entrées -> même clé, à chaque
    appel -- c'est ce qui permet de ne JAMAIS stocker la clé
    elle-même, seulement de la RE-DÉRIVER à chaque déploiement à
    partir de la phrase de passe fournie fraîchement."""
    if not passphrase:
        _log.debug("derive_key : refusé -- phrase de passe vide")
        raise SecretCryptoError("phrase de passe vide")
    if not isinstance(salt, (bytes, bytearray)) or len(salt) < 8:
        _log.debug("derive_key : refusé -- sel invalide (type=%s, longueur=%s)",
                    type(salt).__name__, len(salt) if hasattr(salt, "__len__") else "?")
        raise SecretCryptoError("sel invalide (attendu : bytes, au moins 8 octets)")
    start = time.monotonic()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=bytes(salt), iterations=PBKDF2_ITERATIONS)
    key_bytes = kdf.derive(passphrase.encode("utf-8"))
    elapsed_ms = int((time.monotonic() - start) * 1000)
    _log.debug("derive_key : dérivation PBKDF2 terminée (%d itérations, %d ms) -- jamais la phrase de passe elle-même ici",
               PBKDF2_ITERATIONS, elapsed_ms)
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_value(plaintext, passphrase, salt):
    """Chaîne de caractères -> jeton Fernet (str imprimable, sûr à
    stocker dans un fichier texte comme `.env.encrypted`)."""
    if plaintext is None:
        _log.debug("encrypt_value : refusé -- valeur à chiffrer manquante (None)")
        raise SecretCryptoError("valeur à chiffrer manquante (None)")
    _log.debug("encrypt_value : démarré (longueur en clair : %d caractères)", len(plaintext))
    key = derive_key(passphrase, salt)
    token = Fernet(key).encrypt(plaintext.encode("utf-8"))
    _log.debug("encrypt_value : jeton produit (longueur : %d octets)", len(token))
    return token.decode("ascii")


def decrypt_value(token, passphrase, salt):
    """Inverse de encrypt_value -- lève SecretCryptoError (JAMAIS
    l'exception `cryptography` brute) si la phrase de passe est
    incorrecte ou le jeton corrompu/altéré -- message actionnable
    pour un opérateur qui se serait trompé de phrase de passe, jamais
    un stacktrace opaque à l'exécution de `scripts/run.sh`."""
    if not token:
        _log.debug("decrypt_value : refusé -- jeton à déchiffrer manquant")
        raise SecretCryptoError("jeton à déchiffrer manquant")
    _log.debug("decrypt_value : démarré (longueur du jeton : %d)", len(token))
    key = derive_key(passphrase, salt)
    token_bytes = token.encode("ascii") if isinstance(token, str) else token
    try:
        plaintext_bytes = Fernet(key).decrypt(token_bytes)
    except InvalidToken:
        _log.debug("decrypt_value : ÉCHEC -- phrase de passe incorrecte ou jeton corrompu/altéré")
        raise SecretCryptoError("déchiffrement échoué -- phrase de passe incorrecte, ou donnée corrompue/altérée")
    _log.debug("decrypt_value : succès (longueur en clair obtenue : %d caractères)", len(plaintext_bytes))
    return plaintext_bytes.decode("utf-8")


def encrypt_bytes(plaintext_bytes, passphrase, salt):
    """Version BINAIRE (pour les clés SSH -- des fichiers, pas de
    simples chaînes) -- renvoie le jeton Fernet en bytes BRUTS (pas
    décodé en str), à écrire tel quel dans un fichier `.enc`."""
    if plaintext_bytes is None:
        _log.debug("encrypt_bytes : refusé -- contenu à chiffrer manquant (None)")
        raise SecretCryptoError("contenu à chiffrer manquant (None)")
    _log.debug("encrypt_bytes : démarré (longueur en clair : %d octets)", len(plaintext_bytes))
    key = derive_key(passphrase, salt)
    token = Fernet(key).encrypt(plaintext_bytes)
    _log.debug("encrypt_bytes : jeton produit (longueur : %d octets)", len(token))
    return token


def decrypt_bytes(token_bytes, passphrase, salt):
    if not token_bytes:
        _log.debug("decrypt_bytes : refusé -- contenu à déchiffrer manquant")
        raise SecretCryptoError("contenu à déchiffrer manquant")
    _log.debug("decrypt_bytes : démarré (longueur du jeton : %d octets)", len(token_bytes))
    key = derive_key(passphrase, salt)
    try:
        plaintext_bytes = Fernet(key).decrypt(token_bytes)
    except InvalidToken:
        _log.debug("decrypt_bytes : ÉCHEC -- phrase de passe incorrecte ou jeton corrompu/altéré")
        raise SecretCryptoError("déchiffrement échoué -- phrase de passe incorrecte, ou donnée corrompue/altérée")
    _log.debug("decrypt_bytes : succès (longueur en clair obtenue : %d octets)", len(plaintext_bytes))
    return plaintext_bytes
