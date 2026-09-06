"""
rsyslog-listener -- écoute UDP syslog (livraison #177, backlog
BACKLOG.md #3, étape 4/4, DERNIÈRE de l'initiative "logs de toutes
sortes"). Voir listener.py (mécanique socket) et syslog_parser.py
(parsing RFC 3164/5424, logique pure).

Port UDP EXPOSÉ DIRECTEMENT sur l'hôte (voir docker-compose.yml,
RSYSLOG_LISTENER_PORT) -- CONTRAIREMENT à tous les autres services de
ce projet (atteints via tls-proxy, HTTP/HTTPS) : syslog est un
protocole RÉSEAU BRUT (UDP), pas HTTP -- ne PEUT PAS transiter par un
reverse proxy HTTP. Une machine distante qui pousse ses logs syslog
doit joindre ce port DIRECTEMENT, jamais via GATEWAY_PORT.

UN SEUL worker Gunicorn (voir Dockerfile) -- même raisonnement que
ssh-tunnels-api (#159) : un port UDP ne peut être BOUND que par un
seul processus, un second worker échouerait au démarrage.
"""
import os
import threading

from flask import Flask, jsonify
from flask_cors import CORS

import listener

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "rsyslog-listener")

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))
LISTEN_HOST = os.environ.get("RSYSLOG_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("RSYSLOG_LISTEN_PORT", "5514"))
SOURCE_NAME = os.environ.get("RSYSLOG_SOURCE_NAME", "rsyslog")

try:
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    _MemcacheClient = None


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# Journal PARTAGE (endpoint /logs) -- même mécanisme que les autres
# backends de ce projet (log_buffer.py, #145) -- utile ici aussi pour
# diagnostiquer CE service lui-même (ex. "le socket a-t-il bien
# démarré ?"), séparé du FLUX syslog qu'il reçoit et republie sous
# SOURCE_NAME (deux choses distinctes : les logs applicatifs de
# rsyslog-listener lui-même, vs. les messages syslog qu'il relaie).
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer, append_shared_log_entry, register_shared_log_source
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None
    append_shared_log_entry = None
    register_shared_log_source = None

SERVICE_NAME = "rsyslog-listener"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler and _MemcacheClient:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)

# Registre PARTAGÉ des sources (même registre que push/url/file, voir
# prefs-api/app.py PUSHED_LOG_SOURCES_REGISTRY_KEY) -- clé identique
# EN DUR ici plutôt qu'une config -- ce registre est un contrat
# implicite entre tous les producteurs de logs de ce mécanisme, pas
# une valeur à faire varier par service.
PUSHED_LOG_SOURCES_REGISTRY_KEY = "pushed_log_sources"

# Démarrage du thread d'écoute UDP -- UNE SEULE FOIS, au chargement du
# module (donc avant que Gunicorn ne commence à servir /health) --
# jamais conditionné à une requête HTTP, ce service N'A DE RAISON
# D'ÊTRE QUE pour cette écoute permanente.
if append_shared_log_entry and register_shared_log_source:
    _listener_thread = threading.Thread(
        target=listener.run_listener,
        args=(
            LISTEN_HOST, LISTEN_PORT, SOURCE_NAME, get_memcache_client,
            append_shared_log_entry, register_shared_log_source,
            PUSHED_LOG_SOURCES_REGISTRY_KEY, LOG_BUFFER_SIZE,
        ),
        kwargs={"log_fn": app.logger.warning},
        daemon=True,
    )
    _listener_thread.start()


@app.route("/logs", methods=["GET"])
def get_logs():
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "listening_on_udp_port": LISTEN_PORT}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
