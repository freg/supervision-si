"""
API Recherche OwnCloud — expose en LECTURE SEULE l'instance
Elasticsearch alimentée par l'app ownCloud "search_elastic"
(https://github.com/owncloud/search_elastic), externe à ce projet.

Pas de connexion base de données ici — Elasticsearch EST la source,
interrogée directement en HTTP. Utilise `requests` brut plutôt que le
client Python officiel `elasticsearch` : ce client exige une version
majeure alignée avec le serveur, et `search_elastic` requiert
spécifiquement Elasticsearch 5.6.x (confirmé via sa documentation et
l'image Docker `extremeshok/docker-elasticsearch-owncloud`, qui
embarque le plugin `ingest-attachment` pour l'extraction Tika des
PDF/Office) — un client récent (8.x) casserait sur un serveur aussi
ancien. `requests` sur l'API REST HTTP reste compatible quelle que
soit la version du serveur.

PRINCIPE CENTRAL : le schéma réel de l'index (noms de champs) n'est
PAS supposé ici. Il est découvert à l'exécution via `/mapping`
(`GET <index>/_mapping` côté Elasticsearch) — aucune donnée de
"search_elastic" n'a pu être inspectée depuis cet environnement (pas
d'accès réseau, l'index n'existe même pas encore côté personne au
moment où ceci est écrit). Le frontend construit son sélecteur de
champs à partir de cette réponse, jamais d'une liste codée en dur.

GARANTIE DE SÉCURITÉ : `/search` n'accepte JAMAIS une requête
Elasticsearch brute depuis le frontend. Elle reçoit une spec
structurée (liste de clauses {field, operator, value} + combinateur
AND/OR), validée contre le mapping réel (champ inexistant -> rejeté),
et SEULEMENT alors traduite côté serveur en DSL `bool` — même principe
que `run_select()` dans les autres modules (jamais de SQL/DSL arbitraire
transmis tel quel). Aucune requête de type `script`/`script_score`
n'est atteignable par construction : le traducteur n'en génère jamais.
"""
import os
import time

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymemcache.client.base import Client as MemcacheClient
from pymemcache.exceptions import MemcacheError

app = Flask(__name__)
CORS(app)

ES_URL = os.environ.get("ELASTICSEARCH_URL", "").rstrip("/")
ES_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "").strip()
ES_TIMEOUT_SECONDS = float(os.environ.get("ELASTICSEARCH_TIMEOUT_SECONDS", "10"))

CACHE_TTL = int(os.environ.get("SEARCH_CACHE_TTL", "30"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))

# Opérateurs autorisés -> constructeur de clause DSL. Volontairement
# restreint (pas de passthrough) ; chaque entrée sait comment se
# construire à partir d'un champ + d'une valeur, jamais de DSL fourni
# par l'appelant.
ALLOWED_OPERATORS = {
    "contains": lambda field, value: {"match": {field: value}},
    "phrase": lambda field, value: {"match_phrase": {field: value}},
    "equals": lambda field, value: {"term": {field: value}},
    "exists": lambda field, value: {"exists": {"field": field}},
    "gte": lambda field, value: {"range": {field: {"gte": value}}},
    "lte": lambda field, value: {"range": {field: {"lte": value}}},
}

MAX_RESULT_SIZE = 100
MAX_CLAUSES = 20


# ------------------------------------------------------------------
# Cache (memcache) — même convention que les autres modules.
# ------------------------------------------------------------------

def get_memcache_client():
    return MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


def cache_get(key):
    try:
        raw = get_memcache_client().get(key)
        return raw.decode("utf-8") if raw else None
    except MemcacheError:
        return None


def cache_set(key, value, ttl=None):
    try:
        get_memcache_client().set(key, value.encode("utf-8"), expire=ttl if ttl is not None else CACHE_TTL)
    except MemcacheError:
        app.logger.warning("Memcached indisponible en écriture pour %s", key)


# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached
# (livraison #145, voir shared/log_buffer.py), même motif que les 14
# autres backends de ce projet -- PAS un tampon en memoire de
# processus, ce service tourne avec 2 workers Gunicorn.
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "owncloud-search-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
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


# ------------------------------------------------------------------
# Accès Elasticsearch — HTTP brut, jamais le client `elasticsearch`
# (voir en-tête du module).
# ------------------------------------------------------------------

def es_configured():
    return bool(ES_URL and ES_INDEX)


def es_get(path, timeout=None):
    app.logger.debug("es_get : démarré -- %s", path)
    start = time.monotonic()
    try:
        response = requests.get(f"{ES_URL}/{path.lstrip('/')}", timeout=timeout or ES_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("es_get : ÉCHEC après %d ms -- %s -- %s", elapsed_ms, path, exc)
        raise
    elapsed_ms = int((time.monotonic() - start) * 1000)
    app.logger.debug("es_get : succès en %d ms -- %s", elapsed_ms, path)
    return response.json()


def es_post(path, body, timeout=None):
    app.logger.debug("es_post : démarré -- %s", path)
    start = time.monotonic()
    try:
        response = requests.post(
            f"{ES_URL}/{path.lstrip('/')}", json=body, timeout=timeout or ES_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("es_post : ÉCHEC après %d ms -- %s -- %s", elapsed_ms, path, exc)
        raise
    elapsed_ms = int((time.monotonic() - start) * 1000)
    app.logger.debug("es_post : succès en %d ms -- %s", elapsed_ms, path)
    return response.json()


# ------------------------------------------------------------------
# Mise en forme — fonctions PURES, testables sans Elasticsearch réel.
# ------------------------------------------------------------------

def parse_mapping_response(data, index_name):
    """data : réponse brute de `GET <index>/_mapping`. Retourne une
    liste plate [{name, type}] triée par nom — ignore volontairement
    les métadonnées internes ES (_meta, dynamic_templates...). Gère
    aussi bien le format ES 5.x/6.x (avec "mapping types" imbriqués,
    ex. {index: {mappings: {doc: {properties: {...}}}}}) que le format
    ES 7+ (types supprimés, {index: {mappings: {properties: {...}}}})
    — jamais supposé lequel sans vérifier, pour rester correct quelle
    que soit la version réellement déployée. Ne lève jamais : toute
    forme inattendue -> liste vide plutôt qu'une exception."""
    if not isinstance(data, dict):
        return []
    index_data = data.get(index_name)
    if not isinstance(index_data, dict):
        # un seul index dans la reponse mais sous un nom different
        # (alias, wildcard...) -> on prend le premier disponible
        values = [v for v in data.values() if isinstance(v, dict)]
        index_data = values[0] if values else None
    if not isinstance(index_data, dict):
        return []

    mappings = index_data.get("mappings")
    if not isinstance(mappings, dict):
        return []

    properties = mappings.get("properties")
    if not isinstance(properties, dict):
        # format avec "mapping type" intermediaire (ES 5.x/6.x) :
        # {mappings: {doc: {properties: {...}}}}
        for value in mappings.values():
            if isinstance(value, dict) and isinstance(value.get("properties"), dict):
                properties = value["properties"]
                break
    if not isinstance(properties, dict):
        return []

    fields = []
    for name, spec in properties.items():
        field_type = spec.get("type") if isinstance(spec, dict) else None
        fields.append({"name": name, "type": field_type or "object"})
    fields.sort(key=lambda f: f["name"])
    return fields


def build_query_clause(clause, known_field_names):
    """Un {field, operator, value} valide -> une clause DSL ES, ou None
    si invalide (champ inconnu, opérateur inconnu, valeur manquante
    pour un opérateur qui en a besoin) — jamais d'exception, l'appelant
    décide quoi faire des clauses invalides (les compter/les signaler)."""
    if not isinstance(clause, dict):
        return None
    field = clause.get("field")
    operator = clause.get("operator")
    value = clause.get("value")

    if field not in known_field_names:
        return None
    builder = ALLOWED_OPERATORS.get(operator)
    if builder is None:
        return None
    if operator != "exists" and (value is None or value == ""):
        return None

    return builder(field, value)


def build_search_body(clauses, known_field_names, combinator="AND", size=20, from_=0):
    """Traduit une liste de clauses (déjà validées individuellement
    par build_query_clause) en corps de requête `_search` ES —
    `bool.must` si AND, `bool.should` + `minimum_should_match: 1` si
    OR. Aucune clause valide -> `match_all` (recherche non filtrée),
    jamais une requête vide qui échouerait côté ES."""
    dsl_clauses = [c for c in (build_query_clause(cl, known_field_names) for cl in clauses) if c]

    if not dsl_clauses:
        query = {"match_all": {}}
    elif combinator == "OR":
        query = {"bool": {"should": dsl_clauses, "minimum_should_match": 1}}
    else:
        query = {"bool": {"must": dsl_clauses}}

    return {
        "query": query,
        "size": max(0, min(size, MAX_RESULT_SIZE)),
        "from": max(0, from_),
        "highlight": {"fields": {"*": {}}},
    }


def format_search_results(data):
    """Réponse brute `_search` ES -> forme simplifiée pour le
    frontend. N'expose que ce qu'ES a renvoyé (aucune donnée
    supplémentaire) ; `source` est transmis tel quel — c'est
    `search_elastic` (pas ce module) qui décide de ce qu'il indexe,
    et donc de ce qui peut apparaître ici. Ne lève jamais."""
    if not isinstance(data, dict):
        return {"total": 0, "hits": []}
    hits_block = data.get("hits")
    if not isinstance(hits_block, dict):
        return {"total": 0, "hits": []}

    total_raw = hits_block.get("total", 0)
    total = total_raw.get("value", 0) if isinstance(total_raw, dict) else total_raw

    hits = []
    for hit in hits_block.get("hits", []) if isinstance(hits_block.get("hits"), list) else []:
        if not isinstance(hit, dict):
            continue
        hits.append({
            "id": hit.get("_id"),
            "score": hit.get("_score"),
            "source": hit.get("_source", {}),
            "highlight": hit.get("highlight", {}),
        })
    return {"total": total, "hits": hits}


# ------------------------------------------------------------------
# Routes — GET/POST, toujours en lecture seule côté Elasticsearch
# (aucune route de ce fichier n'écrit ni n'indexe quoi que ce soit).
# ------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    if not es_configured():
        return jsonify({"status": "degraded", "es": "non configuré"}), 200
    try:
        es_get("/_cluster/health")
        return jsonify({"status": "ok", "es": "reachable"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "degraded", "es": "unreachable", "error": str(exc)}), 200


@app.route("/mapping", methods=["GET"])
def mapping():
    if not es_configured():
        return jsonify({"error": "ELASTICSEARCH_URL / ELASTICSEARCH_INDEX non configurés (voir README)"}), 503
    cache_key = f"search:mapping:{ES_INDEX}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")
    try:
        data = es_get(f"/{ES_INDEX}/_mapping")
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Elasticsearch injoignable : {exc}"}), 503

    fields = parse_mapping_response(data, ES_INDEX)
    import json as _json
    body = _json.dumps({"index": ES_INDEX, "fields": fields})
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


@app.route("/search", methods=["POST"])
def search():
    if not es_configured():
        return jsonify({"error": "ELASTICSEARCH_URL / ELASTICSEARCH_INDEX non configurés (voir README)"}), 503

    body_in = request.get_json(silent=True) or {}
    clauses = body_in.get("clauses")
    if not isinstance(clauses, list):
        return jsonify({"error": "'clauses' (liste) requis"}), 400
    if len(clauses) > MAX_CLAUSES:
        return jsonify({"error": f"trop de clauses (max {MAX_CLAUSES})"}), 400
    combinator = "OR" if body_in.get("combinator") == "OR" else "AND"
    size = body_in.get("size", 20)
    from_ = body_in.get("from", 0)
    if not isinstance(size, int) or not isinstance(from_, int):
        return jsonify({"error": "'size'/'from' doivent être des entiers"}), 400

    # Le mapping réel fait toujours foi pour valider les champs — une
    # clause visant un champ absent du mapping est silencieusement
    # ignorée par build_query_clause, jamais transmise telle quelle.
    try:
        mapping_data = es_get(f"/{ES_INDEX}/_mapping")
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Elasticsearch injoignable : {exc}"}), 503
    known_fields = {f["name"] for f in parse_mapping_response(mapping_data, ES_INDEX)}

    search_body = build_search_body(clauses, known_fields, combinator, size, from_)
    try:
        raw = es_post(f"/{ES_INDEX}/_search", search_body)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Elasticsearch injoignable : {exc}"}), 503

    result = format_search_results(raw)
    return jsonify(result), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
