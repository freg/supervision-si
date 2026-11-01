"""Journal des connexions (livraison #612) -- événements Keycloak du realm
(LOGIN, LOGIN_ERROR, LOGOUT, CLIENT_LOGIN_ERROR...), normalisés pour
l'onglet « Connexions » de la tuile Comptes. Fonctions pures : la lecture
et l'écriture Keycloak restent dans kc.py / app.py.

Keycloak ne CONSERVE pas ses événements par défaut (eventsEnabled=false) :
seuls les échecs partent dans son journal texte (WARN). `config_plan`
calcule le réglage minimal à pousser (PUT /events/config) pour les garder
EXPIRATION_DAYS jours, sans toucher aux autres réglages du realm.
"""
import datetime as _dt
import re as _re

WANTED_TYPES = ["LOGIN", "LOGIN_ERROR", "LOGOUT", "CODE_TO_TOKEN", "REFRESH_TOKEN_ERROR",
                "CLIENT_LOGIN_ERROR", "IDENTITY_PROVIDER_LOGIN_ERROR", "RESET_PASSWORD", "UPDATE_PASSWORD"]
SHOWN_TYPES = ["LOGIN", "LOGIN_ERROR", "LOGOUT", "CLIENT_LOGIN_ERROR", "REFRESH_TOKEN_ERROR"]
EXPIRATION_DAYS = 30

TYPE_LABELS = {
    "LOGIN": "connexion", "LOGIN_ERROR": "échec de connexion", "LOGOUT": "déconnexion",
    "CLIENT_LOGIN_ERROR": "échec d'un client (service)", "REFRESH_TOKEN_ERROR": "échec de rafraîchissement",
    "CODE_TO_TOKEN": "jeton délivré", "RESET_PASSWORD": "mot de passe réinitialisé", "UPDATE_PASSWORD": "mot de passe changé",
}
ERROR_LABELS = {
    "invalid_user_credentials": "mot de passe incorrect", "user_not_found": "identifiant inconnu",
    "user_disabled": "compte désactivé", "user_temporarily_disabled": "compte bloqué temporairement (tentatives)",
    "invalid_redirect_uri": "URL de retour non autorisée (origine du hub inconnue de Keycloak)",
    "invalid_client_credentials": "secret du client incorrect", "client_not_found": "client inconnu",
    "invalid_code": "code d'autorisation invalide (page trop ancienne, double clic)",
    "expired_code": "code expiré", "invalid_token": "jeton invalide", "session_expired": "session expirée",
    "not_allowed": "non autorisé", "invalid_grant": "jeton ou code refusé",
}


def label_type(t):
    return TYPE_LABELS.get(t or "", (t or "").lower().replace("_", " "))


def label_error(e):
    if not e:
        return ""
    return ERROR_LABELS.get(e, e.replace("_", " "))


def _iso(ms):
    try:
        return _dt.datetime.fromtimestamp(int(ms) / 1000, tz=_dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def normalize(events):
    """Liste Keycloak (EventRepresentation) -> lignes plates, plus récentes
    d'abord. Les détails ne gardent que ce qui aide à comprendre : identifiant
    saisi, méthode, raison. Jamais de mot de passe (Keycloak ne l'expose pas)."""
    out = []
    for e in events or []:
        d = e.get("details") or {}
        t = e.get("type") or ""
        out.append({
            "time": e.get("time"), "at": _iso(e.get("time")), "type": t, "label": label_type(t),
            "ok": not t.endswith("_ERROR"),
            "user": d.get("username") or e.get("userId") or "", "user_id": e.get("userId"),
            "client": e.get("clientId") or "", "ip": e.get("ipAddress") or "",
            "error": e.get("error") or "", "reason": label_error(e.get("error")),
            "redirect_uri": d.get("redirect_uri") or "", "auth_method": d.get("auth_method") or "",
        })
    out.sort(key=lambda r: r.get("time") or 0, reverse=True)
    return out


def filter_rows(rows, kind="", query=""):
    """kind : '' (tout), 'errors' (échecs seulement), ou un type exact.
    query : début de mot sur utilisateur, IP, client, raison (règle du hub)."""
    q = (query or "").strip().lower()
    out = []
    for r in rows:
        if kind == "errors" and r["ok"]:
            continue
        if kind and kind != "errors" and r["type"] != kind:
            continue
        if q:
            hay = " ".join([r["user"], r["ip"], r["client"], r["reason"], r["label"]]).lower()
            if not any(w.startswith(q) for w in _re.split(r"[\s/_(),'-]+", hay) if w):
                continue
        out.append(r)
    return out


def summary(rows):
    s = {"total": len(rows), "logins": 0, "errors": 0, "users": set(), "ips": set(), "last_error": None}
    for r in rows:
        if r["type"] == "LOGIN":
            s["logins"] += 1
        if not r["ok"]:
            s["errors"] += 1
            s["last_error"] = s["last_error"] or r
        if r["user"]:
            s["users"].add(r["user"])
        if r["ip"]:
            s["ips"].add(r["ip"])
    s["users"], s["ips"] = len(s["users"]), len(s["ips"])
    return s


def config_state(cfg):
    cfg = cfg or {}
    types = cfg.get("enabledEventTypes") or []
    missing = [t for t in WANTED_TYPES if types and t not in types]
    return {"enabled": bool(cfg.get("eventsEnabled")), "expiration_days": (int(cfg.get("eventsExpiration") or 0) // 86400) or None,
            "types_all": not types, "missing_types": missing, "admin_events": bool(cfg.get("adminEventsEnabled"))}


def config_plan(cfg):
    """Réglage à envoyer (PUT /events/config) : conservation activée, types
    voulus ajoutés aux existants, expiration EXPIRATION_DAYS si absente ;
    tout le reste conservé tel quel. Renvoie (nouvelle_config, changé)."""
    cfg = dict(cfg or {})
    changed = False
    if not cfg.get("eventsEnabled"):
        cfg["eventsEnabled"] = True; changed = True
    types = list(cfg.get("enabledEventTypes") or [])
    if types:  # liste vide = tous les types chez Keycloak, on n'y touche pas
        add = [t for t in WANTED_TYPES if t not in types]
        if add:
            cfg["enabledEventTypes"] = types + add; changed = True
    if not cfg.get("eventsExpiration"):
        cfg["eventsExpiration"] = EXPIRATION_DAYS * 86400; changed = True
    return cfg, changed
