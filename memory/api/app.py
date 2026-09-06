"""
memory-api -- livraison #259, backlog item 32 ("Mémoire"). Voir
`store.py` pour le détail complet de la portée (scopée au tampon de
logs partagé, jamais un "tout Memcached" générique -- raison
technique réelle documentée là-bas).
"""
import json
import logging
import os
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS
from pymemcache.client.base import Client as MemcacheClient

import store

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

try:
    from log_buffer import (
        read_shared_log_buffer, read_shared_log_source_registry,
        make_shared_log_handler,
    )
except ImportError:
    read_shared_log_buffer = None
    read_shared_log_source_registry = None
    make_shared_log_handler = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "memory-api")

_log = logging.getLogger("memory_app")

DB_PATH = os.environ.get("MEMORY_DB_PATH", "/data/memory.db")
store.ensure_schema(DB_PATH)

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# Liste des SERVICE_NAME internes CONNUS (livraison #259) -- Memcached
# n'offre PAS de "lister les clés" (voir store.py, docstring) -- cette
# liste a été recensée directement dans le code de chaque backend
# (`grep SERVICE_NAME = "..."` sur tout le projet), jamais devinée.
# Volontairement ICI (pas dans store.py) -- ce n'est PAS une donnée
# persistante, plutôt une CONSTANTE de déploiement, à tenir à jour
# manuellement si un nouveau service rejoint le projet (voir
# memory/README.md pour la procédure).
KNOWN_SERVICE_NAMES = [
    "api", "architecture-api", "backup-restore-api", "cacti-api", "classifier-api",
    "dba-api", "ged-api", "geo-import-api", "glpi-api", "imap-client-api", "ipam-api",
    "ldap-admin-api", "memory-api", "nebula-api", "netprobe-api", "network-agent-api",
    "optick-api", "owncloud-api", "owncloud-search-api", "pixel-grid-api",
    "pixel-grid-bridge", "prefs-api", "relations-api", "retro-api", "rights-api",
    "rsyslog-listener", "schema-analyzer-api", "snmp-api", "ssh-tunnels-api",
    "tasks-api", "tickets-api", "tts-gu-api", "vault-admin-api", "vault-api",
    "vigilance-api", "zenoss-api",
]
PUSHED_LOG_SOURCES_REGISTRY_KEY = "pushed_log_sources"

COLLECTION_INTERVAL_SECONDS = int(os.environ.get("MEMORY_COLLECTION_INTERVAL_SECONDS", "300"))
RETENTION_DAYS = int(os.environ.get("MEMORY_RETENTION_DAYS", "30"))
REPOPULATE_COUNT = int(os.environ.get("MEMORY_REPOPULATE_COUNT", "50"))


def _all_known_services():
    """Combine les deux sources énumérables (voir store.py) --
    services internes CONNUS + sources /push-log déjà vues au moins
    une fois (registre partagé). Best-effort explicite sur le
    registre -- son absence/échec ne doit jamais empêcher la collecte
    des services internes, toujours disponibles."""
    services = list(KNOWN_SERVICE_NAMES)
    if read_shared_log_source_registry:
        try:
            pushed = read_shared_log_source_registry(get_memcache_client, PUSHED_LOG_SOURCES_REGISTRY_KEY)
            services.extend(s for s in pushed if s not in services)
        except Exception as exc:  # noqa: BLE001 -- le registre est un bonus, jamais bloquant
            _log.debug("_all_known_services : registre pushed_log_sources injoignable -- %s", exc)
    return services


def _repopulate_if_empty(service, current_buffer):
    """Repopulation (livraison #259, demandé explicitement) -- si le
    tampon Memcached d'un service est VIDE (cas le plus probable :
    Memcached vient de redémarrer, voir shared/log_buffer.py --
    "perdu seulement si Memcached LUI-MÊME redémarre") ALORS QUE de
    l'historique existe déjà en base, réinjecte les
    `REPOPULATE_COUNT` entrées les plus récentes -- évite qu'un
    gestionnaire de logs affiche un tampon vide juste après un
    redémarrage de Memcached, le temps que de nouvelles entrées
    réelles s'accumulent à nouveau. Best-effort explicite -- une
    réinjection ratée n'est jamais une erreur bloquante pour le reste
    de la collecte."""
    if current_buffer:
        return  # tampon déjà non vide -- rien à repeupler
    recent = store.list_entries(DB_PATH, service=service, limit=REPOPULATE_COUNT)
    if not recent:
        return  # aucun historique connu non plus -- rien à repeupler
    try:
        client = get_memcache_client()
        # Ordre CHRONOLOGIQUE croissant (list_entries renvoie le plus
        # récent en premier -- inversé ici pour reconstituer un
        # tampon dans le même ordre que shared/log_buffer.py l'aurait
        # construit lui-même, plus ancien en premier).
        payload = [
            {"service": e["service"], "timestamp": e["entry_timestamp"], "level": e["level"],
             "logger": e["logger"], "message": e["message"]}
            for e in reversed(recent)
        ]
        client.set(f"logbuf:{service}", json.dumps(payload).encode("utf-8"), expire=0)
        _log.debug("_repopulate_if_empty : %s repeuplé avec %d entrée(s) historique(s)", service, len(payload))
    except Exception as exc:  # noqa: BLE001 -- jamais bloquant pour le reste de la collecte
        _log.debug("_repopulate_if_empty : échec de repopulation pour %s -- %s", service, exc)


def _run_collection_forever():
    """Thread de fond -- "faible impact et simplement supervisé"
    (demandé explicitement) : un passage toutes les
    COLLECTION_INTERVAL_SECONDS (5 min par défaut, jamais chaque
    seconde), lit le tampon de CHAQUE service connu, persiste les
    nouvelles entrées, repeuple si vide, puis purge l'historique trop
    ancien. Ne s'arrête JAMAIS définitivement sur un incident isolé,
    même motif que les autres boucles de fond de ce projet."""
    if not read_shared_log_buffer:
        _log.debug("_run_collection_forever : log_buffer non disponible (hors conteneur Docker réel ?) -- collecte jamais démarrée")
        return
    while True:
        try:
            for service in _all_known_services():
                buffer = read_shared_log_buffer(service, get_memcache_client)
                store.persist_new_entries(DB_PATH, service, buffer)
                _repopulate_if_empty(service, buffer)
            retention_cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - RETENTION_DAYS * 86400))
            purged = store.purge_old_entries(DB_PATH, retention_cutoff)
            if purged:
                _log.debug("_run_collection_forever : %d entrée(s) ancienne(s) purgée(s) (> %d jours)", purged, RETENTION_DAYS)
        except Exception as exc:  # noqa: BLE001 -- jamais un arrêt définitif du thread de fond sur un incident transitoire
            _log.debug("_run_collection_forever : ÉCHEC -- %s", exc)
        time.sleep(COLLECTION_INTERVAL_SECONDS)


_collection_thread = threading.Thread(target=_run_collection_forever, daemon=True)
_collection_thread.start()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/entries", methods=["GET"])
def list_entries():
    service = request.args.get("service")
    level = request.args.get("level")
    since = request.args.get("since", type=float)
    until = request.args.get("until", type=float)
    limit = request.args.get("limit", type=int) or 500
    return jsonify(store.list_entries(DB_PATH, service=service, level=level, since=since, until=until, limit=limit)), 200


@app.route("/services", methods=["GET"])
def known_services():
    """Services ayant AU MOINS une entrée persistée -- distinct de
    KNOWN_SERVICE_NAMES (qui liste tous les services SURVEILLÉS,
    même sans encore avoir généré la moindre entrée)."""
    return jsonify(store.list_known_services(DB_PATH)), 200


@app.route("/stats", methods=["GET"])
def stats():
    """LE "calcul" demandé explicitement -- comptage par service et
    par niveau. `since`/`until` optionnels (timestamps Unix) pour
    restreindre la période."""
    since = request.args.get("since", type=float)
    until = request.args.get("until", type=float)
    return jsonify(store.compute_stats_by_service(DB_PATH, since=since, until=until)), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# ------------------------------------------------------------------
SERVICE_NAME = "memory-api"
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
