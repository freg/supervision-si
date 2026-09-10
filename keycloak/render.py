#!/usr/bin/env python3
"""
Rendu du realm Keycloak depuis le .env du projet.

    python3 keycloak/render.py            # lit ./.env, écrit keycloak/import/supervision-si-realm.json
    python3 keycloak/render.py --check    # rendu + contrôles, sans rien écrire

Pourquoi un rendu plutôt qu'un import direct du gabarit : l'import de
realm Keycloak ne substitue pas les variables d'environnement dans le
JSON — les paramètres LDAP (URL, bind DN, mot de passe...) doivent donc
être injectés AVANT. Le fichier rendu contient le mot de passe de bind
en clair : keycloak/import/ est ignoré par git (voir .gitignore).

La substitution se fait sur l'arbre JSON chargé (jamais sur le texte
brut) : un mot de passe contenant des guillemets ou antislashs ne peut
pas casser le JSON produit.

NE JAMAIS préférer un export/sauvegarde Keycloak (partial-export, ou
tout ce qu'écrit keycloak-backup/) à realm-template.json ici, même
pour "préserver les changements faits à la main dans la console" --
tenté une fois, retiré après un bug réel à deux effets : (1) Keycloak
MASQUE les identifiants sensibles dans ses propres exports
(bindCredential devient des astérisques) -- utiliser un tel export
comme source réinjecte silencieusement un mot de passe LDAP cassé,
peu importe ce que .env contient réellement ; (2) une fois qu'une
telle sauvegarde existe, un NOUVEAU client/groupe ajouté à
realm-template.json n'a plus jamais d'effet tant qu'elle reste
présente -- vault-portal est resté invisible plusieurs sessions à
cause de ça. Pour préserver un état "seulement dans Keycloak" à
travers un réimport (appartenances aux groupes, notamment) : voir
keycloak/group_memberships.py, qui passe par l'API Admin REST
(jamais par un export masquant les identifiants).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "realm-template.json")
DEFAULT_OUT_DIR = os.path.join(HERE, "import")


def parse_env(path):
    """Lecture minimale d'un fichier KEY=VALUE (commentaires # et lignes
    vides ignorés, guillemets simples/doubles enveloppants retirés)."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def normalize_ldap_filter(raw):
    """
    Keycloak exige que 'Custom User LDAP Filter' soit une expression LDAP
    COMPLÈTE, parenthèses incluses — ex. (objectClass=inetOrgPerson) ou
    (&(objectClass=inetOrgPerson)(memberOf=cn=x,ou=y,dc=z)). Un fragment
    sans parenthèses ("objectClass=inetOrgPerson", format accepté par
    certaines autres applis qui l'encadrent elles-mêmes) déclenche
    l'erreur de démarrage 'ldapErrorInvalidCustomFilter'.

    Renvoie (valeur_normalisée, note_ou_None). Lève ValueError si la
    valeur contient des parenthèses mal formées (là, corriger à la main
    plutôt que deviner l'intention).
    """
    value = raw.strip()
    if not value:
        return value, None
    if value.startswith("(") and value.endswith(")") and value.count("(") == value.count(")"):
        return value, None
    if "(" not in value and ")" not in value:
        wrapped = f"({value})"
        return wrapped, (
            f"LDAP_SEARCH_FILTER='{raw}' ne commençait pas par '(' — "
            f"encadré automatiquement en '{wrapped}' (Keycloak exige une "
            f"expression LDAP complète, contrairement à certaines autres applis)."
        )
    raise ValueError(
        f"LDAP_SEARCH_FILTER='{raw}' invalide pour Keycloak : doit être une "
        f"expression LDAP complète entre parenthèses, ex. "
        f"(objectClass=inetOrgPerson) ou "
        f"(&(objectClass=inetOrgPerson)(memberOf=cn=x,ou=y,dc=z)) — "
        f"parenthèses non équilibrées ou absentes en tête/fin dans la valeur fournie."
    )


def build_variables(env):
    """Variables de substitution, avec défauts documentés dans .env.example.
    L'environnement du process (export HOST_IP=... etc.) prime sur .env."""
    get = lambda key, default="": os.environ.get(key, env.get(key, default))

    host = get("HOST_IP", "localhost") or "localhost"
    gateway_port = get("GATEWAY_PORT", "6443")

    ldap_search_filter, filter_note = normalize_ldap_filter(get("LDAP_SEARCH_FILTER", ""))

    # https:// par défaut, entrée UNIQUE par chemin (décidé en cours de
    # session, voir tls-proxy/README.md) — ces URLs alimentent les
    # redirectUris des clients OIDC, qui DOIVENT correspondre à ce que
    # le navigateur utilise réellement pour y arriver, sinon Keycloak
    # refuse la redirection après connexion (erreur "Invalid parameter:
    # redirect_uri" typique dans ce cas).
    variables = {
        "FRONTEND_PUBLIC_URL": get("SUPERVISION_FRONTEND_PUBLIC_URL", f"https://{host}:{gateway_port}/app"),
        "PORTAL_PUBLIC_URL": get("TICKETS_PORTAL_PUBLIC_URL", f"https://{host}:{gateway_port}/tickets"),
        "VAULT_PUBLIC_URL": get("VAULT_PORTAL_PUBLIC_URL", f"https://{host}:{gateway_port}/vault"),
        # Livraison #293 -- vault-admin-portal, PORT DIRECT (jamais
        # routé par tls-proxy, voir docker-compose.yml
        # VAULT_ADMIN_PORTAL_LAN_PORT) -- défaut SANS chemin /vault,
        # contrairement à VAULT_PUBLIC_URL ci-dessus.
        "VAULT_ADMIN_PORTAL_PUBLIC_URL": get("VAULT_ADMIN_PORTAL_PUBLIC_URL", f"https://{host}:{get('VAULT_ADMIN_PORTAL_LAN_PORT', '6120')}"),
        "HUB_PUBLIC_URL": get("SUPERVISION_HUB_PUBLIC_URL", f"https://{host}:{gateway_port}"),
        # Projet SÉPARÉ (trb140-sms-relay), PAS routé par notre
        # tls-proxy -- défaut placeholder explicite (même esprit que
        # LDAP_URL juste en dessous), jamais host:gateway_port qui
        # laisserait croire à tort que cette appli vit derrière notre
        # passerelle.
        "TRB140_SMS_RELAY_URL": get("TRB140_SMS_RELAY_URL", "https://trb140-sms-relay.example.local"),
        # Secret du compte de service prefs-api-service (droits
        # manage-clients UNIQUEMENT -- décidé explicitement avec la
        # personne, jamais un compte plus large) -- provisionnement en
        # direct des clients OIDC des applis externes depuis l'écran
        # d'administration du hub, voir keycloak/README.md.
        "PREFS_API_SERVICE_SECRET": get("PREFS_API_SERVICE_SECRET", "change-me"),
        "LDAP_URL": get("LDAP_URL", "ldap://ldap.example.local:389"),
        "LDAP_BIND_DN": get("LDAP_BIND_DN", "cn=lecture,dc=example,dc=local"),
        "LDAP_BIND_PASSWORD": get("LDAP_BIND_PASSWORD", "change-me"),
        "LDAP_USERS_DN": get("LDAP_USERS_DN", "ou=users,dc=example,dc=local"),
        "LDAP_USERNAME_ATTR": get("LDAP_USERNAME_ATTR", "uid"),
        "LDAP_RDN_ATTR": get("LDAP_RDN_ATTR", get("LDAP_USERNAME_ATTR", "uid")),
        "LDAP_UUID_ATTR": get("LDAP_UUID_ATTR", "entryUUID"),
        "LDAP_USER_OBJECT_CLASSES": get("LDAP_USER_OBJECT_CLASSES", "inetOrgPerson, organizationalPerson"),
        "LDAP_SEARCH_FILTER": ldap_search_filter,
        "LDAP_EDIT_MODE": get("LDAP_EDIT_MODE", "READ_ONLY"),
        "LDAP_VENDOR": get("LDAP_VENDOR", "other"),
        "LDAP_START_TLS": get("LDAP_START_TLS", "false"),
        # Mapper groupes LDAP -> rôles realm (facultatif)
        "LDAP_ROLES_ENABLED": get("LDAP_ROLES_ENABLED", "false").lower(),
        "LDAP_ROLES_DN": get("LDAP_ROLES_DN", "ou=groups,dc=example,dc=local"),
        "LDAP_ROLE_OBJECT_CLASSES": get("LDAP_ROLE_OBJECT_CLASSES", "groupOfNames"),
        "LDAP_ROLE_NAME_ATTR": get("LDAP_ROLE_NAME_ATTR", "cn"),
        "LDAP_ROLE_MEMBER_ATTR": get("LDAP_ROLE_MEMBER_ATTR", "member"),
    }
    return variables, filter_note


def extract_ldap_bind_credential(realm_dict):
    """Retrouve la valeur bindCredential dans un realm déjà parsé --
    séparée du reste pour rester testable directement (donner un dict
    construit à la main plutôt que devoir simuler une vraie corruption
    externe du fichier). None si la structure attendue est absente
    (realm sans composant LDAP configuré, par exemple)."""
    for component_list in realm_dict.get("components", {}).values():
        for component in component_list:
            if component.get("providerId") == "ldap":
                creds = component.get("config", {}).get("bindCredential")
                if creds:
                    return creds[0]
    return None


def substitute(node, variables):
    """Substitution récursive des __VAR__ dans les chaînes de l'arbre JSON.
    Une chaîne exactement égale à __VAR__ est remplacée par la valeur
    telle quelle (mot de passe avec caractères spéciaux inclus) ; les
    __VAR__ inclus dans une chaîne plus large sont remplacés en place."""
    if isinstance(node, dict):
        return {k: substitute(v, variables) for k, v in node.items()}
    if isinstance(node, list):
        return [substitute(v, variables) for v in node]
    if isinstance(node, str):
        for key, value in variables.items():
            token = f"__{key}__"
            if node == token:
                return value
            if token in node:
                node = node.replace(token, value)
        return node
    return node


def add_extra_origins(realm, base_url, extra_origins):
    """#473 : un hub joignable par PLUSIEURS origines (LAN + nom public
    derrière un frontal qui réécrit les URL) -- chaque client OIDC dont les
    redirectUris / webOrigins commencent par l'origine interne (base_url,
    ex. https://192.0.2.10:6443) reçoit en plus les mêmes entrées pour
    chaque origine supplémentaire (ex. https://hub.exemple.fr). Idempotent."""
    base = base_url.rstrip("/")
    extras = [o.rstrip("/") for o in extra_origins if o and o.rstrip("/") != base]
    if not extras:
        return 0
    added = 0
    for client in realm.get("clients", []):
        for key in ("redirectUris", "webOrigins"):
            uris = client.get(key) or []
            for uri in list(uris):
                if isinstance(uri, str) and uri.startswith(base):
                    for extra in extras:
                        candidate = extra + uri[len(base):]
                        if candidate not in uris:
                            uris.append(candidate); added += 1
            if uris:
                client[key] = uris
    return added


def role_mapper(variables):
    """Mapper groupes LDAP -> rôles realm (admin/demandeur/technicien/
    politique) — injecté seulement si LDAP_ROLES_ENABLED=true, sinon les
    rôles s'attribuent à la main dans la console Keycloak."""
    return {
        "name": "roles-depuis-groupes-ldap",
        "providerId": "role-ldap-mapper",
        "config": {
            "roles.dn": [variables["LDAP_ROLES_DN"]],
            "role.name.ldap.attribute": [variables["LDAP_ROLE_NAME_ATTR"]],
            "role.object.classes": [variables["LDAP_ROLE_OBJECT_CLASSES"]],
            "membership.ldap.attribute": [variables["LDAP_ROLE_MEMBER_ATTR"]],
            "membership.attribute.type": ["DN"],
            "membership.user.ldap.attribute": [variables["LDAP_USERNAME_ATTR"]],
            "mode": ["READ_ONLY"],
            "use.realm.roles.mapping": ["true"],
            "user.roles.retrieve.strategy": ["LOAD_ROLES_BY_MEMBER_ATTRIBUTE"],
            "memberof.ldap.attribute": ["memberOf"],
        },
    }


def leftover_tokens(node, found=None):
    """Contrôle final : plus aucun __TOKEN__ ne doit rester."""
    if found is None:
        found = set()
    if isinstance(node, dict):
        for v in node.values():
            leftover_tokens(v, found)
    elif isinstance(node, list):
        for v in node:
            leftover_tokens(v, found)
    elif isinstance(node, str) and "__" in node:
        import re
        for m in re.findall(r"__[A-Z0-9_]+__", node):
            found.add(m)
    return found


# Colonne interne Keycloak DESCRIPTION VARCHAR(255) -- bug réel
# rencontré : une description de rôle à 351 caractères a fait planter
# Keycloak au DÉMARRAGE (erreur SQL H2, pas une erreur d'import propre
# et lisible), jamais détecté avant parce que ce rôle n'avait jamais
# été réellement importé (voir la note en tête de fichier sur la
# sauvegarde retirée). Marge de sécurité sous la vraie limite (255),
# jamais pile dessus.
MAX_DESCRIPTION_LENGTH = 250


def find_oversized_descriptions(node, path="", found=None):
    """Parcourt tout l'arbre à la recherche de champs "description"
    trop longs pour la colonne Keycloak correspondante -- AVANT
    écriture, pour échouer clairement ici plutôt que par une erreur
    SQL obscure au démarrage de Keycloak, des jours plus tard."""
    if found is None:
        found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "description" and isinstance(value, str) and len(value) > MAX_DESCRIPTION_LENGTH:
                found.append((path, len(value)))
            find_oversized_descriptions(value, f"{path}.{key}", found)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            find_oversized_descriptions(item, f"{path}[{i}]", found)
    return found


def resolve_dir(env, var_name, default_dir):
    """Résolution générique d'un chemin de dossier configurable — même
    logique pour KEYCLOAK_IMPORT_DIR et KEYCLOAK_BACKUP_DIR (factorisé
    ici après un vrai trou trouvé en conditions réelles : le dossier de
    sauvegarde avait un chemin codé en dur, ne suivait PAS
    KEYCLOAK_IMPORT_DIR si personnalisé — les deux dossiers portent un
    secret Keycloak, un seul était configurable). Vide -> défaut
    historique, jamais un comportement différent silencieusement.
    Relatif -> résolu depuis la RACINE du projet (le script peut être
    invoqué depuis n'importe où) ; absolu -> utilisé tel quel,
    permettant justement un chemin hors de l'arborescence du projet.

    "~" REFUSÉ explicitement (ValueError) plutôt que silencieusement
    mal résolu -- bug réel rencontré en test : Python ne l'étend pas
    automatiquement, et docker-compose.yml ne le ferait pas non plus
    pour le montage de volume correspondant -- désynchronisation
    garantie entre les deux sinon."""
    raw = os.environ.get(var_name, env.get(var_name, "")).strip()
    if not raw:
        return default_dir
    if raw.startswith("~"):
        raise ValueError(
            f"{var_name}='{raw}' commence par '~' — non supporté : "
            f"Python ne l'étend pas automatiquement, et docker-compose.yml ne "
            f"le ferait pas non plus pour le montage de volume correspondant "
            f"(désynchronisation garantie entre les deux). Utiliser un chemin "
            f"absolu explicite, ex. /home/<utilisateur>/... plutôt que ~/..."
        )
    return raw if os.path.isabs(raw) else os.path.join(ROOT, raw)


def resolve_import_dir(env):
    """Dossier où le realm rendu (et son secret LDAP en clair) est
    écrit — voir resolve_dir() pour le détail complet du mécanisme."""
    return resolve_dir(env, "KEYCLOAK_IMPORT_DIR", DEFAULT_OUT_DIR)


def main():
    check_only = "--check" in sys.argv
    env = parse_env(os.path.join(ROOT, ".env"))
    try:
        variables, filter_note = build_variables(env)
        out_dir = resolve_import_dir(env)
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    out_path = os.path.join(out_dir, "supervision-si-realm.json")

    if filter_note:
        print(f"ℹ️  {filter_note}")

    with open(TEMPLATE, encoding="utf-8") as fh:
        realm = json.load(fh)

    realm = substitute(realm, variables)
    extra = [o.strip() for o in os.environ.get("KEYCLOAK_EXTRA_ORIGINS", env.get("KEYCLOAK_EXTRA_ORIGINS", "")).split(",") if o.strip()]
    n_extra = add_extra_origins(realm, variables["HUB_PUBLIC_URL"], extra)
    if n_extra:
        print(f"origines supplémentaires (KEYCLOAK_EXTRA_ORIGINS) : {n_extra} URL de redirection / origine ajoutée(s) pour {', '.join(extra)}")

    if variables["LDAP_ROLES_ENABLED"] == "true":
        provider = realm["components"]["org.keycloak.storage.UserStorageProvider"][0]
        provider["subComponents"]["org.keycloak.storage.ldap.mappers.LDAPStorageMapper"].append(
            role_mapper(variables)
        )

    remaining = leftover_tokens(realm)
    if remaining:
        print(f"ERREUR : jetons non substitués : {sorted(remaining)}", file=sys.stderr)
        return 1

    oversized = find_oversized_descriptions(realm)
    if oversized:
        print("ERREUR : description(s) dépassant la limite Keycloak (colonne DESCRIPTION VARCHAR(255)) :", file=sys.stderr)
        for path, length in oversized:
            print(f"  {path} : {length} caractères (max {MAX_DESCRIPTION_LENGTH})", file=sys.stderr)
        print("  Raccourcir avant de continuer -- sinon Keycloak plante au démarrage avec une", file=sys.stderr)
        print("  erreur SQL H2 obscure, pas une erreur d'import lisible.", file=sys.stderr)
        return 1

    if variables["LDAP_BIND_PASSWORD"] == "change-me":
        print("⚠️  LDAP_BIND_PASSWORD vaut encore 'change-me' — à renseigner dans .env avant usage réel.")

    if variables["PREFS_API_SERVICE_SECRET"] == "change-me":
        print("⚠️  PREFS_API_SERVICE_SECRET vaut encore 'change-me' — le provisionnement de clients OIDC")
        print("   en direct depuis le hub (écran Liens externes) échouera tant que ce secret n'est pas")
        print("   renseigné de façon identique ici ET côté prefs-api (voir docker-compose.yml).")

    if check_only:
        print("Rendu vérifié (aucune écriture) :")
        print(f"  destination : {out_path}")
        print(f"  frontend : {variables['FRONTEND_PUBLIC_URL']}")
        print(f"  portail  : {variables['PORTAL_PUBLIC_URL']}")
        print(f"  hub      : {variables['HUB_PUBLIC_URL']}")
        print(f"  trb140-sms-relay : {variables['TRB140_SMS_RELAY_URL']}")
        print(f"  LDAP     : {variables['LDAP_URL']} (users: {variables['LDAP_USERS_DN']})")
        print(f"  rôles via groupes LDAP : {variables['LDAP_ROLES_ENABLED']}")
        return 0

    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(realm, fh, ensure_ascii=False, indent=2)

    # Vérification post-écriture -- RELIT le fichier tel qu'il vient
    # d'être écrit sur le disque et confirme que le mot de passe de
    # liaison LDAP y figure bien en clair, pas remplacé par des
    # astérisques. Bug réel rencontré : Keycloak masque les
    # identifiants sensibles dans ses propres exports (comportement
    # documenté) -- si jamais quelque chose réécrit ce fichier après
    # coup (le volume était monté en lecture-écriture avant ce
    # correctif, voir docker-compose.yml), ce test le détecte
    # immédiatement plutôt que de laisser échouer l'authentification
    # en conditions réelles sans piste évidente.
    if variables["LDAP_BIND_PASSWORD"] != "change-me":
        with open(out_path, encoding="utf-8") as fh:
            written = json.load(fh)
        bind_credential = extract_ldap_bind_credential(written)
        if bind_credential is not None and bind_credential != variables["LDAP_BIND_PASSWORD"]:
            print("", file=sys.stderr)
            print("❌ ANOMALIE : le fichier réécrit ne contient PAS le mot de passe LDAP attendu", file=sys.stderr)
            print(f"   (trouvé un masquage ou une valeur différente -- vérifier {out_path} et", file=sys.stderr)
            print("   que rien d'autre n'écrit dans ce dossier après render.py).", file=sys.stderr)
            return 1

    print(f"Realm rendu -> {out_path}")
    if out_dir != DEFAULT_OUT_DIR:
        print(f"  (KEYCLOAK_IMPORT_DIR personnalisé — vérifier que docker-compose.yml monte bien ce même chemin)")
    print(f"  frontend : {variables['FRONTEND_PUBLIC_URL']}")
    print(f"  portail  : {variables['PORTAL_PUBLIC_URL']}")
    print(f"  hub      : {variables['HUB_PUBLIC_URL']}")
    print(f"  trb140-sms-relay : {variables['TRB140_SMS_RELAY_URL']}")
    print(f"  LDAP     : {variables['LDAP_URL']}")
    print(f"  rôles via groupes LDAP : {variables['LDAP_ROLES_ENABLED']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
