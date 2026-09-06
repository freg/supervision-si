"""
Client pour l'API Zyxel Nebula OpenAPI (livraison #196, second "besoin
immédiat" de la demande GLPI -- "importer les données d'un site sous
nebula.zyxel.com"). Recherche RÉELLE effectuée avant d'écrire ce
fichier -- doc officielle : https://zyxelnetworks.github.io/NebulaOpenAPI/
et la spécification OpenAPI complète, consultées le jour de cette
livraison.

**⚠️ PRÉREQUIS BLOQUANTS, à confirmer AVANT tout test réel** :
1. L'organisation Nebula visée doit avoir la licence **Nebula Pro
   Pack** -- confirmé explicitement dans la doc officielle ("Zyxel
   Nebula OpenAPI only supports PRO mode organizations") ET dans la
   page produit Zyxel elle-même ("Ensure your Nebula devices are
   registered under a Nebula Professional Pack licensed
   organization"). Sans Pro Pack, ces appels échoueront
   systématiquement, quel que soit le code.
2. La clé d'API N'EST PAS en libre-service -- la page officielle
   recommande explicitement de contacter le bureau régional Zyxel ou
   d'ouvrir un dossier support NCC Help Center pour en obtenir une
   ("Since Nebula OpenAPI is still in its early stages... it is not
   yet generally available"). Rien ici ne peut contourner cette
   étape administrative, à faire côté personne avant tout test.

**⚠️ Jamais testé contre une vraie API Nebula** -- aucun accès réseau
externe dans cet environnement de développement, ET les deux
prérequis ci-dessus ne peuvent de toute façon pas être satisfaits
depuis ici. Toute la logique ci-dessous est construite à partir de
la spécification OpenAPI officielle, mais reste À CONFIRMER contre
un vrai compte une fois les prérequis réunis.

**Authentification** : PAS de session (contrairement à GLPI, #192) --
une simple clé statique dans l'en-tête `X-ZyxelNebula-API-Key` sur
CHAQUE appel, jamais d'ouverture/fermeture de session.

**Format d'erreur CONFIRMÉ par la doc officielle** (contrairement à
GLPI où ce format restait une hypothèse défensive, #192) : JSON
`{"status": ..., "message": ..., "code": ..., "more_info": {}}` sur
CHAQUE réponse, y compris les 200 -- `_raise_with_detail` reste
quand même défensif sur la FORME exacte (jamais garanti à 100% sans
un essai réel), mais le format attendu est ici documenté noir sur
blanc, pas deviné.
"""
import logging
import time

import requests

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE : la
# clé d'API Nebula n'apparaît JAMAIS dans une trace. `_get`/`_post`
# sont les DEUX points de passage UNIQUES de tous les appels réseau
# de ce client -- les instrumenter ici couvre automatiquement toutes
# les méthodes publiques (list_organizations, list_sites, etc.) sans
# les toucher individuellement.
_log = logging.getLogger("nebula_client")


class NebulaError(Exception):
    pass


class NebulaClient:
    BASE_URL = "https://api.nebula.zyxel.com"

    def __init__(self, api_key, base_url=None, timeout=30):
        self.api_key = api_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout

    def _headers(self):
        return {"X-ZyxelNebula-API-Key": self.api_key, "Content-Type": "application/json"}

    def _raise_with_detail(self, response, context):
        """Format documenté : {"status", "message", "code", "more_info"}
        -- voir docstring du module. Reste défensif sur la forme EXACTE
        (jamais un accès direct à une clé qui pourrait manquer), mais
        le format lui-même est confirmé par la doc officielle, pas
        une hypothèse comme pour GLPI (#192)."""
        detail = None
        try:
            body = response.json()
            if isinstance(body, dict):
                message = body.get("message")
                code = body.get("code")
                detail = f"{message}" + (f" (code {code})" if code else "") if message else None
            if detail is None and isinstance(body, (list, dict)):
                detail = str(body)
        except ValueError:
            pass
        if not detail:
            detail = (response.text or "").strip() or f"code HTTP {response.status_code}"
        _log.debug("_raise_with_detail : %s -- code HTTP %s -- %s", context, response.status_code, detail)
        raise NebulaError(f"{context} : {detail}")

    def _get(self, path, context):
        _log.debug("_get : démarré -- %s (jamais la clé d'API ici)", path)
        start = time.monotonic()
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(), timeout=self.timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code != 200:
            _log.debug("_get : ÉCHEC HTTP %s après %d ms -- %s", resp.status_code, elapsed_ms, path)
            self._raise_with_detail(resp, context)
        try:
            result = resp.json()
        except ValueError:
            # Livraison #287 -- "rendre les erreurs systématiquement
            # plus explicites", généralisé depuis #286 (glpi_client.py) :
            # un 200 avec un corps NON-JSON plantait encore avec une
            # JSONDecodeError brute.
            snippet = (resp.text or "").strip()[:300]
            _log.debug("_get : ÉCHEC -- réponse 200 mais pas du JSON valide -- %s -- %s", path, snippet)
            raise NebulaError(f"{context} : réponse HTTP 200 inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")
        _log.debug("_get : succès en %d ms -- %s", elapsed_ms, path)
        return result

    def _post(self, path, payload, context):
        _log.debug("_post : démarré -- %s (jamais la clé d'API, ni le contenu du payload, ici)", path)
        start = time.monotonic()
        resp = requests.post(f"{self.base_url}{path}", headers=self._headers(), json=payload, timeout=self.timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code != 200:
            _log.debug("_post : ÉCHEC HTTP %s après %d ms -- %s", resp.status_code, elapsed_ms, path)
            self._raise_with_detail(resp, context)
        try:
            result = resp.json()
        except ValueError:
            snippet = (resp.text or "").strip()[:300]
            _log.debug("_post : ÉCHEC -- réponse 200 mais pas du JSON valide -- %s -- %s", path, snippet)
            raise NebulaError(f"{context} : réponse HTTP 200 inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")
        _log.debug("_post : succès en %d ms -- %s", elapsed_ms, path)
        return result

    def list_organizations(self):
        """GET /v1/nebula/organizations -- [{"name", "orgId", "mode",
        "payg_entitlements"}, ...]. `mode` doit valoir "PRO" pour que
        le reste de l'API fonctionne (voir docstring du module)."""
        return self._get("/v1/nebula/organizations", "liste des organisations échouée")

    def get_org_info(self, org_id):
        return self._get(f"/v1/nebula/organizations/{org_id}", f"info organisation '{org_id}' échouée")

    def list_sites(self, org_id):
        """GET .../sites -- [{"name", "siteId", "timeZone", "deviceCount"}, ...]."""
        return self._get(f"/v1/nebula/organizations/{org_id}/sites", f"liste des sites de l'organisation '{org_id}' échouée")

    def list_devices_from_org(self, org_id):
        """GET .../sites/devices -- ENDPOINT CLÉ pour un import de type
        inventaire (même esprit que l'import GLPI, #192) : renvoie TOUS
        les appareils de l'organisation, GROUPÉS PAR SITE --
        [{"siteId", "devices": [{"devId", "name", "mac", "sn", "model",
        "type", "description", "productInfo", "assetId", "tags", ...}]}].
        `sn` (numéro de série) et `mac` en font une source DIRECTEMENT
        exploitable pour alimenter un inventaire GLPI, sur le même
        principe de dédoublonnage par numéro de série déjà utilisé
        côté GLPI (#192)."""
        return self._get(f"/v1/nebula/organizations/{org_id}/sites/devices", f"liste des appareils de l'organisation '{org_id}' échouée")

    def devices_for_site(self, org_id, site_id):
        """Filtre list_devices_from_org sur UN site précis -- l'API
        Nebula ne propose pas d'endpoint "devices d'un site" isolé
        (uniquement "devices de toute l'organisation, groupés par
        site") -- ce filtrage se fait donc CÔTÉ CLIENT, jamais
        d'appel supplémentaire inutile vers l'API."""
        all_sites = self.list_devices_from_org(org_id)
        for entry in all_sites:
            if entry.get("siteId") == site_id:
                return entry.get("devices", [])
        return []

    def get_online_status(self, site_id, device_type=None):
        """GET .../online-status -- [{"devId", "currentStatus"}, ...].
        `device_type` optionnel (AP/SW/GW/FIREWALL/WWAN/SCR/GWH/ACCY,
        voir doc officielle) filtre côté serveur via un paramètre de
        requête."""
        path = f"/v1/nebula/{site_id}/online-status"
        if device_type:
            path += f"?type={device_type}"
        return self._get(path, f"statut en ligne du site '{site_id}' échoué")

    def get_site_clients(self, site_id, features=None, period="2h"):
        """POST .../clients (v2) -- clients RÉSEAU connectés au site
        (PAS les appareils Nebula eux-mêmes -- voir devices_for_site
        pour ça) -- [{"macAddress", "ipv4Address", "status",
        "manufacturer", ...}]. `features` : liste des attributs
        voulus (voir doc officielle pour la liste complète) -- vide
        par défaut, demande l'ensemble raisonnable ci-dessous."""
        default_features = ["mac_address", "ipv4", "status", "last_seen", "description", "os_hostname", "manufacturer"]
        payload = {"period": period, "featrues": features or default_features}  # "featrues" -- faute de frappe RÉELLE dans la doc officielle Zyxel elle-même, reproduite telle quelle (jamais corrigée de notre côté, l'API ne comprendrait pas la version corrigée)
        result = self._post(f"/v2/nebula/{site_id}/clients", payload, f"clients du site '{site_id}' échoués")
        return result.get("data", []) if isinstance(result, dict) else result
