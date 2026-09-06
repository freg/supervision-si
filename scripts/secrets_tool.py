#!/usr/bin/env python3
"""
Outil CLI pour les primitives de shared/secret_crypto.py (livraison
#204, suite des points 2/3 de l'urgence matrice de risque). Permet
de chiffrer/déchiffrer une valeur ou un fichier À LA MAIN, avant
toute automatisation dans scripts/run.sh -- première étape pratique
pour se familiariser avec le mécanisme SANS toucher à un seul secret
réel.

**Portée toujours volontairement limitée** : cet outil ne modifie
JAMAIS `.env` ni aucun fichier de clé SSH existant -- il produit des
valeurs/fichiers chiffrés que la personne choisit ensuite d'utiliser
ou non. La migration effective des secrets réels reste une étape
séparée, à faire consciemment.

La PHRASE DE PASSE n'est JAMAIS acceptée en argument de ligne de
commande (fuiterait dans l'historique shell et la liste des
processus) -- toujours saisie de façon masquée via `getpass`.

Usage :
    python3 scripts/secrets_tool.py init-salt
    python3 scripts/secrets_tool.py encrypt-value
    python3 scripts/secrets_tool.py decrypt-value "gAAAAA..."
    python3 scripts/secrets_tool.py encrypt-file ssh-tunnels/keys/ma_cle.pem
    python3 scripts/secrets_tool.py decrypt-file ssh-tunnels/keys/ma_cle.pem.enc
"""
import argparse
import getpass
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
import secret_crypto as sc  # noqa: E402
import secrets_alert  # noqa: E402

DEFAULT_SALT_PATH = os.path.join(os.path.dirname(__file__), "..", ".secrets.salt")

# Traces DEBUG (livraison #217, suite de #215-216 -- "rien ne doit
# être silencieux"). Cet outil tourne HORS Docker, sur la machine de
# la personne -- pas connecté au tampon partagé Memcached des autres
# services (voir shared/log_buffer.py) -- son propre mécanisme :
# `--debug` en argument de ligne de commande configure un handler
# console pointé sur STDERR (jamais stdout, qui doit rester composé
# UNIQUEMENT de lignes `export` pour `decrypt-env`, voir plus bas).
# Une fois activé, les traces internes de secret_crypto.py (déjà
# posées en #215) remontent AUSSI automatiquement -- ce module est
# un logger ENFANT du logger racine que `--debug` configure ici.
# RÈGLE ABSOLUE, identique au reste du chantier : ni la phrase de
# passe, ni la valeur en clair, ni le contenu déchiffré n'apparaissent
# JAMAIS dans une trace, à aucun niveau.
_log = logging.getLogger("secrets_tool")


def load_or_create_salt(salt_path, allow_create):
    """Le sel n'est PAS secret (voir secret_crypto.py) mais NE DOIT
    JAMAIS être régénéré une fois des secrets réels chiffrés avec --
    ça les rendrait illisibles même avec la bonne phrase de passe.
    `allow_create=False` pour toute commande de DÉCHIFFREMENT (un sel
    absent à ce stade est une vraie anomalie, jamais silencieusement
    remplacé par un nouveau)."""
    _log.debug("load_or_create_salt : recherche à %s (allow_create=%s)", salt_path, allow_create)
    if os.path.isfile(salt_path):
        with open(salt_path, "rb") as f:
            salt = f.read()
        _log.debug("load_or_create_salt : sel existant chargé (%d octets)", len(salt))
        return salt
    if not allow_create:
        _log.debug("load_or_create_salt : ÉCHEC -- aucun sel trouvé et allow_create=False")
        print(f"Erreur : aucun sel trouvé à {salt_path} -- rien à déchiffrer sans le sel d'origine.", file=sys.stderr)
        sys.exit(1)
    salt = sc.generate_salt()
    with open(salt_path, "wb") as f:
        f.write(salt)
    _log.debug("load_or_create_salt : nouveau sel généré et écrit (%d octets)", len(salt))
    print(f"Nouveau sel généré et enregistré dans {salt_path} (non secret, à conserver -- JAMAIS régénérer par la suite).")
    return salt


def prompt_passphrase(confirm=False):
    passphrase = getpass.getpass("Phrase de passe maîtresse : ")
    if confirm:
        again = getpass.getpass("Confirmer la phrase de passe : ")
        if passphrase != again:
            print("Erreur : les deux saisies ne correspondent pas.", file=sys.stderr)
            sys.exit(1)
    return passphrase


def cmd_init_salt(args):
    salt_path = args.salt_file
    if os.path.isfile(salt_path):
        print(f"Un sel existe déjà à {salt_path} -- rien fait (le régénérer rendrait illisible tout ce qui a déjà été chiffré avec).")
        return
    load_or_create_salt(salt_path, allow_create=True)


def cmd_encrypt_value(args):
    salt = load_or_create_salt(args.salt_file, allow_create=True)
    passphrase = prompt_passphrase(confirm=True)
    value = getpass.getpass("Valeur à chiffrer (saisie masquée) : ")
    try:
        token = sc.encrypt_value(value, passphrase, salt)
    except sc.SecretCryptoError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
    print("\nJeton chiffré (à stocker, par exemple dans un fichier .env.encrypted) :\n")
    print(token)


def cmd_decrypt_value(args):
    salt = load_or_create_salt(args.salt_file, allow_create=False)
    passphrase = prompt_passphrase()
    try:
        value = sc.decrypt_value(args.token, passphrase, salt)
    except sc.SecretCryptoError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
    print("\nValeur déchiffrée :\n")
    print(value)


def cmd_encrypt_file(args):
    salt = load_or_create_salt(args.salt_file, allow_create=True)
    passphrase = prompt_passphrase(confirm=True)
    if not os.path.isfile(args.path):
        print(f"Erreur : fichier introuvable : {args.path}", file=sys.stderr)
        sys.exit(1)
    with open(args.path, "rb") as f:
        content = f.read()
    try:
        encrypted = sc.encrypt_bytes(content, passphrase, salt)
    except sc.SecretCryptoError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
    out_path = args.output or (args.path + ".enc")
    with open(out_path, "wb") as f:
        f.write(encrypted)
    print(f"Fichier chiffré écrit dans {out_path} -- le fichier d'origine ({args.path}) n'a PAS été modifié ni supprimé.")


def cmd_decrypt_file(args):
    salt = load_or_create_salt(args.salt_file, allow_create=False)
    passphrase = prompt_passphrase()
    if not os.path.isfile(args.path):
        print(f"Erreur : fichier introuvable : {args.path}", file=sys.stderr)
        sys.exit(1)
    with open(args.path, "rb") as f:
        content = f.read()
    try:
        decrypted = sc.decrypt_bytes(content, passphrase, salt)
    except sc.SecretCryptoError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
    out_path = args.output or (args.path[:-4] if args.path.endswith(".enc") else args.path + ".dec")
    with open(out_path, "wb") as f:
        f.write(decrypted)
    print(f"Fichier déchiffré écrit dans {out_path}.")


def _parse_env_encrypted_line(line):
    """Une ligne d'un fichier .env.encrypted : commentaire (#...) ou
    ligne vide -- renvoyée telle quelle, jamais traitée. `CLE=jeton`
    -- séparée sur le PREMIER '=' seulement (un jeton Fernet ne
    contient jamais '=' qu'à la fin, en padding base64, mais on ne
    coupe jamais dessus par erreur en séparant sur le premier '=')."""
    stripped = line.rstrip("\n")
    if not stripped.strip() or stripped.strip().startswith("#"):
        return None, None
    if "=" not in stripped:
        return None, None
    key, _, token = stripped.partition("=")
    return key.strip(), token.strip()


def cmd_encrypt_env(args):
    """Chiffre un fichier .env EN CLAIR (`--input`, jamais modifié)
    vers un fichier .env.encrypted (`--output`) -- CLE=jeton par
    ligne, commentaires et lignes vides conservés tels quels. Étape
    de MIGRATION -- volontairement séparée de tout usage automatique,
    jamais appelée ailleurs que par une personne qui le décide."""
    salt = load_or_create_salt(args.salt_file, allow_create=True)
    passphrase = prompt_passphrase(confirm=True)
    _log.debug("cmd_encrypt_env : phrase de passe confirmée, lecture de %s", args.input)
    if not os.path.isfile(args.input):
        _log.debug("cmd_encrypt_env : ÉCHEC -- fichier introuvable (%s)", args.input)
        print(f"Erreur : fichier introuvable : {args.input}", file=sys.stderr)
        sys.exit(1)
    out_lines = []
    encrypted_count = 0
    line_count = 0
    with open(args.input, "r") as f:
        for line in f:
            line_count += 1
            stripped = line.rstrip("\n")
            if not stripped.strip() or stripped.strip().startswith("#") or "=" not in stripped:
                out_lines.append(stripped)
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            if not value.strip():
                _log.debug("cmd_encrypt_env : ligne %d, clé '%s' -- valeur vide, conservée telle quelle", line_count, key)
                out_lines.append(stripped)  # valeur vide -- rien a chiffrer, conservee telle quelle
                continue
            try:
                token = sc.encrypt_value(value, passphrase, salt)
            except sc.SecretCryptoError as exc:
                _log.debug("cmd_encrypt_env : ÉCHEC sur la clé '%s' (ligne %d) -- %s", key, line_count, exc)
                print(f"Erreur sur la clé '{key}' : {exc}", file=sys.stderr)
                sys.exit(1)
            out_lines.append(f"{key}={token}")
            encrypted_count += 1
            _log.debug("cmd_encrypt_env : ligne %d, clé '%s' -- chiffrée avec succès", line_count, key)
    with open(args.output, "w") as f:
        f.write("\n".join(out_lines) + "\n")
    _log.debug("cmd_encrypt_env : terminé -- %d ligne(s) lue(s), %d valeur(s) chiffrée(s), écrit dans %s",
               line_count, encrypted_count, args.output)
    print(f"{encrypted_count} valeur(s) chiffrée(s) écrite(s) dans {args.output} -- {args.input} n'a PAS été modifié ni supprimé.")


def cmd_decrypt_env(args):
    """Déchiffre un fichier .env.encrypted et affiche des lignes
    `export CLE='valeur'` sur STDOUT, prêtes pour un `eval` bash --
    voir scripts/run.sh. Le prompt de phrase de passe et TOUS les
    messages d'état passent par STDERR (jamais stdout, qui doit
    rester composé UNIQUEMENT de lignes `export` valides pour l'eval
    appelant -- un message d'erreur qui s'y glisserait serait
    interprété comme une commande shell)."""
    import shlex
    salt = load_or_create_salt(args.salt_file, allow_create=False)
    passphrase = getpass.getpass("Phrase de passe maîtresse : ", stream=sys.stderr)
    _log.debug("cmd_decrypt_env : phrase de passe saisie, lecture de %s", args.input)
    if not os.path.isfile(args.input):
        _log.debug("cmd_decrypt_env : ÉCHEC -- fichier introuvable (%s)", args.input)
        print(f"Erreur : fichier introuvable : {args.input}", file=sys.stderr)
        sys.exit(1)
    exported = 0
    with open(args.input, "r") as f:
        for line_no, line in enumerate(f, start=1):
            key, token = _parse_env_encrypted_line(line)
            if key is None:
                continue
            if not token:
                # Symétrique à encrypt-env : une valeur vide n'est
                # jamais chiffrée à l'écriture, donc jamais déchiffrée
                # ici -- sans ce cas, la moindre variable optionnelle
                # laissée vide (motif courant dans .env.example de ce
                # projet) ferait échouer TOUT le déchiffrement.
                _log.debug("cmd_decrypt_env : ligne %d, clé '%s' -- valeur vide, export vide", line_no, key)
                print(f"export {key}=''")
                exported += 1
                continue
            try:
                value = sc.decrypt_value(token, passphrase, salt)
            except sc.SecretCryptoError as exc:
                _log.debug("cmd_decrypt_env : ÉCHEC sur la clé '%s' (ligne %d) -- %s", key, line_no, exc)
                print(f"Erreur ligne {line_no} (clé '{key}') : {exc}", file=sys.stderr)
                sys.exit(1)
            print(f"export {key}={shlex.quote(value)}")
            exported += 1
            _log.debug("cmd_decrypt_env : ligne %d, clé '%s' -- déchiffrée avec succès", line_no, key)
    _log.debug("cmd_decrypt_env : déchiffrement terminé -- %d variable(s) exportée(s)", exported)
    print(f"{exported} variable(s) déchiffrée(s) et exportée(s).", file=sys.stderr)

    # Alertes PRA (livraison #206, docs/pra-secrets-demarrage.docx
    # section 4) -- BEST-EFFORT, jamais bloquant : le déchiffrement
    # ci-dessus a déjà réussi et ses lignes `export` sont déjà sur
    # stdout -- une alerte qui échoue à partir ne doit JAMAIS faire
    # échouer le déploiement en cours. Silencieusement ignoré si les
    # canaux ne sont pas configurés (voir shared/secrets_alert.py).
    import socket
    import time
    context = f"Secrets déchiffrés sur {socket.gethostname()} à {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ({exported} variable(s))."
    _log.debug("cmd_decrypt_env : envoi des alertes de déploiement (best-effort)")
    alert_result = secrets_alert.send_deployment_alerts(context)
    _log.debug("cmd_decrypt_env : issue des alertes -- sms=%s email=%s", alert_result["sms"], alert_result["email"])
    if alert_result["sms"] or alert_result["email"]:
        sent = [c for c, ok in alert_result.items() if ok]
        print(f"Alerte(s) envoyée(s) : {', '.join(sent)}.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salt-file", default=DEFAULT_SALT_PATH, help=f"chemin du fichier de sel (défaut : {DEFAULT_SALT_PATH})")
    parser.add_argument("--debug", action="store_true",
                         help="active les traces DEBUG détaillées sur stderr (livraison #217) -- jamais un secret, "
                              "seulement les étapes/durées/issues, utile pour identifier un point de blocage")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-salt", help="génère le sel du projet s'il n'existe pas encore").set_defaults(func=cmd_init_salt)

    sub.add_parser("encrypt-value", help="chiffre une valeur saisie au clavier").set_defaults(func=cmd_encrypt_value)

    p_dec = sub.add_parser("decrypt-value", help="déchiffre un jeton (vérification)")
    p_dec.add_argument("token", help="jeton chiffré à déchiffrer")
    p_dec.set_defaults(func=cmd_decrypt_value)

    p_ef = sub.add_parser("encrypt-file", help="chiffre un fichier (ex. une clé SSH)")
    p_ef.add_argument("path", help="chemin du fichier à chiffrer")
    p_ef.add_argument("--output", help="chemin de sortie (défaut : <path>.enc)")
    p_ef.set_defaults(func=cmd_encrypt_file)

    p_df = sub.add_parser("decrypt-file", help="déchiffre un fichier .enc (vérification)")
    p_df.add_argument("path", help="chemin du fichier .enc à déchiffrer")
    p_df.add_argument("--output", help="chemin de sortie (défaut : <path> sans le suffixe .enc)")
    p_df.set_defaults(func=cmd_decrypt_file)

    p_ee = sub.add_parser("encrypt-env", help="chiffre un fichier .env en clair vers un .env.encrypted (migration)")
    p_ee.add_argument("--input", required=True, help="fichier .env EN CLAIR à lire (jamais modifié)")
    p_ee.add_argument("--output", required=True, help="fichier .env.encrypted à écrire")
    p_ee.set_defaults(func=cmd_encrypt_env)

    p_de = sub.add_parser("decrypt-env", help="déchiffre un .env.encrypted -> lignes 'export CLE=valeur' sur stdout (pour eval)")
    p_de.add_argument("--input", required=True, help="fichier .env.encrypted à lire")
    p_de.set_defaults(func=cmd_decrypt_env)

    args = parser.parse_args()
    if args.debug:
        # STDERR uniquement -- jamais stdout, qui doit rester composé
        # UNIQUEMENT de lignes `export` pour `decrypt-env` (voir sa
        # docstring). Configure aussi le logger RACINE -- les traces
        # internes de secret_crypto.py (logger enfant) remontent
        # alors automatiquement, sans rien à faire de plus ici.
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="[DEBUG] %(name)s: %(message)s")
        _log.debug("mode debug activé -- commande : %s", args.command)
    args.func(args)


if __name__ == "__main__":
    main()
