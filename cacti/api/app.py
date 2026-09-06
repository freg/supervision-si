"""
API Cacti — expose en LECTURE SEULE la base MySQL de l'application
Cacti existante (externe à ce projet) pour alimenter l'onglet Cacti du
frontend : racines indépendantes, arbre radial, vue JSON d'un nœud.

Mêmes garanties de lecture seule que les autres modules (voir
ipam/README.md pour le détail des trois niveaux de défense).

Particularité de ce schéma (version ancienne, ~ère Cacti 0.8.x —
MySQL 5.0.32-Debian_7etch12) : `graph_tree_items` N'A PAS de colonne
`parent` (ajoutée dans des versions plus récentes de Cacti). La
hiérarchie y est encodée dans `order_key`, une chaîne de longueur fixe
découpée en segments de 3 chiffres — un segment par niveau de
profondeur, complétée à droite par des segments "000" pour les
niveaux inutilisés (ex. "001003003001000...0" = position 1 à la
racine, puis 3e enfant, puis 3e enfant, puis 1er enfant : 4 niveaux).
Confirmé par des exports réels de la communauté Cacti, pas deviné.

Un item d'arbre de type "host" n'a pas ses graphes stockés comme
items d'arbre séparés — Cacti les affiche dynamiquement à partir de
`graph_local` au moment du rendu. Reproduit ici par une jointure
séparée, batchée en une seule requête (pas de N+1 par host).

Colonnes JAMAIS lues sur `host` : `snmp_community`, `snmp_password`,
`snmp_auth_protocol`, `snmp_priv_passphrase`, `snmp_context` —
identifiants d'authentification SNMP, jamais exposés.
"""
import os
import time

import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymemcache.client.base import Client as MemcacheClient
from pymemcache.exceptions import MemcacheError
# Import DÉFENSIF -- version_endpoint.py n'existe que dans le
# conteneur Docker réel (copié depuis shared/ au build) -- sans ce
# garde, tout test qui importe ce module directement casserait au
# chargement.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "cacti-api")

DB_HOST = os.environ.get("CACTI_DB_HOST", "")
DB_PORT = int(os.environ.get("CACTI_DB_PORT", "3306"))
DB_NAME = os.environ.get("CACTI_DB_NAME", "cacti")
DB_USER = os.environ.get("CACTI_DB_USER", "")
DB_PASSWORD = os.environ.get("CACTI_DB_PASSWORD", "")
DB_SSL = os.environ.get("CACTI_DB_SSL", "false").lower() == "true"
DB_CHARSET = os.environ.get("CACTI_DB_CHARSET", "utf8")

CACHE_TTL = int(os.environ.get("CACTI_CACHE_TTL", "60"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))

ORDER_KEY_SEGMENT_LEN = 3


def get_memcache_client():
    return MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


def cache_get(key):
    try:
        raw = get_memcache_client().get(key)
        return raw.decode("utf-8") if raw else None
    except MemcacheError:
        return None


def cache_set(key, value):
    try:
        get_memcache_client().set(key, value.encode("utf-8"), expire=CACHE_TTL)
    except MemcacheError:
        app.logger.warning("Memcached indisponible en écriture pour %s", key)


def get_connection():
    if not DB_HOST or not DB_USER:
        raise RuntimeError("CACTI_DB_HOST / CACTI_DB_USER non configurés (voir cacti/README.md)")
    # Traces DEBUG (livraison #224, audit rétroactif) -- RÈGLE
    # ABSOLUE : DB_PASSWORD n'apparaît JAMAIS dans une trace.
    app.logger.debug("get_connection : démarré (%s:%s, base=%s, jamais le mot de passe ici)", DB_HOST, DB_PORT, DB_NAME)
    start = time.monotonic()
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset=DB_CHARSET,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=15,
            ssl={"ssl": {}} if DB_SSL else None,
            autocommit=False,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("get_connection : ÉCHEC après %d ms -- %s", elapsed_ms, exc)
        raise
    elapsed_ms = int((time.monotonic() - start) * 1000)
    app.logger.debug("get_connection : succès en %d ms", elapsed_ms)
    return conn


def run_select(cur, sql, params=None):
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("run_select() n'accepte que des requêtes SELECT")
    cur.execute(sql, params or [])
    return cur.fetchall()


# ------------------------------------------------------------------
# order_key — fonctions PURES (aucun accès DB).
# ------------------------------------------------------------------

def parse_order_key(order_key):
    """'001003003001000...0' -> (1, 3, 3, 1) — segments de 3 chiffres,
    zéros de fin retirés. Défensif : une valeur mal formée (longueur
    non multiple de 3, caractères non numériques, vide) donne un tuple
    vide plutôt que de planter — l'item correspondant devient alors un
    enfant direct de la racine de l'arbre plutôt que d'être perdu."""
    if not order_key:
        return ()
    if len(order_key) % ORDER_KEY_SEGMENT_LEN != 0:
        return ()
    segments = [order_key[i:i + ORDER_KEY_SEGMENT_LEN] for i in range(0, len(order_key), ORDER_KEY_SEGMENT_LEN)]
    try:
        values = [int(s) for s in segments]
    except ValueError:
        return ()
    while values and values[-1] == 0:
        values.pop()
    return tuple(values)


# ------------------------------------------------------------------
# Assemblage de l'arbre — fonctions PURES (aucun accès DB), testables
# avec des jeux de lignes construits à la main.
# ------------------------------------------------------------------

def node_type_of_item(item):
    """Un item de graph_tree_items est un 'header' (dossier pur), un
    'host' (équipement, ses graphes seront rattachés séparément) ou un
    'graph' (graphe placé directement dans l'arbre)."""
    if item.get("local_graph_id"):
        return "graph"
    if item.get("host_id"):
        return "host"
    return "header"


def build_item_node(item):
    node_type = node_type_of_item(item)
    if node_type == "graph":
        name = item.get("graph_title") or item.get("title") or f"Graphe #{item['local_graph_id']}"
    elif node_type == "host":
        name = item.get("title") or item.get("host_description") or item.get("host_hostname") or f"Hôte #{item['host_id']}"
    else:
        name = item.get("title") or "(sans titre)"
    return {
        "id": item["id"],
        "type": node_type,
        "name": name,
        "children": [],
        "raw": {
            "id": item["id"],
            "title": item.get("title"),
            "hostId": item.get("host_id") or None,
            "hostDescription": item.get("host_description"),
            "hostHostname": item.get("host_hostname"),
            "hostDisabled": item.get("host_disabled") or None,
            "localGraphId": item.get("local_graph_id") or None,
            "graphTitle": item.get("graph_title"),
            "orderKey": item.get("order_key"),
        },
    }


def build_graph_leaf(graph_row):
    return {
        "id": f"g{graph_row['id']}",
        "type": "graph",
        "name": graph_row.get("title_cache") or f"Graphe #{graph_row['id']}",
        "children": [],
        "raw": {
            "id": graph_row["id"],
            "hostId": graph_row.get("host_id"),
            "graphTitle": graph_row.get("title_cache"),
        },
    }


def build_forest(trees, items, graphs_by_host):
    """
    trees          : lignes {id, name, sort_type}
    items          : lignes de graph_tree_items enrichies (host/graphe
                      déjà jointes — voir fetch_tree_items)
    graphs_by_host : {host_id: [lignes graph_local+titre]}

    Retourne (tree_nodes, root_ids). Chaque `graph_tree` est une
    racine indépendante (pas de nesting entre arbres). Un item dont
    order_key ne peut pas être rattaché à un parent existant (chemin
    vide, parent absent, doublon de chemin) devient enfant direct de
    la racine de SON arbre plutôt que d'être perdu.
    """
    tree_nodes = {}
    for row in trees:
        tid = row["id"]
        tree_nodes[tid] = {
            "id": tid,
            "type": "tree",
            "name": row["name"],
            "children": [],
            "raw": {"id": tid, "name": row.get("name"), "sortType": row.get("sort_type")},
        }

    items_by_tree = {}
    for item in items:
        items_by_tree.setdefault(item["graph_tree_id"], []).append(item)

    for tree_id, tree_items in items_by_tree.items():
        if tree_id not in tree_nodes:
            continue  # item orphelin d'un arbre qui n'existe plus (donnée incohérente) — pas de racine à y rattacher, ignoré proprement

        # Une seule passe : construit le nœud de chaque item, et
        # indexe par chemin pour retrouver les parents ensuite.
        node_by_id = {}
        node_by_path = {}
        for item in tree_items:
            node = build_item_node(item)
            path = parse_order_key(item.get("order_key"))
            node_by_id[item["id"]] = (node, path)
            if path and path not in node_by_path:  # premier vu gagne (doublon = donnée corrompue, jamais perdu, juste rattaché à la racine)
                node_by_path[path] = node

        for node, path in node_by_id.values():
            parent_path = path[:-1] if len(path) > 1 else None
            parent_node = node_by_path.get(parent_path) if parent_path else None
            if parent_node is not None and parent_node is not node:
                parent_node["children"].append(node)
            else:
                tree_nodes[tree_id]["children"].append(node)

            # Un item "host" affiche dynamiquement ses graphes dans
            # Cacti — jamais stockés comme items d'arbre séparés.
            if node["type"] == "host" and node["raw"]["hostId"] in graphs_by_host:
                for graph_row in graphs_by_host[node["raw"]["hostId"]]:
                    node["children"].append(build_graph_leaf(graph_row))

    return tree_nodes, list(tree_nodes.keys())


def count_descendants(node):
    """(nb nœuds structurels, nb graphes), racine exclue."""
    structural = leaves = 0
    for child in node["children"]:
        if child["type"] == "graph":
            leaves += 1
        else:
            structural += 1
        cs, cl = count_descendants(child)
        structural += cs
        leaves += cl
    return structural, leaves


# ------------------------------------------------------------------
# Accès DB — SELECT uniquement, colonnes volontairement restreintes.
# ------------------------------------------------------------------

def fetch_trees(cur):
    return run_select(cur, "SELECT id, name, sort_type FROM graph_tree")


def fetch_tree_items(cur):
    return run_select(
        cur,
        """SELECT gti.id, gti.graph_tree_id, gti.local_graph_id, gti.title, gti.host_id, gti.order_key,
                  h.description AS host_description, h.hostname AS host_hostname, h.disabled AS host_disabled,
                  gtg.title_cache AS graph_title
           FROM graph_tree_items gti
           LEFT JOIN host h ON h.id = gti.host_id
           LEFT JOIN graph_templates_graph gtg ON gtg.local_graph_id = gti.local_graph_id""",
    )


def fetch_graphs_by_host(cur):
    """Toutes les associations graphe<->hôte en une seule requête,
    regroupées en Python — évite une requête par host (N+1) quand un
    arbre contient de nombreux hôtes."""
    rows = run_select(
        cur,
        """SELECT gl.id, gl.host_id, gtg.title_cache
           FROM graph_local gl
           LEFT JOIN graph_templates_graph gtg ON gtg.local_graph_id = gl.id
           WHERE gl.host_id IS NOT NULL AND gl.host_id != 0""",
    )
    by_host = {}
    for row in rows:
        by_host.setdefault(row["host_id"], []).append(row)
    return by_host


def load_forest():
    conn = get_connection()
    try:
        cur = conn.cursor()
        trees = fetch_trees(cur)
        items = fetch_tree_items(cur)
        graphs_by_host = fetch_graphs_by_host(cur)
        return build_forest(trees, items, graphs_by_host)
    finally:
        conn.close()


# ------------------------------------------------------------------
# Routes — GET uniquement.
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- capture les WARNING et plus
# graves de CE service. Stocke dans Memcached (livraison #145, voir
# shared/log_buffer.py) -- PAS un tampon en memoire de processus : ce
# service tourne avec 2 workers Gunicorn (processus separes, memoire
# NON partagee), un tampon en memoire laissait des entrees invisibles
# selon le worker qui traitait la lecture suivante. Toujours
# volatile/borne (perdu seulement si Memcached lui-meme redemarre).
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "cacti-api"
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


@app.route("/health", methods=["GET"])
def health():
    if not DB_HOST or not DB_USER:
        return jsonify({"status": "degraded", "db": "non configuré"}), 200
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            run_select(cur, "SELECT 1")
        finally:
            conn.close()
        return jsonify({"status": "ok", "db": "reachable"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "degraded", "db": "unreachable", "error": str(exc)}), 200


@app.route("/roots", methods=["GET"])
def list_roots():
    """Racines indépendantes (les graph_tree eux-mêmes) — panneau de gauche."""
    cached = cache_get("cacti:roots")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        tree_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base Cacti injoignable : {exc}"}), 503

    roots = []
    for rid in root_ids:
        node = tree_nodes[rid]
        n_structural, n_graphs = count_descendants(node)
        roots.append({
            "id": node["id"],
            "name": node["name"],
            "description": None,
            "childSectionCount": n_structural,
            "subnetCount": n_graphs,
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set("cacti:roots", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/tree/<path:root_id>", methods=["GET"])
def get_tree(root_id):
    key_id = int(root_id) if root_id.lstrip("-").isdigit() else root_id

    cache_key = f"cacti:tree:{key_id}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        tree_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base Cacti injoignable : {exc}"}), 503

    if key_id not in root_ids:
        return jsonify({"error": f"'{root_id}' n'est pas une racine indépendante connue"}), 404

    import json as _json
    body = _json.dumps({"tree": tree_nodes[key_id]})
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
