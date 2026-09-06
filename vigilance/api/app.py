"""
vigilance-api -- livraison #262, backlog item 34, suite de
`classifier/` (#260). Voir `store.py` pour le détail complet de la
portée et des trois premiers signaux.
"""
import calendar
import logging
import os
import threading
import time

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import store

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "vigilance-api")

_log = logging.getLogger("vigilance_app")

# Branchement rights-api -- livraison #321, item 38 du backlog. Une
# seule route d'écriture dans ce module -- /analyze déclenche un
# passage immédiat (hors du rythme périodique déjà en place) et
# PERSISTE les signaux détectés. Sans garde, n'importe qui pourrait
# déclencher des passages répétés à volonté (bruit dans l'historique
# des signaux, charge supplémentaire sur network-agent-api en cascade).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-320) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "vigilance-api", "resource_id": None, "action": "manage"},
            timeout=5,
        )
    except requests.RequestException as exc:
        _log.debug("_check_manage_right : rights-api injoignable, refus par prudence -- %s", exc)
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        _log.debug("_check_manage_right : rights-api a répondu %s", resp.status_code)
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    if not allowed:
        _log.debug("_check_manage_right : refusé pour les groupes %s", groups)
    return allowed, None if allowed else "droit 'manage' sur vigilance-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("VIGILANCE_DB_PATH", "/data/vigilance.db")
store.ensure_schema(DB_PATH)

# ⚠️ network-agent-api tourne en network_mode: host (#238-239) --
# HOST_IP, jamais le nom de service Docker (même piège déjà rencontré
# pour backup-restore-api/#249 et architecture-api/#254).
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")
CLASSIFIER_API_URL = os.environ.get("CLASSIFIER_API_INTERNAL_URL", "http://classifier-api:5000").rstrip("/")

SERVICE_DIVERSITY_THRESHOLD = int(os.environ.get("VIGILANCE_SERVICE_DIVERSITY_THRESHOLD", str(store.DEFAULT_SERVICE_DIVERSITY_THRESHOLD)))
VOLUME_GROWTH_THRESHOLD = int(os.environ.get("VIGILANCE_VOLUME_GROWTH_PERCENT_THRESHOLD", str(store.DEFAULT_VOLUME_GROWTH_PERCENT_THRESHOLD)))
SILENCE_THRESHOLD_HOURS = int(os.environ.get("VIGILANCE_SILENCE_THRESHOLD_HOURS", str(store.DEFAULT_SILENCE_THRESHOLD_HOURS)))
ANALYSIS_INTERVAL_SECONDS = int(os.environ.get("VIGILANCE_ANALYSIS_INTERVAL_SECONDS", "1800"))
RETENTION_DAYS = int(os.environ.get("VIGILANCE_RETENTION_DAYS", "30"))
TARGET_CATEGORY = "client_dhcp_dynamique"
INFRASTRUCTURE_CATEGORY = "equipement_infrastructure"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def _get(url, **kwargs):
    """Best-effort explicite -- toujours (résultat, erreur), jamais
    une exception propagée -- une source indisponible ne doit jamais
    faire planter toute l'analyse (même discipline que
    architecture-api/#253)."""
    try:
        resp = requests.get(url, timeout=10, **kwargs)
    except requests.RequestException as exc:
        return None, str(exc)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "réponse illisible"


def _classify_all(devices):
    """Classifie tous les appareils AVEC un nom d'hôte, en un seul
    appel groupé -- renvoie {mac: category}."""
    with_hostname = [d for d in devices if d.get("hostname")]
    if not with_hostname:
        return {}
    items = [{"text": d["hostname"], "ip_address": d.get("ip_address")} for d in with_hostname]
    try:
        resp = requests.post(f"{CLASSIFIER_API_URL}/classify/batch", json=items, timeout=15)
    except requests.RequestException as exc:
        _log.debug("_classify_all : classifier-api injoignable -- %s", exc)
        return {}
    if resp.status_code != 200:
        return {}
    try:
        results = resp.json()
    except ValueError:
        return {}
    mac_to_category = {}
    for device in with_hostname:
        classification = results.get(device["hostname"])
        if classification and classification.get("category"):
            mac_to_category[device["mac_address"]] = classification["category"]
    return mac_to_category


def analyze_segment(segment_id):
    """LE MOTEUR D'ANALYSE -- croise network-agent (appareils,
    échanges, services, historique) et classifier (catégorie
    sémantique) pour détecter les trois signaux ciblés sur les
    clients DHCP dynamiques (voir store.py pour le détail complet du
    raisonnement de chacun). Renvoie le nombre de signaux détectés à
    ce passage. Best-effort explicite à chaque étape -- une source
    indisponible réduit ce que l'analyse peut détecter, ne l'empêche
    jamais entièrement."""
    if not NETWORK_AGENT_API_URL:
        _log.debug("analyze_segment : NETWORK_AGENT_API_URL non configurée -- analyse impossible")
        return 0

    devices, err = _get(f"{NETWORK_AGENT_API_URL}/devices", params={"segment_id": segment_id})
    if err or not devices:
        _log.debug("analyze_segment : devices indisponibles -- %s", err)
        return 0

    mac_to_category = _classify_all(devices)
    mac_to_device = {d["mac_address"]: d for d in devices}
    id_to_mac = {d["id"]: d["mac_address"] for d in devices}

    dhcp_macs = {mac for mac, cat in mac_to_category.items() if cat == TARGET_CATEGORY}
    signals_detected = 0

    # Signaux 1-3 UNIQUEMENT s'il y a des clients DHCP dans ce segment
    # -- signal 4 (infrastructure silencieuse) est INDÉPENDANT des
    # clients DHCP, jamais sauté pour cette raison (bug réel trouvé et
    # corrigé en testant : un `return 0` prématuré ici empêchait le
    # signal 4 de jamais s'exécuter dès qu'un segment n'avait aucun
    # client DHCP connu, même avec de l'infrastructure silencieuse à
    # signaler).
    if dhcp_macs:
        # --- Signal 1 : contact avec de l'infrastructure ---------------------
        links, err_links = _get(f"{NETWORK_AGENT_API_URL}/links", params={"segment_id": segment_id})
        if not err_links and links:
            infra_macs = {mac for mac, cat in mac_to_category.items() if cat == INFRASTRUCTURE_CATEGORY}
            if infra_macs:
                for link in links:
                    mac_a = id_to_mac.get(link.get("device_a_id"))
                    mac_b = id_to_mac.get(link.get("device_b_id"))
                    if mac_a in dhcp_macs and mac_b in infra_macs:
                        dhcp_mac, infra_mac = mac_a, mac_b
                    elif mac_b in dhcp_macs and mac_a in infra_macs:
                        dhcp_mac, infra_mac = mac_b, mac_a
                    else:
                        continue
                    infra_device = mac_to_device.get(infra_mac, {})
                    store.record_signal(
                        DB_PATH, dhcp_mac, mac_to_device.get(dhcp_mac, {}).get("hostname") or dhcp_mac,
                        "contact_infrastructure", "critical",
                        f"a échangé du trafic avec {infra_device.get('hostname') or infra_mac} "
                        f"(classé équipement d'infrastructure) -- violation de segmentation potentielle, "
                        f"un client dynamique ne devrait normalement pas parler directement à ce type d'équipement",
                    )
                    signals_detected += 1

        # --- Signal 2 : diversité de services élevée --------------------------
        all_services, err_services = _get(f"{NETWORK_AGENT_API_URL}/devices/services", params={"segment_id": segment_id})
        if not err_services and all_services:
            for mac in dhcp_macs:
                device = mac_to_device.get(mac, {})
                device_id = str(device.get("id"))
                services = all_services.get(device_id, [])
                if len(services) > SERVICE_DIVERSITY_THRESHOLD:
                    store.record_signal(
                        DB_PATH, mac, device.get("hostname") or mac,
                        "diversite_services", "warning",
                        f"{len(services)} services/ports distincts observés -- s'écarte du profil "
                        f"habituel d'un client dynamique (généralement HTTP/HTTPS/DNS, peu de ports) -- "
                        f"seuil configuré : {SERVICE_DIVERSITY_THRESHOLD}",
                    )
                    signals_detected += 1

        # --- Signal 3 : croissance de volume anormale --------------------------
        for mac in dhcp_macs:
            device = mac_to_device.get(mac, {})
            device_id = device.get("id")
            if device_id is None:
                continue
            history, err_hist = _get(f"{NETWORK_AGENT_API_URL}/devices/{device_id}/presence-history")
            if err_hist or not history or len(history) < 2:
                continue
            first_bytes = history[0].get("bytes_total", 0)
            last_bytes = history[-1].get("bytes_total", 0)
            if first_bytes <= 0:
                continue
            growth_percent = (last_bytes - first_bytes) / first_bytes * 100
            if growth_percent > VOLUME_GROWTH_THRESHOLD:
                store.record_signal(
                    DB_PATH, mac, device.get("hostname") or mac,
                    "croissance_volume", "warning",
                    f"volume cumulé en hausse de {growth_percent:.0f}% depuis le premier relevé -- "
                    f"usage intensif inattendu pour un profil normalement transitoire -- "
                    f"seuil configuré : {VOLUME_GROWTH_THRESHOLD}%",
                )
                signals_detected += 1

    # --- Signal 4 : infrastructure silencieuse (livraison #266) -------------
    infra_macs_for_silence = {mac for mac, cat in mac_to_category.items() if cat == INFRASTRUCTURE_CATEGORY}
    for mac in infra_macs_for_silence:
        device = mac_to_device.get(mac, {})
        last_seen = device.get("last_seen")
        if not last_seen:
            continue
        try:
            last_seen_epoch = calendar.timegm(time.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            continue  # format inattendu -- jamais une exception qui interromprait toute l'analyse pour UN appareil
        hours_since = (time.time() - last_seen_epoch) / 3600
        if hours_since > SILENCE_THRESHOLD_HOURS:
            store.record_signal(
                DB_PATH, mac, device.get("hostname") or mac,
                "infrastructure_silencieuse", "critical",
                f"aucun trafic observé depuis {hours_since:.0f}h -- un équipement d'infrastructure a "
                f"normalement une activité régulière, un silence prolongé peut signaler une panne, "
                f"une coupure réseau, ou une compromission -- seuil configuré : {SILENCE_THRESHOLD_HOURS}h",
            )
            signals_detected += 1

    return signals_detected


def _run_analysis_forever():
    """Thread de fond -- un passage toutes les
    VIGILANCE_ANALYSIS_INTERVAL_SECONDS (30 min par défaut). Analyse
    TOUS les segments connus (via network-agent /sites). Ne s'arrête
    JAMAIS définitivement sur un incident isolé, même motif que les
    autres boucles de fond de ce projet."""
    while True:
        try:
            if NETWORK_AGENT_API_URL:
                sites, err = _get(f"{NETWORK_AGENT_API_URL}/sites")
                if not err and sites:
                    for site in sites:
                        for segment in site.get("segments", []):
                            n = analyze_segment(segment["id"])
                            if n:
                                _log.debug("_run_analysis_forever : %d signal(aux) détecté(s) pour le segment %s", n, segment.get("label"))
            retention_cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - RETENTION_DAYS * 86400))
            store.purge_old_signals(DB_PATH, retention_cutoff)
        except Exception as exc:  # noqa: BLE001 -- jamais un arrêt définitif du thread de fond sur un incident transitoire
            _log.debug("_run_analysis_forever : ÉCHEC -- %s", exc)
        time.sleep(ANALYSIS_INTERVAL_SECONDS)


_analysis_thread = threading.Thread(target=_run_analysis_forever, daemon=True)
_analysis_thread.start()


@app.route("/analyze", methods=["POST"])
def analyze_now():
    """Déclenche un passage d'analyse IMMÉDIAT (hors du rythme
    périodique) -- corps JSON optionnel {"segment_id": N} ; sans
    corps, analyse TOUS les segments connus (voir
    _run_analysis_forever pour le même parcours).

    Protégée par rights-api (#321)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    segment_id = body.get("segment_id")
    if segment_id:
        n = analyze_segment(segment_id)
        return jsonify({"status": "ok", "signals_detected": n}), 200

    if not NETWORK_AGENT_API_URL:
        return jsonify({"error": "NETWORK_AGENT_API_URL non configurée"}), 502
    sites, err = _get(f"{NETWORK_AGENT_API_URL}/sites")
    if err:
        return jsonify({"error": f"network-agent injoignable : {err}"}), 502
    total = 0
    for site in sites or []:
        for segment in site.get("segments", []):
            total += analyze_segment(segment["id"])
    return jsonify({"status": "ok", "signals_detected": total}), 200


@app.route("/signals", methods=["GET"])
def list_signals():
    return jsonify(store.list_signals(
        DB_PATH, signal_type=request.args.get("signal_type"), severity=request.args.get("severity"),
        device_mac=request.args.get("device_mac"), limit=request.args.get("limit", type=int) or 200,
    )), 200


@app.route("/summary", methods=["GET"])
def summary():
    """"Santé du parc" en un coup d'œil -- demandé explicitement."""
    return jsonify(store.signal_summary(DB_PATH)), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

try:
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    _MemcacheClient = None

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


SERVICE_NAME = "vigilance-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler and _MemcacheClient:
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
