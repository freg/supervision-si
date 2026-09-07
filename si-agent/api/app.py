"""si-agent-api -- central des agents hôtes Linux (livraison #421,
backlog 63). Deux faces :

  - face TABLEAU DE BORD (hub, non signée, même niveau de confiance que
    les autres API de module : LAN + passerelle) : flotte, enrôlement,
    catalogue de plugins, affectations, commandes, mesures, risques ;
  - face AGENTS (signée HMAC, préfixe /api/v1, contrat décrit dans
    si-agent/README.md) : configuration, commandes + acquittement, dépôt
    des mesures.

Le protocole et la validation/signature des plugins sont des COPIES de
si-agent/agent/si_agent/{protocol,plugins}.py (voir Dockerfile) -- jamais
une seconde implémentation ici.
"""
import logging
import os
import shlex
import threading
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    import si_agent_protocol as protocol
except ImportError:  # dépôt de développement
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent", "si_agent"))
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import protocol  # noqa: E402
    import si_agent.plugins as _plugins  # noqa: E402
    _sys.modules.setdefault("si_agent_plugins", _plugins)

import store  # noqa: E402

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    make_shared_log_handler = read_shared_log_buffer = _MemcacheClient = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "si-agent-api")

_log = logging.getLogger("si_agent_api")

DB_PATH = os.environ.get("SI_AGENT_DB_PATH", "/data/si-agent.db")
OFFLINE_AFTER_SECONDS = int(os.environ.get("SI_AGENT_OFFLINE_SECONDS", "300"))
RETENTION_DAYS = int(os.environ.get("SI_AGENT_RETENTION_DAYS", "90"))
PUBLIC_URL = os.environ.get("SI_AGENT_PUBLIC_URL", "").rstrip("/")
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))
SERVICE_NAME = "si-agent-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

store.ensure_schema(DB_PATH)


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


if make_shared_log_handler and _MemcacheClient:
    logging.getLogger().addHandler(make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL))


def _purge_loop():
    while True:
        time.sleep(3600)
        try:
            n = store.purge_measurements(DB_PATH, RETENTION_DAYS)
            if n:
                _log.info("purge : %d mesure(s) au-delà de %d jours", n, RETENTION_DAYS)
        except Exception as exc:  # noqa: BLE001
            _log.warning("purge impossible : %s", exc)


if os.environ.get("SI_AGENT_PURGE_THREAD", "1") == "1":
    threading.Thread(target=_purge_loop, daemon=True).start()


# ============================================================
# Face tableau de bord
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME}), 200


@app.route("/status", methods=["GET"])
def status_route():
    agents = store.fleet(DB_PATH, offline_after_seconds=OFFLINE_AFTER_SECONDS)
    counts = {"online": 0, "offline": 0, "never": 0}
    risk_counts = {"critical": 0, "warning": 0, "info": 0}
    for a in agents:
        counts[a["online"]] = counts.get(a["online"], 0) + 1
        for k, v in (a.get("risks") or {}).get("counts", {}).items():
            risk_counts[k] = risk_counts.get(k, 0) + (v or 0)
    return jsonify({"agents": len(agents), "contact": counts, "risks": risk_counts,
                    "plugins": len(store.list_plugins(DB_PATH)), "offline_after_seconds": OFFLINE_AFTER_SECONDS,
                    "retention_days": RETENTION_DAYS, "public_url": PUBLIC_URL or None}), 200


@app.route("/fleet", methods=["GET"])
def fleet_route():
    return jsonify({"agents": store.fleet(DB_PATH, site=request.args.get("site"), offline_after_seconds=OFFLINE_AFTER_SECONDS)}), 200


@app.route("/risks", methods=["GET"])
def risks_route():
    return jsonify({"risks": store.fleet_risks(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/agents", methods=["GET"])
def list_agents_route():
    return jsonify({"agents": store.list_agents(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/agents", methods=["POST"])
def create_agent_route():
    body = request.get_json(silent=True) or {}
    try:
        created = store.create_agent(DB_PATH, body.get("agent_id", ""), body.get("site", ""), label=body.get("label"),
                                     host_interval_seconds=body.get("host_interval_seconds"),
                                     risk_thresholds=body.get("risk_thresholds"), notes=body.get("notes"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    created["install_command"] = _install_command(created["agent_id"], created["secret"], created["site"])
    return jsonify(created), 201


@app.route("/agents/<agent_id>", methods=["GET"])
def get_agent_route(agent_id):
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    a["latest"] = store.latest_per_task(DB_PATH, agent_id)
    a["plugins"] = store.agent_plugins(DB_PATH, agent_id)
    a["commands"] = store.list_commands(DB_PATH, agent_id, limit=20)
    cfg = store.config_for_agent(DB_PATH, agent_id)
    a["config_version"] = cfg["version"] if cfg else None
    a["config_applied"] = bool(cfg and a.get("last_config_version") == cfg["version"])
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["PUT"])
def update_agent_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        a = store.update_agent(DB_PATH, agent_id, label=body.get("label"), active=body.get("active"), site=body.get("site"),
                               host_interval_seconds=body.get("host_interval_seconds"),
                               risk_thresholds=body.get("risk_thresholds"), notes=body.get("notes"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["DELETE"])
def delete_agent_route(agent_id):
    purge = request.args.get("purge", "false").lower() == "true"
    if not store.delete_agent(DB_PATH, agent_id, purge_measurements=purge):
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"deleted": agent_id, "measurements_purged": purge}), 200


@app.route("/agents/<agent_id>/rotate-secret", methods=["POST"])
def rotate_secret_route(agent_id):
    a = store.rotate_secret(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    a["install_command"] = _install_command(a["agent_id"], a["secret"], a["site"])
    return jsonify(a), 200


def _install_command(agent_id, secret, site):
    central = PUBLIC_URL or "https://<VM>:6443/api/si-agent"
    return "sudo ./install.sh --agent %s --secret %s --central %s --site %s" % (
        shlex.quote(agent_id), shlex.quote(secret), shlex.quote(central), shlex.quote(site or "default"))


@app.route("/agents/<agent_id>/install", methods=["GET"])
def install_route(agent_id):
    """Secret + commande d'installation prête à coller sur l'hôte -- la
    seule lecture qui renvoie le secret (même logique que
    netprobe /provision)."""
    a = store.get_agent(DB_PATH, agent_id, with_secret=True)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "secret": a["secret"], "site": a["site"],
                    "central_url": PUBLIC_URL or None,
                    "install_command": _install_command(agent_id, a["secret"], a["site"]),
                    "agent_json": {"agent_id": agent_id, "secret": a["secret"], "site": a["site"],
                                   "central_url": PUBLIC_URL or "https://<VM>:6443/api/si-agent"}}), 200


@app.route("/agents/<agent_id>/measurements", methods=["GET"])
def agent_measurements_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "measurements": store.list_measurements(
        DB_PATH, agent_id, task=request.args.get("task"), limit=request.args.get("limit", 200, type=int),
        since=request.args.get("since"))}), 200


@app.route("/agents/<agent_id>/latest", methods=["GET"])
def agent_latest_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "latest": store.latest_per_task(DB_PATH, agent_id)}), 200


@app.route("/agents/<agent_id>/config-preview", methods=["GET"])
def config_preview_route(agent_id):
    """Ce que l'agent recevra (sans les corps de scripts ni signatures)."""
    cfg = store.config_for_agent(DB_PATH, agent_id)
    if cfg is None:
        return jsonify({"error": "agent inconnu"}), 404
    cfg["plugins"] = [{k: v for k, v in p["manifest"].items() if k != "signature"} for p in cfg["plugins"]]
    return jsonify(cfg), 200


# -- plugins : catalogue et affectations --------------------------------

@app.route("/plugins", methods=["GET"])
def list_plugins_route():
    return jsonify({"plugins": store.list_plugins(DB_PATH)}), 200


@app.route("/plugins", methods=["POST"])
def create_plugin_route():
    body = request.get_json(silent=True) or {}
    manifest = body.get("manifest") if isinstance(body.get("manifest"), dict) else {
        k: body.get(k) for k in ("id", "version", "runner", "entry", "interval_seconds", "timeout_seconds", "args", "description") if k in body}
    try:
        p = store.upsert_plugin(DB_PATH, manifest, body.get("body"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(p), 201


@app.route("/plugins/<plugin_id>", methods=["GET"])
def get_plugin_route(plugin_id):
    p = store.get_plugin(DB_PATH, plugin_id, with_body=request.args.get("body", "false").lower() == "true")
    if p is None:
        return jsonify({"error": "plugin inconnu"}), 404
    return jsonify(p), 200


@app.route("/plugins/<plugin_id>", methods=["DELETE"])
def delete_plugin_route(plugin_id):
    if not store.delete_plugin(DB_PATH, plugin_id):
        return jsonify({"error": "plugin inconnu"}), 404
    return jsonify({"deleted": plugin_id}), 200


@app.route("/agents/<agent_id>/plugins", methods=["GET"])
def agent_plugins_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "plugins": store.agent_plugins(DB_PATH, agent_id)}), 200


@app.route("/agents/<agent_id>/plugins/<plugin_id>", methods=["PUT"])
def assign_plugin_route(agent_id, plugin_id):
    body = request.get_json(silent=True) or {}
    try:
        res = store.assign_plugin(DB_PATH, agent_id, plugin_id, enabled=body.get("enabled", True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if res is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "plugins": res}), 200


@app.route("/agents/<agent_id>/plugins/<plugin_id>", methods=["DELETE"])
def unassign_plugin_route(agent_id, plugin_id):
    if not store.unassign_plugin(DB_PATH, agent_id, plugin_id):
        return jsonify({"error": "affectation inconnue"}), 404
    return jsonify({"agent_id": agent_id, "plugins": store.agent_plugins(DB_PATH, agent_id)}), 200


# -- commandes -------------------------------------------------------------

@app.route("/agents/<agent_id>/commands", methods=["GET"])
def list_commands_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "commands": store.list_commands(
        DB_PATH, agent_id, status=request.args.get("status"), limit=request.args.get("limit", 50, type=int))}), 200


@app.route("/agents/<agent_id>/commands", methods=["POST"])
def create_command_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        c = store.create_command(DB_PATH, agent_id, body.get("type"), body.get("params"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if c is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify(c), 201


@app.route("/commands/<cid>", methods=["GET"])
def get_command_route(cid):
    c = store.get_command(DB_PATH, cid)
    if c is None:
        return jsonify({"error": "commande inconnue"}), 404
    return jsonify(c), 200


# ============================================================
# Face agents (signée)
# ============================================================

def _signed_path():
    """Chemin tel que l'agent l'a signé : tls-proxy retire `/api/si-agent`,
    l'agent signe `/api/v1/agents/<id>/config` et Flask voit ce chemin."""
    qs = request.query_string.decode("utf-8") if request.query_string else ""
    return request.path + ("?" + qs if qs else "")


def _verify_agent(agent_id):
    header_id = request.headers.get(protocol.HEADER_ID)
    if not header_id:
        return None, "en-tête %s absent" % protocol.HEADER_ID
    if header_id != agent_id:
        return None, "identifiant signataire différent de l'URL"
    info = store.get_secret(DB_PATH, agent_id)
    if info is None:
        return None, "agent inconnu ou désactivé"
    ok, why = protocol.verify(info["secret"], request.method, _signed_path(), request.headers, request.get_data())
    if not ok:
        return None, why
    return info, None


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/config", methods=["GET"])
def agent_config_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    cfg = store.config_for_agent(DB_PATH, agent_id)
    conn = store._connect(DB_PATH)
    try:
        store.touch_agent(conn, agent_id, _client_ip(), config_version=cfg["version"])
        conn.commit()
    finally:
        conn.close()
    return jsonify(cfg), 200


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/commands", methods=["GET"])
def agent_commands_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    conn = store._connect(DB_PATH)
    try:
        store.touch_agent(conn, agent_id, _client_ip())
        conn.commit()
    finally:
        conn.close()
    return jsonify({"commands": store.pending_commands_for_agent(DB_PATH, agent_id)}), 200


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/commands/<cid>/ack", methods=["POST"])
def agent_ack_route(agent_id, cid):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    result = request.get_json(silent=True) or {}
    if not store.ack_command(DB_PATH, agent_id, cid, result):
        return jsonify({"error": "commande inconnue ou déjà acquittée"}), 404
    return jsonify({"acked": cid}), 200


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/measurements", methods=["POST"])
def agent_measurements_ingest_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    body = request.get_json(silent=True) or {}
    items = body.get("measurements")
    if not isinstance(items, list):
        return jsonify({"error": "'measurements' (liste) attendu"}), 400
    if len(items) > 5000:
        return jsonify({"error": "lot trop volumineux (max 5000)"}), 400
    accepted, duplicates, rejected = store.ingest_measurements(DB_PATH, agent_id, items, ip=_client_ip())
    if rejected and not accepted and not duplicates and items:
        return jsonify({"error": "aucune mesure valide", "rejected": rejected[:10]}), 400
    return jsonify({"accepted": accepted, "duplicates": duplicates, "rejected": rejected[:10]}), 201


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
