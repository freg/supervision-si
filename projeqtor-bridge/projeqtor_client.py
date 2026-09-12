"""Client minimal pour l'API REST de ProjeQtOr (livraison #484).

L'API ProjeQtOr (src/api/index.php) s'authentifie en HTTP Basic avec
le NOM d'un utilisateur ProjeQtOr et son mot de passe — un compte
dédié « bridge » est attendu (créé une fois dans l'interface
ProjeQtOr, voir projeqtor-bridge/README.md), JAMAIS le compte admin
de la personne.

Routes utilisées (documentées dans src/api/index.php) :

    GET  /api/{Classe}/all          liste (filtrée par les droits du compte)
    POST /api/{Classe}              création, corps JSON des champs
    GET  /api/{Classe}/updated/A/B  objets modifiés entre deux instants

Toutes les erreurs remontent en ProjeqtorApiError avec le détail —
jamais de silence : ce pont est la couture entre deux systèmes, une
erreur discrète ici devient une demande PERDUE pour un demandeur.
"""
import requests


class ProjeqtorApiError(Exception):
    pass


class ProjeqtorClient:
    def __init__(self, base_url, user, password, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)
        self.timeout = timeout

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

    def get_all(self, object_class):
        """Liste complète d'une classe (ex. 'Ticket', 'Contact')."""
        return self._request("GET", f"{object_class}/all")

    def get_updated(self, object_class, since, until):
        """Objets modifiés entre deux instants 'YYYYMMDDHHMNSS'."""
        return self._request("GET", f"{object_class}/updated/{since}/{until}")

    def create(self, object_class, fields):
        """Crée un objet ; retourne la réponse décodée (dict)."""
        return self._request("POST", object_class, json=fields)

    def _request(self, method, path, json=None):
        try:
            resp = requests.request(
                method, self._url(path), auth=self.auth, json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProjeqtorApiError(f"API ProjeQtOr injoignable ({exc})") from exc
        if resp.status_code == 401:
            raise ProjeqtorApiError(
                "authentification refusée par l'API ProjeQtOr — vérifier "
                "PROJEQTOR_API_USER / PROJEQTOR_API_PASSWORD (.env) et que le "
                "compte existe et n'est pas désactivé"
            )
        if resp.status_code >= 400:
            raise ProjeqtorApiError(f"API ProjeQtOr {resp.status_code} : {resp.text[:400]}")
        text = resp.text.strip()
        if not text:
            return {}
        try:
            return resp.json()
        except ValueError:
            # L'API renvoie parfois du texte brut (ex. message
            # « {"result":"OK", "id": N} » ou un simple identifiant) —
            # jamais d'exception sur un succès non-JSON.
            return {"raw": text}
