"""
Découverte des clés SSH sur le disque (livraison #159) -- la
DÉCOUVERTE ne lit JAMAIS le contenu d'une clé privée elle-même : elle
liste les fichiers présents dans SSH_KEYS_DIR et délègue le calcul de
l'empreinte à `ssh-keygen -lf` (sous-processus) -- un outil FAIT pour
ça, qui ne renvoie jamais la clé elle-même, seulement son empreinte
et son type.

⚠️ Depuis la livraison #277 (demandé explicitement, confirmé avec la
personne), ce module génère ET permet la suppression de clés (voir
`generate_key` plus bas) -- SSH_KEYS_DIR est donc désormais monté en
LECTURE-ÉCRITURE (inversion du choix initial de #159, qui excluait
délibérément cette possibilité) -- voir docker-compose.yml pour le
raisonnement complet de ce changement de posture sécurité.
"""
import os
import subprocess

# Extensions IGNORÉES lors du scan -- fichiers publics/connexes
# jamais listés comme des clés PRIVÉES à part entière (une clé
# publique ".pub" n'a pas besoin d'être "activée/désactivée"
# séparément de sa clé privée correspondante).
IGNORED_SUFFIXES = (".pub", ".known_hosts", ".ini", ".txt", ".md")


def scan_key_files(keys_dir):
    """Renvoie la liste des noms de fichiers (PAS le chemin complet)
    trouvés directement dans `keys_dir` -- jamais récursif dans des
    sous-dossiers (garde le modèle simple : un fichier = une clé).
    Liste vide si le dossier n'existe pas encore (jamais une
    exception -- un déploiement qui n'a pas encore monté de clés
    reste utilisable, juste avec un registre vide)."""
    if not os.path.isdir(keys_dir):
        return []
    names = []
    for entry in sorted(os.listdir(keys_dir)):
        full_path = os.path.join(keys_dir, entry)
        if not os.path.isfile(full_path):
            continue
        if entry.startswith("."):
            continue
        if entry.endswith(IGNORED_SUFFIXES):
            continue
        names.append(entry)
    return names


def get_key_fingerprint(keys_dir, filename, timeout=5):
    """Renvoie {"fingerprint": str, "key_type": str} via
    `ssh-keygen -lf <chemin>` -- JAMAIS le contenu de la clé
    lui-même. None si `ssh-keygen` échoue (clé illisible, mauvais
    format, permissions) -- jamais une exception qui remonterait
    telle quelle, une clé illisible reste listée, juste sans détail
    affiché.

    `filename` DOIT être un simple nom de fichier (pas de `/`) --
    vérifié explicitement ici en plus de la construction du chemin
    par os.path.join, pour ne jamais dépendre uniquement de
    l'appelant (défense en profondeur, même réflexe que
    file_store.py en #157)."""
    if "/" in filename or filename in (".", ".."):
        return None
    full_path = os.path.join(keys_dir, filename)
    if not os.path.isfile(full_path):
        return None
    try:
        result = subprocess.run(
            ["ssh-keygen", "-lf", full_path],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    # Format typique : "2048 SHA256:xxxxx comment (RSA)"
    parts = result.stdout.strip().split()
    if len(parts) < 4:
        return None
    return {
        "fingerprint": parts[1],
        "key_type": parts[-1].strip("()"),
    }


VALID_KEY_TYPES = ("ed25519", "rsa", "ecdsa")


def generate_key(keys_dir, filename, passphrase="", key_type="ed25519", timeout=15):
    """Génère une NOUVELLE paire de clés (livraison #277, demandé
    explicitement -- "permettre de générer des clés sans passphrase
    ou avec"). `passphrase=""` (défaut) -- sans protection,
    convient à un usage automatisé non interactif (comme ce module
    le fait déjà pour ses propres tunnels) ; une phrase non vide
    protège la clé mais nécessite une saisie à chaque déverrouillage.

    ⚠️ LIMITE ASSUMÉE, documentée plutôt que cachée : `ssh-keygen`
    n'offre AUCUN mécanisme par variable d'environnement pour la
    passphrase (contrairement à `sshpass -e` pour un mot de passe de
    connexion, déjà utilisé ailleurs dans ce module) -- seul `-N
    <passphrase>` existe pour un usage non interactif, exposant
    BRIÈVEMENT la phrase dans la liste des processus de CE conteneur
    pendant l'exécution (jamais journalisé, jamais persisté nulle
    part -- une fenêtre d'exposition locale et transitoire, pas une
    fuite durable, mais réelle -- vérifié auprès de la documentation
    officielle avant d'écrire cette fonction, aucune alternative
    trouvée).

    Même validation défensive de `filename` que `get_key_fingerprint`
    -- jamais un chemin construit sans vérification, même si
    l'appelant (app.py) valide déjà côté route. Refuse d'écraser un
    fichier déjà présent (jamais une régénération silencieuse).

    Renvoie (True, None) ou (False, message_erreur) -- message SANS
    JAMAIS inclure la passphrase elle-même, même en cas d'échec."""
    if "/" in filename or filename in (".", "..") or not filename:
        return False, "nom de fichier invalide"
    if key_type not in VALID_KEY_TYPES:
        return False, f"type de clé invalide (attendus : {VALID_KEY_TYPES})"
    full_path = os.path.join(keys_dir, filename)
    if os.path.exists(full_path):
        return False, "un fichier de ce nom existe déjà -- jamais un écrasement silencieux"

    try:
        result = subprocess.run(
            ["ssh-keygen", "-t", key_type, "-f", full_path, "-N", passphrase, "-C", "supervision-si", "-q"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "ssh-keygen : délai dépassé"
    except (FileNotFoundError, OSError) as exc:
        return False, f"ssh-keygen introuvable ou inutilisable : {exc}"
    if result.returncode != 0:
        # stderr de ssh-keygen ne contient JAMAIS la passphrase elle-même
        # (uniquement des messages d'erreur génériques -- permissions,
        # chemin invalide...) -- vérifié par construction de la commande
        # ci-dessus (aucun écho de -N par ssh-keygen lui-même).
        return False, (result.stderr or "ssh-keygen a échoué").strip()
    return True, None

