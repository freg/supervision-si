#!/usr/bin/env python3
"""
Rendu du realm Keycloak de l'instance ISOLÉE du coffre-fort.

    python3 vault-standalone/keycloak/render.py            # écrit vault-standalone/keycloak/import/vault-standalone-realm.json
    python3 vault-standalone/keycloak/render.py --check    # rendu + contrôles, sans rien écrire

Réutilise délibérément les fonctions de keycloak/render.py (substitution,
détection de description trop longue, vérification post-écriture du
mot de passe LDAP) PAR IMPORT plutôt que par copie -- toute la
rigueur acquise sur le realm principal (voir son en-tête, notamment
le bug "sauvegarde qui prend le pas sur le gabarit") s'applique donc
ici aussi automatiquement, sans risque de double maintenance qui
diverge avec le temps.

Fédération LDAP IDENTIQUE au realm principal (mêmes variables LDAP_*,
lues dans le MÊME .env à la racine du projet) -- décidé avec la
personne : le LDAP est déjà joignable depuis l'extérieur (utilisé par
des applications clientes distantes), pas de raison d'avoir un compte
séparé pour l'instance isolée. Realm volontairement allégé par
ailleurs : un seul client (vault-portal), aucun groupe/rôle complexe
(le contrôle d'accès réel se fait déjà au niveau du coffre lui-même).
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STANDALONE_ROOT = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(STANDALONE_ROOT)
TEMPLATE = os.path.join(HERE, "realm-template.json")
DEFAULT_OUT_DIR = os.path.join(HERE, "import")

# Réutilise le realm principal -- voir docstring ci-dessus. Chargé par
# CHEMIN EXPLICITE (importlib), jamais par sys.path.insert() + "from
# render import ..." : les deux scripts s'appellent "render.py" dans
# des dossiers différents -- un import par nom entrerait en collision
# dans le cache des modules Python (le second "render" chargé
# récupérerait le premier, déjà en cours d'initialisation). Rencontré
# réellement en écrivant les tests de ce fichier.
_main_render_path = os.path.join(PROJECT_ROOT, "keycloak", "render.py")
_spec = importlib.util.spec_from_file_location("supervision_si_main_keycloak_render", _main_render_path)
_main_render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_main_render)

parse_env = _main_render.parse_env
build_variables = _main_render.build_variables
substitute = _main_render.substitute
leftover_tokens = _main_render.leftover_tokens
find_oversized_descriptions = _main_render.find_oversized_descriptions
extract_ldap_bind_credential = _main_render.extract_ldap_bind_credential
resolve_dir = _main_render.resolve_dir
MAX_DESCRIPTION_LENGTH = _main_render.MAX_DESCRIPTION_LENGTH


def build_standalone_variables(env):
    """Toutes les variables LDAP_* du realm principal (build_variables,
    réutilisée telle quelle) + VAULT_STANDALONE_PUBLIC_URL, calculée
    depuis SES PROPRES HOST_IP/GATEWAY_PORT -- une IP/entrée DNS et un
    certificat distincts du realm principal, décidé avec la personne,
    jamais les mêmes VAULT_STANDALONE_HOST_IP/GATEWAY_PORT que
    HOST_IP/GATEWAY_PORT (qui restent ceux du hub)."""
    variables, filter_note = build_variables(env)

    get = lambda key, default="": os.environ.get(key, env.get(key, default))
    host = get("VAULT_STANDALONE_HOST_IP", get("HOST_IP", "localhost")) or "localhost"
    gateway_port = get("VAULT_STANDALONE_GATEWAY_PORT", "7443")
    # /vault ajouté par défaut -- vault/portal/vite.config.js a son
    # chemin de base "/vault/" figé en dur (partagé tel quel avec le
    # stack principal, jamais reconstruit différemment pour
    # l'isolée) : l'URL publique réelle DOIT refléter ce même chemin,
    # sinon les redirectUris Keycloak ne correspondraient jamais à ce
    # que le navigateur utilise vraiment pour y arriver.
    variables["VAULT_STANDALONE_PUBLIC_URL"] = get(
        "VAULT_STANDALONE_PUBLIC_URL", f"https://{host}:{gateway_port}/vault"
    )
    return variables, filter_note


def resolve_import_dir(env):
    return resolve_dir(env, "VAULT_STANDALONE_KEYCLOAK_IMPORT_DIR", DEFAULT_OUT_DIR)


def main():
    check_only = "--check" in sys.argv
    # MÊME .env que le hub, à la racine du projet -- décidé avec la
    # personne ("même infra") : pas un .env séparé à maintenir en
    # double pour les seules variables LDAP_*, qui doivent de toute
    # façon rester identiques aux deux endroits.
    env = parse_env(os.path.join(PROJECT_ROOT, ".env"))
    try:
        variables, filter_note = build_standalone_variables(env)
        out_dir = resolve_import_dir(env)
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    out_path = os.path.join(out_dir, "vault-standalone-realm.json")

    if filter_note:
        print(f"ℹ️  {filter_note}")

    with open(TEMPLATE, encoding="utf-8") as fh:
        realm = json.load(fh)

    realm = substitute(realm, variables)

    remaining = leftover_tokens(realm)
    if remaining:
        print(f"ERREUR : jetons non substitués : {sorted(remaining)}", file=sys.stderr)
        return 1

    oversized = find_oversized_descriptions(realm)
    if oversized:
        print("ERREUR : description(s) dépassant la limite Keycloak (colonne DESCRIPTION VARCHAR(255)) :", file=sys.stderr)
        for path, length in oversized:
            print(f"  {path} : {length} caractères (max {MAX_DESCRIPTION_LENGTH})", file=sys.stderr)
        return 1

    if variables["LDAP_BIND_PASSWORD"] == "change-me":
        print("⚠️  LDAP_BIND_PASSWORD vaut encore 'change-me' — à renseigner dans .env avant usage réel.")

    if check_only:
        print("Rendu vérifié (aucune écriture) :")
        print(f"  destination      : {out_path}")
        print(f"  vault (isolé)    : {variables['VAULT_STANDALONE_PUBLIC_URL']}")
        print(f"  LDAP             : {variables['LDAP_URL']} (users: {variables['LDAP_USERS_DN']})")
        return 0

    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(realm, fh, ensure_ascii=False, indent=2)

    # Vérification post-écriture -- même garde-fou que le realm
    # principal (voir keycloak/render.py) : relit le fichier tel
    # qu'il vient d'être écrit et confirme que le mot de passe de
    # liaison LDAP y figure bien en clair.
    if variables["LDAP_BIND_PASSWORD"] != "change-me":
        with open(out_path, encoding="utf-8") as fh:
            written = json.load(fh)
        bind_credential = extract_ldap_bind_credential(written)
        if bind_credential is not None and bind_credential != variables["LDAP_BIND_PASSWORD"]:
            print("", file=sys.stderr)
            print("❌ ANOMALIE : le fichier réécrit ne contient PAS le mot de passe LDAP attendu", file=sys.stderr)
            print(f"   (vérifier {out_path})", file=sys.stderr)
            return 1

    print(f"Realm isolé rendu -> {out_path}")
    print(f"  vault (isolé) : {variables['VAULT_STANDALONE_PUBLIC_URL']}")
    print(f"  LDAP          : {variables['LDAP_URL']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
