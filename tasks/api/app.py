"""
tasks-api -- livraison #271, gestion de tâches INDÉPENDANTE des
tickets avec vue Kanban (demandé explicitement). Voir store.py pour
le détail complet de la portée et du raisonnement.
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
    register_version_route(app, "tasks-api")

_log = logging.getLogger("tasks_app")

# Branchement rights-api -- livraison #312, item 38 du backlog.
# SCOPE VOLONTAIREMENT ÉTROIT : ce kanban est délibérément
# COLLABORATIF (aucune notion de propriétaire dans le schéma --
# créer/déplacer/modifier une carte est l'usage NORMAL de l'outil,
# pas une élévation de privilège). Gardé UNIQUEMENT sur la
# suppression (DELETE /tasks/<id>, suppression définitive, aucun
# mécanisme d'archive) -- la seule action qualitativement différente
# du fonctionnement collaboratif attendu. Jamais sur create/update/
# move, qui resteraient bloqués pour un usage normal sans fermer
# aucune brèche réelle.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-311) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "tasks-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur tasks-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("TASKS_DB_PATH", "/data/tasks.db")
store.ensure_schema(DB_PATH)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(store.list_tasks(DB_PATH)), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    body = request.get_json(silent=True) or {}
    task_id, error = store.create_task(
        DB_PATH, body.get("title"), description=body.get("description"),
        status=body.get("status", "todo"), due_date=body.get("due_date"),
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"status": "ok", "id": task_id}), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = store.get_task(DB_PATH, task_id)
    if task is None:
        return jsonify({"error": "tâche introuvable"}), 404
    return jsonify(task), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    """Mise à jour SIMPLE (titre/description/échéance) -- pour un
    déplacement Kanban, voir PUT /tasks/<id>/move."""
    body = request.get_json(silent=True) or {}
    if store.get_task(DB_PATH, task_id) is None:
        return jsonify({"error": "tâche introuvable"}), 404
    store.update_task(DB_PATH, task_id, **body)
    return jsonify({"status": "ok"}), 200


@app.route("/tasks/<int:task_id>/move", methods=["PUT"])
def move_task(task_id):
    """LE déplacement Kanban -- corps JSON {"status", "position"}."""
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    position = body.get("position")
    if status is None or position is None:
        return jsonify({"error": "'status' et 'position' requis"}), 400
    ok, error = store.move_task(DB_PATH, task_id, status, position)
    if not ok:
        code = 404 if error == "tâche introuvable" else 400
        return jsonify({"error": error}), code
    return jsonify({"status": "ok"}), 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    """Protégée par rights-api (#312) -- suppression DÉFINITIVE,
    aucun mécanisme d'archive. Seule route gardée de ce module, voir
    le commentaire en tête de fichier."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_task(DB_PATH, task_id)
    if not deleted:
        return jsonify({"error": "tâche introuvable"}), 404
    return jsonify({"status": "ok"}), 200


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


SERVICE_NAME = "tasks-api"
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
