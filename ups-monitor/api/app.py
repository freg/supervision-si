"""
ups-monitor-api (livraison #415) -- tuile « UPS » du hub, demandée en
urgence : une liste d'onduleurs (site / IP / utilisateur / mot de passe),
un automate qui interroge chaque carte réseau par HTTP
(`http://user:password@ip/index.htm`, version 0), une fiche d'état
extraite de la page (tous les champs présentés), archivée et consultable
en timeline. Fréquence initiale 1 h, paramétrable (globale et par onduleur).

Routes (préfixe /api/ups via tls-proxy) :
  GET    /health, /status                      -- santé, compteurs, réglages effectifs
  GET    /ups                                  -- liste (sans mot de passe) + dernier état
  POST   /ups                                  -- créer {name, site, host, scheme, path, username, password, poll_interval_seconds, enabled, notes}
  GET    /ups/<id>                             -- fiche : onduleur + dernier relevé + dernière fiche complète
  PUT    /ups/<id>                             -- modifier (mot de passe vide = inchangé, clear_password pour l'effacer)
  DELETE /ups/<id>                             -- supprimer (archive comprise)
  POST   /ups/<id>/poll                        -- relever MAINTENANT (test après saisie)
  POST   /ups/test                             -- essayer une saisie SANS l'enregistrer ni l'archiver
  GET    /ups/<id>/readings?start&end&limit&fields=1   -- timeline (archive)
  GET    /ups/<id>/series?key=input_voltage&start&end  -- série d'un champ
  GET    /logs                                 -- journal partagé
"""
import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

import credential_crypto
import poller
import store

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "ups-monitor-api")

_log = logging.getLogger("ups_monitor_app")

DB_PATH = os.environ.get("UPS_MONITOR_DB_PATH", "/data/ups-monitor.db")
store.ensure_schema(DB_PATH)
poller.start_background_thread(DB_PATH)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "ok",
        "counts": store.counts(DB_PATH),
        "settings": {
            "default_interval_seconds": poller.DEFAULT_INTERVAL_SECONDS,
            "tick_seconds": poller.TICK_SECONDS,
            "http_timeout_seconds": poller.HTTP_TIMEOUT_SECONDS,
            "retention_days": poller.RETENTION_DAYS,
            "poll_enabled": os.environ.get("UPS_POLL_ENABLED", "true").strip().lower() != "false",
            # Faux = mots de passe stockés en clair dans /data : fournir
            # UPS_CRED_PASSPHRASE et UPS_CRED_SALT (voir README).
            "secrets_encrypted": credential_crypto.is_configured(),
        },
    }), 200


@app.route("/ups", methods=["GET"])
def list_ups():
    return jsonify(store.list_devices(DB_PATH)), 200


@app.route("/ups", methods=["POST"])
def create_ups():
    data = request.get_json(silent=True) or {}
    device, err = store.create_device(DB_PATH, data)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(device), 201


@app.route("/ups/test", methods=["POST"])
def test_ups():
    """Essai d'une saisie (formulaire) : requête + parse, rien d'enregistré.
    Le mot de passe voyage dans le corps de CETTE requête seulement."""
    data = request.get_json(silent=True) or {}
    values, err = store._normalize_device(data)  # noqa: SLF001 -- même validation que la création
    if err:
        return jsonify({"error": err}), 400
    result = poller.poll_device(values)
    return jsonify(_public_result(result)), 200


@app.route("/ups/<int:ups_id>", methods=["GET"])
def get_ups(ups_id):
    device = store.get_device(DB_PATH, ups_id)
    if device is None:
        return jsonify({"error": "onduleur inconnu"}), 404
    latest = store.latest_reading(DB_PATH, ups_id)
    latest_ok = latest if (latest and latest["ok"]) else store.latest_ok_reading(DB_PATH, ups_id)
    return jsonify({"device": device, "latest": latest, "latest_ok": latest_ok, "url": poller.build_url(device)}), 200


@app.route("/ups/<int:ups_id>", methods=["PUT"])
def update_ups(ups_id):
    data = request.get_json(silent=True) or {}
    device, err = store.update_device(DB_PATH, ups_id, data)
    if err:
        return jsonify({"error": err}), 404 if err == "onduleur inconnu" else 400
    return jsonify(device), 200


@app.route("/ups/<int:ups_id>", methods=["DELETE"])
def delete_ups(ups_id):
    if not store.delete_device(DB_PATH, ups_id):
        return jsonify({"error": "onduleur inconnu"}), 404
    return jsonify({"status": "deleted", "id": ups_id}), 200


@app.route("/ups/<int:ups_id>/poll", methods=["POST"])
def poll_ups(ups_id):
    device = store.get_device(DB_PATH, ups_id, include_secret=True)
    if device is None:
        return jsonify({"error": "onduleur inconnu"}), 404
    result = poller.poll_device(device)
    store.record_reading(DB_PATH, ups_id, result)
    return jsonify(_public_result(result)), 200


@app.route("/ups/<int:ups_id>/readings", methods=["GET"])
def readings(ups_id):
    if store.get_device(DB_PATH, ups_id) is None:
        return jsonify({"error": "onduleur inconnu"}), 404
    with_fields = request.args.get("fields", "0") in ("1", "true")
    rows = store.list_readings(
        DB_PATH, ups_id,
        start=request.args.get("start"), end=request.args.get("end"),
        limit=request.args.get("limit", 500, type=int), with_fields=with_fields,
    )
    return jsonify({"ups_id": ups_id, "readings": rows}), 200


@app.route("/ups/<int:ups_id>/series", methods=["GET"])
def series(ups_id):
    if store.get_device(DB_PATH, ups_id) is None:
        return jsonify({"error": "onduleur inconnu"}), 404
    key = (request.args.get("key") or "").strip()
    if not key:
        return jsonify({"error": "'key' requis (ex. input_voltage)"}), 400
    points = store.field_series(
        DB_PATH, ups_id, key,
        start=request.args.get("start"), end=request.args.get("end"),
        limit=request.args.get("limit", 2000, type=int),
    )
    return jsonify({"ups_id": ups_id, "key": key, "points": points}), 200


def _public_result(result):
    """Résultat de relevé sans l'URL complète (elle ne contient pas le mot
    de passe, mais on ne renvoie que l'hôte/chemin par prudence)."""
    out = dict(result)
    out.pop("url", None)
    return out


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


SERVICE_NAME = "ups-monitor-api"
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
