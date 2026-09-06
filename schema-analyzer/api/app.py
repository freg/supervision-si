"""
schema-analyzer -- module d'analyse de schémas hérités (livraison
#151-#154, backlog BACKLOG.md #5). Décision d'architecture prise avec
la personne AVANT de coder : nouveau module dédié (onglet + API), qui
s'appuie sur dba-api pour la couche accès (connexions MySQL/Postgres/
SQLite déjà gérées là-bas, dump mysqldump déjà importable) plutôt que
de la reconstruire -- voir schema_client.py.

/analyze reste un DIAGNOSTIC EN LECTURE, jamais persisté (relit le
schéma en direct à chaque appel). Les relations, elles, SONT
persistées (livraison #152, relations_store.py) -- "proposition
automatique et validation manuelle" demandée explicitement : une
proposition qu'on ne peut ni accepter ni corriger ni rejeter
durablement n'est qu'un diagnostic, pas un éditeur. Le pont entre les
deux : POST /relations/import-proposals relance l'analyse et
ENREGISTRE chaque proposition (status="proposed") -- jamais
automatique, une action explicite.

GET /relations/graph (livraison #154) exporte les tables + relations
CONFIRMÉES en JSON ou XML -- voir graph_export.py.
"""
import logging
import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from schema_client import fetch_full_schema, fetch_tables_and_columns, execute_sql, DbaApiError
from relation_detector import detect_name_based_relations, guess_referenced_table, get_primary_key
from list_detector import detect_list_like_column
from graph_export import build_graph, graph_to_xml
import relations_store
import relation_validator

# Import DÉFENSIF -- version_endpoint.py n'existe que dans l'image
# Docker construite (copié au build, voir Dockerfile), jamais présent
# lors d'un test direct de ce fichier hors conteneur.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "schema-analyzer")

_log = logging.getLogger("schema_analyzer_app")

# Branchement rights-api -- livraison #319, item 38 du backlog.
# /analyze et /relations/validate sont EXPLICITEMENT documentées
# comme lecture pure (aucun effet de bord, voir leurs docstrings) --
# jamais gardées. Gardé UNIQUEMENT sur les 4 routes qui PERSISTENT
# des relations (create/update/delete + import en masse des
# propositions) -- une relation trafiquée pourrait faire croire à
# tort qu'une colonne référence une autre, source d'erreurs de
# compréhension pour quiconque s'appuie ensuite sur ce schéma déclaré.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-318) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "schema-analyzer-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur schema-analyzer-api requis (groupe admin_hub, ou un octroi explicite)"

# Adresse INTERNE au réseau Docker -- dba-api et schema-analyzer
# vivent dans le MÊME docker-compose.yml (stack "main"), jamais via
# tls-proxy (trafic conteneur-à-conteneur, pas navigateur -- même
# motif que KEYCLOAK_INTERNAL_URL dans prefs-api).
DBA_API_BASE = os.environ.get("DBA_API_BASE", "http://dba-api:5000")
DEFAULT_SAMPLE_SIZE = int(os.environ.get("SCHEMA_ANALYZER_SAMPLE_SIZE", "20"))

# Persistance des relations (livraison #152) -- même motif que
# dba-api/prefs-api (DB_PATH + ensure_schema au démarrage).
DB_PATH = os.environ.get("SCHEMA_ANALYZER_DB_PATH", "/data/schema-analyzer.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
relations_store.ensure_schema(DB_PATH)


def _build_proposals(tables, samples):
    """Cœur PARTAGÉ entre /analyze et /relations/import-proposals --
    calcule les relations proposées (clés étrangères classiques ET
    colonnes-listes) à partir d'un schéma déjà introspecté. Renvoie
    (proposed_relations, list_like_columns) dans le même format que
    /analyze renvoyait déjà avant #152 (non-régression)."""
    table_names = list(tables.keys())
    proposed_relations = detect_name_based_relations(tables)

    list_like_columns = []
    for tname, cols_samples in samples.items():
        for cname, values in cols_samples.items():
            result = detect_list_like_column(values)
            if not result["is_list_like"]:
                continue
            entry = {
                "table": tname,
                "column": cname,
                "ratio": result["ratio"],
                "sample_size": result["sample_size"],
            }
            guessed_table = guess_referenced_table(cname, table_names)
            if guessed_table and guessed_table != tname:
                entry["guessed_referenced_table"] = guessed_table
            list_like_columns.append(entry)

    return proposed_relations, list_like_columns


def _fetch_and_build(connection_id, database, sample_size):
    """Récupère le schéma via dba-api ET construit les propositions --
    factorisé car utilisé identiquement par /analyze et
    /relations/import-proposals. Lève DbaApiError (laissée remonter,
    chaque appelant HTTP la traduit lui-même)."""
    schema = fetch_full_schema(DBA_API_BASE, connection_id, database=database, sample_size=sample_size)
    tables = schema["tables"]
    samples = schema["samples"]
    proposed_relations, list_like_columns = _build_proposals(tables, samples)
    return tables, proposed_relations, list_like_columns


@app.route("/analyze", methods=["POST"])
def analyze():
    """Corps : {"connection_id": int, "database": str (optionnel),
    "sample_size": int (optionnel)}. Récupère le schéma via dba-api,
    propose des relations par nom de champs (clés étrangères
    classiques ET colonnes-listes, ex. "sites": "1,2,5"). Connexion
    inconnue/injoignable côté dba-api -- 502 avec le message
    d'erreur réel (jamais un plantage silencieux), 400 si
    connection_id manquant. Diagnostic EN LECTURE -- rien n'est
    enregistré ici, voir POST /relations/import-proposals pour ça."""
    body = request.get_json(silent=True) or {}
    connection_id = body.get("connection_id")
    if not connection_id:
        return jsonify({"error": "'connection_id' requis"}), 400
    database = body.get("database")
    sample_size = int(body.get("sample_size") or DEFAULT_SAMPLE_SIZE)

    try:
        tables, proposed_relations, list_like_columns = _fetch_and_build(connection_id, database, sample_size)
    except DbaApiError as exc:
        app.logger.warning("Analyse échouée pour la connexion %s : %s", connection_id, exc)
        return jsonify({"error": str(exc)}), 502

    return jsonify({
        "connection_id": connection_id,
        "database": database,
        "tables": {tname: {"columns": tinfo["columns"]} for tname, tinfo in tables.items()},
        "proposed_relations": proposed_relations,
        "list_like_columns": list_like_columns,
    }), 200


# ------------------------------------------------------------------
# Éditeur de relations (livraison #152) -- CRUD sur les relations
# PERSISTÉES (voir relations_store.py), plus l'action d'import qui
# fait le pont avec /analyze ci-dessus. AUCUNE vérification de rôle
# côté serveur (même posture que /external-links dans prefs-api) --
# le hub gère l'accès à l'écran d'administration côté client.
# ------------------------------------------------------------------
VALID_RELATION_TYPES = relations_store.VALID_RELATION_TYPES
VALID_STATUSES = relations_store.VALID_STATUSES


@app.route("/relations", methods=["GET"])
def list_relations():
    """Query params : connection_id (requis), database (optionnel --
    omis = TOUTES les relations de cette connexion, toutes bases
    confondues)."""
    connection_id = request.args.get("connection_id", type=int)
    if not connection_id:
        return jsonify({"error": "paramètre 'connection_id' requis"}), 400
    database = request.args.get("database")
    return jsonify(relations_store.list_relations(DB_PATH, connection_id, database=database)), 200


@app.route("/relations", methods=["POST"])
def create_relation():
    """Création MANUELLE d'une relation -- source="manual",
    status="confirmed" par défaut (une personne qui la saisit
    directement EST la validation, contrairement à une proposition
    automatique). Corps : {"connection_id", "database" (optionnel),
    "from_table", "from_column", "to_table", "to_column",
    "relation_type" (optionnel, défaut "foreign_key"), "actor"
    (optionnel, login de la personne)}.

    Protégée par rights-api (#319)."""
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    connection_id = body.get("connection_id")
    from_table = (body.get("from_table") or "").strip()
    from_column = (body.get("from_column") or "").strip()
    to_table = (body.get("to_table") or "").strip()
    to_column = (body.get("to_column") or "").strip()
    if not connection_id or not from_table or not from_column or not to_table or not to_column:
        return jsonify({"error": "'connection_id', 'from_table', 'from_column', 'to_table', 'to_column' requis"}), 400
    relation_type = (body.get("relation_type") or "foreign_key").strip()
    if relation_type not in VALID_RELATION_TYPES:
        return jsonify({"error": f"'relation_type' doit être l'un de {VALID_RELATION_TYPES}"}), 400
    database = body.get("database")
    created_by = (body.get("actor") or "").strip() or None

    new_id, error = relations_store.create_relation(
        DB_PATH, connection_id, database, from_table, from_column, to_table, to_column,
        relation_type=relation_type, status="confirmed", source="manual", confidence=None,
        created_by=created_by,
    )
    if error:
        return jsonify({"error": error}), 409
    return jsonify({"status": "ok", "id": new_id}), 201


@app.route("/relations/<int:relation_id>", methods=["PUT"])
def update_relation(relation_id):
    """Mise à jour PARTIELLE -- seuls les champs fournis sont
    modifiés. Sert aussi bien à CORRIGER une proposition (from_table/
    from_column/to_table/to_column/relation_type) qu'à la VALIDER/la
    REJETER (status). `status` invalide -- 400, jamais silencieusement
    ignoré.

    Protégée par rights-api (#319)."""
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    fields = {}
    for key in ("from_table", "from_column", "to_table", "to_column"):
        if key in body:
            value = (body[key] or "").strip()
            if not value:
                return jsonify({"error": f"'{key}' ne peut pas être vidé"}), 400
            fields[key] = value
    if "relation_type" in body:
        value = (body["relation_type"] or "").strip()
        if value not in VALID_RELATION_TYPES:
            return jsonify({"error": f"'relation_type' doit être l'un de {VALID_RELATION_TYPES}"}), 400
        fields["relation_type"] = value
    if "status" in body:
        value = (body["status"] or "").strip()
        if value not in VALID_STATUSES:
            return jsonify({"error": f"'status' doit être l'un de {VALID_STATUSES}"}), 400
        fields["status"] = value

    ok, error = relations_store.update_relation(DB_PATH, relation_id, **fields)
    if not ok:
        return jsonify({"error": error}), 404 if error == "introuvable" else 409
    return jsonify({"status": "ok"}), 200


@app.route("/relations/<int:relation_id>", methods=["DELETE"])
def delete_relation(relation_id):
    """Protégée par rights-api (#319)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = relations_store.delete_relation(DB_PATH, relation_id)
    return jsonify({"status": "ok", "deleted": deleted}), 200


@app.route("/relations/import-proposals", methods=["POST"])
def import_proposals():
    """Corps : {"connection_id": int, "database": str (optionnel),
    "sample_size": int (optionnel), "actor": str (optionnel)}. Relance
    l'analyse (même logique que /analyze) et ENREGISTRE chaque
    proposition -- relations classiques ET colonnes-listes (celles
    avec une table cible devinée uniquement -- une colonne-liste SANS
    cible devinée n'est qu'un SIGNALEMENT dans /analyze, rien à
    enregistrer comme relation tant qu'aucune table n'est identifiée).

    Les relations déjà connues (même si rejetées/confirmées entre
    temps) ne sont JAMAIS écrasées -- SIGNALÉ explicitement dans la
    réponse (`skipped`, avec le statut ACTUEL de chacune), pas
    seulement déductible d'un delta de compteur -- demandé
    explicitement par la personne après la livraison initiale de cet
    endpoint (#152).

    Protégée par rights-api (#319)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    connection_id = body.get("connection_id")
    if not connection_id:
        return jsonify({"error": "'connection_id' requis"}), 400
    database = body.get("database")
    sample_size = int(body.get("sample_size") or DEFAULT_SAMPLE_SIZE)
    created_by = (body.get("actor") or "").strip() or None

    try:
        tables, proposed_relations, list_like_columns = _fetch_and_build(connection_id, database, sample_size)
    except DbaApiError as exc:
        app.logger.warning("Import de propositions échoué pour la connexion %s : %s", connection_id, exc)
        return jsonify({"error": str(exc)}), 502

    candidates = list(proposed_relations)
    for entry in list_like_columns:
        guessed = entry.get("guessed_referenced_table")
        if not guessed:
            continue  # aucune cible devinée -- rien à enregistrer comme relation
        candidates.append({
            "from_table": entry["table"],
            "from_column": entry["column"],
            "to_table": guessed,
            "to_column": get_primary_key(tables, guessed) or "id",
            "relation_type": "list",
            "confidence": "moyenne",  # une colonne-liste devinée par nom reste moins sûre qu'une FK classique
        })

    result = relations_store.import_proposals(DB_PATH, connection_id, database, candidates, created_by=created_by)
    return jsonify({
        "status": "ok",
        "imported": result["imported"],
        "skipped": result["skipped"],
        "candidates_seen": len(candidates),
    }), 200


@app.route("/relations/graph", methods=["GET"])
def relations_graph():
    """Query params : connection_id (requis), database (optionnel),
    format ("json" ou "xml", défaut "json"). Exporte les tables
    (noeuds) et les relations CONFIRMÉES uniquement (arêtes) -- jamais
    les propositions "proposed"/"rejected", qui ne représentent pas
    encore un schéma validé. Voir graph_export.py."""
    connection_id = request.args.get("connection_id", type=int)
    if not connection_id:
        return jsonify({"error": "paramètre 'connection_id' requis"}), 400
    database = request.args.get("database")
    fmt = (request.args.get("format") or "json").strip().lower()
    if fmt not in ("json", "xml"):
        return jsonify({"error": "'format' doit être 'json' ou 'xml'"}), 400

    try:
        tables = fetch_tables_and_columns(DBA_API_BASE, connection_id, database=database)
    except DbaApiError as exc:
        app.logger.warning("Export du graphe échoué pour la connexion %s : %s", connection_id, exc)
        return jsonify({"error": str(exc)}), 502

    relations = relations_store.list_relations(DB_PATH, connection_id, database=database)
    graph = build_graph(connection_id, database, tables, relations)

    if fmt == "xml":
        return graph_to_xml(graph), 200, {"Content-Type": "application/xml; charset=utf-8"}
    return jsonify(graph), 200


@app.route("/relations/validate", methods=["POST"])
def validate_relation_route():
    """Confirme (ou infirme) une relation CANDIDATE contre les VRAIES
    données (livraison #241, backlog #5 -- demandé explicitement :
    "à partir du schéma et des données... pour conforter la
    relation"). Corps : {"connection_id", "database" (optionnel),
    "from_table", "from_column", "to_table", "to_column",
    "relation_type" (optionnel, défaut "foreign_key"), "sample_size"
    (optionnel, défaut 200)}.

    AUCUN effet de bord sur les relations stockées -- pure lecture,
    voir `relation_validator.py`. La personne décide ENSUITE, au vu
    du résultat, de confirmer/rejeter via les routes `/relations`
    existantes -- jamais une confirmation automatique même à 100% de
    couverture (une coïncidence statistique n'est pas une certitude
    -- toujours une décision humaine, même principe que
    `relation_detector.py`)."""
    body = request.get_json(silent=True) or {}
    connection_id = body.get("connection_id")
    from_table = (body.get("from_table") or "").strip()
    from_column = (body.get("from_column") or "").strip()
    to_table = (body.get("to_table") or "").strip()
    to_column = (body.get("to_column") or "").strip()
    if not connection_id or not from_table or not from_column or not to_table or not to_column:
        return jsonify({"error": "'connection_id', 'from_table', 'from_column', 'to_table', 'to_column' requis"}), 400
    relation_type = (body.get("relation_type") or "foreign_key").strip()
    database = body.get("database")
    sample_size = int(body.get("sample_size") or 200)

    def executor(sql):
        return execute_sql(DBA_API_BASE, connection_id, sql, database=database)

    try:
        result = relation_validator.validate_relation(
            executor, from_table, from_column, to_table, to_column,
            relation_type=relation_type, sample_size=sample_size,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except DbaApiError as exc:
        app.logger.warning(
            "Validation de relation échouée (%s.%s -> %s.%s) : %s",
            from_table, from_column, to_table, to_column, exc,
        )
        return jsonify({"error": str(exc)}), 502

    return jsonify(result), 200


# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py, livraison #145), même motif que les 15 autres
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


SERVICE_NAME = "schema-analyzer-api"
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
