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
import urllib.parse
import urllib.request

KINDS = ("microsoft-graph", "csv-export", "manual")
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
