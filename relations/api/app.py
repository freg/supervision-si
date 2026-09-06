"""
relations-api -- livraisons #335-338, backlog item 38 point 2 ("vue
relations" de la super tuile ENT). Voir hub/README.md pour le
cadrage complet du modèle, clarifié par la personne le 2026-09-04,
et relations/README.md pour le détail de chaque passe.

SERVICE SANS ÉTAT PROPRE -- contrairement à la quasi-totalité des
autres modules de ce projet, celui-ci ne possède AUCUNE base de
données à lui : il interroge les autres services (tickets-api,
ged-api, tasks-api, et pixel-grid-api pour les coordonnées connues)
à la volée à chaque requête, et calcule les relations en mémoire.
Jamais de cache/persistance -- le volume de données croisées reste
modeste, recalculer à chaque appel est largement suffisant tant que
ça ne devient pas un problème réel de performance.

QUATRE formes de relation DIRECTE construites, cumulées au fil des
passes (voir relation_engine.py pour le détail complet de chacune) :
- correspondance EXACTE de nom/label (#335)
- correspondance d'adresse IPv4 identique dans le texte (#336)
- proximité SÉMANTIQUE, au moins un mot significatif commun,
  technique déjà établie dans ce projet pour une tâche apparentée
  (tickets/api/suggestion_engine.py), jamais un modèle NLP réel (#337)
- proximité GÉOGRAPHIQUE, distance sous un seuil entre les
  coordonnées connues (via pixel-grid-api) des sites associés à
  deux entités -- SEULE forme parmi les quatre qui n'exige pas une
  correspondance exacte (#338). pixel-grid-api est une source
  OPTIONNELLE (contrairement aux trois autres, essentielles) --
  injoignable ou vide, la proximité géographique est simplement
  absente des résultats, jamais une erreur qui bloquerait les trois
  autres critères.

Relations INDIRECTES (deux éléments d'un même ENSEMBLE connecté par
des relations directes) : calculées via une recherche de composantes
connexes sur le graphe des relations directes -- voir
relation_engine.py. Devenues RÉELLEMENT possibles depuis #336 (une
entité porte désormais potentiellement plusieurs marqueurs
distincts, permettant un pont entre deux clusters).
"""
import logging
import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import entity_fetchers
import relation_engine

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "relations-api")

_log = logging.getLogger("relations_app")

TICKETS_API_URL = os.environ.get("TICKETS_API_INTERNAL_URL", "http://tickets-api:5000").rstrip("/")
GED_API_URL = os.environ.get("GED_API_INTERNAL_URL", "http://ged-api:5000").rstrip("/")
TASKS_API_URL = os.environ.get("TASKS_API_INTERNAL_URL", "http://tasks-api:5000").rstrip("/")
PIXEL_GRID_API_URL = os.environ.get("PIXEL_GRID_API_INTERNAL_URL", "http://pixel-grid-api:5000").rstrip("/")


def _fetch_geolocations_best_effort():
    """Contrairement aux trois autres sources (tickets/ged/tasks --
    ESSENTIELLES, sans elles rien à mettre en relation), pixel-grid
    est une AMÉLIORATION optionnelle -- injoignable ou vide, la
    proximité géographique est simplement absente des résultats,
    jamais une 502 qui empêcherait les trois autres critères de
    fonctionner (#338)."""
    try:
        return entity_fetchers.fetch_geolocations(PIXEL_GRID_API_URL)
    except entity_fetchers.FetchError as exc:
        _log.debug("_fetch_geolocations_best_effort : pixel-grid-api injoignable, proximité géographique ignorée -- %s", exc)
        return {}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/graph", methods=["GET"])
def graph():
    """Calcule et renvoie TOUTES les relations directes trouvées
    (tous types d'entités confondus) -- vue d'ensemble, jamais scopée
    à une entité précise. Peut être coûteux si le volume grandit
    beaucoup (voir docstring du module) -- accepté pour cette
    première passe."""
    try:
        entities = entity_fetchers.fetch_all_entities(TICKETS_API_URL, GED_API_URL, TASKS_API_URL)
    except entity_fetchers.FetchError as exc:
        return jsonify({"error": str(exc)}), 502
    geolocations = _fetch_geolocations_best_effort()
    direct = relation_engine.compute_direct_relations(entities, geolocations)
    return jsonify({
        "entity_count": len(entities),
        "direct_relations": [
            {"a": {"type": a[0], "id": a[1]}, "b": {"type": b[0], "id": b[1]}, "marker": marker}
            for (a, b, marker) in direct
        ],
    }), 200


@app.route("/relations", methods=["GET"])
def entity_relations():
    """Relations d'UNE entité précise -- query params `entity_type`
    (ticket|calendar_event|document|task) + `entity_id` (requis).
    Renvoie ses relations DIRECTES (avec le marqueur qui les justifie)
    et INDIRECTES (les autres membres du même ensemble connecté,
    hors relations directes déjà listées séparément)."""
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id")
    if not entity_type or not entity_id:
        return jsonify({"error": "'entity_type' et 'entity_id' requis"}), 400
    if entity_type not in entity_fetchers.KNOWN_ENTITY_TYPES:
        return jsonify({"error": f"entity_type doit être l'un de {sorted(entity_fetchers.KNOWN_ENTITY_TYPES)}"}), 400

    try:
        entities = entity_fetchers.fetch_all_entities(TICKETS_API_URL, GED_API_URL, TASKS_API_URL)
    except entity_fetchers.FetchError as exc:
        return jsonify({"error": str(exc)}), 502

    key = (entity_type, str(entity_id))
    if key not in entities:
        return jsonify({"error": f"entité {entity_type}#{entity_id} introuvable (ou hors du périmètre déjà chargé -- voir entity_fetchers.py)"}), 404

    direct = relation_engine.compute_direct_relations(entities, _fetch_geolocations_best_effort())
    result = relation_engine.relations_for(key, direct)
    return jsonify({
        "entity": {"type": entity_type, "id": entity_id, "label": entities[key]["label"]},
        "direct": [
            {"type": other[0], "id": other[1], "label": entities[other]["label"], "marker": marker}
            for (other, marker) in result["direct"]
        ],
        "indirect": [
            {"type": other[0], "id": other[1], "label": entities[other]["label"]}
            for other in result["indirect"]
        ],
    }), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# Manquait ici jusqu'à cette livraison (#351, backlog item 8) --
# trouvé en vérifiant que memory-api archive réellement TOUS les
# services du projet.
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


SERVICE_NAME = "relations-api"
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
    app.run(host="0.0.0.0", port=5000, debug=True)
