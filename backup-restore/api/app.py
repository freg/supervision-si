"""
backup-restore-api -- livraison #249, backlog item 27
("backup-restore"), sous-volet marqué URGENT par la personne. Voir
`store.py` pour le détail complet de la portée (suivi/couverture,
PAS l'automatisation réelle de Clonezilla -- hors de portée sans
infrastructure matérielle réelle à tester).
"""
import logging
import os

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
    register_version_route(app, "backup-restore-api")

_log = logging.getLogger("backup_restore_app")

DB_PATH = os.environ.get("BACKUP_RESTORE_DB_PATH", "/data/backup-restore.db")
store.ensure_schema(DB_PATH)

# Branchement rights-api -- livraison #309, item 38 du backlog.
# Service de SUIVI de couverture uniquement (voir docstring en tête
# de fichier -- jamais l'automatisation réelle de Clonezilla/
# BackupPC) -- mais falsifier ou supprimer un enregistrement de
# sauvegarde pourrait masquer un vrai trou de couverture (créer un
# enregistrement pour prétendre qu'une sauvegarde existe, ou en
# supprimer un pour cacher qu'elle a échoué). Gardé sur les deux
# routes d'ÉCRITURE (create_image, delete_image) uniquement -- /coverage
# et /logs restent en lecture libre, même motif que partout ailleurs
# dans ce projet.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308) -- jamais fail-open, y compris pour admin_hub
    si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "backup-restore-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur backup-restore-api requis (groupe admin_hub, ou un octroi explicite)"

# **Joindre network-agent-api** (livraison #249) -- ⚠️ ce service
# tourne en `network_mode: host` (#238-239, confirmé nécessaire en
# déploiement réel) : il n'est PLUS sur le réseau Docker partagé,
# don le nom de service Docker habituel (`http://network-agent-api:5000`)
# NE RÉSOUT PAS depuis un autre conteneur normal comme celui-ci --
# MÊME piège que pour la passerelle nginx, déjà rencontré et corrigé.
# Valeur par défaut construite avec HOST_IP (voir docker-compose.yml)
# -- jamais le nom de service Docker par défaut ici, contrairement à
# tous les AUTRES appels inter-services de ce projet.
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")

VALID_TOOLS = {"clonezilla", "backuppc", "other"}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/images", methods=["GET"])
def list_images():
    device_mac = request.args.get("device_mac")
    return jsonify(store.list_images(DB_PATH, device_mac=device_mac)), 200


@app.route("/images", methods=["POST"])
def create_image():
    """Corps : {"device_label" (requis), "tool" (requis, voir
    VALID_TOOLS), "taken_at" (requis, ISO 8601), "device_mac"
    (optionnel -- pour le rapprochement avec network-agent),
    "image_type", "storage_path", "size_bytes", "notes"
    (optionnels), "groups" (pour rights-api, voir #309).

    Protégée par rights-api (#309) -- créer un faux enregistrement
    pourrait faire croire à une couverture de sauvegarde inexistante."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    device_label = (body.get("device_label") or "").strip()
    tool = (body.get("tool") or "").strip()
    taken_at = (body.get("taken_at") or "").strip()
    if not device_label or not tool or not taken_at:
        return jsonify({"error": "'device_label', 'tool' et 'taken_at' sont requis"}), 400
    if tool not in VALID_TOOLS:
        return jsonify({"error": f"'tool' doit être l'un de {sorted(VALID_TOOLS)}"}), 400
    new_id = store.create_image(
        DB_PATH,
        device_mac=body.get("device_mac"),
        device_label=device_label,
        tool=tool,
        taken_at=taken_at,
        image_type=body.get("image_type"),
        storage_path=body.get("storage_path"),
        size_bytes=body.get("size_bytes"),
        notes=body.get("notes"),
    )
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/images/<int:image_id>", methods=["DELETE"])
def delete_image(image_id):
    """Protégée par rights-api (#309) -- supprimer un enregistrement
    pourrait masquer qu'une sauvegarde a échoué ou n'existe plus."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_image(DB_PATH, image_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


def _fetch_network_agent_devices():
    """Renvoie (devices, error) -- l'un des deux est toujours None.
    BEST-EFFORT explicite : network-agent-api peut être indisponible
    (pas encore déployé, en panne, mauvaise config de
    NETWORK_AGENT_API_URL) sans que /coverage ne devienne inutilisable
    pour autant -- l'erreur est renvoyée clairement à la personne
    plutôt qu'un 500 nu."""
    if not NETWORK_AGENT_API_URL:
        return None, "NETWORK_AGENT_API_URL non configurée côté backup-restore-api"
    try:
        resp = requests.get(f"{NETWORK_AGENT_API_URL}/devices", timeout=10)
    except requests.RequestException as exc:
        return None, f"impossible de joindre network-agent-api : {exc}"
    if resp.status_code != 200:
        return None, f"network-agent-api a répondu {resp.status_code}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "réponse de network-agent-api illisible (pas du JSON valide)"


@app.route("/coverage", methods=["GET"])
def coverage():
    """Répond à l'exigence explicite du backlog : "toute machine
    détectée doit avoir une image prête à la restauration". Croise
    les appareils DÉCOUVERTS par network-agent avec le registre local
    des images connues (par adresse MAC) -- renvoie, PAR APPAREIL,
    s'il a une image, sa date, et depuis combien de jours (jamais
    calculé côté client -- une seule source de vérité pour "aujourd'hui",
    celle du serveur).

    ⚠️ Couverture nécessairement PARTIELLE et honnêtement signalée
    comme telle : une machine SANS trafic réseau récent (éteinte,
    débranchée du LAN surveillé) n'apparaît PAS dans network-agent,
    donc pas ici non plus -- ce n'est PAS un inventaire exhaustif du
    parc, seulement des machines ACTIVEMENT vues sur le réseau
    surveillé."""
    devices, agent_error = _fetch_network_agent_devices()
    if agent_error:
        return jsonify({"error": agent_error}), 502

    latest_by_mac = store.most_recent_by_mac(DB_PATH)
    now = store.now_iso()

    result = []
    for device in devices:
        mac = (device.get("mac_address") or "").lower().strip()
        image = latest_by_mac.get(mac)
        entry = {
            "mac_address": device.get("mac_address"),
            "ip_address": device.get("ip_address"),
            "role_hint": device.get("role_hint"),
            "network_last_seen": device.get("last_seen"),
            "has_backup": image is not None,
            "last_backup_at": image["taken_at"] if image else None,
            "last_backup_tool": image["tool"] if image else None,
        }
        if image:
            entry["days_since_backup"] = _days_between(image["taken_at"], now)
        else:
            entry["days_since_backup"] = None
        result.append(entry)

    # Machines SANS COUVERTURE en tête -- c'est la question que pose
    # le backlog ("toute machine doit avoir une image"), jamais une
    # liste neutre que la personne devrait retrier elle-même.
    result.sort(key=lambda e: (e["has_backup"], -(e["days_since_backup"] or 0)))
    return jsonify({"devices": result, "total": len(result), "without_backup": sum(1 for e in result if not e["has_backup"])}), 200


def _days_between(iso_a, iso_b):
    """Nombre de jours (entier, arrondi vers le bas) entre deux
    horodatages ISO 8601 UTC (format `now_iso()`, voir store.py) --
    jamais une exception sur un format inattendu, repli sur `None`
    plutôt qu'un calcul faux affiché avec assurance."""
    import datetime
    try:
        dt_a = datetime.datetime.strptime(iso_a, "%Y-%m-%dT%H:%M:%SZ")
        dt_b = datetime.datetime.strptime(iso_b, "%Y-%m-%dT%H:%M:%SZ")
        return (dt_b - dt_a).days
    except (ValueError, TypeError):
        return None


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


SERVICE_NAME = "backup-restore-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler and _MemcacheClient:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

# ===================================================================
# Routes livraison #270 -- Connecteurs BackupPC, Clonezilla, Restic
# ===================================================================

CONNECTOR_TYPES = {"backuppc", "clonezilla", "restic"}


@app.route("/connectors", methods=["GET"])
def list_connectors():
    """Liste les configurations de connecteurs."""
    connector_type = request.args.get("type")
    return jsonify(store.list_connector_configs(DB_PATH, connector_type=connector_type)), 200


@app.route("/connectors", methods=["POST"])
def create_connector():
    """Crée une configuration de connecteur."""
    body = request.get_json(silent=True) or {}
    connector_type = (body.get("connector_type") or "").strip()
    name = (body.get("name") or "").strip()
    if not connector_type or not name:
        return jsonify({"error": "'connector_type' et 'name' sont requis"}), 400
    if connector_type not in CONNECTOR_TYPES:
        return jsonify({"error": f"'connector_type' doit être l'un de {sorted(CONNECTOR_TYPES)}"}), 400
    new_id = store.create_connector_config(
        DB_PATH,
        connector_type=connector_type,
        name=name,
        url=body.get("url"),
        config_json=body.get("config_json"),
    )
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/connectors/<int:config_id>", methods=["DELETE"])
def delete_connector(config_id):
    """Supprime une configuration de connecteur."""
    deleted = store.delete_connector_config(DB_PATH, config_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


@app.route("/jobs", methods=["GET"])
def list_all_jobs():
    """Liste les jobs de sauvegarde."""
    connector_type = request.args.get("connector_type")
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(store.list_jobs(DB_PATH, connector_type=connector_type, status=status, limit=limit)), 200


@app.route("/jobs", methods=["POST"])
def create_new_job():
    """Crée un nouveau job de sauvegarde."""
    body = request.get_json(silent=True) or {}
    connector_type = (body.get("connector_type") or "").strip()
    job_type = (body.get("job_type") or "").strip()
    if not connector_type or not job_type:
        return jsonify({"error": "'connector_type' et 'job_type' sont requis"}), 400
    if connector_type not in CONNECTOR_TYPES:
        return jsonify({"error": f"'connector_type' doit être l'un de {sorted(CONNECTOR_TYPES)}"}), 400
    new_id = store.create_job(
        DB_PATH,
        connector_type=connector_type,
        job_type=job_type,
        connector_id=body.get("connector_id"),
        device=body.get("device"),
        image_name=body.get("image_name"),
        snapshot_id=body.get("snapshot_id"),
        target_path=body.get("target_path"),
    )
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/jobs/<int:job_id>", methods=["GET"])
def get_job_detail(job_id):
    """Récupère les détails d'un job."""
    job = store.get_job(DB_PATH, job_id)
    if not job:
        return jsonify({"error": "Job non trouvé"}), 404
    return jsonify(job), 200


@app.route("/jobs/<int:job_id>/status", methods=["PATCH"])
def update_job(job_id):
    """Met à jour le statut d'un job."""
    body = request.get_json(silent=True) or {}
    status = (body.get("status") or "").strip()
    if not status:
        return jsonify({"error": "'status' est requis"}), 400
    updated = store.update_job_status(
        DB_PATH,
        job_id,
        status=status,
        progress_percent=body.get("progress_percent"),
        error_message=body.get("error_message"),
    )
    return jsonify({"status": "ok", "updated": updated}), 200


@app.route("/schedules", methods=["GET"])
def list_all_schedules():
    """Liste les planifications."""
    connector_type = request.args.get("connector_type")
    return jsonify(store.list_schedules(DB_PATH, connector_type=connector_type)), 200


@app.route("/schedules", methods=["POST"])
def create_new_schedule():
    """Crée une planification."""
    body = request.get_json(silent=True) or {}
    connector_type = (body.get("connector_type") or "").strip()
    name = (body.get("name") or "").strip()
    cron_expression = (body.get("cron_expression") or "").strip()
    if not connector_type or not name or not cron_expression:
        return jsonify({"error": "'connector_type', 'name' et 'cron_expression' sont requis"}), 400
    if connector_type not in CONNECTOR_TYPES:
        return jsonify({"error": f"'connector_type' doit être l'un de {sorted(CONNECTOR_TYPES)}"}), 400
    new_id = store.create_schedule(
        DB_PATH,
        connector_type=connector_type,
        name=name,
        cron_expression=cron_expression,
        connector_id=body.get("connector_id"),
        config_json=body.get("config_json"),
    )
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/schedules/<int:schedule_id>", methods=["DELETE"])
def delete_schedule_route(schedule_id):
    """Supprime une planification."""
    deleted = store.delete_schedule(DB_PATH, schedule_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


@app.route("/file-versions", methods=["GET"])
def list_all_file_versions():
    """Liste les versions de fichiers."""
    host = request.args.get("host")
    file_path = request.args.get("file_path")
    connector_type = request.args.get("connector_type")
    limit = request.args.get("limit", 20, type=int)
    if host and file_path:
        return jsonify(store.list_file_versions(DB_PATH, host=host, file_path=file_path, limit=limit)), 200
    return jsonify(store.get_hosts_with_versions(DB_PATH, connector_type=connector_type)), 200


@app.route("/file-versions", methods=["POST"])
def add_new_file_version():
    """Ajoute une version de fichier."""
    body = request.get_json(silent=True) or {}
    connector_type = (body.get("connector_type") or "").strip()
    host = (body.get("host") or "").strip()
    file_path = (body.get("file_path") or "").strip()
    version_number = body.get("version_number")
    if not connector_type or not host or not file_path or version_number is None:
        return jsonify({"error": "'connector_type', 'host', 'file_path' et 'version_number' sont requis"}), 400
    new_id = store.add_file_version(
        DB_PATH,
        connector_type=connector_type,
        host=host,
        file_path=file_path,
        version_number=version_number,
        snapshot_id=body.get("snapshot_id"),
        size_bytes=body.get("size_bytes"),
        modified_at=body.get("modified_at"),
        hash=body.get("hash"),
    )
    return jsonify({"status": "ok", "id": new_id}), 201


# --- Routes spécifiques aux connecteurs (données simulées/réelles) ---

@app.route("/backuppc/hosts", methods=["GET"])
def backuppc_hosts():
    """Liste les hôtes BackupPC (via le connecteur)."""
    from connectors.backuppc import get_connector
    connector = get_connector()
    return jsonify({"hosts": connector.get_hosts()}), 200


@app.route("/backuppc/hosts/<host>/versions", methods=["GET"])
def backuppc_host_versions(host):
    """Liste les versions d'un hôte BackupPC."""
    from connectors.backuppc import get_connector
    connector = get_connector()
    return jsonify({"host": host, "versions": connector.get_host_versions(host)}), 200


@app.route("/backuppc/hosts/<host>/content", methods=["GET"])
def backuppc_host_content(host):
    """Liste le contenu d'une sauvegarde BackupPC."""
    from connectors.backuppc import get_connector
    connector = get_connector()
    version = request.args.get("version", type=int)
    return jsonify(connector.get_host_content(host, version=version)), 200


@app.route("/backuppc/pool/stats", methods=["GET"])
def backuppc_pool_stats():
    """Statistiques du pool BackupPC."""
    from connectors.backuppc import get_connector
    connector = get_connector()
    return jsonify(connector.get_pool_stats()), 200


@app.route("/clonezilla/images", methods=["GET"])
def clonezilla_images():
    """Liste les images Clonezilla."""
    from connectors.clonezilla import get_connector
    connector = get_connector()
    return jsonify({"images": connector.get_images()}), 200


@app.route("/clonezilla/jobs", methods=["GET"])
def clonezilla_jobs():
    """Liste les jobs Clonezilla."""
    from connectors.clonezilla import get_connector
    connector = get_connector()
    status = request.args.get("status")
    return jsonify({"jobs": connector.get_jobs(status=status)}), 200


@app.route("/clonezilla/jobs", methods=["POST"])
def clonezilla_create_job():
    """Crée un job Clonezilla."""
    from connectors.clonezilla import get_connector
    connector = get_connector()
    body = request.get_json(silent=True) or {}
    job_type = body.get("type", "save")
    if job_type == "save":
        result = connector.trigger_save(body.get("device"), body.get("image_name"), body.get("method", "partclone"))
    elif job_type == "restore":
        result = connector.trigger_restore(body.get("image_name"), body.get("device"))
    else:
        return jsonify({"error": "Type de job invalide"}), 400
    return jsonify(result), 201


@app.route("/clonezilla/pxe-config", methods=["GET"])
def clonezilla_pxe_config():
    """Configuration PXE Clonezilla."""
    from connectors.clonezilla import get_connector
    connector = get_connector()
    return jsonify(connector.get_pxe_config()), 200


@app.route("/restic/snapshots", methods=["GET"])
def restic_snapshots():
    """Liste les snapshots Restic."""
    from connectors.restic import get_connector
    connector = get_connector()
    return jsonify({"snapshots": connector.get_snapshots()}), 200


@app.route("/restic/snapshots/<snapshot_id>/content", methods=["GET"])
def restic_snapshot_content(snapshot_id):
    """Contenu d'un snapshot Restic."""
    from connectors.restic import get_connector
    connector = get_connector()
    path = request.args.get("path", "/")
    return jsonify(connector.get_snapshot_content(snapshot_id, path=path)), 200


@app.route("/restic/stats", methods=["GET"])
def restic_stats():
    """Statistiques du dépôt Restic."""
    from connectors.restic import get_connector
    connector = get_connector()
    return jsonify(connector.get_stats()), 200


@app.route("/restic/restore", methods=["POST"])
def restic_restore():
    """Déclenche une restauration Restic."""
    from connectors.restic import get_connector
    connector = get_connector()
    body = request.get_json(silent=True) or {}
    result = connector.restore(
        snapshot_id=body.get("snapshot_id"),
        target_path=body.get("target_path"),
        includes=body.get("includes"),
        excludes=body.get("excludes"),
    )
    return jsonify(result), 200 if result.get("status") == "ok" else 400


@app.route("/restic/forget", methods=["POST"])
def restic_forget():
    """Applique la politique de rétention Restic."""
    from connectors.restic import get_connector
    connector = get_connector()
    body = request.get_json(silent=True) or {}
    result = connector.forget(body)
    return jsonify(result), 200 if result.get("status") == "ok" else 400


@app.route("/restic/check", methods=["GET"])
def restic_check():
    """Vérifie l'intégrité du dépôt Restic."""
    from connectors.restic import get_connector
    connector = get_connector()
    return jsonify(connector.check()), 200
