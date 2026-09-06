"""
netmap-orchestrator-api -- livraison #388. Propose des étapes
d'analyse/supervision réseau à partir des données DÉJÀ COLLECTÉES par
network-agent-api (appareils IP/MAC/DNS/ports confirmés dans le
temps, liens/flux/volumes -- voir network-agent/api/store.py) --
NE DUPLIQUE RIEN de ces données, les LIT via l'API HTTP et applique
des règles (rules/*.py) pour SUGGÉRER des actions concrètes (ex.
lancer un scan nmap via netprobe, enregistrer une cible SNMP).

Volet Nebula recentré (voir CHANGELOG.md #388) : "le besoin d'analyse
et de supervision d'un environnement réseau... est prioritaire" --
demandé explicitement après avoir constaté que network-agent-api
couvrait déjà l'essentiel du modèle de données envisagé.
"""
import logging
import os
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

import store
import engine
from rules import RULES

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "netmap-orchestrator-api")

_log = logging.getLogger("netmap_orchestrator_app")

DB_PATH = os.environ.get("NETMAP_ORCHESTRATOR_DB_PATH", "/data/netmap-orchestrator.db")
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/") or None
store.ensure_schema(DB_PATH)

# Passage périodique en arrière-plan -- même motif que netprobe
# (scheduler.py) : jamais bloquant au démarrage, un échec d'un
# passage ne doit jamais arrêter la boucle.
RUN_INTERVAL_SECONDS = int(os.environ.get("NETMAP_ORCHESTRATOR_INTERVAL_SECONDS", "300"))


def _background_loop(stop_event=None):
    while stop_event is None or not stop_event.is_set():
        try:
            results = engine.run_all_rules(DB_PATH, NETWORK_AGENT_API_URL)
            _log.debug("_background_loop : passage terminé -- %s", results)
        except Exception as exc:  # noqa: BLE001 -- un passage en échec ne doit jamais arrêter la boucle
            _log.debug("_background_loop : échec, on continue -- %s", exc)
        if stop_event is not None:
            stop_event.wait(RUN_INTERVAL_SECONDS)
        else:
            time.sleep(RUN_INTERVAL_SECONDS)


_bg_thread = threading.Thread(target=_background_loop, daemon=True)
_bg_thread.start()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/rules", methods=["GET"])
def list_rules():
    return jsonify({"rules": list(RULES)}), 200


@app.route("/run", methods=["POST"])
def run_now():
    """Déclenche un passage IMMÉDIAT (toutes les règles) -- best-effort,
    ne bloque jamais la boucle de fond (appel direct à engine, pas de
    coordination avec le thread -- un passage manuel et un passage
    automatique qui se chevauchent ne posent pas de problème, chacun
    ne fait qu'ÉCRIRE/METTRE À JOUR des lignes, jamais une opération
    destructrice)."""
    results = engine.run_all_rules(DB_PATH, NETWORK_AGENT_API_URL)
    return jsonify({"results": results}), 200


@app.route("/run/<rule_name>", methods=["POST"])
def run_one_rule(rule_name):
    count, error = engine.run_rule(DB_PATH, NETWORK_AGENT_API_URL, rule_name)
    if count is None:
        return jsonify({"error": error}), 404
    return jsonify({"count": count, "error": error}), 200


@app.route("/suggestions", methods=["GET"])
def list_suggestions_route():
    status = request.args.get("status")
    rule_name = request.args.get("rule_name")
    if status and status not in store.STATUSES:
        return jsonify({"error": f"'status' doit être l'un de {store.STATUSES}"}), 400
    limit = request.args.get("limit", default=200, type=int)
    return jsonify({"suggestions": store.list_suggestions(DB_PATH, status=status, rule_name=rule_name, limit=limit)}), 200


@app.route("/suggestions/<int:suggestion_id>", methods=["GET"])
def get_suggestion_route(suggestion_id):
    suggestion = store.get_suggestion(DB_PATH, suggestion_id)
    if suggestion is None:
        return jsonify({"error": "suggestion introuvable"}), 404
    return jsonify(suggestion), 200


@app.route("/suggestions/<int:suggestion_id>/status", methods=["POST"])
def set_suggestion_status_route(suggestion_id):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in store.STATUSES:
        return jsonify({"error": f"'status' doit être l'un de {store.STATUSES}"}), 400
    updated = store.set_suggestion_status(DB_PATH, suggestion_id, status)
    if not updated:
        return jsonify({"error": "suggestion introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/summary", methods=["GET"])
def summary_route():
    return jsonify({"by_status": store.count_by_status(DB_PATH)}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (/logs) -- même motif que tous les autres services
# de ce projet (voir shared/log_buffer.py, livraison #145).
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


SERVICE_NAME = "netmap-orchestrator-api"
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
