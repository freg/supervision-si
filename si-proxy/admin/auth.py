# -*- coding: utf-8 -*-
"""Vérification d'identité de si-proxy-admin-api (livraison #454).

PREMIÈRE API du projet à VÉRIFIER RÉELLEMENT le jeton Keycloak plutôt qu'à
faire confiance à des `groups` envoyés dans le corps : le bastion est
réservé à une personne (freg), donc le pont vers son interface de contrôle
exige un jeton d'accès OIDC valide (signature RS256 contre les clés
publiques du realm, expiration) ET un `preferred_username` dans la liste
blanche `SI_PROXY_ADMIN_USERS`.

Logique PURE (récupération des clés injectable) : testable avec une paire
RSA jetable, sans Keycloak.
"""
import json
import time
import urllib.request

import jwt
from jwt.algorithms import RSAAlgorithm


class AuthError(Exception):
    def __init__(self, message, status=401):
        Exception.__init__(self, message)
        self.status = status


class KeycloakVerifier(object):
    """Vérifie un access token Keycloak. `jwks_url` = .../protocol/openid-connect/certs
    (URL INTERNE Docker) ; `fetch` injectable pour les tests ; cache des clés
    rafraîchi au plus toutes les `refresh_s` secondes ou sur `kid` inconnu."""

    def __init__(self, jwks_url, allowed_users, fetch=None, refresh_s=300, clock=time.time,
                 expected_azp=None):
        self.jwks_url = jwks_url
        self.allowed_users = set(u.strip().lower() for u in (allowed_users or []) if u and u.strip())
        self.fetch = fetch or self._http_fetch
        self.refresh_s = refresh_s
        self.clock = clock
        self.expected_azp = expected_azp
        self._keys = {}          # kid -> clé publique
        self._loaded_at = 0

    @staticmethod
    def _http_fetch(url):
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 (URL interne configurée)
            return json.loads(resp.read().decode("utf-8"))

    def _load_keys(self, force=False):
        now = self.clock()
        if not force and self._keys and now - self._loaded_at < self.refresh_s:
            return
        try:
            doc = self.fetch(self.jwks_url)
        except Exception as exc:  # noqa: BLE001
            if self._keys:
                return  # on garde les clés connues si Keycloak est momentanément injoignable
            raise AuthError("clés de signature Keycloak injoignables : %s" % exc, 503)
        keys = {}
        for k in doc.get("keys", []):
            if k.get("kty") == "RSA" and k.get("use", "sig") == "sig" and k.get("kid"):
                keys[k["kid"]] = RSAAlgorithm.from_jwk(json.dumps(k))
        self._keys = keys
        self._loaded_at = now

    def _key_for(self, token):
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthError("jeton illisible : %s" % exc)
        kid = header.get("kid")
        self._load_keys()
        if kid not in self._keys:
            self._load_keys(force=True)  # rotation de clés côté Keycloak
        key = self._keys.get(kid)
        if key is None:
            raise AuthError("clé de signature inconnue")
        return key

    def verify(self, token):
        """-> {username, name, groups} ou lève AuthError (401 jeton invalide,
        403 utilisateur non autorisé, 503 Keycloak injoignable)."""
        if not token:
            raise AuthError("jeton d'accès requis")
        key = self._key_for(token)
        try:
            claims = jwt.decode(token, key=key, algorithms=["RS256"], options={"verify_aud": False},
                                leeway=30)
        except jwt.ExpiredSignatureError:
            raise AuthError("jeton expiré")
        except jwt.PyJWTError as exc:
            raise AuthError("jeton invalide : %s" % exc)
        if claims.get("typ") not in (None, "Bearer"):
            raise AuthError("type de jeton inattendu")
        if self.expected_azp and claims.get("azp") != self.expected_azp:
            raise AuthError("jeton émis pour un autre client (azp)")
        username = (claims.get("preferred_username") or "").strip().lower()
        if not username:
            raise AuthError("jeton sans preferred_username")
        if username not in self.allowed_users:
            raise AuthError("utilisateur « %s » non autorisé sur le bastion" % username, 403)
        return {"username": username, "name": claims.get("name") or username,
                "groups": list(claims.get("groups") or [])}


def bearer_from_header(value):
    """'Bearer xyz' -> 'xyz' ; None sinon."""
    if not value:
        return None
    parts = value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None
