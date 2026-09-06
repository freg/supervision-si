"""
API TTS-GU — expose en LECTURE SEULE la base MySQL de "tts-gu", un
clone/fork de l'outil de tickets "optick3" dont le schéma a divergé :
contrairement à optick3, il n'y a ICI ni table `tts_parent_category`
ni colonne `id_parent` sur `tts_category` (catégorisation à plat).

Racines indépendantes retenues en conséquence : les DOMAINES
(`tts_domains`, ids uniques — contrairement à `domain_id` sur les
catégories/tickets qui est un tag) plutôt que des familles qui
n'existent pas dans ce schéma. Une catégorie peut être taguée de
plusieurs domaines (`tts_category.domain_id` est un SET) : elle
apparaît alors sous CHAQUE domaine racine correspondant, avec un
comptage de tickets propre à chaque domaine (`tts_tickets.domain_id`
est un entier simple, non ambigu — contrairement au tag de la
catégorie).

Mêmes garanties de lecture seule qu'ipam/api/app.py et
optick/api/app.py (voir ces fichiers) : aucune route d'écriture,
run_select() qui refuse tout ce qui n'est pas SELECT, et surtout un
compte MySQL limité au privilège SELECT côté serveur (voir
tts-gu/README.md).
"""
import os
import time

import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymemcache.client.base import Client as MemcacheClient
from pymemcache.exceptions import MemcacheError
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "tts-gu-api")

DB_HOST = os.environ.get("TTSGU_DB_HOST", "")
DB_PORT = int(os.environ.get("TTSGU_DB_PORT", "3306"))
DB_NAME = os.environ.get("TTSGU_DB_NAME", "optick3")
DB_USER = os.environ.get("TTSGU_DB_USER", "")
DB_PASSWORD = os.environ.get("TTSGU_DB_PASSWORD", "")
DB_SSL = os.environ.get("TTSGU_DB_SSL", "false").lower() == "true"
DB_CHARSET = os.environ.get("TTSGU_DB_CHARSET", "utf8")

CACHE_TTL = int(os.environ.get("TTSGU_CACHE_TTL", "60"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


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
        raise RuntimeError("TTSGU_DB_HOST / TTSGU_DB_USER non configurés (voir tts-gu/README.md)")
    # Traces DEBUG (livraison #225, audit rétroactif) -- RÈGLE
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
# Assemblage de l'arbre — fonctions PURES.
# ------------------------------------------------------------------

def decode_domain_ids(raw_value):
    """Colonne MySQL SET "1,3,5" (ou vide) -> liste d'ids entiers."""
    if not raw_value:
        return []
    return [int(x) for x in str(raw_value).split(",") if x.strip().isdigit()]


def build_forest(domains, categories, ticket_counts_by_domain, ticket_totals):
    """
    domains               : lignes {id, label}
    categories            : lignes {id, name, color, domain_id (SET brut)}
    ticket_counts_by_domain : {(category_id, domain_id): {"total","open"}}
                              — comptage SCOPÉ à un domaine (tts_tickets.domain_id
                              est un entier simple, donc sans ambiguïté).
    ticket_totals          : {category_id: {"total","open"}} tous domaines
                              confondus — utilisé seulement pour les
                              catégories orphelines (aucun domaine connu).

    Une catégorie taguée de plusieurs domaines apparaît sous CHAQUE
    domaine racine correspondant (autant de nœuds distincts, un par
    domaine, chacun avec son propre comptage). Une catégorie dont
    AUCUN domaine tagué ne correspond à un domaine connu est regroupée
    sous une racine synthétique "_orphans", jamais perdue.
    """
    domain_nodes = {}
    for row in domains:
        did = row["id"]
        domain_nodes[did] = {
            "id": did,
            "type": "domain",
            "name": row.get("label") or f"Domaine {did}",
            "children": [],
            "raw": {"id": did, "label": row.get("label")},
        }

    matched_category_ids = set()
    for row in categories:
        cid = row["id"]
        tagged_domain_ids = decode_domain_ids(row.get("domain_id"))
        for did in tagged_domain_ids:
            if did in domain_nodes:
                matched_category_ids.add(cid)
                counts = ticket_counts_by_domain.get((cid, did), {"total": 0, "open": 0})
                domain_nodes[did]["children"].append({
                    "id": cid,
                    "type": "category",
                    "name": row.get("name"),
                    "children": [],
                    "raw": {
                        "id": cid,
                        "name": row.get("name"),
                        "color": row.get("color"),
                        "domainId": did,
                        "ticketCount": counts["total"],
                        "openTicketCount": counts["open"],
                    },
                })

    orphan_children = []
    for row in categories:
        if row["id"] in matched_category_ids:
            continue
        cid = row["id"]
        counts = ticket_totals.get(cid, {"total": 0, "open": 0})
        orphan_children.append({
            "id": cid,
            "type": "category",
            "name": row.get("name"),
            "children": [],
            "raw": {
                "id": cid,
                "name": row.get("name"),
                "color": row.get("color"),
                "domainId": None,
                "ticketCount": counts["total"],
                "openTicketCount": counts["open"],
            },
        })

    root_ids = list(domain_nodes.keys())
    if orphan_children:
        domain_nodes["_orphans"] = {
            "id": "_orphans",
            "type": "domain",
            "name": "⚠️ Catégories sans domaine valide",
            "children": orphan_children,
            "raw": {"note": "domain_id ne correspond à aucun tts_domains existant"},
        }
        root_ids.append("_orphans")

    return domain_nodes, root_ids


def count_descendants(node):
    """(nb catégories descendantes, nb tickets cumulés), racine exclue."""
    categories = tickets = 0
    for child in node["children"]:
        categories += 1
        tickets += child["raw"].get("ticketCount", 0)
        cc, ct = count_descendants(child)
        categories += cc
        tickets += ct
    return categories, tickets


# ------------------------------------------------------------------
# Accès DB — SELECT uniquement.
# ------------------------------------------------------------------

def fetch_domains(cur):
    return run_select(cur, "SELECT id, label FROM tts_domains")


def fetch_categories(cur):
    return run_select(cur, "SELECT id, name, color, domain_id FROM tts_category")


def fetch_ticket_counts_by_domain(cur, start=None, end=None):
    """Comptage scopé par (catégorie, domaine) — même choix de sémantique
    fenêtre que le module Optick (open_date dans la fenêtre, pas
    "actif pendant")."""
    if start is not None and end is not None:
        rows = run_select(
            cur,
            """SELECT id_category, domain_id,
                      COUNT(*) AS total,
                      SUM(CASE WHEN close_date = 0 THEN 1 ELSE 0 END) AS open_n
               FROM tts_tickets
               WHERE open_date BETWEEN %s AND %s
               GROUP BY id_category, domain_id""",
            [start, end],
        )
    else:
        rows = run_select(
            cur,
            """SELECT id_category, domain_id,
                      COUNT(*) AS total,
                      SUM(CASE WHEN close_date = 0 THEN 1 ELSE 0 END) AS open_n
               FROM tts_tickets
               GROUP BY id_category, domain_id""",
        )
    return {
        (row["id_category"], row["domain_id"]): {"total": row["total"], "open": int(row["open_n"] or 0)}
        for row in rows
        if row["id_category"] is not None
    }


def fetch_ticket_totals(cur, start=None, end=None):
    """Comptage tous domaines confondus — utilisé pour les catégories
    orphelines (voir build_forest)."""
    if start is not None and end is not None:
        rows = run_select(
            cur,
            """SELECT id_category,
                      COUNT(*) AS total,
                      SUM(CASE WHEN close_date = 0 THEN 1 ELSE 0 END) AS open_n
               FROM tts_tickets
               WHERE open_date BETWEEN %s AND %s
               GROUP BY id_category""",
            [start, end],
        )
    else:
        rows = run_select(
            cur,
            """SELECT id_category,
                      COUNT(*) AS total,
                      SUM(CASE WHEN close_date = 0 THEN 1 ELSE 0 END) AS open_n
               FROM tts_tickets
               GROUP BY id_category""",
        )
    return {
        row["id_category"]: {"total": row["total"], "open": int(row["open_n"] or 0)}
        for row in rows
        if row["id_category"] is not None
    }


def fetch_date_bounds(cur, category_ids, domain_id=None):
    """MIN/MAX open_date pour dimensionner le curseur. Scopé par
    domaine si `domain_id` est fourni (cohérent avec le comptage
    domain-scopé d'un vrai domaine racine) ; non scopé pour la racine
    synthétique '_orphans' (cohérent avec fetch_ticket_totals, qui
    agrège tous domaines confondus)."""
    if not category_ids:
        return None
    placeholders = ",".join(["%s"] * len(category_ids))
    if domain_id is not None:
        sql = (
            f"SELECT MIN(open_date) AS min_d, MAX(open_date) AS max_d FROM tts_tickets "
            f"WHERE id_category IN ({placeholders}) AND domain_id = %s"
        )
        params = [*category_ids, domain_id]
    else:
        sql = f"SELECT MIN(open_date) AS min_d, MAX(open_date) AS max_d FROM tts_tickets WHERE id_category IN ({placeholders})"
        params = category_ids
    rows = run_select(cur, sql, params)
    if not rows or rows[0]["min_d"] is None:
        return None
    return {"min": rows[0]["min_d"], "max": rows[0]["max_d"]}


def collect_category_ids(node):
    """Fonction pure — liste des ids de catégories dans un sous-arbre."""
    ids = []
    if node["type"] == "category":
        ids.append(node["id"])
    for c in node["children"]:
        ids.extend(collect_category_ids(c))
    return ids


def load_forest(start=None, end=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        domains = fetch_domains(cur)
        categories = fetch_categories(cur)
        counts_by_domain = fetch_ticket_counts_by_domain(cur, start, end)
        totals = fetch_ticket_totals(cur, start, end)
        return build_forest(domains, categories, counts_by_domain, totals)
    finally:
        conn.close()


def load_date_bounds(category_ids, domain_id):
    if not category_ids:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        return fetch_date_bounds(cur, category_ids, domain_id)
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

SERVICE_NAME = "tts-gu-api"
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
    cached = cache_get("ttsgu:roots")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        domain_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base TTS-GU injoignable : {exc}"}), 503

    roots = []
    for rid in root_ids:
        node = domain_nodes[rid]
        n_categories, n_tickets = count_descendants(node)
        roots.append({
            "id": node["id"],
            "name": node["name"],
            "description": None,
            "childSectionCount": n_categories,
            "subnetCount": n_tickets,
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set("ttsgu:roots", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/tree/<path:root_id>", methods=["GET"])
def get_tree(root_id):
    key_id = int(root_id) if root_id.lstrip("-").isdigit() else root_id

    start = request.args.get("start", type=int)
    end = request.args.get("end", type=int)
    windowed = start is not None and end is not None

    cache_key = f"ttsgu:tree:{key_id}"
    if not windowed:
        cached = cache_get(cache_key)
        if cached:
            return app.response_class(cached, mimetype="application/json")

    try:
        domain_nodes, root_ids = load_forest(start if windowed else None, end if windowed else None)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base TTS-GU injoignable : {exc}"}), 503

    if key_id not in root_ids:
        return jsonify({"error": f"'{root_id}' n'est pas une racine indépendante connue"}), 404

    tree_node = domain_nodes[key_id]
    # '_orphans' n'est pas un vrai domaine : bornes non scopées (voir
    # fetch_date_bounds), cohérent avec fetch_ticket_totals.
    domain_id_for_bounds = key_id if isinstance(key_id, int) else None
    try:
        date_bounds = load_date_bounds(collect_category_ids(tree_node), domain_id_for_bounds)
    except Exception:  # noqa: BLE001
        date_bounds = None

    import json as _json
    body = _json.dumps({"tree": tree_node, "dateBounds": date_bounds})
    if not windowed:
        cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
