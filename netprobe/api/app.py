"""
netprobe-api -- livraison #295. Voir store.py pour le raisonnement
complet (module séparé de network-agent pour isoler la charge du
sondage actif, fondation = collecteur d'IP + système de contrôle).
"""
import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

import store
import scheduler
import nmap_probe
import iperf3_probe
import tcpdump_probe
import analyzer_engine
import agents_store

# Protocole des sondes distribuées (#405/#406) -- SOURCE CANONIQUE :
# netprobe/agent/netprobe_agent/protocol.py. Le Dockerfile en copie une
# instance sous le nom netprobe_protocol.py ; en développement, on la lit
# directement dans le dépôt. Jamais une seconde implémentation ici.
try:
    import netprobe_protocol as protocol
except ImportError:  # dépôt de développement
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from netprobe_agent import protocol

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "netprobe-api")

_log = logging.getLogger("netprobe_app")

DB_PATH = os.environ.get("NETPROBE_DB_PATH", "/data/netprobe.db")
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/") or None
store.ensure_schema(DB_PATH)
agents_store.ensure_schema(DB_PATH)

# Livraison #297 -- démarre l'ordonnanceur smokeping en thread daemon,
# jamais bloquant au démarrage. Respecte le système de contrôle
# (#295) à chaque tick -- désactivé par défaut, jamais de sondage
# sans configuration explicite.
scheduler.start_background_thread(DB_PATH)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ============================================================
# Collecteur d'IP (point 4)
# ============================================================

@app.route("/targets", methods=["GET"])
def list_targets_route():
    active_only = request.args.get("active_only", "false").strip().lower() == "true"
    return jsonify({"targets": store.list_targets(DB_PATH, active_only=active_only)}), 200


@app.route("/targets", methods=["POST"])
def add_target_route():
    body = request.get_json(silent=True) or {}
    ip_address = (body.get("ip_address") or "").strip()
    if not ip_address:
        return jsonify({"error": "'ip_address' requis"}), 400
    target_id, created = store.add_target(DB_PATH, ip_address, label=body.get("label"), source="manual")
    return jsonify({"status": "ok", "id": target_id, "created": created}), 201 if created else 200


@app.route("/targets/<int:target_id>", methods=["PUT"])
def update_target_route(target_id):
    body = request.get_json(silent=True) or {}
    if "active" not in body:
        return jsonify({"error": "'active' requis"}), 400
    ok = store.set_target_active(DB_PATH, target_id, bool(body["active"]))
    if not ok:
        return jsonify({"error": "cible introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/targets/<int:target_id>", methods=["DELETE"])
def delete_target_route(target_id):
    ok = store.delete_target(DB_PATH, target_id)
    if not ok:
        return jsonify({"error": "cible introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/targets/import-from-network-agent", methods=["POST"])
def import_from_network_agent_route():
    """Best-effort -- network-agent-api indisponible ne doit jamais
    faire échouer bruyamment tout le reste de ce module (même
    raisonnement que backup-restore-api pour ce même service)."""
    if not NETWORK_AGENT_API_URL:
        return jsonify({"error": "NETWORK_AGENT_API_URL non configurée"}), 502
    try:
        resp = requests.get(f"{NETWORK_AGENT_API_URL}/devices", timeout=15)
    except requests.RequestException as exc:
        _log.debug("import_from_network_agent_route : network-agent-api injoignable -- %s", exc)
        return jsonify({"error": f"network-agent-api injoignable : {exc}"}), 502
    if resp.status_code != 200:
        return jsonify({"error": f"network-agent-api a répondu {resp.status_code}"}), 502
    try:
        devices = resp.json()
    except ValueError:
        snippet = (resp.text or "").strip()[:300]
        return jsonify({"error": f"réponse de network-agent-api illisible : {snippet!r}"}), 502
    if not isinstance(devices, list):
        return jsonify({"error": "réponse de network-agent-api inattendue (liste attendue)"}), 502
    result = store.import_targets_from_network_agent(DB_PATH, devices)
    return jsonify({"status": "ok", **result}), 200


# ============================================================
# Système de contrôle (point 6)
# ============================================================

@app.route("/probe-config", methods=["GET"])
def list_probe_config_route():
    probe_type = request.args.get("probe_type")
    if probe_type and probe_type not in store.PROBE_TYPES:
        return jsonify({"error": f"probe_type invalide (attendu : {', '.join(store.PROBE_TYPES)})"}), 400
    return jsonify({"configs": store.list_probe_configs(DB_PATH, probe_type)}), 200


@app.route("/probe-config/effective", methods=["GET"])
def get_effective_config_route():
    probe_type = request.args.get("probe_type")
    if not probe_type or probe_type not in store.PROBE_TYPES:
        return jsonify({"error": f"'probe_type' requis (attendu : {', '.join(store.PROBE_TYPES)})"}), 400
    target_id = request.args.get("target_id", type=int)
    return jsonify(store.get_effective_config(DB_PATH, probe_type, target_id=target_id)), 200


@app.route("/probe-config", methods=["POST"])
def set_probe_config_route():
    body = request.get_json(silent=True) or {}
    probe_type = body.get("probe_type")
    if probe_type not in store.PROBE_TYPES:
        return jsonify({"error": f"probe_type invalide (attendu : {', '.join(store.PROBE_TYPES)})"}), 400
    if "enabled" not in body:
        return jsonify({"error": "'enabled' requis"}), 400
    try:
        store.set_probe_config(
            DB_PATH, probe_type, bool(body["enabled"]),
            frequency_seconds=body.get("frequency_seconds"),
            schedule_start_hour=body.get("schedule_start_hour"),
            schedule_end_hour=body.get("schedule_end_hour"),
            target_id=body.get("target_id"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok"}), 200


@app.route("/probe-config/<int:config_id>", methods=["PUT"])
def update_probe_config_route(config_id):
    """Bascule RAPIDE activé/désactivé -- jamais besoin de
    resoumettre fréquence/fenêtre/cible pour ce seul champ (voir
    livraison #306, demandé explicitement -- "suspendre" une
    sonde)."""
    body = request.get_json(silent=True) or {}
    if "enabled" not in body:
        return jsonify({"error": "'enabled' requis"}), 400
    ok = store.set_probe_config_enabled(DB_PATH, config_id, bool(body["enabled"]))
    if not ok:
        return jsonify({"error": "configuration introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/probe-config/<int:config_id>", methods=["DELETE"])
def delete_probe_config_route(config_id):
    ok = store.delete_probe_config(DB_PATH, config_id)
    if not ok:
        return jsonify({"error": "configuration introuvable"}), 404
    return jsonify({"status": "ok"}), 200


# ============================================================
# Smokeping (volet 1 de la demande, livraison #297)
# ============================================================

@app.route("/smokeping/samples", methods=["GET"])
def list_samples_route():
    target_id = request.args.get("target_id", type=int)
    if not target_id:
        return jsonify({"error": "'target_id' requis"}), 400
    limit = request.args.get("limit", default=100, type=int)
    return jsonify({"samples": store.list_samples(DB_PATH, target_id, limit=limit)}), 200


@app.route("/smokeping/latest", methods=["GET"])
def latest_samples_route():
    """Vue d'ensemble -- un échantillon par cible, le plus récent."""
    return jsonify({"latest": store.latest_sample_per_target(DB_PATH)}), 200


# ============================================================
# nmap à la demande (volet 2, livraison #302)
# ============================================================

@app.route("/nmap/scan", methods=["POST"])
def nmap_scan_route():
    """SYNCHRONE -- geste EXPLICITE de la personne (voir docstring de
    nmap_probe.py, jamais programmé automatiquement), l'appelant
    attend le résultat. Peut prendre jusqu'à
    nmap_probe.DEFAULT_TIMEOUT_SECONDS (120s par défaut) -- assumé,
    pas de file d'attente asynchrone pour ce premier volet."""
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"error": "'target_id' requis"}), 400
    targets = {t["id"]: t for t in store.list_targets(DB_PATH)}
    target = targets.get(target_id)
    if target is None:
        return jsonify({"error": "cible introuvable"}), 404

    result = nmap_probe.scan_target(target["ip_address"], ports=body.get("ports"))
    store.record_nmap_scan(
        DB_PATH, target_id, success=result["success"], open_ports=result["open_ports"],
        scan_duration_seconds=result["scan_duration_seconds"], error=result["error"],
    )
    return jsonify(result), 200


@app.route("/nmap/scans", methods=["GET"])
def list_nmap_scans_route():
    target_id = request.args.get("target_id", type=int)
    if not target_id:
        return jsonify({"error": "'target_id' requis"}), 400
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"scans": store.list_nmap_scans(DB_PATH, target_id, limit=limit)}), 200


# ============================================================
# Débit réel à la demande (backlog item 47 reformulé 2026-09-05,
# livraison #385) -- "couche expérience client" SANS matériel RF.
# ============================================================

@app.route("/iperf3/test", methods=["POST"])
def iperf3_test_route():
    """SYNCHRONE -- geste EXPLICITE de la personne, jamais programmé
    automatiquement (voir docstring de iperf3_probe.py -- un test
    consomme de la vraie bande passante pendant plusieurs secondes,
    contrairement à un ping unique). La CIBLE doit être un serveur
    iperf3 DÉJÀ EN ÉCOUTE (`iperf3 -s`), enregistré comme n'importe
    quel autre target de ce module -- réutilise le système de cibles
    existant plutôt que d'en inventer un second."""
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"error": "'target_id' requis"}), 400
    targets = {t["id"]: t for t in store.list_targets(DB_PATH)}
    target = targets.get(target_id)
    if target is None:
        return jsonify({"error": "cible introuvable"}), 404

    port = int(body.get("port") or 5201)
    duration_raw = body.get("duration_seconds")
    duration_seconds = int(duration_raw) if duration_raw is not None else 5
    if duration_seconds < 1 or duration_seconds > 30:
        return jsonify({"error": "'duration_seconds' doit être entre 1 et 30 secondes"}), 400

    result = iperf3_probe.iperf3_throughput(target["ip_address"], port=port, duration_seconds=duration_seconds)
    store.record_iperf3_test(
        DB_PATH, target_id, success=result["success"], sent_mbps=result["sent_mbps"],
        received_mbps=result["received_mbps"], retransmits=result["retransmits"], error=result["error"],
    )
    return jsonify(result), 200


@app.route("/iperf3/tests", methods=["GET"])
def list_iperf3_tests_route():
    target_id = request.args.get("target_id", type=int)
    if not target_id:
        return jsonify({"error": "'target_id' requis"}), 400
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"tests": store.list_iperf3_tests(DB_PATH, target_id, limit=limit)}), 200


# ============================================================
# tcpdump partagé, sans stockage (volet 3, livraison #305)
# ============================================================

@app.route("/tcpdump/capture", methods=["POST"])
def tcpdump_capture_route():
    """SANS STOCKAGE, VOLONTAIREMENT (voir docstring de
    tcpdump_probe.py) -- le résultat est renvoyé, jamais persisté en
    base. SYNCHRONE, geste EXPLICITE -- peut prendre jusqu'à
    `timeout_seconds` (30s par défaut) sur une interface calme."""
    body = request.get_json(silent=True) or {}
    interface = body.get("interface")
    packet_count = body.get("packet_count", tcpdump_probe.DEFAULT_PACKET_COUNT)
    timeout_seconds = body.get("timeout_seconds", tcpdump_probe.DEFAULT_TIMEOUT_SECONDS)
    try:
        packet_count = int(packet_count)
        timeout_seconds = int(timeout_seconds)
    except (TypeError, ValueError):
        return jsonify({"error": "'packet_count' et 'timeout_seconds' doivent être des entiers"}), 400

    result = tcpdump_probe.capture(interface=interface, packet_count=packet_count, timeout_seconds=timeout_seconds)
    return jsonify(result), 200


# ============================================================
# Analyseur multi-scripts (volet 4, livraison #307)
# ============================================================

@app.route("/analysis/results", methods=["GET"])
def list_analysis_results_route():
    target_id = request.args.get("target_id", type=int)
    analyzer_name = request.args.get("analyzer_name")
    limit = request.args.get("limit", default=100, type=int)
    return jsonify({"results": store.list_analysis_results(DB_PATH, target_id=target_id, analyzer_name=analyzer_name, limit=limit)}), 200


@app.route("/analysis/run", methods=["POST"])
def run_analysis_route():
    """Geste EXPLICITE -- lance tout ou un analyseur nommé
    immédiatement, sans attendre le prochain tick programmé (utile
    pour tester une configuration ou obtenir un constat à jour tout
    de suite)."""
    body = request.get_json(silent=True) or {}
    analyzer_name = body.get("analyzer_name")
    if analyzer_name:
        count = analyzer_engine.run_analyzer(DB_PATH, analyzer_name)
        if count is None:
            return jsonify({"error": f"analyseur inconnu (disponibles : {', '.join(analyzer_engine.ANALYZERS)})"}), 400
        return jsonify({"status": "ok", "results": {analyzer_name: count}}), 200
    return jsonify({"status": "ok", "results": analyzer_engine.run_all_analyzers(DB_PATH)}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# Manquait ici jusqu'à cette livraison (#351, backlog item 8) --
# trouvé en vérifiant que memory-api archive réellement TOUS les
# services du projet.
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


SERVICE_NAME = "netprobe-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler and _MemcacheClient:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)


# ============================================================
# Sondes distribuées (livraison #406, items 45/47/48) -- flotte de
# sondes/collecteurs Raspberry Pi et mesures remontées. Voir
# netprobe/agent/README.md pour l'architecture et agents_store.py pour
# le stockage.
# ============================================================

def _signed_path():
    """Chemin tel que l'appareil l'a signé : tls-proxy retire le préfixe
    `/api/netprobe` (rewrite explicite, voir render_nginx_conf.py), donc
    l'appareil signe `/fleet?site=x` et Flask voit `/fleet` + query."""
    qs = request.query_string.decode("utf-8") if request.query_string else ""
    return request.path + ("?" + qs if qs else "")


def _verify_device(expected_roles):
    """Authentifie l'appareil signataire ; renvoie (device|None, erreur)."""
    device_id = request.headers.get(protocol.HEADER_ID)
    if not device_id:
        return None, "en-tête %s absent" % protocol.HEADER_ID
    info = agents_store.get_secret(DB_PATH, device_id)
    if info is None:
        return None, "appareil inconnu ou inactif"
    if info["role"] not in expected_roles:
        return None, "rôle %s non autorisé ici" % info["role"]
    ok, why = protocol.verify(info["secret"], request.method, _signed_path(), request.headers, request.get_data())
    if not ok:
        return None, why
    info["id"] = device_id
    return info, None


@app.route("/agents", methods=["GET"])
def list_agents_route():
    return jsonify({"agents": agents_store.list_agents(DB_PATH, site=request.args.get("site"), role=request.args.get("role"))}), 200


@app.route("/agents", methods=["POST"])
def create_agent_route():
    body = request.get_json(silent=True) or {}
    try:
        created = agents_store.create_agent(DB_PATH, body.get("agent_id", ""), body.get("site", ""), body.get("role", "probe"),
                                            label=body.get("label"), tasks=body.get("tasks"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    # Le secret n'est renvoyé QU'ICI (et par rotate-secret/provision) --
    # c'est le moment de le mettre dans la configuration de l'image.
    return jsonify(created), 201


@app.route("/agents/latest", methods=["GET"])
def agents_latest_route():
    return jsonify({"latest": agents_store.latest_per_agent_task(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/agents/<agent_id>", methods=["GET"])
def get_agent_route(agent_id):
    a = agents_store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "sonde inconnue"}), 404
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["PUT"])
def update_agent_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        a = agents_store.update_agent(DB_PATH, agent_id, label=body.get("label"), active=body.get("active"),
                                      tasks=body.get("tasks"), site=body.get("site"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if a is None:
        return jsonify({"error": "sonde inconnue"}), 404
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["DELETE"])
def delete_agent_route(agent_id):
    purge = request.args.get("purge", "false").lower() == "true"
    if not agents_store.delete_agent(DB_PATH, agent_id, purge_measurements=purge):
        return jsonify({"error": "sonde inconnue"}), 404
    return jsonify({"deleted": agent_id, "measurements_purged": purge}), 200


@app.route("/agents/<agent_id>/rotate-secret", methods=["POST"])
def rotate_secret_route(agent_id):
    a = agents_store.rotate_secret(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "sonde inconnue"}), 404
    return jsonify(a), 200


@app.route("/agents/<agent_id>/provision", methods=["GET"])
def provision_route(agent_id):
    """Configuration PRÊTE À ÉCRIRE dans l'image (agent.json ou
    collector.json), secret compris -- consommée par
    netprobe/agent/image/build-image.sh. `collector_url` / `central_url`
    sont à fournir en paramètres de requête (ils dépendent du site)."""
    a = agents_store.get_agent(DB_PATH, agent_id, with_secret=True)
    if a is None:
        return jsonify({"error": "sonde inconnue"}), 404
    if a["role"] == "probe":
        cfg = {"agent_id": a["agent_id"], "secret": a["secret"], "site": a["site"], "role": "probe",
               "collector_url": request.args.get("collector_url", ""), "interface": request.args.get("interface", "wlan0"),
               "default_tasks": a["tasks"] or None}
        if cfg["default_tasks"] is None:
            cfg.pop("default_tasks")
    else:
        cfg = {"collector_id": a["agent_id"], "secret": a["secret"], "site": a["site"],
               "central_url": request.args.get("central_url", ""), "port": 6127}
    return jsonify(cfg), 200


@app.route("/fleet", methods=["GET"])
def fleet_route():
    """Flotte d'un site pour son COLLECTEUR (signé) : sondes actives du
    site avec secrets et tâches. Un collecteur ne voit que SON site."""
    device, err = _verify_device(("collector",))
    if device is None:
        return jsonify({"error": err}), 401
    site = request.args.get("site") or device["site"]
    if site != device["site"]:
        return jsonify({"error": "site %s : hors du périmètre de ce collecteur" % site}), 403
    return jsonify(agents_store.fleet_for_site(DB_PATH, site)), 200


@app.route("/agents/measurements/bulk", methods=["POST"])
def ingest_measurements_route():
    """Lot de mesures, signé par un collecteur (mesures de ses sondes) ou
    par une sonde parlant directement au central (ses mesures seulement)."""
    device, err = _verify_device(("collector", "probe"))
    if device is None:
        return jsonify({"error": err}), 401
    body = request.get_json(silent=True) or {}
    items = body.get("measurements")
    if not isinstance(items, list):
        return jsonify({"error": "'measurements' (liste) attendu"}), 400
    if len(items) > 5000:
        return jsonify({"error": "lot trop volumineux (max 5000)"}), 400
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if device["role"] == "collector":
        accepted, duplicates, rejected = agents_store.ingest_measurements(
            DB_PATH, items, via=device["id"], ip=ip, site=device["site"])
        # Le collecteur lui-même est vu, même si le lot est vide
        conn = agents_store._connect(DB_PATH)
        try:
            agents_store.touch_agent(conn, device["id"], "direct", ip); conn.commit()
        finally:
            conn.close()
    else:
        accepted, duplicates, rejected = agents_store.ingest_measurements(
            DB_PATH, items, via="direct", ip=ip, only_agent=device["id"])
    if rejected and not accepted and not duplicates and items:
        return jsonify({"error": "aucune mesure valide", "rejected": rejected[:10]}), 400
    return jsonify({"accepted": accepted, "duplicates": duplicates, "rejected": rejected[:10]}), 200


@app.route("/agents/<agent_id>/measurements", methods=["GET"])
def agent_measurements_route(agent_id):
    if agents_store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "sonde inconnue"}), 404
    limit = request.args.get("limit", 200, type=int)
    return jsonify({"agent_id": agent_id, "measurements": agents_store.list_measurements(
        DB_PATH, agent_id, task=request.args.get("task"), limit=limit, since=request.args.get("since"))}), 200


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
