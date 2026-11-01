# -*- coding: utf-8 -*-
"""Connecteurs « sites des vendeurs » (livraison #595). Chaque connecteur lit
l'état des abonnements chez l'éditeur et le rend sous une forme commune :
[{"sku", "label", "quantity", "assigned", "end", "users": [upn...]}].
Identifiants : le NOM d'un accès du coffre (credentials-api), jamais un
secret ici. Un connecteur ne modifie jamais rien chez le vendeur.

- microsoft-graph : Microsoft 365 (client credentials : tenant, client_id ;
  secret = mot de passe de l'accès du coffre ; permissions applicatives
  Organization.Read.All + User.Read.All). `subscribedSkus` + `users` avec
  `assignedLicenses`.
- csv-export : export du centre d'administration déposé à la main
  (rules.import_m365) -- sans accès.
- manual : saisie dans la tuile.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

KINDS = ("microsoft-graph", "microsoft-account", "csv-export", "manual")
# #602 : « microsoft-account » = le compte d'un administrateur Microsoft 365 (pas
# d'inscription d'application) : soit e-mail + mot de passe (accès du coffre,
# flux ROPC -- refusé par Microsoft dès que l'authentification multifacteur est
# exigée, ce qui est le cas des comptes administrateurs depuis 2025), soit
# connexion PAR CODE (flux « device code » : le hub affiche un code, la
# personne se connecte une fois avec MFA, le hub garde un jeton de
# rafraîchissement). Client public Microsoft Graph PowerShell, pré-consenti
# dans la plupart des tenants ; Organization.Read.All + User.Read.All délégués.
PUBLIC_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
DELEGATED_SCOPE = "https://graph.microsoft.com/Organization.Read.All https://graph.microsoft.com/User.Read.All offline_access"
# #598 : portail de gestion des licences chez le vendeur (lien « gérer chez le vendeur »),
# remplaçable par config.url sur le compte.
PORTALS = {"microsoft-graph": "https://admin.microsoft.com/#/licenses", "microsoft-account": "https://admin.microsoft.com/#/licenses", "csv-export": "", "manual": ""}


def portal_url(kind, config):
    return str((config or {}).get("url") or PORTALS.get(kind) or "")
GRAPH = "https://graph.microsoft.com/v1.0"
SKU_LABELS = {  # libellés lisibles des SKU Microsoft les plus courants
    "O365_BUSINESS_PREMIUM": "Microsoft 365 Business Standard", "O365_BUSINESS_ESSENTIALS": "Microsoft 365 Business Basic",
    "SPB": "Microsoft 365 Business Premium", "O365_BUSINESS": "Microsoft 365 Apps for business", "SMB_APPS": "Microsoft 365 Apps for business",
    "POWER_BI_STANDARD": "Microsoft Fabric (Free)", "TEAMS_EXPLORATORY": "Microsoft Teams (exploratoire)", "TEAMS_COMMERCIAL_TRIAL": "Microsoft Teams Commercial (essai)",
    "FLOW_FREE": "Power Automate (gratuit)", "POWERAPPS_VIRAL": "Power Apps (essai)", "ENTERPRISEPACK": "Office 365 E3", "STANDARDPACK": "Office 365 E1",
}


def _http(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8") or "{}")


def graph_token(tenant, client_id, secret, http=None):
    http = http or _http
    body = urllib.parse.urlencode({"client_id": client_id, "client_secret": secret, "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"}).encode()
    tok = http("https://login.microsoftonline.com/%s/oauth2/v2.0/token" % tenant, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if not tok.get("access_token"):
        raise RuntimeError("jeton Graph refusé : %s" % (tok.get("error_description") or tok.get("error") or "?")[:200])
    return tok["access_token"]


def _token_call(tenant, form, http=None):
    http = http or _http
    body = urllib.parse.urlencode(form).encode()
    try:
        return http("https://login.microsoftonline.com/%s/oauth2/v2.0/token" % (tenant or "organizations"), {"Content-Type": "application/x-www-form-urlencoded"}, body)
    except urllib.error.HTTPError as exc:  # les refus OAuth arrivent en 400 avec un corps JSON
        try:
            return json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            return {"error": "http_%s" % exc.code}


ROPC_HINTS = {"AADSTS50076": "authentification multifacteur exigée : utiliser la connexion par code", "AADSTS50079": "MFA à enregistrer : utiliser la connexion par code",
              "AADSTS50126": "e-mail ou mot de passe refusé", "AADSTS65001": "consentement requis : se connecter une fois par code", "AADSTS7000218": "flux mot de passe désactivé sur le tenant : utiliser la connexion par code",
              "AADSTS50034": "compte inconnu dans ce tenant", "AADSTS50053": "compte verrouillé", "AADSTS50057": "compte désactivé"}


def _explain(tok):
    desc = str(tok.get("error_description") or tok.get("error") or "?")
    for code, hint in ROPC_HINTS.items():
        if code in desc:
            return "%s (%s)" % (hint, code)
    return desc[:200]


def ropc_token(tenant, username, password, client_id=PUBLIC_CLIENT_ID, http=None):
    """E-mail + mot de passe (flux ROPC). -> {access_token, refresh_token}. Échoue avec MFA."""
    tok = _token_call(tenant, {"client_id": client_id, "scope": DELEGATED_SCOPE, "grant_type": "password", "username": username, "password": password}, http)
    if not tok.get("access_token"):
        raise RuntimeError("connexion Microsoft refusée : %s" % _explain(tok))
    return tok


def device_code_start(tenant, client_id=PUBLIC_CLIENT_ID, http=None):
    """Connexion par code : -> {device_code, user_code, verification_uri, expires_in, interval, message}."""
    http = http or _http
    body = urllib.parse.urlencode({"client_id": client_id, "scope": DELEGATED_SCOPE}).encode()
    r = http("https://login.microsoftonline.com/%s/oauth2/v2.0/devicecode" % (tenant or "organizations"), {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if not r.get("device_code"):
        raise RuntimeError("code de connexion refusé : %s" % _explain(r))
    return r


def device_code_poll(tenant, device_code, client_id=PUBLIC_CLIENT_ID, http=None):
    """-> ("pending", None) | ("ok", tokens) | ("error", message)."""
    tok = _token_call(tenant, {"client_id": client_id, "grant_type": "urn:ietf:params:oauth:grant-type:device_code", "device_code": device_code}, http)
    if tok.get("access_token"):
        return "ok", tok
    if tok.get("error") in ("authorization_pending", "slow_down"):
        return "pending", None
    return "error", _explain(tok)


def refresh_token(tenant, refresh, client_id=PUBLIC_CLIENT_ID, http=None):
    tok = _token_call(tenant, {"client_id": client_id, "scope": DELEGATED_SCOPE, "grant_type": "refresh_token", "refresh_token": refresh}, http)
    if not tok.get("access_token"):
        raise RuntimeError("session Microsoft expirée, se reconnecter par code : %s" % _explain(tok))
    return tok


def sync_with_token(token, http=None):
    skus = graph_pages(GRAPH + "/subscribedSkus", token, http)
    users = graph_pages(GRAPH + "/users?$select=userPrincipalName,mail,displayName,assignedLicenses,accountEnabled&$top=999", token, http)
    return normalize_skus(skus, users)


def graph_pages(url, token, http=None):
    http = http or _http
    out = []
    while url:
        page = http(url, {"Authorization": "Bearer " + token})
        out += page.get("value") or []
        url = page.get("@odata.nextLink")
    return out


def normalize_skus(skus, users):
    """subscribedSkus + users(assignedLicenses) -> forme commune."""
    by_sku = {}
    for s in skus or []:
        units = s.get("prepaidUnits") or {}
        by_sku[s.get("skuId")] = {"sku": s.get("skuPartNumber"), "label": SKU_LABELS.get(s.get("skuPartNumber"), s.get("skuPartNumber")),
                                  "quantity": int(units.get("enabled") or 0), "assigned": int(s.get("consumedUnits") or 0), "suspended": int(units.get("suspended") or 0),
                                  "warning": int(units.get("warning") or 0), "status": s.get("capabilityStatus"), "end": None, "users": []}
    for u in users or []:
        upn = u.get("userPrincipalName") or u.get("mail") or ""
        for lic in u.get("assignedLicenses") or []:
            if lic.get("skuId") in by_sku:
                by_sku[lic["skuId"]]["users"].append(upn)
    for v in by_sku.values():
        v["users"].sort()
    return sorted(by_sku.values(), key=lambda x: x["label"] or "")


def sync_microsoft_graph(config, secret, http=None):
    """config : {tenant, client_id} ; secret : mot de passe de l'accès du coffre."""
    tenant, client_id = (config or {}).get("tenant"), (config or {}).get("client_id")
    if not tenant or not client_id or not secret:
        raise RuntimeError("tenant, client_id et accès du coffre requis")
    token = graph_token(tenant, client_id, secret, http)
    skus = graph_pages(GRAPH + "/subscribedSkus", token, http)
    users = graph_pages(GRAPH + "/users?$select=userPrincipalName,mail,displayName,assignedLicenses,accountEnabled&$top=999", token, http)
    return normalize_skus(skus, users)
