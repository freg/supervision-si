#!/usr/bin/env python3
"""
Vérification de cohérence AVANT déploiement — jamais bloquant (des
avertissements, pas des erreurs fatales : certains écarts sont
volontaires), mais rend visible ce qui autrement ne se découvre qu'au
runtime, parfois de façon confuse.

Trois vérifications :
1. Chemins référencés par les variables *_DIR (quand renseignées, non
   vides) : existent-ils réellement sur le disque ? Docker créera
   silencieusement un dossier vide sinon -- rarement ce que la
   personne voulait si elle pointait vers des données existantes.
2. Variables utilisées par docker-compose.yml (${VAR}/${VAR:-défaut})
   mais ABSENTES de .env -- la valeur par défaut du compose est
   utilisée silencieusement, ce qui peut masquer un oubli réel.
3. Variables présentes dans .env mais jamais référencées dans
   docker-compose.yml -- probablement obsolètes (retirées d'un
   service, ou faute de frappe dans le nom).

Appelé automatiquement par scripts/run.sh avant chaque démarrage.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def parse_env_file(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def find_compose_vars(path):
    """Toutes les variables ${VAR} ou ${VAR:-défaut} référencées dans
    docker-compose.yml -- capture le nom AVANT tout ':-défaut', jamais
    le défaut lui-même."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)(?::-[^}]*)?\}", content))


# Fichiers qui consomment DIRECTEMENT des clés .env pour générer de la
# config (realm Keycloak, nginx, certificats, sauvegarde) -- distincts
# des app.py de chaque backend, qui reçoivent leurs variables déjà
# résolues via docker-compose.yml (environment:), jamais .env
# directement. Repéré une fois en trouvant un faux positif massif
# (LDAP_*, *_API_PORT signalées "obsolètes" alors qu'utilisées ici).
OTHER_CONSUMER_FILES = [
    "keycloak/render.py",
    "tls-proxy/render_nginx_conf.py",
    "keycloak/backup/backup-loop.sh",
    "keycloak/group_memberships.py",
    "pki/scripts/generate-ca.sh",
    "pki/scripts/generate-server-cert.sh",
    "apache/render_apache_conf.py",
    # gateway/ (livraison #135) et mayan/ (livraison #158) -- LEURS
    # PROPRES docker-compose.yml, jamais lus par find_compose_vars
    # (qui ne regarde QUE le docker-compose.yml principal) -- même
    # bug que vault-standalone ci-dessous, trouvé ici en relisant ce
    # script après un signalement réel de déploiement (2026-09-05) :
    # KEYCLOAK_DATA_VOLUME_NAME et les MAYAN_* (RABBITMQ/REDIS/
    # DATABASE/AUTOADMIN_EMAIL/PORT) signalées à tort "jamais
    # référencées, probablement obsolètes" alors qu'elles servent
    # bien -- juste dans ces deux fichiers séparés.
    "gateway/docker-compose.yml",
    "gateway/scripts/run.sh",
    "mayan/docker-compose.yml",
    # Instance isolée du coffre-fort (vault-standalone/) -- son PROPRE
    # docker-compose.yml, jamais lu par find_compose_vars (qui ne
    # regarde QUE le docker-compose.yml principal) : sans cette
    # entrée, toutes les variables VAULT_STANDALONE_* étaient
    # signalées à tort comme "jamais référencées", alors qu'elles
    # servent bien -- juste dans ce second fichier. Bug réel signalé
    # par la personne, corrigé ici.
    "vault-standalone/docker-compose.yml",
    "vault-standalone/keycloak/render.py",
    "vault-standalone/tls-proxy/render_nginx_conf.py",
    "vault-standalone/scripts/run.sh",
]


def find_other_referenced_vars(root):
    """Cherche le nom de CHAQUE variable .env comme chaîne/mot entier
    dans les fichiers ci-dessus -- motif volontairement large (chaîne
    Python 'VAR', $VAR shell, ${VAR} shell...) plutôt qu'un seul motif
    d'appel précis, pour ne pas rater un style d'utilisation différent
    d'un fichier à l'autre."""
    found = set()
    for rel_path in OTHER_CONSUMER_FILES:
        path = os.path.join(root, rel_path)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        for match in re.findall(r"[A-Z][A-Z0-9_]{2,}", content):
            found.add(match)
    return found


def check_paths(env_values):
    """Ne signale QUE les variables *_DIR explicitement renseignées
    (non vides) -- une valeur vide est un repli assumé (voir
    ENV_CHANGELOG.md), jamais un problème."""
    warnings = []
    for key, value in sorted(env_values.items()):
        if key.endswith("_DIR") and value:
            path = value if os.path.isabs(value) else os.path.join(ROOT, value)
            if not os.path.isdir(path):
                warnings.append(
                    f"{key}={value} -- chemin absent du disque ({path}). "
                    f"Docker le créera vide au démarrage -- vérifiez que ce n'est "
                    f"pas censé pointer vers des données déjà existantes."
                )
    return warnings


def check_drift(env_values, compose_vars, all_referenced_vars):
    # HOST_IP est injectée par run.sh lui-même (détection automatique),
    # jamais attendue dans .env -- exclusion volontaire, pas un oubli.
    ignored = {"HOST_IP"}
    # "Manquante" reste spécifique aux ${VAR} de docker-compose.yml --
    # c'est LE seul mécanisme à repli silencieux (":-défaut"), les
    # autres fichiers consommateurs n'ont pas cette notion de repli.
    missing_in_env = sorted(v for v in compose_vars if v not in env_values and v not in ignored)
    # "Obsolète" utilise l'ensemble LARGE (compose + tous les autres
    # fichiers consommateurs) -- sinon LDAP_BIND_PASSWORD et consorts
    # ressortent comme obsolètes alors qu'utilisées ailleurs (faux
    # positif massif rencontré en testant contre le vrai projet).
    unused_in_compose = sorted(k for k in env_values if k not in all_referenced_vars)
    return missing_in_env, unused_in_compose


def main():
    env_path = os.path.join(ROOT, ".env")
    compose_path = os.path.join(ROOT, "docker-compose.yml")

    env_values = parse_env_file(env_path)
    compose_vars = find_compose_vars(compose_path)
    other_vars = find_other_referenced_vars(ROOT)
    all_referenced = compose_vars | other_vars

    path_warnings = check_paths(env_values)
    missing, unused = check_drift(env_values, compose_vars, all_referenced)

    found_anything = False

    if path_warnings:
        found_anything = True
        print("⚠️  Chemins référencés dans .env mais absents du disque :")
        for w in path_warnings:
            print(f"   - {w}")

    if missing:
        found_anything = True
        print("⚠️  Variables utilisées par docker-compose.yml mais ABSENTES de .env")
        print("   (valeur par défaut du compose utilisée silencieusement) :")
        for v in missing:
            print(f"   - {v}")

    if unused:
        found_anything = True
        print("ℹ️  Variables présentes dans .env mais jamais référencées dans docker-compose.yml")
        print("   (probablement obsolètes, ou faute de frappe dans le nom) :")
        for v in unused:
            print(f"   - {v}")

    if not found_anything:
        print("✓ .env cohérent avec docker-compose.yml et le disque.")

    return 0  # jamais un code d'échec -- purement informatif


if __name__ == "__main__":
    sys.exit(main())
