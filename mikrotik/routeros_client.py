"""Client pour l'API REST native de RouterOS v7 (livraison #485).

RouterOS v7 expose une API REST en HTTPS (service www-ssl) avec
authentification HTTP Basic — mêmes verbes que la console :

    GET    /rest/system/resource        lecture (print)
    PATCH  /rest/interface/ethernet/*3  modification (set)
    POST   /rest/ping                   outil/action (avec arguments)

Documentée par MikroTik (« RouterOS API » → « REST API »). Limite
assumée : RouterOS v6 n'a PAS d'API REST (seulement l'API binaire
:8728, non couverte par ce module) — un routeur v6 apparaîtra comme
« injoignable » dans l'interface, jamais comme une donnée fausse.

TLS : les routeurs d'infrastructure ont quasi toujours des
certificats AUTO-SIGNÉS — la vérification est donc désactivée par
défaut (posture LAN, même réseau de confiance que le reste du hub) ;
MIKROTIK_TLS_VERIFY=1 la réactive si des certificats propres sont
déployés un jour.
"""
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RouterOSError(Exception):
    """Erreur parlante côté interface — jamais un stack trace brut
    (un routeur éteint ou v6 doit donner un message exploitable)."""


class RouterOSClient:
    def __init__(self, host, port, user, password, tls_verify=False, timeout=10):
        scheme = "https"
        self.base = f"{scheme}://{host}:{port}/rest"
        self.auth = (user, password)
        self.verify = tls_verify
        self.timeout = timeout

    def get(self, path):
        return self._request("GET", path)

    def patch(self, path, fields):
        return self._request("PATCH", path, json=fields)

    def post_action(self, path, args):
        """Actions/outils (ping, reboot...) : POST avec les arguments
        en corps JSON — convention REST de RouterOS pour les verbes."""
        return self._request("POST", path, json=args)

    def _request(self, method, path, json=None):
        url = f"{self.base}/{path.lstrip('/')}"
        try:
            resp = requests.request(
                method, url, auth=self.auth, json=json,
                verify=self.verify, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RouterOSError(
                f"routeur injoignable ({exc.__class__.__name__}) — éteint, "
                "port www-ssl fermé, ou RouterOS v6 (pas d'API REST)"
            ) from exc
        if resp.status_code == 401:
            raise RouterOSError("authentification refusée (accès du coffre à corriger dans la tuile Accès d'équipements ?)")
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail") or resp.json().get("message") or ""
            except ValueError:
                detail = resp.text[:200]
            raise RouterOSError(f"RouterOS {resp.status_code} : {detail}")
        if not resp.text.strip():
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}
