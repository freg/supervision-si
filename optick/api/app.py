"""
API Optick — expose en LECTURE SEULE la base MySQL de l'outil de
tickets interne existant "optick" (externe à ce projet) pour alimenter
l'onglet Optick du frontend : racines indépendantes (familles de
catégories), arbre radial (familles -> catégories), vue JSON d'un
nœud.

Mêmes garanties de lecture seule que ipam/api/app.py (voir ce fichier
pour le détail des trois niveaux de défense) : aucune route d'écriture
ici, run_select() qui refuse tout ce qui n'est pas SELECT, et surtout
le compte MySQL utilisé doit lui-même n'avoir que le privilège SELECT
(voir optick/README.md).

Tables lues : tts_parent_category, tts_category, tts_tickets (en
agrégat de comptage uniquement — jamais le contenu individuel des
tickets), tts_domains (résolution des libellés). tts_users (comptes
applicatifs), tts_contacts, tts_notes, tts_attachments et les autres
tables ne sont jamais lues ici.
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
    register_version_route(app, "optick-api")

DB_HOST = os.environ.get("OPTICK_DB_HOST", "")
DB_PORT = int(os.environ.get("OPTICK_DB_PORT", "3306"))
DB_NAME = os.environ.get("OPTICK_DB_NAME", "optick3")
DB_USER = os.environ.get("OPTICK_DB_USER", "")
DB_PASSWORD = os.environ.get("OPTICK_DB_PASSWORD", "")
DB_SSL = os.environ.get("OPTICK_DB_SSL", "false").lower() == "true"
# Dump d'origine en charset latin1 par table (malgré un SET NAMES utf8
# en tête de dump) — configurable car la vraie base en place peut avoir
# été migrée depuis. Si les accents ressortent mal formés, essayer
# OPTICK_DB_CHARSET=latin1 (voir README).
DB_CHARSET = os.environ.get("OPTICK_DB_CHARSET", "utf8")

CACHE_TTL = int(os.environ.get("OPTICK_CACHE_TTL", "60"))
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
        raise RuntimeError("OPTICK_DB_HOST / OPTICK_DB_USER non configurés (voir optick/README.md)")
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
            autocommit=False,  # jamais de commit dans ce fichier
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
# Assemblage de l'arbre — fonctions PURES (aucun accès DB), testables
# avec des jeux de lignes construits à la main.
#
# Hiérarchie à DEUX niveaux fixes (contrairement à IPAM) :
# tts_parent_category (racine, "famille") -> tts_category (via
# id_parent) -> tickets comptés en agrégat sur chaque catégorie (pas
# de nœud par ticket individuel : leur volume réel rendrait un arbre
# radial illisible, même logique que le comptage d'IP par subnet côté
# IPAM plutôt qu'un nœud par adresse). Pas de nesting catégorie dans
# catégorie dans ce schéma -> pas de risque de cycle à ce niveau.
# ------------------------------------------------------------------

def decode_domain_ids(raw_value):
    """La colonne MySQL SET domain_id revient en chaîne "1,3,5" (ou
    vide) via PyMySQL — décodée ici en liste d'ids entiers."""
    if not raw_value:
        return []
    return [int(x) for x in str(raw_value).split(",") if x.strip().isdigit()]


def build_forest(families, categories, ticket_counts, domain_labels):
    """
    families      : lignes {id, family, domain_id}
    categories    : lignes {id, id_parent, name, color, domain_id}
    ticket_counts : {category_id: {"total": n, "open": n}}
    domain_labels : {domain_id: label}

    Retourne (family_nodes, root_ids). Tous les ids de familles sont
    racines (pas de nesting entre familles) ; une catégorie dont
    id_parent ne correspond à aucune famille est regroupée sous une
    racine synthétique "_orphans", jamais perdue silencieusement.
    """
    def resolve_domains(raw_domain_id):
        ids = decode_domain_ids(raw_domain_id)
        return [domain_labels[i] for i in ids if i in domain_labels]

    category_nodes = {}
    categories_by_family = {}
    for row in categories:
        cid = row["id"]
        counts = ticket_counts.get(cid, {"total": 0, "open": 0})
        node = {
            "id": cid,
            "type": "category",
            "name": row["name"],
            "children": [],
            "raw": {
                "id": cid,
                "name": row.get("name"),
                "color": row.get("color"),
                "idParent": row.get("id_parent"),
                "domainLabels": resolve_domains(row.get("domain_id")),
                "ticketCount": counts["total"],
                "openTicketCount": counts["open"],
            },
        }
        category_nodes[cid] = node
        categories_by_family.setdefault(row.get("id_parent"), []).append(node)

    family_nodes = {}
    for row in families:
        fid = row["id"]
        family_nodes[fid] = {
            "id": fid,
            "type": "family",
            "name": row["family"],
            "children": [],
            "raw": {
                "id": fid,
                "family": row.get("family"),
                "domainLabels": resolve_domains(row.get("domain_id")),
            },
        }

    root_ids = []
    for fid, node in family_nodes.items():
        node["children"].extend(categories_by_family.get(fid, []))
        root_ids.append(fid)

    orphan_family_ids = set(categories_by_family) - set(family_nodes) - {None, 0}
    if orphan_family_ids:
        orphan_children = []
        for orphan_id in sorted(orphan_family_ids, key=str):
            orphan_children.extend(categories_by_family[orphan_id])
        family_nodes["_orphans"] = {
            "id": "_orphans",
            "type": "family",
            "name": "⚠️ Catégories sans famille valide",
            "children": orphan_children,
            "raw": {"note": "id_parent ne correspond à aucune tts_parent_category existante"},
        }
        root_ids.append("_orphans")

    return family_nodes, root_ids


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
# Accès DB — SELECT uniquement, colonnes volontairement restreintes.
# ------------------------------------------------------------------

def fetch_families(cur):
    return run_select(cur, "SELECT id, family, domain_id FROM tts_parent_category")


def fetch_categories(cur):
    return run_select(cur, "SELECT id, id_parent, name, color, domain_id FROM tts_category")


def fetch_ticket_counts(cur, start=None, end=None):
    """Comptage de tickets par catégorie — REGARDLESS de fenêtre par
    défaut (comportement historique, inchangé). Si `start`/`end` sont
    fournis (epoch secondes), scope sur les tickets OUVERTS pendant
    cette fenêtre (open_date compris dedans) — pas "actifs pendant"
    (qui inclurait aussi des tickets ouverts avant mais fermés après
    le début de la fenêtre) : choix simple et documenté, à faire
    évoluer si le besoin réel est différent."""
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


def fetch_date_bounds(cur, category_ids):
    """MIN/MAX open_date sur un ensemble de catégories — sert à
    dimensionner le curseur de fenêtre côté front, TOUJOURS calculé
    sur la totalité des tickets de ces catégories (pas la fenêtre
    active), pour que la fenêtre puisse être élargie à nouveau après
    avoir été resserrée. None si aucune catégorie ou aucun ticket."""
    if not category_ids:
        return None
    placeholders = ",".join(["%s"] * len(category_ids))
    rows = run_select(
        cur,
        f"SELECT MIN(open_date) AS min_d, MAX(open_date) AS max_d FROM tts_tickets WHERE id_category IN ({placeholders})",
        category_ids,
    )
    if not rows or rows[0]["min_d"] is None:
        return None
    return {"min": rows[0]["min_d"], "max": rows[0]["max_d"]}


def collect_category_ids(node):
    """Liste des ids de catégories dans un sous-arbre (fonction pure,
    aucun accès DB) — utilisée pour scoper la requête de bornes
    temporelles à ce qui est effectivement sous une racine donnée."""
    ids = []
    if node["type"] == "category":
        ids.append(node["id"])
    for c in node["children"]:
        ids.extend(collect_category_ids(c))
    return ids


def fetch_domain_labels(cur):
    rows = run_select(cur, "SELECT id, label FROM tts_domains")
    return {row["id"]: row["label"] for row in rows if row.get("label")}


def load_forest(start=None, end=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        families = fetch_families(cur)
        categories = fetch_categories(cur)
        ticket_counts = fetch_ticket_counts(cur, start, end)
        domain_labels = fetch_domain_labels(cur)
        return build_forest(families, categories, ticket_counts, domain_labels)
    finally:
        conn.close()


def load_date_bounds(category_ids):
    """Connexion dédiée (courte) — load_forest() a déjà refermé la
    sienne au moment où l'arbre est prêt et où category_ids est connu."""
    if not category_ids:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        return fetch_date_bounds(cur, category_ids)
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

SERVICE_NAME = "optick-api"
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
    cached = cache_get("optick:roots")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        family_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base Optick injoignable : {exc}"}), 503

    roots = []
    for rid in root_ids:
        node = family_nodes[rid]
        n_categories, n_tickets = count_descendants(node)
        roots.append({
            "id": node["id"],
            "name": node["name"],
            "description": ", ".join(node["raw"].get("domainLabels", [])) or None,
            "childSectionCount": n_categories,
            "subnetCount": n_tickets,  # même contrat de champ que /roots d'ipam-api (front générique)
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set("optick:roots", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/tree/<path:root_id>", methods=["GET"])
def get_tree(root_id):
    key_id = int(root_id) if root_id.lstrip("-").isdigit() else root_id

    # Fenêtre temporelle optionnelle (epoch secondes) — filtre les
    # comptages de tickets par catégorie sur open_date. Absente : même
    # comportement qu'avant (tout l'historique), mis en cache comme
    # précédemment. Présente : jamais mis en cache (combinaisons de
    # fenêtre non bornées) et toujours recalculé.
    start = request.args.get("start", type=int)
    end = request.args.get("end", type=int)
    windowed = start is not None and end is not None

    cache_key = f"optick:tree:{key_id}"
    if not windowed:
        cached = cache_get(cache_key)
        if cached:
            return app.response_class(cached, mimetype="application/json")

    try:
        family_nodes, root_ids = load_forest(start if windowed else None, end if windowed else None)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base Optick injoignable : {exc}"}), 503

    if key_id not in root_ids:
        return jsonify({"error": f"'{root_id}' n'est pas une racine indépendante connue"}), 404

    tree_node = family_nodes[key_id]
    try:
        date_bounds = load_date_bounds(collect_category_ids(tree_node))
    except Exception:  # noqa: BLE001 — dégradé : pas de timeline plutôt qu'une réponse en erreur
        date_bounds = None

    import json as _json
    body = _json.dumps({"tree": tree_node, "dateBounds": date_bounds})
    if not windowed:
        cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
