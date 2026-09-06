"""
rights-api -- livraison #283. Voir store.py pour le raisonnement
complet (court-circuit admin_hub, refus par défaut, jamais de
contenu de fichier exposé).

Modèle de confiance : ce service reçoit la liste des GROUPES de
l'appelant directement dans la requête (jamais un jeton à décoder
lui-même) -- même motif que le reste de ce projet, où les services
internes se font confiance sur le réseau Docker interne, derrière
Keycloak/tls-proxy en frontal (aucun de ces ~40 services ne vérifie
de jeton lui-même aujourd'hui). Le hub, authentifié via OIDC,
transmet les groupes déjà présents dans le jeton de l'utilisateur.
"""
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

import store
import file_inventory

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "rights-api")

DB_PATH = os.environ.get("RIGHTS_DB_PATH", "/data/rights.db")
PROJECT_ROOT = os.environ.get("RIGHTS_PROJECT_ROOT", "/project")
store.ensure_schema(DB_PATH)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def _require_admin(body):
    """Garde commune à toute route de GESTION des droits -- seul
    admin_hub peut octroyer/révoquer (demandé explicitement :
    "notamment celui de gérer les droits"). `groups` transmis dans
    le corps de la requête, même convention que /check."""
    groups = body.get("groups") or []
    return store.ADMIN_GROUP in groups


@app.route("/check", methods=["POST"])
def check_permission():
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or []
    resource_type = body.get("resource_type")
    resource_id = body.get("resource_id")
    action = body.get("action")
    if not resource_type or not action:
        return jsonify({"error": "'resource_type' et 'action' requis"}), 400
    allowed = store.has_permission(DB_PATH, groups, resource_type, resource_id, action)
    return jsonify({"allowed": allowed}), 200


@app.route("/filter", methods=["POST"])
def filter_items():
    """Filtre une liste d'items selon la visibilité -- le CŒUR de
    "une gestion de droit incluant la visibilité en listing"."""
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or []
    resource_type = body.get("resource_type")
    items = body.get("items")
    action = body.get("action", "view")
    id_key = body.get("id_key", "identifier")
    if not resource_type or not isinstance(items, list):
        return jsonify({"error": "'resource_type' et 'items' (liste) requis"}), 400
    visible = store.filter_visible(DB_PATH, groups, resource_type, items, action=action, id_key=id_key)
    return jsonify({"items": visible}), 200


@app.route("/permissions", methods=["GET"])
def list_permissions():
    resource_type = request.args.get("resource_type")
    return jsonify({"permissions": store.list_permissions(DB_PATH, resource_type)}), 200


@app.route("/permissions", methods=["POST"])
def grant_permission():
    body = request.get_json(silent=True) or {}
    if not _require_admin(body):
        return jsonify({"error": "seul le groupe admin_hub peut octroyer des droits"}), 403
    resource_type = body.get("resource_type")
    group_name = body.get("group_name")
    action = body.get("action")
    resource_id = body.get("resource_id")  # optionnel -- None = octroi large
    if not resource_type or not group_name or not action:
        return jsonify({"error": "'resource_type', 'group_name' et 'action' requis"}), 400
    granted_by = (body.get("groups") or ["?"])[0]
    perm_id = store.grant_permission(DB_PATH, resource_type, resource_id, group_name, action, granted_by)
    return jsonify({"status": "ok", "id": perm_id}), 201


@app.route("/permissions/<int:permission_id>", methods=["DELETE"])
def revoke_permission(permission_id):
    body = request.get_json(silent=True) or {}
    if not _require_admin(body):
        return jsonify({"error": "seul le groupe admin_hub peut révoquer des droits"}), 403
    ok = store.revoke_permission(DB_PATH, permission_id)
    if not ok:
        return jsonify({"error": "permission introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/resource-types", methods=["GET"])
def resource_types():
    return jsonify({"resource_types": store.list_resource_types(DB_PATH)}), 200


@app.route("/files", methods=["POST"])
def list_files():
    """Inventaire de fichiers (livraison #283, "tout fichier
    importé, de configuration, généré ou même de secret doit être
    listé"), filtré par la visibilité de l'appelant. Rescanne à
    CHAQUE appel (même motif que ssh-tunnels/key_scanner -- jamais un
    cache périmé) et enregistre chaque chemin comme ressource
    "hub-file" pour que la gestion des droits puisse s'y référer."""
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or []
    results = file_inventory.scan_files(PROJECT_ROOT)
    for r in results:
        store.upsert_resource(DB_PATH, "hub-file", r["identifier"], label=r["category"])
    visible = store.filter_visible(DB_PATH, groups, "hub-file", results, action="view")
    return jsonify({"files": visible, "total_scanned": len(results), "visible_count": len(visible)}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# Manquait ici jusqu'à cette livraison (#351, backlog item 8) --
# rights-api n'avait AUCUN logging jusque-là (ni ce mécanisme, ni
# même `import logging` de base), trouvé en vérifiant que memory-api
# archive réellement TOUS les services du projet.
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


SERVICE_NAME = "rights-api"
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
