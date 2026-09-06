"""
classifier-api -- livraison #260, backlog item 34 ("à prioriser fort
car central"). Voir `store.py` pour le détail complet de la portée
et du raisonnement (dictionnaires importables plutôt que codés en
dur, NLTK non installable/non pertinent ici, suivi d'usage et
orientation manuelle).
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
    register_version_route(app, "classifier-api")

_log = logging.getLogger("classifier_app")

# Branchement rights-api -- livraison #315, item 38 du backlog.
# Service CENTRAL ("à prioriser fort", #260) -- son dictionnaire est
# utilisé par d'autres modules (ex. Exploration réseau, voir
# classify/batch). Tamponner/vider le dictionnaire partagé
# corromprait silencieusement les classifications de TOUS les
# consommateurs, pas seulement de celui qui a fait le changement.
# Gardé sur import_dictionary/delete_term/delete_source (mutation
# directe du dictionnaire) et confirm (peut AUSSI ajouter au
# dictionnaire via `add_to_dictionary`, gardé en bloc plutôt que
# construire une garde conditionnelle sur ce seul paramètre -- même
# raisonnement de prudence que pour snmp-api #313, jamais une
# demi-garde bâclée). Jamais sur classify/classify_batch (lecture/
# interrogation du dictionnaire, jamais une mutation).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-314) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "classifier-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur classifier-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("CLASSIFIER_DB_PATH", "/data/classifier.db")
store.ensure_schema(DB_PATH)

# Taille maximale d'un import de dictionnaire -- "faible impact",
# jamais un fichier de plusieurs dizaines de Mo accepté sans limite.
MAX_IMPORT_SIZE_BYTES = int(os.environ.get("CLASSIFIER_MAX_IMPORT_MB", "5")) * 1024 * 1024


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# --- Dictionnaires (import demandé explicitement) --------------------

@app.route("/dictionaries/import", methods=["POST"])
def import_dictionary():
    """Corps multipart : `file` (un terme par ligne, `#commentaire`
    et lignes vides ignorés), `category` (requis), `source`
    (optionnel -- nom du dictionnaire, par défaut le nom du fichier).

    Protégée par rights-api (#315) -- `groups` lu depuis
    `request.form` (multipart, jamais un corps JSON ici)."""
    allowed, error = _check_manage_right({"groups": request.form.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "'file' requis (upload multipart)"}), 400
    category = (request.form.get("category") or "").strip()
    if not category:
        return jsonify({"error": "'category' requis"}), 400
    upload = request.files["file"]
    source = (request.form.get("source") or upload.filename or "import").strip()

    raw = upload.read(MAX_IMPORT_SIZE_BYTES + 1)
    if len(raw) > MAX_IMPORT_SIZE_BYTES:
        return jsonify({"error": f"fichier trop volumineux (> {MAX_IMPORT_SIZE_BYTES // (1024*1024)} Mo)"}), 400
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 -- un fichier illisible ne doit jamais planter la route
        return jsonify({"error": "fichier illisible (encodage inattendu)"}), 400

    added, skipped = store.import_terms(DB_PATH, category, source, text)
    return jsonify({"status": "ok", "added": added, "skipped_lines": skipped, "source": source}), 201


@app.route("/dictionaries/terms", methods=["GET"])
def list_terms():
    return jsonify(store.list_terms(DB_PATH, category=request.args.get("category"), source=request.args.get("source"))), 200


@app.route("/dictionaries/terms/<int:term_id>", methods=["DELETE"])
def delete_term(term_id):
    """Protégée par rights-api (#315)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_term(DB_PATH, term_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


@app.route("/dictionaries/sources/<path:source>", methods=["DELETE"])
def delete_source(source):
    """Protégée par rights-api (#315)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_source(DB_PATH, source)
    return jsonify({"status": "ok", "deleted": deleted}), 200


@app.route("/dictionaries/categories", methods=["GET"])
def list_categories():
    return jsonify(store.list_categories(DB_PATH)), 200


# --- Classification -----------------------------------------------------

@app.route("/classify", methods=["GET"])
def classify():
    """`text` requis (typiquement un nom d'hôte), `ip_address`
    optionnel (bonus de confiance pour le motif DHCP, voir store.py).
    `preview=true` -- ne journalise PAS le résultat ni n'incrémente
    les statistiques d'usage (essai avant import, par exemple)."""
    text = request.args.get("text")
    if not text:
        return jsonify({"error": "'text' requis"}), 400
    preview = request.args.get("preview", "").lower() == "true"
    result = store.classify(DB_PATH, text, ip_address=request.args.get("ip_address"), record=not preview)
    return jsonify(result), 200


@app.route("/classify/batch", methods=["POST"])
def classify_batch():
    """Corps JSON : [{"text": "...", "ip_address": "..." (optionnel)}, ...]
    -- classifie plusieurs textes en un seul appel (ex. toute la liste
    d'appareils d'Exploration réseau d'un coup, plutôt qu'un appel par
    ligne)."""
    body = request.get_json(silent=True)
    if not isinstance(body, list):
        return jsonify({"error": "corps JSON attendu : liste de {\"text\", \"ip_address\"}"}), 400
    results = {}
    for item in body:
        text = item.get("text") if isinstance(item, dict) else None
        if not text:
            continue
        results[text] = store.classify(DB_PATH, text, ip_address=item.get("ip_address"))
    return jsonify(results), 200


@app.route("/classify/confirm", methods=["POST"])
def confirm():
    """Orientation manuelle (demandé explicitement) -- corps JSON :
    {"text", "category", "add_to_dictionary" (bool, optionnel),
    "source" (optionnel)}.

    Protégée par rights-api (#315) -- gardée en BLOC (jamais
    seulement quand `add_to_dictionary` est vrai) : cette route peut
    ajouter au dictionnaire partagé, une garde conditionnelle sur ce
    seul paramètre serait plus fine mais pas construite ici, même
    prudence que pour snmp-api (#313)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    text = body.get("text")
    category = body.get("category")
    if not text or not category:
        return jsonify({"error": "'text' et 'category' requis"}), 400
    store.confirm_classification(
        DB_PATH, text, category,
        add_to_dictionary=bool(body.get("add_to_dictionary")), source=body.get("source"),
    )
    return jsonify({"status": "ok"}), 200


@app.route("/results", methods=["GET"])
def results():
    return jsonify(store.list_results(
        DB_PATH, category=request.args.get("category"),
        confirmed_only=request.args.get("confirmed_only", "").lower() == "true",
        limit=request.args.get("limit", type=int) or 200,
    )), 200


@app.route("/stats", methods=["GET"])
def stats():
    """LES "stats d'usage des mots, lexèmes" demandées explicitement."""
    return jsonify(store.usage_stats(DB_PATH)), 200


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


SERVICE_NAME = "classifier-api"
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
