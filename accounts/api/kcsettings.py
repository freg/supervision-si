"""Réglages Keycloak depuis le hub, en liste blanche (livraison #614, item 98).

Demandé : « rester (ou créer une interface) dans le hub pour modifier la
configuration du Keycloak, en limitant ou protégeant les parties
névralgiques ». Ici : les SEULS réglages du realm que le hub accepte de
lire et d'écrire (`FIELDS`), avec type et bornes ; tout le reste de la
représentation du realm est ignoré en lecture et jamais renvoyé à Keycloak
en écriture (`plan` ne produit que les champs de la liste qui changent).

Protégé / interdit par construction : realm master, nom / suppression du
realm, clients de service et secrets, rôles realm-management, comptes,
mot de passe de liaison LDAP (jamais lu : Keycloak le masque, on ne le
renvoie pas). Les origines des clients OIDC ne s'ajoutent que par
`origin_plan` (dérivation des URL existantes, jamais de retrait).
"""
import re

SECONDS = "seconds"
FIELDS = {
    # clé Keycloak : (libellé, type, min, max, groupe)
    "displayName": ("Nom affiché du realm", "text", 0, 120, "general"),
    "displayNameHtml": ("Nom affiché (HTML, page de connexion)", "text", 0, 300, "general"),
    "loginTheme": ("Thème de connexion", "text", 0, 60, "general"),
    "defaultLocale": ("Langue par défaut", "text", 0, 8, "general"),
    "rememberMe": ("« Se souvenir de moi »", "bool", None, None, "login"),
    "resetPasswordAllowed": ("Mot de passe oublié (lien sur la page de connexion)", "bool", None, None, "login"),
    "loginWithEmailAllowed": ("Connexion par adresse e-mail", "bool", None, None, "login"),
    "ssoSessionIdleTimeout": ("Session : inactivité maximale", SECONDS, 60, 30 * 86400, "sessions"),
    "ssoSessionMaxLifespan": ("Session : durée maximale", SECONDS, 60, 90 * 86400, "sessions"),
    "accessTokenLifespan": ("Jeton d'accès : durée de vie", SECONDS, 60, 86400, "sessions"),
    "offlineSessionIdleTimeout": ("Session hors ligne : inactivité maximale", SECONDS, 60, 365 * 86400, "sessions"),
    "bruteForceProtected": ("Protection force brute", "bool", None, None, "bruteforce"),
    "permanentLockout": ("Blocage permanent après échecs (sinon temporaire)", "bool", None, None, "bruteforce"),
    "failureFactor": ("Échecs avant blocage", "int", 1, 100, "bruteforce"),
    "waitIncrementSeconds": ("Attente ajoutée à chaque blocage", SECONDS, 1, 3600, "bruteforce"),
    "maxFailureWaitSeconds": ("Attente maximale", SECONDS, 1, 86400, "bruteforce"),
    "maxDeltaTimeSeconds": ("Fenêtre de comptage des échecs", SECONDS, 60, 7 * 86400, "bruteforce"),
    "minimumQuickLoginWaitSeconds": ("Attente après connexions trop rapides", SECONDS, 1, 3600, "bruteforce"),
    "passwordPolicy": ("Politique de mots de passe (ex. length(12) and digits(1))", "text", 0, 500, "passwords"),
    "eventsExpiration": ("Conservation des événements", SECONDS, 3600, 365 * 86400, "events"),
}
GROUPS = {"general": "Général", "login": "Page de connexion", "sessions": "Sessions et jetons", "bruteforce": "Protection force brute",
          "passwords": "Mots de passe", "events": "Événements"}
POLICY_RE = re.compile(r"^[A-Za-z0-9_()\s,.\-]*$")
ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d{2,5})?$")


def describe():
    return [{"key": k, "label": v[0], "type": v[1], "min": v[2], "max": v[3], "group": v[4]} for k, v in FIELDS.items()]


def current(realm):
    """Représentation du realm -> uniquement les champs de la liste blanche."""
    return {k: (realm or {}).get(k) for k in FIELDS}


def _coerce(key, value):
    label, kind, lo, hi, _ = FIELDS[key]
    if kind == "bool":
        if isinstance(value, bool):
            return value, None
        if str(value).lower() in ("true", "1", "oui", "on"):
            return True, None
        if str(value).lower() in ("false", "0", "non", "off", ""):
            return False, None
        return None, "%s : oui / non" % label
    if kind in ("int", SECONDS):
        try:
            v = int(value)
        except (TypeError, ValueError):
            return None, "%s : entier attendu" % label
        if v < lo or v > hi:
            return None, "%s : entre %d et %d%s" % (label, lo, hi, " s" if kind == SECONDS else "")
        return v, None
    v = "" if value is None else str(value).strip()
    if len(v) > hi:
        return None, "%s : %d caractères maximum" % (label, hi)
    if key == "passwordPolicy" and not POLICY_RE.match(v):
        return None, "%s : caractères autorisés lettres, chiffres, ( ) , . - _" % label
    if key in ("displayNameHtml",) and re.search(r"<\s*script", v, re.I):
        return None, "%s : pas de script" % label
    return v, None


def plan(realm, wanted):
    """-> (changes {clé: {before, after}}, erreurs). Clés hors liste : refusées
    (signalées, jamais appliquées en silence). Champs inchangés ignorés."""
    changes, errors = {}, []
    cur = current(realm)
    for key, value in (wanted or {}).items():
        if key not in FIELDS:
            errors.append("%s : réglage non modifiable depuis le hub" % key)
            continue
        v, err = _coerce(key, value)
        if err:
            errors.append(err)
            continue
        if v != cur.get(key):
            changes[key] = {"before": cur.get(key), "after": v}
    return changes, errors


def apply_body(changes):
    """Corps du PUT : uniquement les champs changés (Keycloak accepte une
    représentation partielle du realm)."""
    return {k: c["after"] for k, c in (changes or {}).items()}


def origin_plan(clients, base_origin, origin):
    """Dérive pour chaque client OIDC dont les redirectUris commencent par
    l'origine interne les mêmes entrées pour `origin` -- même règle que
    keycloak/render.py add_extra_origins. -> ([(clientId, id, {clé: liste})], erreur)."""
    o = (origin or "").strip().rstrip("/")
    if not ORIGIN_RE.match(o):
        return [], "origine : https://nom-ou-ip[:port], sans chemin"
    base = (base_origin or "").rstrip("/")
    out = []
    for c in clients or []:
        updates = {}
        for key in ("redirectUris", "webOrigins"):
            uris = [u for u in (c.get(key) or []) if isinstance(u, str)]
            add = []
            for u in uris:
                if u.startswith(base):
                    cand = o + u[len(base):]
                    if cand not in uris and cand not in add:
                        add.append(cand)
            if add:
                updates[key] = uris + add
        if updates:
            out.append((c.get("clientId"), c.get("id"), updates))
    return out, None


def ldap_providers(components):
    """Composants UserStorageProvider -> vue sans secret."""
    out = []
    for c in components or []:
        if c.get("providerId") != "ldap":
            continue
        cfg = c.get("config") or {}
        first = lambda k: (cfg.get(k) or [None])[0]
        out.append({"id": c.get("id"), "name": c.get("name"), "url": first("connectionUrl"), "users_dn": first("usersDn"),
                    "bind_dn": first("bindDn"), "edit_mode": first("editMode"), "enabled": str(first("enabled")).lower() != "false",
                    "sync_period": first("fullSyncPeriod"), "changed_sync_period": first("changedSyncPeriod"),
                    "last_sync": first("lastSync")})
    return out
