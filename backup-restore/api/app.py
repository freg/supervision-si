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
