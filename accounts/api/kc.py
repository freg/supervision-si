"""Client de l'API Admin REST Keycloak pour la gestion des comptes et des
groupes (livraison #557) -- logique pure autour de `requests`, testée avec
un serveur simulé dans accounts/tests/test_accounts.py.

Authentification : compte de service de bootstrap (KEYCLOAK_SERVICE_CLIENT_ID
/ SECRET, grant client_credentials sur le realm master) -- les mêmes
identifiants que tickets-api et keycloak/group_memberships.py, jamais une
nouvelle variable. Aucun mot de passe n'est jamais renvoyé ni journalisé.

Utilisateurs fédérés LDAP : Keycloak écrit dans l'annuaire seulement si la
fédération est en `WRITABLE` (LDAP_EDIT_MODE) ; en READ_ONLY la création
d'un compte est refusée par Keycloak et l'erreur est renvoyée en clair.
"""
import os
import time

import requests


class KeycloakError(Exception):
    """Erreur présentable telle quelle (jamais une trace brute)."""


class Keycloak:
    def __init__(self, base_url=None, realm=None, client_id=None, client_secret=None, timeout=10, session=None):
        self.base_url = (base_url or os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")).rstrip("/")
        self.realm = realm or os.environ.get("KEYCLOAK_REALM", "supervision-si")
        self.client_id = client_id or os.environ.get("KEYCLOAK_SERVICE_CLIENT_ID", "supervision-si-service")
        self.client_secret = client_secret or os.environ.get("KEYCLOAK_SERVICE_CLIENT_SECRET", "")
        self.timeout = timeout
        self.s = session or requests.Session()
        self._token, self._token_at = None, 0

    # ------------------------------------------------------------ transport
    def token(self):
        if self._token and time.time() - self._token_at < 50:
            return self._token
        try:
            r = self.s.post(f"{self.base_url}/realms/master/protocol/openid-connect/token",
                            data={"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise KeycloakError("Keycloak injoignable : %s" % exc.__class__.__name__)
        if r.status_code != 200:
            raise KeycloakError("authentification du compte de service refusée (%s)" % r.status_code)
        self._token, self._token_at = r.json().get("access_token"), time.time()
        return self._token

    def req(self, method, path, body=None, params=None, ok=(200, 201, 204)):
        url = f"{self.base_url}/admin/realms/{self.realm}{path}"
        try:
            r = self.s.request(method, url, json=body, params=params, headers={"Authorization": "Bearer " + self.token()}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise KeycloakError("Keycloak injoignable : %s" % exc.__class__.__name__)
        if r.status_code not in ok:
            detail = ""
            try:
                j = r.json()
                detail = j.get("errorMessage") or j.get("error_description") or j.get("error") or ""
            except ValueError:
                detail = (r.text or "")[:200]
            if r.status_code == 409:
                raise KeycloakError("déjà existant : %s" % (detail or "conflit"))
            if r.status_code == 404:
                raise KeycloakError("introuvable")
            if r.status_code == 403:
                raise KeycloakError("le compte de service n'a pas le droit (%s)" % (detail or "403"))
            raise KeycloakError("Keycloak a répondu %s %s" % (r.status_code, detail))
        if r.status_code == 204 or not r.content:
            return r
        try:
            return r.json()
        except ValueError:
            return r

    # ------------------------------------------------------------ événements (#612)
    def events(self, types=None, max_results=300, first=0, user_id=None, ip=None):
        params = [("max", max_results), ("first", first)]
        for t in types or []:
            params.append(("type", t))
        if user_id:
            params.append(("user", user_id))
        if ip:
            params.append(("ipAddress", ip))
        return self.req("GET", "/events", params=params) or []

    def events_config(self):
        return self.req("GET", "/events/config") or {}

    def set_events_config(self, cfg):
        self.req("PUT", "/events/config", cfg)

    # ------------------------------------------------------------ réglages du realm (#614, liste blanche dans kcsettings.py)
    def realm(self):
        return self.req("GET", "") or {}

    def update_realm(self, body):
        self.req("PUT", "", body)

    def oidc_clients(self):
        return [c for c in (self.req("GET", "/clients", params={"max": 500}) or []) if c.get("protocol", "openid-connect") == "openid-connect"]

    def update_client_uris(self, live_id, updates):
        self.req("PUT", f"/clients/{live_id}", {"id": live_id, **updates})

    def user_storage_components(self):
        return self.req("GET", "/components", params={"type": "org.keycloak.storage.UserStorageProvider"}) or []

    def ldap_sync(self, component_id, full=True):
        return self.req("POST", f"/user-storage/{component_id}/sync", params={"action": "triggerFullSync" if full else "triggerChangedUsersSync"}) or {}

    # ------------------------------------------------------------ groupes
    def groups(self):
        out = []
        for g in self.req("GET", "/groups", params={"max": 500, "briefRepresentation": "true"}) or []:
            out.append({"id": g.get("id"), "name": g.get("name"), "path": g.get("path")})
        return sorted(out, key=lambda g: (g["name"] or "").lower())

    def group_by_name(self, name):
        return next((g for g in self.groups() if g["name"] == name), None)

    def create_group(self, name):
        name = (name or "").strip()
        if not name or len(name) > 64 or any(c in name for c in "/\\"):
            raise KeycloakError("nom de groupe invalide (1-64 caractères, sans / ni \\)")
        self.req("POST", "/groups", {"name": name})
        return self.group_by_name(name)

    def delete_group(self, group_id):
        self.req("DELETE", f"/groups/{group_id}")

    def group_members(self, group_id):
        return [_user_repr(u) for u in self.req("GET", f"/groups/{group_id}/members", params={"max": 500}) or []]

    # ------------------------------------------------------------ utilisateurs
    def users(self, search=None, max_results=200):
        params = {"max": max_results, "briefRepresentation": "false"}
        if search:
            params["search"] = search
        users = [_user_repr(u) for u in self.req("GET", "/users", params=params) or []]
        for u in users:
            u["groups"] = [g.get("name") for g in self.req("GET", f"/users/{u['id']}/groups", params={"max": 100}) or []]
        return sorted(users, key=lambda u: (u["username"] or "").lower())

    def user(self, user_id):
        u = _user_repr(self.req("GET", f"/users/{user_id}"))
        u["groups"] = [g.get("name") for g in self.req("GET", f"/users/{user_id}/groups", params={"max": 100}) or []]
        return u

    def create_user(self, username, email=None, first_name=None, last_name=None, enabled=True, groups=None, password=None, temporary=True):
        username = (username or "").strip().lower()
        if not username or len(username) > 64:
            raise KeycloakError("identifiant requis (64 caractères max)")
        body = {"username": username, "email": (email or "").strip() or None, "firstName": (first_name or "").strip() or None,
                "lastName": (last_name or "").strip() or None, "enabled": bool(enabled), "emailVerified": bool(email)}
        body = {k: v for k, v in body.items() if v is not None}
        if password:
            body["credentials"] = [{"type": "password", "value": password, "temporary": bool(temporary)}]
        self.req("POST", "/users", body)
        found = self.req("GET", "/users", params={"username": username, "exact": "true"}) or []
        if not found:
            raise KeycloakError("compte créé mais introuvable ensuite (fédération LDAP ?)")
        uid = found[0]["id"]
        if groups:
            self.set_groups(uid, groups)
        return self.user(uid)

    def update_user(self, user_id, **fields):
        allowed = {"email": "email", "first_name": "firstName", "last_name": "lastName", "enabled": "enabled"}
        body = {allowed[k]: v for k, v in fields.items() if k in allowed and v is not None}
        if not body:
            return self.user(user_id)
        cur = self.req("GET", f"/users/{user_id}")
        cur.update(body)
        self.req("PUT", f"/users/{user_id}", cur)
        return self.user(user_id)

    def delete_user(self, user_id):
        self.req("DELETE", f"/users/{user_id}")

    def set_groups(self, user_id, names):
        """Rend l'appartenance ÉGALE à `names` (ajouts et retraits)."""
        wanted = {n for n in names or [] if n}
        by_name = {g["name"]: g["id"] for g in self.groups()}
        unknown = sorted(wanted - set(by_name))
        if unknown:
            raise KeycloakError("groupe inconnu : %s" % ", ".join(unknown))
        current = {g.get("name"): g.get("id") for g in self.req("GET", f"/users/{user_id}/groups", params={"max": 100}) or []}
        for n in wanted - set(current):
            self.req("PUT", f"/users/{user_id}/groups/{by_name[n]}")
        for n in set(current) - wanted:
            self.req("DELETE", f"/users/{user_id}/groups/{current[n]}")
        return sorted(wanted)

    def set_password(self, user_id, password, temporary=True):
        if not password or len(password) < 8:
            raise KeycloakError("mot de passe : 8 caractères minimum")
        self.req("PUT", f"/users/{user_id}/reset-password", {"type": "password", "value": password, "temporary": bool(temporary)})

    def send_reset_email(self, user_id):
        self.req("PUT", f"/users/{user_id}/execute-actions-email", ["UPDATE_PASSWORD"])

    def logout(self, user_id):
        self.req("POST", f"/users/{user_id}/logout")


def _user_repr(u):
    u = u or {}
    return {"id": u.get("id"), "username": u.get("username"), "email": u.get("email"), "first_name": u.get("firstName"), "last_name": u.get("lastName"),
            "enabled": bool(u.get("enabled", True)), "federated": bool(u.get("federationLink")), "created_at": u.get("createdTimestamp"),
            "required_actions": u.get("requiredActions") or []}
