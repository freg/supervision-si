"""
Client HTTP vers network-agent-api -- même motif déjà établi dans ce
projet (voir netprobe/api/app.py, route
/targets/import-from-network-agent) : best-effort, JAMAIS une
exception qui remonterait brute à l'appelant, network-agent-api
injoignable est un résultat NORMAL à signaler, pas une panne de CE
module.
"""
import logging

import requests

_log = logging.getLogger("netmap_orchestrator_na_client")


def _get(api_base, path, params=None, timeout=15):
    """GET générique -- renvoie (data, error). `error` est None en
    cas de succès, une chaîne lisible sinon -- jamais une exception
    qui remonterait à l'appelant."""
    if not api_base:
        return None, "NETWORK_AGENT_API_URL non configurée"
    try:
        resp = requests.get(f"{api_base}{path}", params=params, timeout=timeout)
    except requests.RequestException as exc:
        _log.debug("_get(%s) : network-agent-api injoignable -- %s", path, exc)
        return None, f"network-agent-api injoignable : {exc}"
    if resp.status_code != 200:
        return None, f"network-agent-api a répondu {resp.status_code} sur {path}"
    try:
        return resp.json(), None
    except ValueError:
        snippet = (resp.text or "").strip()[:300]
        return None, f"réponse illisible de network-agent-api sur {path} : {snippet!r}"


def list_devices(api_base, network_segment_id=None):
    """Renvoie (liste_appareils, error). Liste VIDE (pas None) en cas
    d'erreur -- laisse l'appelant décider comment réagir à `error`,
    plutôt que de propager un None qui casserait une boucle `for`."""
    params = {"segment_id": network_segment_id} if network_segment_id else None
    data, error = _get(api_base, "/devices", params=params)
    return (data if isinstance(data, list) else []), error


def list_device_services(api_base, device_id):
    data, error = _get(api_base, f"/devices/{device_id}/services")
    return (data if isinstance(data, list) else []), error


def list_services_by_segment(api_base, network_segment_id):
    """Services de TOUS les appareils d'un segment EN UN SEUL appel
    (voir network-agent/api/store.py list_services_by_segment) --
    préféré à list_device_services (un appel par appareil) pour
    l'orchestrateur, qui a besoin des services de TOUS les appareils
    à chaque passage. Renvoie ({device_id_str: [services]}, error)."""
    data, error = _get(api_base, "/devices/services", params={"segment_id": network_segment_id})
    return (data if isinstance(data, dict) else {}), error


def list_links(api_base, network_segment_id):
    data, error = _get(api_base, "/links", params={"segment_id": network_segment_id})
    return (data if isinstance(data, list) else []), error


def list_sites(api_base):
    data, error = _get(api_base, "/sites")
    return (data if isinstance(data, list) else []), error
