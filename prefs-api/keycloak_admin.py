"""
Client HTTP minimal vers l'API Admin REST de Keycloak -- réservé au
provisionnement de clients OIDC pour les liens externes (voir
ExternalLinksAdminView côté hub, routes /external-links/<id>/keycloak
dans app.py). Backlog "interface d'intégration Keycloak", livraison
#124.

Authentification via le compte de service dédié "prefs-api-service"
(grant client_credentials -- PAS le grant password utilisé par
keycloak/group_memberships.py : celui-là s'authentifie comme un vrai
utilisateur avec le mot de passe admin COMPLET, celui-ci est un
compte de service confidentiel aux droits volontairement limités --
manage-clients UNIQUEMENT, décidé explicitement avec la personne
plutôt que de réutiliser l'accès admin complet déjà en place). Peut
créer/modifier/supprimer des CLIENTS OIDC, mais PAS créer de nouveaux
RÔLES REALM (ça relève de manage-realm, un droit plus large --
volontairement pas donné ici) -- voir keycloak/README.md pour cette
limite assumée. Les rôles applicatifs propres à une appli externe
(ex. send/full/compose pour trb140-sms-relay) restent donc un ajout
manuel dans keycloak/realm-template.json pour l'instant.

stdlib uniquement (urllib) -- même choix que group_memberships.py,
pas de nouvelle dépendance pour un besoin aussi ciblé.

**Jamais testé contre un vrai Keycloak dans cet environnement de
développement** (aucun réseau, aucun Keycloak réellement démarré ici)
-- vérifié uniquement par construction de requêtes (urllib.request.
urlopen mocké), voir prefs-api/README.md ou hub/README.md pour le
détail de ce qui a pu/n'a pas pu être vérifié.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class KeycloakAdminError(Exception):
    """Erreur remontée par l'API Admin Keycloak -- message déjà
    présentable tel quel à l'admin (jamais une trace Python brute
    renvoyée côté client)."""


class KeycloakNotFoundError(KeycloakAdminError):
    """Cas particulier -- 404 précisément, distingué des autres
    erreurs pour permettre un traitement idempotent explicite (voir
    delete_oidc_client) sans reposer sur un test fragile du message
    d'erreur."""


def _base_url():
    return os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth").rstrip("/")


def _realm():
    return os.environ.get("KEYCLOAK_REALM", "supervision-si")


def _service_client_id():
    return os.environ.get("KEYCLOAK_SERVICE_CLIENT_ID", "prefs-api-service")


def _service_client_secret():
    return os.environ.get("KEYCLOAK_SERVICE_CLIENT_SECRET", "")


def public_issuer():
    """URL d'issuer PUBLIQUE (jamais l'adresse interne Docker
    utilisée pour les appels Admin ci-dessus) -- c'est CETTE valeur
    que l'appli externe doit configurer comme émetteur OIDC, joignable
    depuis son propre navigateur/serveur. Même formule que
    VITE_KEYCLOAK_URL côté hub/tickets-portal (docker-compose.yml)."""
    base = os.environ.get("KEYCLOAK_PUBLIC_URL", "").rstrip("/")
    return f"{base}/realms/{_realm()}" if base else None


def get_token():
    """Jeton du compte de service (grant client_credentials) --
    JAMAIS mis en cache : un provisionnement est une action ADMIN
    ponctuelle (pas un usage assez fréquent pour justifier la
    complexité d'un cache avec expiration à gérer)."""
    data = urllib.parse.urlencode({
        "client_id": _service_client_id(),
        "client_secret": _service_client_secret(),
        "grant_type": "client_credentials",
    }).encode()
    req = urllib.request.Request(
        f"{_base_url()}/realms/{_realm()}/protocol/openid-connect/token", data=data,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)["access_token"]
    except urllib.error.HTTPError as exc:
        raise KeycloakAdminError(
            f"Authentification du compte de service Keycloak refusée ({exc.code}) -- "
            "PREFS_API_SERVICE_SECRET est-il identique ici et côté Keycloak ?"
        ) from exc
    except urllib.error.URLError as exc:
        raise KeycloakAdminError(f"Keycloak injoignable ({exc.reason}) -- le service tourne-t-il ?") from exc


def _admin_request(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{_base_url()}/admin/realms/{_realm()}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            location = resp.headers.get("Location")
            body_text = resp.read()
            parsed = json.loads(body_text) if body_text else None
            return parsed, location
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 404:
            raise KeycloakNotFoundError(f"Ressource introuvable côté Keycloak (404) : {detail[:300]}") from exc
        raise KeycloakAdminError(f"Keycloak a refusé la requête ({exc.code}) : {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise KeycloakAdminError(f"Keycloak injoignable ({exc.reason}).") from exc


def find_client_by_client_id(client_id, token):
    """Renvoie le client Keycloak (dict) portant ce clientId, ou None.
    Vérifié AVANT toute création -- le modèle Keycloak n'empêche pas
    deux clients distincts de porter le même clientId "affiché",
    source de confusion réelle -- jamais laissé arriver silencieusement
    ici."""
    clients, _ = _admin_request("GET", f"/clients?clientId={urllib.parse.quote(client_id)}", token)
    return clients[0] if clients else None


def create_oidc_client(client_id, name, redirect_uri, token):
    """Crée un client OIDC PUBLIC (Authorization Code + PKCE), même
    patron que les clients internes du projet (voir
    keycloak/realm-template.json) -- mapper `groups` inclus (l'appli
    peut lire les groupes Keycloak de l'utilisateur si besoin), PAS de
    mapper audience-apis (une appli externe n'appelle jamais nos APIs
    internes -- même raisonnement que pour trb140-sms-relay). Renvoie
    l'id INTERNE (UUID) du client créé -- Keycloak ne le renvoie que
    dans l'en-tête Location d'une réponse 201 sans corps, jamais dans
    le corps lui-même (comportement standard de cette API)."""
    parsed = urllib.parse.urlparse(redirect_uri)
    web_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else redirect_uri
    body = {
        "clientId": client_id,
        "name": name,
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": True,
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "fullScopeAllowed": True,
        "redirectUris": [redirect_uri],
        "webOrigins": [web_origin],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": f"{web_origin}/*",
        },
        "protocolMappers": [
            {
                "name": "groups",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                },
            },
        ],
    }
    _, location = _admin_request("POST", "/clients", token, body=body)
    return location.rstrip("/").rsplit("/", 1)[-1] if location else None


def delete_oidc_client(internal_id, token):
    """Supprime un client par son id INTERNE (UUID, PAS le clientId
    affiché) -- IDEMPOTENT : un 404 (client déjà absent, par exemple
    supprimé à la main dans la console Keycloak) est traité comme un
    succès silencieux, jamais une erreur bloquante qui empêcherait de
    "retirer" un lien côté external_links pour une ressource qui, de
    fait, n'existe déjà plus côté Keycloak."""
    try:
        _admin_request("DELETE", f"/clients/{internal_id}", token)
    except KeycloakNotFoundError:
        pass
