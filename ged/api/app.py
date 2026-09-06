"""
ged -- gestion électronique de documents (livraison #157-#158).
Demandé explicitement : "gestion de documents liés/joints" pour les
tickets + "interface/API GED" dans le hub.

#157 : fondation homemade (stockage disque + SQLite), choix d'une
vraie GED tierce EXPLICITEMENT DÉFÉRÉ ("on travaillera cet aspect
plus tard").
#158 : "allons-y pour Mayan EDMS" -- la fondation homemade est
REMPLACÉE ici par de vrais appels à l'API REST de Mayan EDMS (voir
mayan_client.py) pour tout ce qui touche au stockage/versioning des
fichiers. La table de liaison POLYMORPHE (documents_store.py) reste
LOCALE -- Mayan n'a pas cet équivalent, répond directement à "accès
polymorphe aux documents" demandé en #157.

L'API HTTP EXPOSÉE ICI reste STABLE malgré ce changement de backend
(objectif explicite de #157) -- l'onglet hub et l'intégration côté
tickets (encore à construire, voir BACKLOG.md) n'ont pas besoin de
changer si le backend change à nouveau plus tard.

⚠️ Voir mayan_client.py pour le détail de ce qui est confirmé vs
déduit dans l'API Mayan -- NON VÉRIFIÉ contre une vraie instance dans
cet environnement (aucun moteur Docker disponible ici).
"""
import logging
import os

import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

import documents_store as store
import mayan_client as mayan

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "ged")

_log = logging.getLogger("ged_app")

# Branchement rights-api -- livraison #311, item 38 du backlog.
# Documents liés aux tickets, potentiellement du contenu métier
# sensible -- gardé sur les 5 routes d'ÉCRITURE (créer/supprimer un
# document, nouvelle version, créer/supprimer un lien polymorphe),
# jamais la lecture (liste, détail, téléchargement de version).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-310) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "ged-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur ged-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("GED_DB_PATH", "/data/ged.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
store.ensure_schema(DB_PATH)

# Adresse INTERNE au réseau Docker PARTAGÉ (voir mayan/docker-compose.yml,
# livraison #158) -- jamais via tls-proxy, trafic conteneur-à-conteneur.
MAYAN_BASE = os.environ.get("MAYAN_BASE", "http://mayan-app:8000")
# MÊMES identifiants que MAYAN_AUTOADMIN_USERNAME/PASSWORD dans
# mayan/docker-compose.yml -- doivent rester synchronisés entre les
# deux stacks (aucune vérification automatique de cohérence, à
# surveiller manuellement si l'un des deux change).
MAYAN_USERNAME = os.environ.get("MAYAN_USERNAME", "admin")
MAYAN_PASSWORD = os.environ.get("MAYAN_PASSWORD", "change-me")
MAYAN_DOCUMENT_TYPE_LABEL = os.environ.get("MAYAN_DOCUMENT_TYPE_LABEL", "Default")

# Limite de taille d'upload -- ged-api reste un INTERMÉDIAIRE (le
# fichier transite par lui avant d'être relayé à Mayan), une limite
# ici reste une protection utile même si le stockage final n'est
# plus local depuis #158.
MAX_UPLOAD_MB = int(os.environ.get("GED_MAX_UPLOAD_MB", "50"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _sorted_files(document_id):
    """Fichiers Mayan d'un document, TRIÉS PAR ID croissant PAR CE
    MODULE (jamais présumé de l'ordre renvoyé par Mayan lui-même --
    voir mayan_client.py, "MOINS CERTAIN") -- donne un ordre
    PRÉVISIBLE et STABLE pour numéroter les versions (position dans
    cette liste = version_number)."""
    files = mayan.list_document_files(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id)
    return sorted(files, key=lambda f: f.get("id", 0))


def _document_with_versions(document_id):
    """Détail d'un document -- combine Mayan (label, fichiers/versions)
    et la table locale (liaisons). None si le document n'existe pas
    côté Mayan -- vérifié EXPLICITEMENT via get_document (jamais
    déduit d'une liste de fichiers vide, qui pourrait aussi bien
    signifier "document sans aucun fichier" -- voir mayan_client.py)."""
    try:
        meta = mayan.get_document(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id)
        if meta is None:
            return None
        files = _sorted_files(document_id)
    except mayan.MayanError:
        return None
    versions = [
        {"version_number": i + 1, "mayan_file_id": f.get("id"), "raw": f}
        for i, f in enumerate(files)
    ]
    return {
        "id": document_id,
        "name": meta.get("label"),
        "versions": versions,
        "links": store.list_links(DB_PATH, document_id),
    }


@app.route("/documents", methods=["GET"])
def list_documents():
    """Query params : linked_type + linked_id (optionnels, ENSEMBLE
    -- filtre sur les documents liés à cette entité précise, ex.
    ?linked_type=ticket&linked_id=42). SANS filtre : tous les
    documents CONNUS de ged-api (au moins une liaison enregistrée) --
    PAS littéralement tous les documents de Mayan (qui pourrait
    contenir des documents créés directement via l'interface Mayan,
    sans rapport avec ce module)."""
    linked_type = request.args.get("linked_type")
    linked_id = request.args.get("linked_id")
    if linked_type and linked_id:
        document_ids = store.list_linked_document_ids(DB_PATH, linked_type, linked_id)
    else:
        # Tous les documents ayant AU MOINS une liaison connue --
        # jamais un appel "lister tout Mayan", hors de portée de ce
        # module (voir docstring ci-dessus).
        conn = store.get_connection(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT document_id FROM document_links")
            document_ids = [r["document_id"] for r in cur.fetchall()]
        finally:
            conn.close()

    docs = []
    for doc_id in document_ids:
        doc = _document_with_versions(doc_id)
        if doc is not None:
            docs.append(doc)
    return jsonify(docs), 200


@app.route("/documents", methods=["POST"])
def create_document():
    """multipart/form-data : `file` (requis), `name` (optionnel,
    repli sur le nom du fichier envoyé), `actor` (optionnel),
    `linked_type`+`linked_id` (optionnels, ENSEMBLE -- lie
    immédiatement le document créé à cette entité).

    ⚠️ Réponse Mayan `202 Accepted` -- le fichier est traité de façon
    ASYNCHRONE en arrière-plan côté Mayan, PAS immédiatement
    disponible juste après cet appel (voir mayan_client.py).

    Protégée par rights-api (#311) -- `groups` lu depuis
    `request.form` (multipart, jamais un corps JSON ici, même motif
    que glpi/api/app.py:import_excel_route, #294)."""
    allowed, error = _check_manage_right({"groups": request.form.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "'file' requis (multipart/form-data)"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "fichier vide ou nom de fichier manquant"}), 400

    name = (request.form.get("name") or upload.filename).strip()
    actor = request.form.get("actor") or None
    linked_type = request.form.get("linked_type")
    linked_id = request.form.get("linked_id")

    document_id = None
    try:
        type_id = mayan.get_default_document_type_id(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, MAYAN_DOCUMENT_TYPE_LABEL)
        document_id = mayan.create_document(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, type_id, name)
        mayan.upload_file(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id, upload.stream, upload.filename, is_new_version=False)
    except mayan.MayanError as exc:
        # Contexte tracable dans le log (fichier, entité liée,
        # demandeur) -- demandé explicitement : un message d'erreur
        # SEUL ("Création de document Mayan échouée : ...") ne dit ni
        # quel ticket, ni quel fichier, ni qui -- impossible à
        # rattacher à une action précise si plusieurs essais ont lieu
        # sur des tickets différents.
        context_bits = [f"fichier={upload.filename!r}"]
        if linked_type and linked_id:
            context_bits.append(f"lié à {linked_type}#{linked_id}")
        if actor:
            context_bits.append(f"demandé par {actor}")
        app.logger.warning("Création de document Mayan échouée (%s) : %s", ", ".join(context_bits), exc)
        if document_id is not None:
            # Le CONTENEUR document a été créé côté Mayan, mais
            # l'envoi du fichier a échoué juste après -- nettoyage
            # AUTOMATIQUE plutôt que de laisser une coquille vide
            # orpheline derrière (visible mais inutilisable dans
            # l'interface Mayan, "Pages: 0" -- rencontré RÉELLEMENT
            # lors du premier essai, #163). Best-effort : si le
            # nettoyage lui-même échoue, on le signale sans faire
            # échouer la réponse (l'erreur PRINCIPALE, celle de
            # l'envoi du fichier, reste ce qui compte pour la
            # personne).
            try:
                mayan.delete_document(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id)
            except mayan.MayanError as cleanup_exc:
                app.logger.warning("Nettoyage du document Mayan orphelin %s échoué : %s", document_id, cleanup_exc)
        return jsonify({"error": str(exc)}), 502

    link_error = None
    if linked_type and linked_id:
        _, link_error = store.create_link(DB_PATH, document_id, linked_type, linked_id, linked_by=actor)

    result = {"id": document_id, "name": name, "processing": "Fichier envoyé, traitement Mayan en cours (asynchrone)"}
    if link_error:
        result["link_warning"] = link_error
    return jsonify(result), 201


@app.route("/documents/<int:document_id>", methods=["GET"])
def get_document(document_id):
    doc = _document_with_versions(document_id)
    if doc is None:
        return jsonify({"error": "document introuvable"}), 404
    return jsonify(doc), 200


def _link_context(document_id):
    """Chaîne courte listant les entités liées à ce document (ex.
    "lié à ticket#42, ticket#43") -- utilisée pour enrichir les logs
    d'erreur sur des routes qui n'ont que `document_id` (add_version,
    delete, download) sans le linked_type/linked_id en paramètre
    direct (contrairement à create_document, qui les reçoit dans le
    corps de la requête). Chaîne vide si aucune liaison connue."""
    links = store.list_links(DB_PATH, document_id)
    if not links:
        return ""
    return "lié à " + ", ".join(f"{l['linked_type']}#{l['linked_id']}" for l in links)


@app.route("/documents/<int:document_id>", methods=["DELETE"])
def delete_document(document_id):
    """Protégée par rights-api (#311)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    try:
        mayan.delete_document(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id)
    except mayan.MayanError as exc:
        app.logger.warning("Suppression de document Mayan %s échouée (%s) : %s", document_id, _link_context(document_id), exc)
        return jsonify({"error": str(exc)}), 502
    store.delete_links_for_document(DB_PATH, document_id)
    return jsonify({"status": "ok"}), 200


@app.route("/documents/<int:document_id>/versions", methods=["POST"])
def add_version(document_id):
    """multipart/form-data : `file` (requis).

    Protégée par rights-api (#311) -- `groups` lu depuis
    `request.form`, même motif que create_document."""
    allowed, error = _check_manage_right({"groups": request.form.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "'file' requis (multipart/form-data)"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "fichier vide ou nom de fichier manquant"}), 400
    try:
        mayan.upload_file(MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id, upload.stream, upload.filename, is_new_version=True)
    except mayan.MayanError as exc:
        app.logger.warning(
            "Ajout de version Mayan pour %s échoué (fichier=%r, %s) : %s",
            document_id, upload.filename, _link_context(document_id), exc,
        )
        return jsonify({"error": str(exc)}), 502
    return jsonify({"status": "ok", "processing": "Fichier envoyé, traitement Mayan en cours (asynchrone)"}), 201


@app.route("/documents/<int:document_id>/versions/<version_spec>/download", methods=["GET"])
def download_version(document_id, version_spec):
    """`version_spec` : un entier (POSITION dans la liste des
    fichiers, triée par id Mayan croissant -- voir _sorted_files),
    OU "latest" (le dernier de cette même liste)."""
    try:
        files = _sorted_files(document_id)
    except mayan.MayanError as exc:
        app.logger.warning("Téléchargement échoué (liste des fichiers Mayan) pour %s (%s) : %s", document_id, _link_context(document_id), exc)
        return jsonify({"error": str(exc)}), 502
    if not files:
        return jsonify({"error": "aucune version disponible pour ce document"}), 404

    if version_spec == "latest":
        target_file = files[-1]
    else:
        try:
            index = int(version_spec) - 1
        except ValueError:
            return jsonify({"error": "'version_spec' doit être un entier ou 'latest'"}), 400
        if index < 0 or index >= len(files):
            return jsonify({"error": "version introuvable"}), 404
        target_file = files[index]

    try:
        content, content_type, filename = mayan.download_file(
            MAYAN_BASE, MAYAN_USERNAME, MAYAN_PASSWORD, document_id, target_file["id"],
        )
    except mayan.MayanError as exc:
        app.logger.warning("Téléchargement Mayan échoué pour %s (%s) : %s", document_id, _link_context(document_id), exc)
        return jsonify({"error": str(exc)}), 502

    return Response(
        content,
        mimetype=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/documents/<int:document_id>/links", methods=["POST"])
def create_link(document_id):
    """Corps JSON : {"linked_type": str, "linked_id": str|int,
    "actor": str (optionnel)}.

    Protégée par rights-api (#311)."""
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    linked_type = (body.get("linked_type") or "").strip()
    linked_id = body.get("linked_id")
    if not linked_type or linked_id is None or str(linked_id).strip() == "":
        return jsonify({"error": "'linked_type' et 'linked_id' requis"}), 400
    actor = (body.get("actor") or "").strip() or None
    link_id, error = store.create_link(DB_PATH, document_id, linked_type, linked_id, linked_by=actor)
    if error:
        return jsonify({"error": error}), 409
    return jsonify({"status": "ok", "id": link_id}), 201


@app.route("/documents/<int:document_id>/links/<int:link_id>", methods=["DELETE"])
def delete_link(document_id, link_id):
    """Protégée par rights-api (#311)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_link(DB_PATH, link_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py, livraison #145), même motif que les autres
# backends de ce projet -- ce service tourne avec 2 workers Gunicorn.
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


SERVICE_NAME = "ged-api"
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
