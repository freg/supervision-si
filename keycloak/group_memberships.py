#!/usr/bin/env python3
"""
Capture et restaure les appartenances aux groupes Keycloak pour les
utilisateurs fédérés LDAP -- ces appartenances ne vivent QUE dans la
base interne de Keycloak (ni dans LDAP -- rôles via groupes LDAP
désactivé dans ce projet --, ni dans realm-template.json, qui ne
définit que les groupes eux-mêmes en tant qu'entités, jamais qui en
fait partie). Toute purge du volume Keycloak (voir scripts/run.sh)
les efface donc silencieusement, sans exception possible avec
l'architecture actuelle -- bug réel rencontré et documenté (groupes
perdus après un incident LDAP, puis à nouveau après un réimport pour
ajouter le client vault-portal).

`keycloak/backup/backup-loop.sh` existant sauvegarde déjà le realm via
`partial-export` -- mais cette API Keycloak n'exporte QUE la structure
des groupes (quels groupes existent), jamais qui en est membre. Ce
script comble précisément ce manque, en s'appuyant sur la même API
Admin REST (client `admin-cli`, grant password) que ce backup.

Usage :
  python3 keycloak/group_memberships.py export   # avant une purge du volume
  python3 keycloak/group_memberships.py restore  # après un réimport, LDAP synchronisé

`export` : à lancer PENDANT que Keycloak tourne encore avec ses
groupes actuels -- appelé automatiquement par scripts/run.sh juste
avant de proposer une purge.

`restore` : à lancer manuellement APRÈS un réimport, une fois Keycloak
redémarré ET la synchronisation LDAP relancée ("Sync all users" dans
la console) -- sans quoi les utilisateurs n'existent pas encore
localement, rien à quoi rattacher un groupe. Jamais automatiquement
enchaîné après un `up` : le délai de démarrage de Keycloak et le
moment où lancer la synchronisation LDAP varient trop pour être fiables
sans confirmation de la personne.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REALM = "supervision-si"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup", "group-memberships.json")


def get_env(name, default=""):
    return os.environ.get(name, default)


def kc_base():
    # Port LAN direct (voir keycloak/README.md, "Accès direct de
    # secours") -- ce script tourne sur l'hôte (appelé par
    # scripts/run.sh), jamais dans un conteneur, pas besoin de passer
    # par tls-proxy. Lié spécifiquement à HOST_IP côté docker-compose
    # (pas 0.0.0.0), donc HOST_IP ici aussi, pas juste "localhost".
    host = get_env("HOST_IP") or "localhost"
    port = get_env("KEYCLOAK_PORT", "6180")
    return f"http://{host}:{port}/auth"


def get_token():
    # Compte de SERVICE de bootstrap (livraison #361) -- voir
    # keycloak/README.md pour le raisonnement complet du passage
    # depuis l'utilisateur de bootstrap (grant_type=password), même
    # changement que backup-loop.sh et tickets/api/app.py.
    data = urllib.parse.urlencode({
        "client_id": get_env("KEYCLOAK_SERVICE_CLIENT_ID", "supervision-si-service"),
        "client_secret": get_env("KEYCLOAK_SERVICE_CLIENT_SECRET", "change-me"),
        "grant_type": "client_credentials",
    }).encode()
    req = urllib.request.Request(f"{kc_base()}/realms/master/protocol/openid-connect/token", data=data)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)["access_token"]


def api_get(path, token):
    req = urllib.request.Request(f"{kc_base()}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def api_put_empty(path, token):
    req = urllib.request.Request(f"{kc_base()}{path}", headers={"Authorization": f"Bearer {token}"}, method="PUT")
    req.add_header("Content-Length", "0")
    urllib.request.urlopen(req, timeout=15)


def export_memberships(token=None):
    """Renvoie {login: [nom_de_groupe, ...]} pour CHAQUE groupe du
    realm -- une seule structure, jamais un fichier par groupe (plus
    simple à comparer/versionner)."""
    token = token or get_token()
    groups = api_get(f"/admin/realms/{REALM}/groups", token)
    mapping = {}
    for group in groups:
        members = api_get(f"/admin/realms/{REALM}/groups/{group['id']}/members?max=1000", token)
        for member in members:
            username = member.get("username")
            if not username:
                continue
            mapping.setdefault(username, []).append(group["name"])
    return mapping


def write_export(mapping, path=OUTPUT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)


def restore_memberships(mapping, token=None):
    """Réapplique `mapping` ({login: [groupes]}) sur le realm ACTUEL --
    résout les noms en identifiants à chaque appel (jamais des
    identifiants figés dans le fichier exporté : ils changent à
    chaque réimport, seuls les NOMS de groupes/logins restent
    stables). Jamais bloquant sur un échec individuel (utilisateur pas
    encore synchronisé, groupe renommé...) -- continue et RAPPORTE ce
    qui a échoué plutôt que de s'arrêter au premier problème.
    Renvoie (nb_restaurees, [(login, groupe, raison), ...])."""
    token = token or get_token()
    groups = api_get(f"/admin/realms/{REALM}/groups", token)
    group_id_by_name = {g["name"]: g["id"] for g in groups}

    restored = 0
    failures = []
    for username, group_names in mapping.items():
        users = api_get(f"/admin/realms/{REALM}/users?username={urllib.parse.quote(username)}&exact=true", token)
        if not users:
            for group_name in group_names:
                failures.append((username, group_name, "utilisateur introuvable (LDAP pas encore synchronisé ?)"))
            continue
        user_id = users[0]["id"]
        for group_name in group_names:
            group_id = group_id_by_name.get(group_name)
            if not group_id:
                failures.append((username, group_name, "groupe introuvable dans le realm actuel"))
                continue
            try:
                api_put_empty(f"/admin/realms/{REALM}/users/{user_id}/groups/{group_id}", token)
                restored += 1
            except urllib.error.HTTPError as exc:
                failures.append((username, group_name, f"HTTP {exc.code}"))
    return restored, failures


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("export", "restore"):
        print("Usage : python3 keycloak/group_memberships.py [export|restore]", file=sys.stderr)
        sys.exit(1)

    try:
        token = get_token()
    except Exception as exc:  # noqa: BLE001 — Keycloak indisponible/identifiants admin invalides, message clair plutôt qu'une trace Python brute
        print(f"Impossible de s'authentifier auprès de Keycloak : {exc}", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "export":
        mapping = export_memberships(token)
        write_export(mapping)
        total_memberships = sum(len(g) for g in mapping.values())
        print(f"{len(mapping)} utilisateur(s), {total_memberships} appartenance(s) exportée(s) -> {OUTPUT_PATH}")
    else:
        if not os.path.exists(OUTPUT_PATH):
            print(f"Aucune sauvegarde trouvée ({OUTPUT_PATH}) -- rien à restaurer.")
            return
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            mapping = json.load(f)
        restored, failures = restore_memberships(mapping, token)
        print(f"{restored} appartenance(s) restaurée(s).")
        if failures:
            print(f"{len(failures)} échec(s) :")
            for username, group_name, reason in failures:
                print(f"  - {username} / {group_name} : {reason}")


if __name__ == "__main__":
    main()
