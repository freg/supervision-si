"""Import des utilisateurs depuis l'annuaire LDAP CENTRAL de la
société (externe au hub, livraison #484 — demandé explicitement :
« importer les utilisateurs depuis le ldap externe au hub et central
pour notre SI »).

L'annuaire du HUB (openldap-test) reste ce qu'il est ; ce script
concerne l'annuaire de PRODUCTION de la société, dont l'adresse et le
compte de lecture vivent dans .env (secret, jamais dans le dépôt) :

    CENTRAL_LDAP_URL           ldap://ds.exemple.local:389 ou ldaps://...
    CENTRAL_LDAP_BIND_DN       cn=lecture,dc=exemple,dc=local
    CENTRAL_LDAP_BIND_PASSWORD (secret)
    CENTRAL_LDAP_USERS_DN      ou=personnes,dc=exemple,dc=local
    CENTRAL_LDAP_FILTER        (objectClass=inetOrgPerson) par défaut
    CENTRAL_LDAP_ATTR_LOGIN    uid par défaut
    CENTRAL_LDAP_ATTR_NAME     cn par défaut
    CENTRAL_LDAP_ATTR_MAIL     mail par défaut

Usage (dans le conteneur) :

    docker compose exec projeqtor-bridge python ldap_import.py --dry-run
    docker compose exec projeqtor-bridge python ldap_import.py

Chaque entrée crée un UTILISATEUR ProjeQtOr (classe User, nom =
login, email) avec le profil PROJEQTOR_IMPORT_PROFILE (id numérique,
optionnel — ProjeQtOr applique son profil par défaut sinon). Un
utilisateur existant (même nom, insensible à la casse) est IGNORE —
jamais d'écrasement d'un compte existant, jamais de doublon au
re-lancement. Le compte créé a un mot de passe aléatoire inutilisable
(l'authentification réelle se fait par LDAP, voir paramLdap_* —
ProjeQtOr exige un mot de passe local non vide).

--dry-run : liste ce qui SERAIT créé, n'écrit rien.
"""
import argparse
import os
import secrets
import sys

from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPException

from optline_format import normalize_key
from projeqtor_client import ProjeqtorApiError, ProjeqtorClient


def env(name, default=""):
    return os.environ.get(name, default).strip()


def main():
    parser = argparse.ArgumentParser(description="Import des utilisateurs du LDAP central vers ProjeQtOr")
    parser.add_argument("--dry-run", action="store_true", help="liste sans écrire")
    args = parser.parse_args()

    url = env("CENTRAL_LDAP_URL")
    bind_dn = env("CENTRAL_LDAP_BIND_DN")
    bind_pw = env("CENTRAL_LDAP_BIND_PASSWORD")
    users_dn = env("CENTRAL_LDAP_USERS_DN")
    ldap_filter = env("CENTRAL_LDAP_FILTER", "(objectClass=inetOrgPerson)")
    attr_login = env("CENTRAL_LDAP_ATTR_LOGIN", "uid")
    attr_name = env("CENTRAL_LDAP_ATTR_NAME", "cn")
    attr_mail = env("CENTRAL_LDAP_ATTR_MAIL", "mail")
    profile = env("PROJEQTOR_IMPORT_PROFILE")

    missing = [n for n, v in [
        ("CENTRAL_LDAP_URL", url), ("CENTRAL_LDAP_BIND_DN", bind_dn),
        ("CENTRAL_LDAP_BIND_PASSWORD", bind_pw), ("CENTRAL_LDAP_USERS_DN", users_dn),
    ] if not v]
    if missing:
        print(f"❌ Variables manquantes dans .env : {', '.join(missing)}")
        print("   (sync-env.py les a insérées vides si absentes — à renseigner)")
        return 1

    print(f"Connexion à {url} (base {users_dn}, filtre {ldap_filter}) ...")
    try:
        server = Server(url, connect_timeout=10)
        conn = Connection(server, user=bind_dn, password=bind_pw, auto_bind=True)
        conn.search(users_dn, ldap_filter, attributes=[attr_login, attr_name, attr_mail])
        entries = conn.entries
        conn.unbind()
    except LDAPException as exc:
        print(f"❌ LDAP : {exc}")
        return 1
    print(f"{len(entries)} entrée(s) trouvée(s)")

    client = ProjeqtorClient(
        env("PROJEQTOR_API_URL", "http://projeqtor-app/projeqtor/api"),
        env("PROJEQTOR_API_USER"), env("PROJEQTOR_API_PASSWORD"),
    )
    try:
        existing = client.get_all("User")
        if isinstance(existing, dict):
            existing = existing.get("items") or existing.get("user") or []
        known = {normalize_key(u.get("name")) for u in existing if u.get("name")}
    except ProjeqtorApiError as exc:
        print(f"❌ API ProjeQtOr : {exc}")
        return 1

    created, skipped, failed = 0, 0, 0
    for entry in entries:
        login = str(getattr(entry, attr_login, "") or "").strip()
        name = str(getattr(entry, attr_name, "") or "").strip() or login
        mail = str(getattr(entry, attr_mail, "") or "").strip()
        if not login:
            print(f"  ⚠️  entrée sans {attr_login} ignorée : {entry.entry_dn}")
            skipped += 1
            continue
        if normalize_key(login) in known:
            skipped += 1
            continue
        fields = {
            "name": login,
            "fullName": name,
            "email": mail,
            # Mot de passe local aléatoire inutilisable : ProjeQtOr
            # exige un mot de passe, mais l'authentification réelle se
            # fait par LDAP (paramLdap_allow_login, voir
            # projeqtor/README.md).
            "password": secrets.token_urlsafe(24),
        }
        if profile.isdigit():
            fields["idProfile"] = int(profile)
        if args.dry_run:
            print(f"  [dry-run] créerait : {login} ({name} <{mail}>)")
            created += 1
            continue
        try:
            client.create("User", fields)
            known.add(normalize_key(login))
            created += 1
            print(f"  ✅ créé : {login}")
        except ProjeqtorApiError as exc:
            failed += 1
            print(f"  ❌ {login} : {exc}")

    print(f"\nTerminé : {created} {'à créer' if args.dry_run else 'créés'}, "
          f"{skipped} ignorés (existants ou sans login), {failed} en échec")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
