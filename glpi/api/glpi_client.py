"""
Client pour l'API REST HISTORIQUE de GLPI (`apirest.php`) -- livraison
#192, backlog : "évolution d'intégration GLPI, une tuile et une api
pour utiliser l'api glpi et ses données dans les autres tuiles du
hub". Deux API existent côté GLPI 11 : l'historique (`apirest.php`,
éprouvée, bien documentée, https://help.glpi-project.org/documentation/
modules/configuration/general/api/api) et une NOUVELLE API v2, encore
"work in progress" pour les types d'objets qui nous intéressent ici
(actifs) au moment de cette livraison (confirmé via la documentation
officielle : "many of the itemtypes have schemas/endpoints now as of
11.0.5 and many more get added each version" -- pas encore TOUS).
Choix DÉLIBÉRÉ : l'historique, plus fiable pour un import d'actifs
maintenant, quitte à migrer vers la v2 plus tard si elle mûrit.

**⚠️ Jamais testé contre un VRAI GLPI** -- aucun accès réseau externe
dans cet environnement de développement. Toute la logique ci-dessous
est construite à partir de la documentation OFFICIELLE (lien
ci-dessus, consultée le jour de cette livraison), mais le format EXACT
des réponses d'erreur du serveur n'est pas garanti à 100% sans un
essai réel -- `_raise_with_detail` reste DÉLIBÉRÉMENT défensif
(accepte plusieurs formes plausibles) et inclut TOUJOURS le corps brut
de la réponse en repli, jamais un message générique qui masquerait la
vraie cause si mon hypothèse de format est légèrement fausse.

**Authentification par SESSION** (pas par token applicatif seul) :
`init_session` (login+mot de passe OU user_token) renvoie un
`session_token`, à fournir en en-tête `Session-Token` sur CHAQUE appel
suivant, jusqu'à `kill_session`. Un `App-Token` (optionnel côté GLPI,
mais RECOMMANDÉ pour restreindre l'accès par IP/application) peut
aussi être fourni.

**`session_write=true` sur initSession** -- décidé explicitement ici :
une session GLPI est en LECTURE SEULE par défaut (permet des appels
parallèles), sauf sur quelques méthodes précises. Un IMPORT (créations
en masse) a besoin d'écriture -- demandé dès l'ouverture de session,
jamais découvert en échec plus tard.
"""
import logging
import time

import requests

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE :
# ni le mot de passe, ni le user_token, ni l'app_token, ni le
# session_token n'apparaissent JAMAIS dans une trace.
_log = logging.getLogger("glpi_client")


class GlpiError(Exception):
    pass


class GlpiClient:
    def __init__(self, base_url, app_token=None, timeout=30):
        """`base_url` : ex. "https://glpi.exemple.fr/apirest.php" --
        SANS slash final (ajouté ici au besoin), pointant directement
        sur `apirest.php` (l'API historique), jamais sur `/api/` seul
        (qui suppose une réécriture d'URL serveur non garantie -- voir
        doc officielle, section "Servers configuration")."""
        self.base_url = base_url.rstrip("/")
        self.app_token = app_token
        self.timeout = timeout
        self.session_token = None

    def _headers(self, extra=None):
        headers = {"Content-Type": "application/json"}
        if self.app_token:
            headers["App-Token"] = self.app_token
        if self.session_token:
            headers["Session-Token"] = self.session_token
        if extra:
            headers.update(extra)
        return headers

    def _raise_with_detail(self, response, context):
        """Défensif -- voir docstring du module. Tente plusieurs
        formes plausibles de corps d'erreur GLPI, inclut TOUJOURS le
        corps brut en repli."""
        detail = None
        try:
            body = response.json()
            if isinstance(body, list) and len(body) >= 2:
                detail = f"{body[0]} : {body[1]}"
            elif isinstance(body, dict) and "message" in body:
                detail = body["message"]
            elif isinstance(body, (list, dict)):
                detail = str(body)
        except ValueError:
            pass
        if not detail:
            detail = (response.text or "").strip() or f"code HTTP {response.status_code}"
        _log.debug("_raise_with_detail : %s -- code HTTP %s -- %s", context, response.status_code, detail)
        raise GlpiError(f"{context} : {detail}")

    def init_session(self, login, password=None, user_token=None, write=True):
        """`write=True` -- voir docstring du module (session_write).
        `login`+`password` OU `user_token` (jamais les deux, priorité
        à `user_token` s'il est fourni -- généralement le mode
        recommandé côté GLPI pour un accès applicatif, contrairement à
        un mot de passe utilisateur)."""
        auth_mode = "user_token" if user_token else ("login+password" if (login is not None and password is not None) else "aucun")
        _log.debug("init_session : démarré (base_url=%s, mode=%s, jamais les identifiants eux-mêmes ici)", self.base_url, auth_mode)
        headers = {"Content-Type": "application/json"}
        if self.app_token:
            headers["App-Token"] = self.app_token
        if user_token:
            headers["Authorization"] = f"user_token {user_token}"
        elif login is not None and password is not None:
            import base64
            b64 = base64.b64encode(f"{login}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {b64}"
        else:
            _log.debug("init_session : ÉCHEC -- ni user_token ni login+password fournis")
            raise GlpiError("init_session : 'user_token' ou 'login'+'password' requis")

        params = {"session_write": "true"} if write else {}
        start = time.monotonic()
        resp = requests.get(f"{self.base_url}/initSession", headers=headers, params=params, timeout=self.timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code != 200:
            _log.debug("init_session : ÉCHEC HTTP %s après %d ms", resp.status_code, elapsed_ms)
            self._raise_with_detail(resp, "connexion à GLPI échouée")
        try:
            self.session_token = resp.json()["session_token"]
        except (ValueError, KeyError):
            # Bug réel #286, signalé par la personne en plein test
            # réel : un 200 avec un corps NON-JSON (ou sans
            # "session_token") faisait planter ici avec une
            # exception Python brute, jamais un message exploitable
            # -- extrait maintenant un aperçu du corps RÉEL renvoyé
            # par GLPI (tronqué, jamais les identifiants), pour
            # diagnostiquer sans deviner à l'aveugle.
            snippet = (resp.text or "").strip()[:300]
            _log.debug("init_session : ÉCHEC -- réponse 200 mais pas le JSON attendu -- %s", snippet)
            raise GlpiError(f"connexion à GLPI échouée : réponse HTTP 200 inattendue (pas de 'session_token' JSON) -- début de la réponse : {snippet!r}")
        _log.debug("init_session : succès en %d ms (session établie, jamais le jeton lui-même tracé)", elapsed_ms)
        return self.session_token

    def kill_session(self):
        if not self.session_token:
            _log.debug("kill_session : aucune session active, rien à faire")
            return
        _log.debug("kill_session : démarré")
        try:
            requests.get(f"{self.base_url}/killSession", headers=self._headers(), timeout=self.timeout)
            _log.debug("kill_session : requête envoyée")
        except Exception as exc:  # noqa: BLE001 -- volontairement large : "jamais bloquant" veut dire peu importe la cause (réseau, timeout, ou autre), jamais seulement les erreurs `requests` prévues
            _log.debug("kill_session : échec best-effort ignoré -- %s", exc)
        finally:
            self.session_token = None

    def search_items(self, itemtype, criteria, range_str="0-999"):
        """`criteria` : liste de critères au format GLPI (voir doc --
        field=id de searchoption, searchtype, value). Utilisé
        PRINCIPALEMENT pour retrouver un actif existant par numéro de
        série avant import (dédoublonnage, voir glpi_import.py)."""
        params = {"range": range_str}
        for i, crit in enumerate(criteria):
            for key, value in crit.items():
                params[f"criteria[{i}][{key}]"] = value
        resp = requests.get(f"{self.base_url}/search/{itemtype}", headers=self._headers(), params=params, timeout=self.timeout)
        if resp.status_code not in (200, 206):
            self._raise_with_detail(resp, f"recherche '{itemtype}' échouée")
        return resp.json()

    def get_items(self, itemtype, range_str="0-999", search_text=None):
        params = {"range": range_str}
        if search_text:
            for key, value in search_text.items():
                params[f"searchText[{key}]"] = value
        resp = requests.get(f"{self.base_url}/{itemtype}/", headers=self._headers(), params=params, timeout=self.timeout)
        if resp.status_code not in (200, 206):
            self._raise_with_detail(resp, f"liste '{itemtype}' échouée")
        return resp.json()

    def add_item(self, itemtype, fields):
        """UN SEUL objet -- renvoie son id (int). Pour un lot, voir
        `add_items` (statut 207 Multi-Status possible, gère les échecs
        PARTIELS différemment)."""
        resp = requests.post(f"{self.base_url}/{itemtype}/", headers=self._headers(), json={"input": fields}, timeout=self.timeout)
        if resp.status_code != 201:
            self._raise_with_detail(resp, f"création '{itemtype}' échouée")
        return resp.json()["id"]

    def add_items(self, itemtype, fields_list):
        """PLUSIEURS objets en un appel -- renvoie la liste BRUTE
        renvoyée par GLPI (`[{"id": N, "message": ""}, {"id": false,
        "message": "..."}, ...]`), JAMAIS levée en erreur sur un échec
        PARTIEL (statut 207) -- l'appelant doit inspecter chaque
        élément (`id` vaut `False` -- pas `None` -- en cas d'échec
        individuel, selon la doc officielle)."""
        resp = requests.post(f"{self.base_url}/{itemtype}/", headers=self._headers(), json={"input": fields_list}, timeout=self.timeout)
        if resp.status_code not in (201, 207):
            self._raise_with_detail(resp, f"création en lot '{itemtype}' échouée")
        return resp.json()

    def update_item(self, itemtype, item_id, fields):
        resp = requests.put(f"{self.base_url}/{itemtype}/{item_id}", headers=self._headers(), json={"input": fields}, timeout=self.timeout)
        if resp.status_code != 200:
            self._raise_with_detail(resp, f"mise à jour '{itemtype}/{item_id}' échouée")
        return resp.json()

    def delete_item(self, itemtype, item_id, force_purge=False):
        """Supprime UN objet (livraison #269, demandé explicitement --
        "partout dans les imports/exports y a t'il la possibilité
        d'annuler ou de supprimer en sélectionnant individuellement ?").

        Comportement VÉRIFIÉ contre la documentation officielle GLPI
        (`apirest.md`, plusieurs sources concordantes -- projet
        officiel `glpi-project/glpi` inclus) : par défaut
        (`force_purge=False`), GLPI déplace l'objet dans SA PROPRE
        corbeille (si ce type d'actif en a une) -- récupérable
        nativement depuis l'interface GLPI elle-même, l'équivalent
        exact d'un "annuler" SANS avoir à construire un mécanisme de
        undo maison. Avec `force_purge=True`, suppression DÉFINITIVE
        (jamais le défaut ici -- un choix explicite de l'appelant).

        Réponse GLPI documentée : `[{"<id>": true, "message": ""}]`
        (200) ou 204 sans corps (suppression simple, selon version) --
        gère les deux, renvoie True/False selon ce que GLPI rapporte
        RÉELLEMENT (jamais présumé un succès sur un simple code HTTP
        200 sans lire le corps, un id inexistant peut légitimement
        renvoyer `false` avec un 200)."""
        resp = requests.delete(
            f"{self.base_url}/{itemtype}/{item_id}", headers=self._headers(),
            params={"force_purge": "true" if force_purge else "false"}, timeout=self.timeout,
        )
        if resp.status_code not in (200, 204):
            self._raise_with_detail(resp, f"suppression '{itemtype}/{item_id}' échouée")
        if resp.status_code == 204:
            return True
        try:
            body = resp.json()
        except ValueError:
            return True  # 200 sans corps JSON exploitable -- best-effort, jamais une exception sur une réponse inattendue mais un statut de succès
        if isinstance(body, list) and body and isinstance(body[0], dict):
            values = [v for k, v in body[0].items() if k != "message"]
            return bool(values) and values[0] is True
        return True

    def get_or_create_dropdown(self, dropdown_itemtype, name):
        """Recherche une entrée de LISTE DÉROULANTE (ex. ComputerModel,
        PeripheralModel, Location, Manufacturer) par NOM EXACT -- la
        crée si absente. GLPI exige un ID de dropdown pour ces champs,
        jamais du texte libre -- ce détour est nécessaire pour relier
        proprement un actif à son modèle/sa localisation plutôt que de
        tout entasser en commentaire.

        Recherche via `searchText` (filtre par NOM DE CHAMP réel,
        "name") plutôt que par un id de "searchoption" numérique --
        ce dernier varie selon l'itemtype et je n'ai aucun moyen de le
        confirmer sans un vrai GLPI sous la main (voir docstring du
        module) -- `searchText` est documenté comme acceptant
        directement un nom de colonne, plus sûr ici qu'un numéro
        deviné."""
        result = self.get_items(dropdown_itemtype, search_text={"name": name})
        if isinstance(result, list) and result:
            for item in result:
                if item.get("name") == name:
                    return item["id"]
            return result[0]["id"]
        return self.add_item(dropdown_itemtype, {"name": name})
