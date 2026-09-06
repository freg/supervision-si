"""
API de l'agent d'exploration réseau (livraison #233, backlog item
20). UN SEUL agent, déployé en conteneur Docker sur un poste ayant
accès EN VPN au réseau interne déjà géré par Nebula -- CLARIFIÉ
explicitement avec la personne avant de coder ("un seul agent... une
seule tuile"), voir BACKLOG.md item 20 pour l'historique complet de
cette clarification.

Thread de capture en ARRIÈRE-PLAN, démarré UNE SEULE FOIS au
chargement du module -- même motif que rsyslog-listener (#177) :
ce service n'a de raison d'être que pour cette capture permanente,
jamais conditionnée à une requête HTTP. `tcpdump` nécessite des
privilèges élevés (CAP_NET_RAW/CAP_NET_ADMIN) -- voir Dockerfile et
docker-compose.yml.

**Redémarrage automatique en cas d'échec** -- `tcpdump` peut mourir
(interface qui disparaît, conteneur qui perd temporairement l'accès
VPN...) : la boucle de fond réessaie avec un délai, jamais un arrêt
DÉFINITIF de la capture sur un incident transitoire.
"""
import logging
import os
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

import capture
import store
import dns_resolver

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "network-agent-api")

_log = logging.getLogger("network_agent_app")

DB_PATH = os.environ.get("NETWORK_AGENT_DB_PATH", "/data/network-agent.db")
CAPTURE_INTERFACE = os.environ.get("NETWORK_AGENT_INTERFACE", "eth0")
SITE_NAME = os.environ.get("NETWORK_AGENT_SITE_NAME", "").strip()
SEGMENT_LABEL = os.environ.get("NETWORK_AGENT_SEGMENT_LABEL", "").strip()
SEGMENT_CIDR = os.environ.get("NETWORK_AGENT_SEGMENT_CIDR", "").strip() or None
CAPTURE_RETRY_SECONDS = int(os.environ.get("NETWORK_AGENT_RETRY_SECONDS", "30"))
# Désactivable explicitement (tests, environnement sans capacité
# CAP_NET_RAW) -- jamais un crash au démarrage si tcpdump ne peut
# tout simplement pas tourner ici.
CAPTURE_ENABLED = os.environ.get("NETWORK_AGENT_CAPTURE_ENABLED", "true").strip().lower() != "false"

# Résolution DNS (livraison #250, "afficher la résolution dns" +
# "récupérer le dns et le domain par défaut depuis l'hôte OU le
# faire paramétrer") -- voir dns_resolver.py pour le détail complet
# des deux mécanismes (résolveur système par défaut, serveur DNS
# spécifique si configuré).
DNS_SERVER = os.environ.get("NETWORK_AGENT_DNS_SERVER", "").strip() or None
DEFAULT_DOMAIN = os.environ.get("NETWORK_AGENT_DEFAULT_DOMAIN", "").strip()
DNS_RESOLVE_INTERVAL_SECONDS = int(os.environ.get("NETWORK_AGENT_DNS_RESOLVE_INTERVAL", "30"))
DNS_STALE_SECONDS = int(os.environ.get("NETWORK_AGENT_DNS_STALE_SECONDS", str(6 * 3600)))  # 6h -- re-resolution periodique (bail DHCP qui change)

# Relevés périodiques / rémanence (livraison #251, demandé
# explicitement : "voir dans le temps... présence des ip/mac,
# volumes échangés/usages par paire d'ip, services connectés par
# paire d'ip"). Défauts : un relevé par heure, conservé 30 jours --
# raisonnable pour observer une tendance sans croissance illimitée,
# ajustable si besoin (voir network-agent/README.md).
SNAPSHOT_INTERVAL_SECONDS = int(os.environ.get("NETWORK_AGENT_SNAPSHOT_INTERVAL_SECONDS", str(3600)))
HISTORY_RETENTION_DAYS = int(os.environ.get("NETWORK_AGENT_HISTORY_RETENTION_DAYS", "30"))

store.ensure_schema(DB_PATH)

_capture_status = {"running": False, "last_error": None, "started_at": None, "packets_processed": 0}
_capture_status_lock = threading.Lock()


def _run_capture_forever():
    """Boucle de fond -- ne s'arrête JAMAIS définitivement sur un
    échec isolé (tcpdump qui meurt, interface indisponible) --
    réessaie après CAPTURE_RETRY_SECONDS. Voir docstring du module."""
    if not SITE_NAME or not SEGMENT_LABEL:
        _log.debug("_run_capture_forever : NETWORK_AGENT_SITE_NAME/SEGMENT_LABEL non configurés -- capture jamais démarrée")
        with _capture_status_lock:
            _capture_status["last_error"] = "NETWORK_AGENT_SITE_NAME et NETWORK_AGENT_SEGMENT_LABEL requis pour démarrer la capture"
        return

    conn = store.get_connection(DB_PATH)
    try:
        site_id = store.get_or_create_site(conn, SITE_NAME)
        segment_id = store.get_or_create_segment(conn, site_id, SEGMENT_LABEL, cidr=SEGMENT_CIDR)
        conn.commit()
    finally:
        conn.close()

    while True:
        with _capture_status_lock:
            _capture_status["running"] = True
            _capture_status["started_at"] = store.now_iso()
            _capture_status["last_error"] = None
        try:
            _log.debug("_run_capture_forever : démarrage de la capture (interface=%s, site=%s, segment=%s)",
                       CAPTURE_INTERFACE, SITE_NAME, SEGMENT_LABEL)
            processed = capture.run_capture(CAPTURE_INTERFACE, segment_id, SEGMENT_CIDR, DB_PATH)
            with _capture_status_lock:
                _capture_status["packets_processed"] += processed
        except Exception as exc:  # noqa: BLE001 -- jamais un arrêt définitif du thread de fond sur un incident transitoire
            _log.debug("_run_capture_forever : ÉCHEC -- %s -- nouvelle tentative dans %ss", exc, CAPTURE_RETRY_SECONDS)
            with _capture_status_lock:
                _capture_status["running"] = False
                _capture_status["last_error"] = str(exc)
        time.sleep(CAPTURE_RETRY_SECONDS)


if CAPTURE_ENABLED:
    _capture_thread = threading.Thread(target=_run_capture_forever, daemon=True)
    _capture_thread.start()
else:
    _log.debug("app.py : capture désactivée explicitement (NETWORK_AGENT_CAPTURE_ENABLED=false)")


def _run_dns_resolution_forever():
    """Boucle de fond DISTINCTE du thread de capture (livraison #250)
    -- la résolution DNS est un appel réseau potentiellement LENT
    (jusqu'à quelques secondes en cas de timeout), jamais mêlée à la
    boucle de capture PAR PAQUET qui doit rester rapide. Ne s'arrête
    JAMAIS définitivement sur un incident isolé, même motif que
    `_run_capture_forever`."""
    while True:
        try:
            stale_before = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - DNS_STALE_SECONDS))
            candidates = store.list_devices_needing_dns_resolution(DB_PATH, stale_before)
            for device in candidates:
                hostname = dns_resolver.resolve_hostname(device["ip_address"], dns_server=DNS_SERVER)
                if hostname and DEFAULT_DOMAIN:
                    hostname = dns_resolver.strip_default_domain(hostname, DEFAULT_DOMAIN)
                store.update_device_hostname(DB_PATH, device["id"], hostname)
        except Exception as exc:  # noqa: BLE001 -- jamais un arrêt définitif du thread de fond sur un incident transitoire
            _log.debug("_run_dns_resolution_forever : ÉCHEC -- %s", exc)
        time.sleep(DNS_RESOLVE_INTERVAL_SECONDS)


_dns_thread = threading.Thread(target=_run_dns_resolution_forever, daemon=True)
_dns_thread.start()


def _run_snapshot_forever():
    """Boucle de fond DISTINCTE des deux autres (livraison #251) --
    prend un relevé de l'état cumulatif à intervalle régulier, puis
    purge les relevés trop anciens. Ne s'arrête JAMAIS définitivement
    sur un incident isolé, même motif que les deux autres boucles de
    fond. Ne fait RIEN tant que SITE_NAME/SEGMENT_LABEL ne sont pas
    configurés (même garde que la capture elle-même -- pas de segment
    à quoi rattacher un relevé sinon)."""
    if not SITE_NAME or not SEGMENT_LABEL:
        _log.debug("_run_snapshot_forever : NETWORK_AGENT_SITE_NAME/SEGMENT_LABEL non configurés -- relevés jamais démarrés")
        return
    while True:
        try:
            conn = store.get_connection(DB_PATH)
            try:
                site_id = store.get_or_create_site(conn, SITE_NAME)
                segment_id = store.get_or_create_segment(conn, site_id, SEGMENT_LABEL, cidr=SEGMENT_CIDR)
                conn.commit()
            finally:
                conn.close()
            store.take_snapshot(DB_PATH, segment_id)
            retention_cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - HISTORY_RETENTION_DAYS * 86400))
            purged = store.purge_old_snapshots(DB_PATH, retention_cutoff)
            if purged:
                _log.debug("_run_snapshot_forever : %d relevé(s) ancien(s) purgé(s) (> %d jours)", purged, HISTORY_RETENTION_DAYS)
        except Exception as exc:  # noqa: BLE001 -- jamais un arrêt définitif du thread de fond sur un incident transitoire
            _log.debug("_run_snapshot_forever : ÉCHEC -- %s", exc)
        time.sleep(SNAPSHOT_INTERVAL_SECONDS)


_snapshot_thread = threading.Thread(target=_run_snapshot_forever, daemon=True)
_snapshot_thread.start()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/capture/status", methods=["GET"])
def capture_status():
    with _capture_status_lock:
        return jsonify(dict(_capture_status)), 200


@app.route("/sites", methods=["GET"])
def list_sites():
    return jsonify(store.list_sites_with_segments(DB_PATH)), 200


@app.route("/devices", methods=["GET"])
def list_devices():
    """Filtres ajoutés (livraison #392, backlog item 58) : `depth`
    (répétable -- ?depth=p0&depth=p0.1 -- OU logique), `building`,
    `room`, `zone` (correspondance exacte), `min_bytes_total`. Tous
    optionnels, `segment_id` reste le seul déjà existant."""
    segment_id = request.args.get("segment_id", type=int)
    depths = request.args.getlist("depth") or None
    building = request.args.get("building")
    room = request.args.get("room")
    zone = request.args.get("zone")
    min_bytes_total = request.args.get("min_bytes_total", type=int)
    return jsonify(store.list_devices(
        DB_PATH, network_segment_id=segment_id, depths=depths,
        building=building, room=room, zone=zone, min_bytes_total=min_bytes_total,
    )), 200


@app.route("/filter-options", methods=["GET"])
def filter_options():
    """Valeurs distinctes réellement présentes (profondeurs,
    bâtiments, salles, zones) -- pour peupler les filtres côté
    interface (livraison #392). `segment_id` optionnel."""
    segment_id = request.args.get("segment_id", type=int)
    return jsonify(store.list_filter_options(DB_PATH, network_segment_id=segment_id)), 200


@app.route("/devices/for-period", methods=["GET"])
def list_devices_for_period_route():
    """Volume ÉCHANGÉ PENDANT une période précise (livraison #394,
    dernier des 4 filtres demandés -- "période temporelle") --
    `segment_id`/`start`/`end` (ISO 8601) tous requis. Voir
    store.list_devices_for_period pour le raisonnement complet
    (différence entre deux relevés, jamais un cumul brut)."""
    segment_id = request.args.get("segment_id", type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    if not segment_id or not start or not end:
        return jsonify({"error": "'segment_id', 'start' et 'end' requis"}), 400
    return jsonify(store.list_devices_for_period(DB_PATH, segment_id, start, end)), 200


@app.route("/observed-subnets", methods=["GET"])
def observed_subnets():
    """Découverte de sous-réseaux DEPUIS LE TRAFIC OBSERVÉ (livraison
    #256, "notre module d'exploration doit répondre à cette question
    [combien de segments réseau distincts faut-il couvrir]") --
    `segment_id` requis, `prefix_length` optionnel (défaut 24)."""
    segment_id = request.args.get("segment_id", type=int)
    if not segment_id:
        return jsonify({"error": "'segment_id' requis"}), 400
    prefix_length = request.args.get("prefix_length", type=int) or 24
    return jsonify(store.list_observed_subnets(DB_PATH, segment_id, prefix_length=prefix_length)), 200


@app.route("/devices/<int:device_id>/services", methods=["GET"])
def list_device_services(device_id):
    return jsonify(store.list_device_services(DB_PATH, device_id)), 200


@app.route("/devices/services", methods=["GET"])
def list_all_device_services():
    """Services de TOUS les appareils d'un segment, groupés par
    appareil (livraison #250) -- évite un appel par appareil côté
    hub pour afficher les points de service sur chaque ligne de la
    liste simultanément. `segment_id` requis."""
    segment_id = request.args.get("segment_id", type=int)
    if not segment_id:
        return jsonify({"error": "'segment_id' requis"}), 400
    grouped = store.list_services_by_segment(DB_PATH, segment_id)
    return jsonify({str(k): v for k, v in grouped.items()}), 200


@app.route("/links", methods=["GET"])
def list_links():
    """Échanges entre appareils d'un segment (livraison #250, "qui
    parle à qui") -- `segment_id` requis (les échanges n'ont de sens
    que rapportés à un segment précis, même contrainte que
    `list_devices`)."""
    segment_id = request.args.get("segment_id", type=int)
    if not segment_id:
        return jsonify({"error": "'segment_id' requis"}), 400
    return jsonify(store.list_device_links(DB_PATH, segment_id)), 200


@app.route("/links/services", methods=["GET"])
def list_link_services():
    """Services utilisés entre DEUX appareils précis (livraison #251,
    "services connectés par paire d'ip") -- `device_a_id`/`device_b_id`
    requis (les deux sens confondus, voir
    `store.list_device_link_services`)."""
    device_a_id = request.args.get("device_a_id", type=int)
    device_b_id = request.args.get("device_b_id", type=int)
    if not device_a_id or not device_b_id:
        return jsonify({"error": "'device_a_id' et 'device_b_id' requis"}), 400
    return jsonify(store.list_device_link_services(DB_PATH, device_a_id, device_b_id)), 200


@app.route("/devices/<int:device_id>/presence-history", methods=["GET"])
def device_presence_history(device_id):
    """Évolution dans le temps de la présence d'un appareil
    (livraison #251, "rémanence" -- voir store.list_presence_history)."""
    return jsonify(store.list_presence_history(DB_PATH, device_id)), 200


@app.route("/links/history", methods=["GET"])
def link_history():
    """Évolution dans le temps du volume échangé entre deux appareils
    précis (livraison #251) -- mêmes paramètres que `/links/services`."""
    device_a_id = request.args.get("device_a_id", type=int)
    device_b_id = request.args.get("device_b_id", type=int)
    if not device_a_id or not device_b_id:
        return jsonify({"error": "'device_a_id' et 'device_b_id' requis"}), 400
    return jsonify(store.list_link_history(DB_PATH, device_a_id, device_b_id)), 200


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
    from pymemcache.client.base import Client as MemcacheClient
except ImportError:
    MemcacheClient = None

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")


def get_memcache_client():
    return MemcacheClient((MEMCACHED_HOST, 11211))


SERVICE_NAME = "network-agent-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
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
