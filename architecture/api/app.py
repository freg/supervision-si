"""
architecture-api -- livraison #253, nouveau chantier : vue/outil de
parcours de l'architecture réseau. Voir `store.py` pour le détail
complet de la portée (ce qui est croisé À LA LECTURE depuis d'autres
modules déjà existants, ce que ce module apporte de nouveau -- la
topologie amont/aval déclarée).
"""
import logging
import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import store
from safe_json import safe_json

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "architecture-api")

_log = logging.getLogger("architecture_app")

# Branchement rights-api -- livraison #316, item 38 du backlog.
# Ce module ne configure JAMAIS d'équipement réel -- topologie
# amont/aval DÉCLARÉE, documentation pure. Une donnée trafiquée
# n'endommage aucun équipement, mais pourrait égarer un technicien
# en plein dépannage (mauvais lien/équipement affiché comme source
# d'un incident). Gardé sur les 8 routes d'ÉCRITURE (équipements,
# import network-agent, interfaces, liens) -- jamais la lecture.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-315) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "architecture-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur architecture-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("ARCHITECTURE_DB_PATH", "/data/architecture.db")
store.ensure_schema(DB_PATH)

# Croisement EN DIRECT avec deux modules déjà existants (livraison
# #253) -- jamais une copie stockée ici, voir docstring de store.py.
GED_API_URL = os.environ.get("GED_API_INTERNAL_URL", "http://ged-api:5000").rstrip("/")
SSH_TUNNELS_API_URL = os.environ.get("SSH_TUNNELS_API_INTERNAL_URL", "http://ssh-tunnels-api:5000").rstrip("/")
# ⚠️ network-agent-api tourne en `network_mode: host` (#238-239) --
# JAMAIS le nom de service Docker habituel, voir
# backup-restore-api/#249 pour le même piège déjà rencontré et
# corrigé. Croisement AJOUTÉ en #254 -- "niveaux d'usage... anticiper
# les engorgements... justifier des investissements".
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")
# URL interne vers zenoss-api (livraison #268) -- croisement de
# localisation ("lieux d'intervention"), volontairement différé en
# #253-254 faute d'une route dédiée côté zenoss-api -- corrigé
# depuis (GET /device_location).
ZENOSS_API_URL = os.environ.get("ZENOSS_API_INTERNAL_URL", "http://zenoss-api:5000").rstrip("/")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# --- Équipements -------------------------------------------------------

@app.route("/equipment", methods=["GET"])
def list_equipment():
    return jsonify(store.list_equipment(DB_PATH, search=request.args.get("search"))), 200


@app.route("/equipment", methods=["POST"])
def create_equipment():
    """Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "'name' requis"}), 400
    new_id = store.create_equipment(
        DB_PATH, name,
        ip_address=body.get("ip_address"), mac_address=body.get("mac_address"),
        equipment_type=body.get("equipment_type"), notes=body.get("notes"),
    )
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/import/network-agent", methods=["POST"])
def import_from_network_agent():
    """Import/synchronisation depuis les appareils déjà découverts
    par `network-agent` (livraison #263, "reste à faire" signalé dès
    #253). Corps JSON optionnel {"segment_id": N} -- sans corps,
    importe TOUS les segments connus. Voir
    `store.import_from_network_agent` pour le détail complet du
    comportement (idempotent, personnalisations jamais écrasées).

    Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    if not NETWORK_AGENT_API_URL:
        return jsonify({"error": "NETWORK_AGENT_API_URL non configurée"}), 502
    segment_id = body.get("segment_id")
    params = {"segment_id": segment_id} if segment_id else {}

    try:
        resp = requests.get(f"{NETWORK_AGENT_API_URL}/devices", params=params, timeout=10)
    except requests.RequestException as exc:
        return jsonify({"error": f"network-agent injoignable : {exc}"}), 502
    if resp.status_code != 200:
        return jsonify({"error": f"network-agent a répondu {resp.status_code}"}), 502

    try:
        payload = safe_json(resp, "import depuis network-agent")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    result = store.import_from_network_agent(DB_PATH, payload)
    return jsonify({"status": "ok", **result}), 200


@app.route("/equipment/<int:equipment_id>", methods=["GET"])
def get_equipment(equipment_id):
    equipment = store.get_equipment(DB_PATH, equipment_id)
    if equipment is None:
        return jsonify({"error": "équipement introuvable"}), 404
    return jsonify(equipment), 200


@app.route("/equipment/<int:equipment_id>", methods=["PUT"])
def update_equipment(equipment_id):
    """Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    updated = store.update_equipment(DB_PATH, equipment_id, **body)
    return jsonify({"status": "ok", "updated": updated}), 200


@app.route("/equipment/<int:equipment_id>", methods=["DELETE"])
def delete_equipment(equipment_id):
    """Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_equipment(DB_PATH, equipment_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


# --- Interfaces ----------------------------------------------------------

@app.route("/equipment/<int:equipment_id>/interfaces", methods=["GET"])
def list_interfaces(equipment_id):
    return jsonify(store.list_interfaces(DB_PATH, equipment_id)), 200


@app.route("/equipment/<int:equipment_id>/interfaces", methods=["POST"])
def create_interface(equipment_id):
    """Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label = (body.get("label") or "").strip()
    if not label:
        return jsonify({"error": "'label' requis"}), 400
    new_id = store.create_interface(DB_PATH, equipment_id, label, notes=body.get("notes"))
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/interfaces/<int:interface_id>", methods=["DELETE"])
def delete_interface(interface_id):
    """Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_interface(DB_PATH, interface_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


# --- Liens topologiques ----------------------------------------------------

@app.route("/links", methods=["POST"])
def create_link():
    """Corps : {"upstream_interface_id", "downstream_interface_id",
    "notes" (optionnel)} -- déclare qu'une interface est EN AMONT
    d'une autre (voir store.py pour le raisonnement complet).

    Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    upstream_id = body.get("upstream_interface_id")
    downstream_id = body.get("downstream_interface_id")
    if not upstream_id or not downstream_id:
        return jsonify({"error": "'upstream_interface_id' et 'downstream_interface_id' requis"}), 400
    try:
        new_id = store.create_link(DB_PATH, upstream_id, downstream_id, notes=body.get("notes"))
    except Exception as exc:  # noqa: BLE001 -- ex. contrainte UNIQUE déjà violée (lien déjà déclaré), renvoyé tel quel plutôt qu'un 500 nu
        return jsonify({"error": str(exc)}), 409
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/links/<int:link_id>", methods=["DELETE"])
def delete_link(link_id):
    """Protégée par rights-api (#316)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_link(DB_PATH, link_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


# --- Vue agrégée -- le cœur de la demande ---------------------------------

def _fetch_ged_documents(equipment_id):
    """Best-effort explicite -- ged-api peut être indisponible sans
    que la vue d'ensemble ne devienne inutilisable pour autant (voir
    même raisonnement que `backup-restore-api`/#249 pour
    network-agent-api). Renvoie (documents, error)."""
    try:
        resp = requests.get(f"{GED_API_URL}/documents", params={"linked_type": "equipment", "linked_id": equipment_id}, timeout=10)
    except requests.RequestException as exc:
        return [], f"GED injoignable : {exc}"
    if resp.status_code != 200:
        return [], f"GED a répondu {resp.status_code}"
    try:
        return resp.json(), None
    except ValueError:
        return [], "réponse GED illisible"


def _fetch_ssh_access(ip_address):
    """Croisement PAR ADRESSE IP contre les connexions SSH déjà
    enregistrées (voir store.py -- jamais stocké ici, toujours
    interrogé en direct). `None` si `ip_address` n'est pas renseignée
    sur l'équipement -- rien à croiser dans ce cas."""
    if not ip_address:
        return [], None
    try:
        resp = requests.get(f"{SSH_TUNNELS_API_URL}/connections", timeout=10)
    except requests.RequestException as exc:
        return [], f"ssh-tunnels injoignable : {exc}"
    if resp.status_code != 200:
        return [], f"ssh-tunnels a répondu {resp.status_code}"
    try:
        connections = resp.json()
    except ValueError:
        return [], "réponse ssh-tunnels illisible"
    matches = [c for c in connections if c.get("ssh_host") == ip_address]
    return matches, None


def _fetch_usage_history(ip_address):
    """Croisement PAR ADRESSE IP contre les appareils déjà découverts
    par `network-agent` (livraison #254, "niveaux d'usage... anticiper
    les engorgements... justifier des investissements") -- si un
    appareil correspondant est trouvé, renvoie son historique de
    présence/volume (déjà construit en #251), avec un TAUX DE
    VARIATION calculé entre le premier et le dernier relevé -- le
    signal le plus direct pour repérer une TENDANCE (croissance
    soutenue = engorgement possible à anticiper, ou argument concret
    pour justifier un investissement).

    `(None, None)` si `ip_address` non renseignée, `NETWORK_AGENT_API_URL`
    non configurée, OU aucun appareil correspondant trouvé -- ce
    DERNIER cas n'est PAS une erreur : la plupart des équipements de
    ce registre ne seront pas nécessairement surveillés par
    `network-agent`, jamais présenté comme un échec."""
    if not ip_address or not NETWORK_AGENT_API_URL:
        return None, None
    try:
        resp = requests.get(f"{NETWORK_AGENT_API_URL}/devices", timeout=10)
    except requests.RequestException as exc:
        return None, f"network-agent injoignable : {exc}"
    if resp.status_code != 200:
        return None, f"network-agent a répondu {resp.status_code}"
    try:
        devices = resp.json()
    except ValueError:
        return None, "réponse network-agent illisible"

    matching = next((d for d in devices if d.get("ip_address") == ip_address), None)
    if matching is None:
        return None, None  # pas trouvé -- normal, jamais une erreur

    try:
        history_resp = requests.get(f"{NETWORK_AGENT_API_URL}/devices/{matching['id']}/presence-history", timeout=10)
    except requests.RequestException as exc:
        return None, f"network-agent injoignable (historique) : {exc}"
    if history_resp.status_code != 200:
        return None, f"network-agent a répondu {history_resp.status_code} (historique)"
    try:
        history = history_resp.json()
    except ValueError:
        return None, "réponse network-agent illisible (historique)"

    growth_percent = None
    if len(history) >= 2 and history[0]["bytes_total"] > 0:
        growth_percent = round((history[-1]["bytes_total"] - history[0]["bytes_total"]) / history[0]["bytes_total"] * 100, 1)

    return {"device": matching, "history": history, "growth_percent": growth_percent}, None


def _fetch_zenoss_location(name, ip_address):
    """Croisement de localisation ("lieux d'intervention", livraison
    #268) -- volontairement différé en #253-254 faute d'une route
    dédiée côté zenoss-api (structure en arbre, pas de recherche
    directe), corrigé depuis (GET /device_location, requête ciblée,
    jamais un parcours de tout l'arbre). Essaie PAR NOM d'abord (le
    `name` de l'équipement dans ce registre -- souvent son nom
    d'hôte), PUIS par IP si le nom n'a rien donné -- deux tentatives
    plutôt qu'une, jamais présumé que l'un des deux suffira toujours.
    `(None, None)` si rien trouvé -- normal, la plupart des
    équipements de ce registre ne seront pas nécessairement connus de
    Zenoss."""
    if not name and not ip_address:
        return None, None
    try:
        if name:
            resp = requests.get(f"{ZENOSS_API_URL}/device_location", params={"device": name}, timeout=10)
            if resp.status_code == 200 and resp.json().get("result"):
                return resp.json()["result"], None
        if ip_address:
            resp = requests.get(f"{ZENOSS_API_URL}/device_location", params={"ip": ip_address}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("result"), None
    except (requests.RequestException, ValueError) as exc:
        # ValueError ajouté en #287 -- "rendre les erreurs
        # systématiquement plus explicites" -- un 200 avec un corps
        # non-JSON (zenoss-api derrière un proxy, panne
        # intermédiaire...) échappait auparavant à ce filet.
        return None, f"zenoss-api injoignable ou réponse invalide : {exc}"
    return None, None


@app.route("/equipment/<int:equipment_id>/overview", methods=["GET"])
def equipment_overview(equipment_id):
    """LA route centrale de ce module -- répond directement à la
    demande d'origine : pour UN équipement, en un seul appel,
    topologie amont/aval (déclarée ici), accès de gestion (croisé
    depuis ssh-tunnels par IP), documents liés (croisés depuis la
    GED). Chaque croisement est BEST-EFFORT et signale son propre
    échec éventuel SANS faire échouer les autres -- une source
    indisponible ne doit jamais masquer ce que les autres ont pu
    fournir."""
    equipment = store.get_equipment(DB_PATH, equipment_id)
    if equipment is None:
        return jsonify({"error": "équipement introuvable"}), 404

    neighbors = store.get_neighbors(DB_PATH, equipment_id)
    documents, ged_error = _fetch_ged_documents(equipment_id)
    ssh_access, ssh_error = _fetch_ssh_access(equipment.get("ip_address"))
    usage, usage_error = _fetch_usage_history(equipment.get("ip_address"))
    location, location_error = _fetch_zenoss_location(equipment.get("name"), equipment.get("ip_address"))

    return jsonify({
        "equipment": equipment,
        "neighbors": neighbors,
        "documents": documents,
        "documents_error": ged_error,
        "ssh_access": ssh_access,
        "ssh_access_error": ssh_error,
        "usage": usage,
        "usage_error": usage_error,
        "location": location,
        "location_error": location_error,
    }), 200


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


SERVICE_NAME = "architecture-api"
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
