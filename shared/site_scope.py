# -*- coding: utf-8 -*-
"""Périmètre de site par groupe Keycloak -- garde commune des API (A1,
livraison #620, item 97). Copiée au build de chaque API concernée à côté
de `auth.py` (si-proxy/admin/auth.py : vérification RS256 / JWKS).

Réglage : SITE_SCOPE_GROUPS = JSON {"groupe": ["site", ...]} (vide = aucun
périmètre, comportement inchangé) ; SITE_SCOPE_FULL_GROUPS = groupes qui
voient tout (défaut administrateurs,admin_hub).

Règle (pure : `resolve`) : une personne dont AUCUN groupe n'est « plein » et
dont au moins un groupe est « à périmètre » ne voit que l'union des sites de
ses groupes à périmètre. Pour elle, sur chaque requête portant un jeton :
`?site=` hors périmètre -> 403 ; `?site=` absent -> injecté (premier site
du périmètre, ou le seul) ; une ressource dont le site se déduit du chemin
(`resolve_site(path)` fourni par l'API, ex. /agents/<id>) hors périmètre
-> 403. Les écritures suivent la même règle. Sans jeton (agents, scripts,
lecture LAN historique) : rien ne change -- depuis Internet le frontal
exige le jeton (A0), c'est là que le périmètre devient contraignant.
"""
import json
import os

from flask import g, jsonify, request
from werkzeug.datastructures import ImmutableMultiDict

try:
    from auth import AuthError, KeycloakVerifier, bearer_from_header
except ImportError:  # pragma: no cover -- tests hors image
    AuthError = KeycloakVerifier = bearer_from_header = None


def load_groups(raw):
    """JSON {groupe: [sites]} -> dict propre (clés et sites en chaînes non vides)."""
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        return {}
    out = {}
    for grp, sites in (data or {}).items():
        if not isinstance(grp, str) or not grp.strip():
            continue
        if isinstance(sites, str):
            sites = [sites]
        clean = sorted({str(s).strip() for s in (sites or []) if str(s).strip()})
        if clean:
            out[grp.strip()] = clean
    return out


def resolve(groups, scope_groups, full_groups):
    """Groupes de la personne -> liste des sites autorisés, ou None (tout)."""
    gs = {str(x).strip("/") for x in (groups or [])}
    if gs & set(full_groups or ()):
        return None
    sites = set()
    scoped = False
    for grp in gs:
        if grp in scope_groups:
            scoped = True
            sites.update(scope_groups[grp])
    return sorted(sites) if scoped else None


def check(path_site, requested_site, allowed):
    """-> (site effectif, erreur). Pure."""
    if allowed is None:
        return requested_site, None
    if path_site and path_site not in allowed:
        return None, "hors du périmètre de site autorisé (%s)" % ", ".join(allowed)
    if requested_site:
        if requested_site not in allowed:
            return None, "site %s hors du périmètre autorisé (%s)" % (requested_site, ", ".join(allowed))
        return requested_site, None
    return (allowed[0] if allowed else None), None


def install(app, jwks_url, resolve_site=None, exempt_prefixes=("/health", "/version", "/api/v1/"), what="cette API"):
    """Pose la garde en before_request. `resolve_site(path) -> site|None` :
    site de la ressource visée quand il se lit dans le chemin."""
    scope_groups = load_groups(os.environ.get("SITE_SCOPE_GROUPS", ""))
    full_groups = [x.strip() for x in os.environ.get("SITE_SCOPE_FULL_GROUPS", "administrateurs,admin_hub").split(",") if x.strip()]
    app.config["SITE_SCOPE_GROUPS"] = scope_groups
    app.config["SITE_SCOPE_FULL_GROUPS"] = full_groups
    if not scope_groups or KeycloakVerifier is None:
        return None
    verifier = KeycloakVerifier(jwks_url, [], allowed_groups=None, what=what)
    verifier.allowed_groups = set()
    _orig_verify = verifier.verify

    def verify_any(token):
        """Tout utilisateur authentifié du realm est accepté ici ; le périmètre décide ensuite."""
        verifier.allowed_users = _AnyUser()
        return _orig_verify(token)

    @app.before_request
    def _site_scope_guard():
        if request.method == "OPTIONS" or any(request.path.startswith(p) for p in exempt_prefixes):
            return None
        token = bearer_from_header(request.headers.get("Authorization")) if bearer_from_header else None
        if not token:
            return None  # sans jeton : modèle LAN inchangé (le frontal exige le jeton depuis Internet)
        try:
            user = verify_any(token)
        except AuthError as exc:
            return jsonify({"error": str(exc)}), exc.status
        allowed = resolve(user.get("groups"), scope_groups, full_groups)
        g.user = user
        g.site_scope = allowed
        if allowed is None:
            return None
        path_site = None
        if resolve_site:
            try:
                path_site = resolve_site(request.path)
            except Exception:  # noqa: BLE001
                path_site = None
        site, err = check(path_site, request.args.get("site"), allowed)
        if err:
            return jsonify({"error": err, "site_scope": allowed}), 403
        if site and not request.args.get("site"):
            args = request.args.to_dict(flat=False)
            args["site"] = [site]
            request.args = ImmutableMultiDict([(k, v) for k, vs in args.items() for v in vs])
        return None

    return _site_scope_guard


class _AnyUser:
    """Ensemble qui contient tout : KeycloakVerifier teste `username in allowed_users`."""
    def __contains__(self, item):
        return True
