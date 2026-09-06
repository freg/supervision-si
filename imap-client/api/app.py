"""
imap-client -- volets 1 et 2/4 de "client IMAP + interpréteur de
messages" (livraisons #179/#189/#190, backlog BACKLOG.md #4). Voir
imap_wrapper.py pour le détail complet du raisonnement
(approximations assumées, distinction avec parse_zenoss_emails.py).

**Règles de tri (livraison #190)** : précision apportée par la
personne sur le sens de "filtres" -- "trier et poser des étiquettes,
déplacer vers des dossiers, déclencher des actions". PREMIÈRE base
de données de ce module (voir rules_store.py) -- les règles doivent
PERSISTER, contrairement au reste du module qui reste SANS ÉTAT
(connexion IMAP neuve à chaque requête). Application des règles
VOLONTAIREMENT À LA DEMANDE (`POST /rules/apply`), PAS encore une
tâche de fond automatique -- une automatisation qui MODIFIE la boîte
toute seule (déplace/étiquette des messages sans supervision directe)
est un pas plus risqué, laissé à une décision explicite plus tard
plutôt que présumé maintenant.

UN SEUL identifiant de boîte configuré (`.env`) -- pas encore de
gestion multi-comptes, jamais demandée explicitement, à ajouter si
besoin plus tard plutôt que présumée maintenant.

Connexion NEUVE à CHAQUE requête (jamais une connexion IMAP
persistante partagée entre requêtes) -- même raisonnement que
dba-api pour ses connecteurs SGBD : une connexion IMAP GARDÉE
ouverte entre deux requêtes HTTP pourrait avoir expiré côté serveur
(timeout d'inactivité IMAP, courant), la détection d'une connexion
"encore valide" ajouterait de la complexité pour un gain minime sur
ce volume d'usage attendu (diagnostic/consultation, pas un flux
haute fréquence).
"""
import logging
import os
import time

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import imap_wrapper as imap
import rules_store as store
import rule_engine
import interpreters_store as interp_store
import interpreter_engine

# Traces DEBUG (cohérent avec le chantier #215-225) -- RÈGLE ABSOLUE :
# le contenu du message (sujet, corps, valeurs interprétées) n'est
# JAMAIS tracé -- seuls les métadonnées non sensibles (nom de
# l'interpréteur, source cible, durée, issue).
_log = logging.getLogger("imap_client_connector")

# Connecteur source (livraison #230, backlog item 4) -- appel
# CONTENEUR-À-CONTENEUR vers le service `api` principal, même motif
# que NEBULA_API_INTERNAL_URL (glpi/api/app.py, #208).
API_INTERNAL_URL = os.environ.get("API_INTERNAL_URL", "http://api:5000").rstrip("/")

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "imap-client")

# Branchement rights-api -- livraison #310, item 38 du backlog. Cette
# boîte est OPÉRATIONNELLE (reçoit des notifications de systèmes qui
# ne savent alerter que par e-mail, voir README.md), jamais une boîte
# personnelle -- mais une règle ou un interprète trafiqué pourrait
# faire disparaître silencieusement une alerte critique (règle
# malveillante qui supprime/déplace les messages d'un expéditeur
# précis avant que quiconque les voie). Gardé sur toutes les routes
# d'ÉCRITURE qui changent l'état de la boîte ou son traitement
# automatique (dossiers, déplacement, règles, interprètes) --
# JAMAIS sur la lecture (dossiers/messages/règles/interprètes en
# liste, ni /messages/<uid>/interpret qui ne fait qu'analyser un
# message déjà lisible sans y toucher, fonctionnellement une lecture
# malgré le verbe POST).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308, #309) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "imap-client-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur imap-client-api requis (groupe admin_hub, ou un octroi explicite)"

IMAP_HOST = os.environ.get("IMAP_HOST", "").strip()
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "").strip()
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")
IMAP_USE_SSL = os.environ.get("IMAP_USE_SSL", "true").strip().lower() != "false"
IMAP_DEFAULT_FOLDER = os.environ.get("IMAP_DEFAULT_FOLDER", "INBOX").strip() or "INBOX"

# Règles de tri (livraison #190) -- SEULE donnée persistante de ce
# module, tout le reste reste sans état (voir docstring).
RULES_DB_PATH = os.environ.get("IMAP_RULES_DB_PATH", "/data/imap-rules.db")
os.makedirs(os.path.dirname(RULES_DB_PATH), exist_ok=True)
store.ensure_schema(RULES_DB_PATH)

# Interpréteurs (livraison #191) -- MÊME fichier SQLite que les
# règles (tables SÉPARÉES, `imap_interpreters` vs `imap_rules`) --
# une seule base à sauvegarder/monter pour ce module, pas deux
# fichiers distincts sans raison technique de les séparer.
interp_store.ensure_schema(RULES_DB_PATH)


def _connect():
    """Lève imap.ImapError si .env n'est pas encore renseigné --
    jamais une KeyError/ValueError confuse plus loin, un message
    actionnable dès la première tentative de connexion."""
    if not IMAP_HOST or not IMAP_USER:
        raise imap.ImapError(
            "IMAP_HOST/IMAP_USER non configurés -- voir imap-client/README.md pour les variables .env attendues"
        )
    return imap.connect(IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD, use_ssl=IMAP_USE_SSL)


@app.route("/folders", methods=["GET"])
def get_folders():
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        folders = imap.list_folders(conn)
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)
    return jsonify(folders), 200


@app.route("/messages", methods=["GET"])
def get_messages():
    folder = request.args.get("folder") or IMAP_DEFAULT_FOLDER
    limit = min(int(request.args.get("limit", 50)), 200)  # plafond dur -- jamais un dump complet accidentel d'une grosse boîte
    offset = max(int(request.args.get("offset", 0)), 0)
    # Filtres (livraison #189) -- voir imap_wrapper.list_messages.
    subject_filter = request.args.get("subject") or None
    from_filter = request.args.get("from") or None
    unseen_only = request.args.get("unseen", "").strip().lower() == "true"
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        messages, total = imap.list_messages(
            conn, folder, limit=limit, offset=offset,
            subject_filter=subject_filter, from_filter=from_filter, unseen_only=unseen_only,
        )
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)
    return jsonify({"messages": messages, "total": total, "folder": folder}), 200


@app.route("/messages/<uid>", methods=["GET"])
def get_message(uid):
    folder = request.args.get("folder") or IMAP_DEFAULT_FOLDER
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        message = imap.fetch_message(conn, folder, uid)
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)
    return jsonify(message), 200


# ------------------------------------------------------------------
# Gestion de la boîte (livraison #189, volet 2/4 -- "Interface de
# gestion de la boîte"). PREMIÈRES routes d'ÉCRITURE de ce module.
# ------------------------------------------------------------------
@app.route("/folders", methods=["POST"])
def post_folder():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "'name' requis"}), 400
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        imap.create_folder(conn, name)
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)
    return jsonify({"status": "ok", "name": name}), 201


@app.route("/folders", methods=["DELETE"])
def delete_folder_route():
    """Nom du dossier en PARAMÈTRE DE REQUÊTE, jamais un segment
    d'URL -- un nom de dossier IMAP peut lui-même contenir le
    séparateur hiérarchique ('/' ou '.' selon le serveur), ce qui
    casserait un routage par segment de chemin."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"error": "paramètre 'name' requis"}), 400
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        imap.delete_folder(conn, name)
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)
    return jsonify({"status": "ok"}), 200


@app.route("/messages/<uid>/move", methods=["POST"])
def move_message_route(uid):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    source_folder = (body.get("from_folder") or request.args.get("folder") or IMAP_DEFAULT_FOLDER).strip()
    dest_folder = (body.get("to_folder") or "").strip()
    if not dest_folder:
        return jsonify({"error": "'to_folder' requis"}), 400
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        imap.move_message(conn, source_folder, uid, dest_folder)
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)
    return jsonify({"status": "ok", "from_folder": source_folder, "to_folder": dest_folder}), 200


# ------------------------------------------------------------------
# Règles de tri (livraison #190) -- "trier et poser des étiquettes,
# déplacer vers des dossiers, déclencher des actions". Application
# VOLONTAIREMENT à la demande, voir docstring du module.
# ------------------------------------------------------------------
@app.route("/rules", methods=["GET"])
def list_rules():
    return jsonify(store.list_rules(RULES_DB_PATH)), 200


@app.route("/rules", methods=["POST"])
def create_rule():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    name = (body.get("name") or "").strip()
    watch_folder = (body.get("watch_folder") or IMAP_DEFAULT_FOLDER).strip()
    if not name:
        return jsonify({"error": "'name' requis"}), 400
    has_action = any([body.get("action_move_to"), body.get("action_add_label"), body.get("action_mark_seen")])
    if not has_action:
        return jsonify({"error": "au moins une action requise (action_move_to, action_add_label ou action_mark_seen)"}), 400
    rule_id = store.create_rule(
        RULES_DB_PATH, name, watch_folder,
        match_subject=body.get("match_subject") or None,
        match_from=body.get("match_from") or None,
        match_unseen_only=bool(body.get("match_unseen_only")),
        action_move_to=body.get("action_move_to") or None,
        action_add_label=body.get("action_add_label") or None,
        action_mark_seen=bool(body.get("action_mark_seen")),
    )
    return jsonify(store.get_rule(RULES_DB_PATH, rule_id)), 201


@app.route("/rules/<int:rule_id>", methods=["PUT"])
def update_rule_route(rule_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    updated = store.update_rule(RULES_DB_PATH, rule_id, body)
    if updated is None:
        return jsonify({"error": "règle introuvable"}), 404
    return jsonify(updated), 200


@app.route("/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule_route(rule_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_rule(RULES_DB_PATH, rule_id)
    if not deleted:
        return jsonify({"error": "règle introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/rules/apply", methods=["POST"])
def apply_rules():
    """Applique TOUTES les règles ACTIVÉES (une règle désactivée est
    ignorée, jamais supprimée -- voir `enabled` sur PUT /rules/<id>).
    UNE SEULE connexion IMAP réutilisée pour toutes les règles de cet
    appel -- inutile d'en rouvrir une par règle. Renvoie le résumé
    PAR règle, jamais un total agrégé qui masquerait quelle règle a
    fait quoi (ou a échoué)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    rules = [r for r in store.list_rules(RULES_DB_PATH) if r["enabled"]]
    if not rules:
        return jsonify({"results": []}), 200
    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    results = []
    try:
        for rule in rules:
            try:
                summary = rule_engine.apply_rule(conn, rule)
                results.append({"rule_id": rule["id"], "rule_name": rule["name"], **summary})
            except imap.ImapError as exc:
                results.append({"rule_id": rule["id"], "rule_name": rule["name"], "error": str(exc)})
    finally:
        imap.safe_logout(conn)
    return jsonify({"results": results}), 200


# ------------------------------------------------------------------
# Interpréteurs (livraison #191, volet 3/4) -- généralise en outil
# CONFIGURABLE ce que parse_zenoss_emails.py fait en dur pour un seul
# format, voir interpreters_store.py.
# ------------------------------------------------------------------
@app.route("/interpreters", methods=["GET"])
def list_interpreters():
    return jsonify(interp_store.list_interpreters(RULES_DB_PATH)), 200


@app.route("/interpreters", methods=["POST"])
def create_interpreter():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    name = (body.get("name") or "").strip()
    fields = body.get("fields")
    if not name:
        return jsonify({"error": "'name' requis"}), 400
    ok, error = interp_store.validate_fields(fields)
    if not ok:
        return jsonify({"error": error}), 400
    interp_id = interp_store.create_interpreter(
        RULES_DB_PATH, name, fields,
        match_subject=body.get("match_subject") or None,
        match_from=body.get("match_from") or None,
        target_source=(body.get("target_source") or "").strip() or None,
    )
    return jsonify(interp_store.get_interpreter(RULES_DB_PATH, interp_id)), 201


@app.route("/interpreters/<int:interpreter_id>", methods=["PUT"])
def update_interpreter_route(interpreter_id):
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    updated, error = interp_store.update_interpreter(RULES_DB_PATH, interpreter_id, body)
    if error:
        return jsonify({"error": error}), 400
    if updated is None:
        return jsonify({"error": "interpréteur introuvable"}), 404
    return jsonify(updated), 200


@app.route("/interpreters/<int:interpreter_id>", methods=["DELETE"])
def delete_interpreter_route(interpreter_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = interp_store.delete_interpreter(RULES_DB_PATH, interpreter_id)
    if not deleted:
        return jsonify({"error": "interpréteur introuvable"}), 404
    return jsonify({"status": "ok"}), 200


def _push_to_source(target_source, payload):
    """Connecteur source (livraison #230, backlog item 4) -- pousse
    le résultat d'interprétation vers `POST /ingest/<source>` (`api`
    principal, chemin de confiance déjà établi pour qu'une source
    s'enregistre). BEST-EFFORT, jamais bloquant pour l'appelant --
    une source d'e-mail interprétée qui échoue à se pousser ne doit
    JAMAIS faire échouer l'interprétation elle-même (déjà réussie à
    ce stade, son résultat est de toute façon renvoyé à l'appelant
    HTTP indépendamment de ce push). Renvoie (ok, error) -- jamais
    une exception."""
    _log.debug("_push_to_source : démarré vers '%s' (jamais le contenu du message ici)", target_source)
    start = time.monotonic()
    try:
        resp = requests.post(f"{API_INTERNAL_URL}/ingest/{target_source}", json=payload, timeout=10)
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log.debug("_push_to_source : ÉCHEC réseau après %d ms vers '%s' -- %s", elapsed_ms, target_source, exc)
        return False, f"push vers la source '{target_source}' échoué : {exc}"
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if resp.status_code >= 300:
        _log.debug("_push_to_source : ÉCHEC HTTP %s après %d ms vers '%s'", resp.status_code, elapsed_ms, target_source)
        return False, f"push vers la source '{target_source}' refusé (HTTP {resp.status_code})"
    _log.debug("_push_to_source : succès en %d ms vers '%s'", elapsed_ms, target_source)
    return True, None


@app.route("/messages/<uid>/interpret", methods=["POST"])
def interpret_message(uid):
    """Corps optionnel `{"interpreter_id": N}` -- si absent, le
    PREMIER interpréteur activé dont les critères correspondent est
    choisi automatiquement (voir interpreter_engine.find_matching_interpreter).
    404 si aucun interpréteur ne correspond (ou si `interpreter_id`
    fourni est introuvable) -- jamais un résultat vide qui masquerait
    la vraie raison."""
    folder = request.args.get("folder") or IMAP_DEFAULT_FOLDER
    body = request.get_json(silent=True) or {}
    requested_id = body.get("interpreter_id")

    try:
        conn = _connect()
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        message = imap.fetch_message(conn, folder, uid)
    except imap.ImapError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        imap.safe_logout(conn)

    if requested_id:
        chosen = interp_store.get_interpreter(RULES_DB_PATH, requested_id)
        if chosen is None:
            return jsonify({"error": "interpréteur introuvable"}), 404
    else:
        interpreters = [r for r in interp_store.list_interpreters(RULES_DB_PATH) if r["enabled"]]
        chosen = interpreter_engine.find_matching_interpreter(interpreters, message)
        if chosen is None:
            return jsonify({"error": "aucun interpréteur ne correspond à ce message"}), 404

    result, errors = interpreter_engine.apply_interpreter(chosen, message)
    response_body = {
        "interpreter_id": chosen["id"], "interpreter_name": chosen["name"],
        "result": result, "errors": errors,
    }

    # Connecteur source (livraison #230) -- OPT-IN, seulement si
    # l'interpréteur a une target_source configurée. Best-effort --
    # voir _push_to_source, jamais bloquant pour cette réponse.
    target_source = chosen.get("target_source")
    if target_source:
        pushed_ok, push_error = _push_to_source(target_source, {
            "interpreter_id": chosen["id"], "interpreter_name": chosen["name"],
            "message_uid": uid, "result": result, "errors": errors,
        })
        response_body["pushed_to_source"] = target_source
        response_body["push_ok"] = pushed_ok
        if push_error:
            response_body["push_error"] = push_error

    return jsonify(response_body), 200


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


SERVICE_NAME = "imap-client-api"
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
