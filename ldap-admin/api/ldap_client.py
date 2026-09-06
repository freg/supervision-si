"""
Client LDAP -- par sous-processus vers les VRAIS outils standards
(`ldapsearch`/`ldapmodify`, paquet Debian `ldap-utils`), jamais une
bibliothèque Python (aucune disponible dans l'environnement de
développement pour la tester -- ni réseau pour l'installer, ni
serveur LDAP réel pour s'y connecter). Même motif déjà établi et
éprouvé que `backup_manager.py` pour PostgreSQL (`pg_dump`/`psql`) :
dépendances (exécuteur de sous-processus) injectées en paramètre,
jamais un appel direct en dur, pour rester testable au niveau de la
CONSTRUCTION des commandes même sans pouvoir exécuter les vrais
binaires ici.

RÉSERVE HONNÊTE, comme pour le chemin PostgreSQL de
backup_manager.py : la construction des commandes et la gestion des
réponses sont testées avec un faux sous-processus injecté, jamais
une vraie connexion LDAP bout en bout -- ni serveur LDAP réel, ni
binaires `ldap-utils` disponibles dans cet environnement.

SÉCURITÉ -- mot de passe de liaison JAMAIS en argument de ligne de
commande (visible dans `ps`, même précaution que PGPASSWORD ailleurs
dans ce projet) : passé via un fichier temporaire (`-y <fichier>`,
supporté nativement par ldapsearch/ldapmodify), créé avec des
permissions restrictives, supprimé immédiatement après usage --
y compris si la commande échoue (bloc finally).
"""

import base64
import hashlib
import logging
import os
import secrets
import subprocess
import tempfile
import time

# Traces DEBUG (livraison #223, suite de #215-217 -- audit rétroactif
# des modules antérieurs à cette session). RÈGLE ABSOLUE, identique
# au reste du projet : ni le mot de passe de liaison LDAP, ni un mot
# de passe utilisateur en clair n'apparaissent JAMAIS dans une trace.
_log = logging.getLogger("ldap_client")


def ssha_password(plaintext, salt=None):
    """Hache un mot de passe au format SSHA ({SSHA}base64(SHA1(mdp +
    sel) + sel)) -- le schéma de hachage standard OpenLDAP, calculé
    ICI plutôt que de compter sur le serveur pour le faire (évite de
    dépendre d'un overlay pw-hash configuré côté serveur, jamais
    garanti). Implémentation pure Python -- aucune dépendance
    externe, contrairement à l'outil `slappasswd` qui fait la même
    chose. `salt` injecté (8 octets aléatoires par défaut, taille
    standard OpenLDAP) pour rester testable de façon déterministe."""
    if salt is None:
        salt = secrets.token_bytes(8)
    digest = hashlib.sha1(plaintext.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")


def verify_ssha_password(plaintext, hashed):
    """Vérifie qu'un mot de passe correspond bien à un hachage SSHA
    donné -- utile pour les tests (jamais exposée aux routes, pas de
    raison de redonner ce pouvoir à l'API elle-même)."""
    if not hashed.startswith("{SSHA}"):
        return False
    try:
        raw = base64.b64decode(hashed[len("{SSHA}"):])
    except Exception:
        return False
    digest, salt = raw[:20], raw[20:]  # SHA1 = 20 octets
    return hashlib.sha1(plaintext.encode("utf-8") + salt).digest() == digest


class TempPasswordFile:
    """Fichier temporaire contenant UNIQUEMENT le mot de passe de
    liaison, permissions restrictives (0600), toujours supprimé --
    y compris en cas d'exception (context manager, bloc finally
    implicite via __exit__). Jamais le mot de passe en argument de
    ligne de commande."""

    def __init__(self, password):
        self.password = password
        self.path = None

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(prefix="ldap-bind-")
        try:
            os.chmod(self.path, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(self.password)
        except Exception:
            os.close(fd)
            raise
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.path and os.path.exists(self.path):
            os.remove(self.path)
        return False


def build_ldapsearch_command(config, password_file, extra_args=None):
    """Pure -- construit la commande d'export LDIF complet, testable
    sans lancer de vrai sous-processus. `-o ldif-wrap=no` : désactive
    le repliement de ligne (ldif_tools.parse_ldif le gère correctement
    de toute façon, mais un LDIF non replié reste plus simple à
    relire tel quel dans un shell)."""
    cmd = [
        "ldapsearch", "-x",
        "-H", config["url"],
        "-D", config["bind_dn"],
        "-y", password_file,
        "-b", config["base_dn"],
        "-o", "ldif-wrap=no",
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append("(objectClass=*)")
    return cmd


def build_ldapmodify_command(config, password_file, ldif_path):
    """Pure -- construit la commande de réinjection d'un fichier LDIF
    (ajouts ET modifications, `ldapmodify` gère les deux contrairement
    à `ldapadd` qui ne gère que les ajouts) -- exactement la commande
    qu'une personne pourrait taper elle-même depuis un shell avec le
    même fichier de sauvegarde, demandé explicitement."""
    return [
        "ldapmodify", "-x",
        "-H", config["url"],
        "-D", config["bind_dn"],
        "-y", password_file,
        "-f", ldif_path,
    ]


def build_password_reset_ldif(user_dn, new_password_hash):
    """Pure -- construit le fragment LDIF de changement de mot de
    passe (changetype: modify / replace: userPassword) pour UN
    utilisateur. Le hachage est déjà calculé (voir ssha_password) --
    cette fonction ne fait QUE construire le texte LDIF, jamais le
    hachage elle-même, pour rester testable séparément."""
    return (
        f"dn: {user_dn}\n"
        f"changetype: modify\n"
        f"replace: userPassword\n"
        f"userPassword: {new_password_hash}\n"
    )


def build_modify_ldif(dn, attr_changes):
    """Pure -- construit un fragment LDIF de modification générique,
    demandé explicitement ("éditer tous les attributs à tous les
    niveaux, en particulier les feuilles"). `attr_changes` :
    {nom_attribut: [nouvelles_valeurs...]} -- REMPLACE entièrement
    les valeurs de chaque attribut listé (jamais un ajout/retrait
    incrémental) : "voici l'état final voulu pour cet attribut",
    plus simple et plus prévisible à raisonner qu'un diff. Une liste
    VIDE supprime complètement l'attribut de l'entrée
    (`delete:`, sans valeur). Plusieurs attributs dans le même
    changement -- séparés par une ligne "-" seule, syntaxe LDIF
    standard (RFC 2849) pour un `changetype: modify` à plusieurs
    volets. Dict vide -- LDIF minimal avec juste le dn/changetype,
    jamais une exception (l'appelant est censé filtrer les
    changements vides en amont, mais cette fonction reste sûre même
    si ce n'est pas le cas)."""
    lines = [f"dn: {dn}", "changetype: modify"]
    items = list(attr_changes.items())
    for i, (attr, values) in enumerate(items):
        if values:
            lines.append(f"replace: {attr}")
            for v in values:
                lines.append(f"{attr}: {v}")
        else:
            lines.append(f"delete: {attr}")
        if i < len(items) - 1:
            lines.append("-")
    return "\n".join(lines) + "\n"


def run_command(cmd, runner=subprocess.run, timeout=60):
    """Point d'entrée unique d'exécution -- `runner` injecté, jamais
    un sous-processus lancé en dur ailleurs dans ce module. Renvoie
    {ok, stdout, stderr, returncode} -- jamais une exception pour un
    échec normal de commande (code de retour non nul), seulement pour
    une erreur d'exécution elle-même (binaire introuvable, etc.),
    laissée remonter volontairement à l'appelant."""
    binary = cmd[0] if cmd else "?"
    _log.debug("run_command : démarré (binaire=%s, timeout=%ss)", binary, timeout)
    start = time.monotonic()
    result = runner(cmd, capture_output=True, timeout=timeout)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else result.stdout
    stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else result.stderr
    _log.debug("run_command : terminé en %d ms (code retour %s)", elapsed_ms, result.returncode)
    return {"ok": result.returncode == 0, "stdout": stdout, "stderr": stderr, "returncode": result.returncode}


def export_ldif(config, runner=subprocess.run):
    """Point d'entrée unique -- export complet de l'annuaire en LDIF.
    Le mot de passe de liaison ne transite JAMAIS par la ligne de
    commande (fichier temporaire, supprimé même en cas d'échec)."""
    _log.debug("export_ldif : démarré (hôte=%s, jamais le mot de passe de liaison ici)", config.get("url"))
    with TempPasswordFile(config["bind_password"]) as password_file:
        cmd = build_ldapsearch_command(config, password_file)
        result = run_command(cmd, runner=runner)
    _log.debug("export_ldif : terminé (%s)", "succès" if result["ok"] else "échec")
    return result


def apply_ldif(config, ldif_text, runner=subprocess.run):
    """Point d'entrée unique -- réinjection d'un LDIF (restauration
    complète, ou changement ciblé comme un reset de mot de passe).
    `ldif_text` écrit dans un fichier temporaire séparé du mot de
    passe (deux fichiers distincts, jamais mélangés) -- supprimé lui
    aussi systématiquement."""
    _log.debug("apply_ldif : démarré (hôte=%s, LDIF de %d caractères -- jamais son contenu tracé)", config.get("url"), len(ldif_text))
    ldif_fd, ldif_path = tempfile.mkstemp(prefix="ldap-apply-", suffix=".ldif")
    try:
        with os.fdopen(ldif_fd, "w") as f:
            f.write(ldif_text)
        with TempPasswordFile(config["bind_password"]) as password_file:
            cmd = build_ldapmodify_command(config, password_file, ldif_path)
            result = run_command(cmd, runner=runner)
        _log.debug("apply_ldif : terminé (%s)", "succès" if result["ok"] else "échec")
        return result
    finally:
        if os.path.exists(ldif_path):
            os.remove(ldif_path)
        _log.debug("apply_ldif : fichier LDIF temporaire supprimé")


def reset_user_password(config, user_dn, new_plaintext_password, runner=subprocess.run):
    """Point d'entrée unique -- réinitialisation d'un mot de passe.
    Hache AVANT tout envoi réseau (le mot de passe en clair ne
    transite jamais vers le serveur ni n'apparaît dans le LDIF
    envoyé)."""
    _log.debug("reset_user_password : démarré pour dn=%s (jamais le mot de passe, ni l'ancien ni le nouveau, ici)", user_dn)
    hashed = ssha_password(new_plaintext_password)
    ldif_text = build_password_reset_ldif(user_dn, hashed)
    result = apply_ldif(config, ldif_text, runner=runner)
    _log.debug("reset_user_password : terminé pour dn=%s (%s)", user_dn, "succès" if result["ok"] else "échec")
    return result
