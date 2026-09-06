"""
API OwnCloud — expose en LECTURE SEULE la base MySQL de l'instance
ownCloud/Nextcloud existante (externe à ce projet) pour alimenter
l'onglet OwnCloud du frontend.

Mêmes garanties de lecture seule que ipam/optick/zenoss (voir
ipam/README.md pour le détail des trois niveaux de défense).

DIFFÉRENCE ARCHITECTURALE IMPORTANTE avec ipam/optick/zenoss : la
table `oc_filecache` du schéma fourni est à AUTO_INCREMENT=2 473 859 —
environ 2,5 MILLIONS de lignes. Charger un arbre complet en un seul
appel (comme pour IPAM ou Optick, où quelques milliers de lignes au
plus sont en jeu) est ici impossible : la réponse serait gigantesque
et la requête pourrait mettre la base à genoux. Ce module ne renvoie
donc QUE la racine + les enfants DIRECTS d'un nœud à la fois
(chargement à la demande / lazy-loading) — c'est au frontend de
déplier l'arbre progressivement au clic, en accumulant l'état côté
client (voir frontend/src/apps/owncloudLib.js: mergeChildren()).

Colonnes JAMAIS lues : email, quota, authentification, partages
nominatifs — tout le reste de `oc_accounts`. Seuls `oc_mounts.mount_point`
(un chemin, pas une donnée personnelle) et, EXCEPTION délibérée et
scopée demandée explicitement, `oc_accounts.display_name` (+ la clé
de jointure `oc_mounts.user_id`) sont lus — uniquement pour remplacer
l'identifiant technique de storage (parfois un hash illisible) par un
nom humain dans la liste des racines. Voir fetch_display_names() et
owncloud/README.md pour le détail exact et les limites de vérification
de cette exception.
"""
import hashlib
import os
import time

import pymysql
import pymysql.cursors
import pymysql.err
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
    register_version_route(app, "owncloud-api")

DB_HOST = os.environ.get("OWNCLOUD_DB_HOST", "")
DB_PORT = int(os.environ.get("OWNCLOUD_DB_PORT", "3306"))
DB_NAME = os.environ.get("OWNCLOUD_DB_NAME", "owncloud")
DB_USER = os.environ.get("OWNCLOUD_DB_USER", "")
DB_PASSWORD = os.environ.get("OWNCLOUD_DB_PASSWORD", "")
DB_SSL = os.environ.get("OWNCLOUD_DB_SSL", "false").lower() == "true"
DB_CHARSET = os.environ.get("OWNCLOUD_DB_CHARSET", "utf8mb4")

CACHE_TTL = int(os.environ.get("OWNCLOUD_CACHE_TTL", "60"))
# TTL SÉPARÉ, bien plus long que CACHE_TTL ci-dessus -- livraison
# #354, backlog "chemins trop longs pour Windows" (demandé
# explicitement, priorité signalée sur la synchronisation --
# ceci est la partie immédiatement actionnable, sans nouvel accès).
# `WHERE LENGTH(path) > ...` sur oc_filecache (~2,5M lignes, voir
# docstring de ce fichier) n'a AUCUN index exploitable -- balaie la
# table ENTIÈRE à chaque appel non caché. Les chemins ne changent pas
# à la minute -- un TTL de plusieurs minutes reste largement
# suffisant pour un usage interactif, sans réinterroger inutilement
# une requête coûteuse à chaque clic.
LONG_PATH_CACHE_TTL = int(os.environ.get("OWNCLOUD_LONG_PATH_CACHE_TTL", "900"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))

# md5('') — hash de chemin du nœud RACINE d'un storage dans oc_filecache
# (convention ownCloud/Nextcloud : path='' pour la racine, path_hash en
# est le md5). Constant, calculé une fois.
EMPTY_PATH_HASH = hashlib.md5(b"").hexdigest()

FOLDER_MIMETYPE = "httpd/unix-directory"


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


def get_connection():
    if not DB_HOST or not DB_USER:
        raise RuntimeError("OWNCLOUD_DB_HOST / OWNCLOUD_DB_USER non configurés (voir owncloud/README.md)")
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
# Mise en forme — fonctions PURES, testables sans base réelle.
# ------------------------------------------------------------------

def format_file_row(row, mimetype_map):
    """Ligne oc_filecache brute -> nœud du contrat API. `raw.name` reste
    la valeur BRUTE (peut être vide pour une racine de storage) — la
    présentation (libellé affiché) est laissée au frontend, qui connaît
    déjà le nom convivial du storage."""
    mimetype = mimetype_map.get(row.get("mimetype"), None)
    is_dir = mimetype == FOLDER_MIMETYPE
    return {
        "id": row["fileid"],
        "type": "folder" if is_dir else "file",
        "name": row.get("name") or "",
        "raw": {
            "fileid": row["fileid"],
            "storage": row.get("storage"),
            "path": row.get("path"),
            "name": row.get("name"),
            "mimetype": mimetype,
            "isDir": is_dir,
            "size": row.get("size"),
            "mtime": row.get("mtime"),
            "permissions": row.get("permissions"),
            "encrypted": bool(row.get("encrypted")),
            "childCount": row.get("child_count", 0),
        },
        "children": [],  # jamais peuplé ici — dépliage à la demande côté client
    }


# ------------------------------------------------------------------
# Accès DB — SELECT uniquement.
# ------------------------------------------------------------------

def fetch_mimetype_map(cur):
    rows = run_select(cur, "SELECT id, mimetype FROM oc_mimetypes")
    return {row["id"]: row["mimetype"] for row in rows}


def fetch_storages(cur):
    return run_select(cur, "SELECT numeric_id, id FROM oc_storages")


def fetch_storage_aggregates(cur):
    """Une seule requête groupée (indexée sur `storage`, en tête de
    plusieurs index de la table) — jamais un scan complet non filtré.

    SUM() sur une colonne entière renvoie un `decimal.Decimal` côté
    pymysql (MySQL type le résultat d'un SUM en DECIMAL, pas dans le
    type de la colonne d'origine) — non sérialisable tel quel par
    `json.dumps`. Converti explicitement en `int` ici, au plus près de
    la source, plutôt que de laisser le Decimal se propager jusqu'à la
    réponse HTTP (où l'erreur n'est apparue qu'en conditions réelles,
    jamais testée depuis cet environnement faute de vrai MySQL)."""
    rows = run_select(
        cur,
        "SELECT storage, COUNT(*) AS n, SUM(size) AS total_size FROM oc_filecache GROUP BY storage",
    )
    return {
        row["storage"]: {"count": row["n"], "totalSize": int(row["total_size"]) if row["total_size"] is not None else 0}
        for row in rows
    }


def fetch_storage_owner_mounts(cur):
    """Comme l'ancien fetch_storage_example_mounts, mais récupère aussi
    `user_id` du mount pour résoudre ensuite un nom humain (voir
    fetch_display_names). Si plusieurs utilisateurs montent le même
    storage_id (partage), un seul est retenu arbitrairement (MIN) —
    déjà le choix assumé pour mount_point avant cet ajout ; sans
    conséquence pour le cas normal (un storage "home" = un seul
    utilisateur, une seule ligne dans oc_mounts)."""
    rows = run_select(
        cur,
        "SELECT storage_id, MIN(mount_point) AS mount_point, MIN(user_id) AS user_id "
        "FROM oc_mounts GROUP BY storage_id",
    )
    return {row["storage_id"]: {"mount_point": row["mount_point"], "user_id": row["user_id"]} for row in rows}


def fetch_display_names(cur, user_ids):
    """EXCEPTION délibérée et scopée au périmètre "jamais lu" (voir
    en-tête du module) : lit `oc_accounts.display_name` (+ la clé de
    jointure `user_id`), demandé explicitement pour remplacer
    l'identifiant technique de storage (parfois un hash illisible,
    ex. stockage objet) par un nom humain dans la liste des racines.
    RIEN d'autre n'est lu sur `oc_accounts` — pas d'email, pas de
    quota, pas de champ d'authentification.

    Nom de table/colonnes non vérifié contre un vrai schéma depuis cet
    environnement (convention ownCloud/Nextcloud classique assumée,
    confirmée par la personne pour `display_name`, mais pas pour le nom
    exact de la table ni la colonne de jointure `user_id`) — dégrade
    silencieusement vers l'identifiant technique brut (comportement
    précédent) si la requête échoue, plutôt que de faire tomber tout
    l'onglet sur une hypothèse de schéma erronée. Une trace est
    laissée dans les logs serveur pour ne pas masquer un vrai souci de
    configuration."""
    user_ids = [u for u in user_ids if u]
    if not user_ids:
        return {}
    placeholders = ",".join(["%s"] * len(user_ids))
    try:
        rows = run_select(
            cur,
            f"SELECT user_id, display_name FROM oc_accounts WHERE user_id IN ({placeholders})",
            user_ids,
        )
    except pymysql.err.Error as exc:
        app.logger.warning(
            "fetch_display_names a échoué (schéma oc_accounts différent de l'hypothèse "
            "user_id/display_name ?) — repli sur l'identifiant technique brut : %s", exc,
        )
        return {}
    return {row["user_id"]: row["display_name"] for row in rows if row.get("display_name")}


def fetch_storage_roots(cur, storage_ids):
    """Ligne racine (path='') de chaque storage, en UNE requête — exploite
    l'index (storage, path_hash) via un IN sur la colonne de tête."""
    if not storage_ids:
        return {}
    placeholders = ",".join(["%s"] * len(storage_ids))
    rows = run_select(
        cur,
        f"""SELECT fileid, storage, path, name, mimetype, size, mtime, permissions, encrypted
            FROM oc_filecache
            WHERE storage IN ({placeholders}) AND path_hash = %s""",
        [*storage_ids, EMPTY_PATH_HASH],
    )
    return {row["storage"]: row for row in rows}


def fetch_children_rows(cur, parent_fileid):
    return run_select(
        cur,
        """SELECT fileid, storage, path, name, mimetype, size, mtime, permissions, encrypted
           FROM oc_filecache WHERE parent = %s ORDER BY name""",
        [parent_fileid],
    )


def fetch_child_counts(cur, fileids):
    """Combien d'enfants directs a chacun des fileids donnés — batché en
    une requête (jamais N+1), pour savoir si un dossier est vide ou non
    sans le déplier."""
    if not fileids:
        return {}
    placeholders = ",".join(["%s"] * len(fileids))
    rows = run_select(
        cur, f"SELECT parent, COUNT(*) AS n FROM oc_filecache WHERE parent IN ({placeholders}) GROUP BY parent",
        fileids,
    )
    return {row["parent"]: row["n"] for row in rows}


def fetch_node_row(cur, fileid):
    rows = run_select(
        cur,
        """SELECT fileid, storage, path, name, mimetype, size, mtime, permissions, encrypted
           FROM oc_filecache WHERE fileid = %s""",
        [fileid],
    )
    return rows[0] if rows else None


def fetch_long_paths(cur, threshold, limit):
    """Chemins dont la longueur dépasse `threshold` -- livraison #354,
    "identifier les chemins trop longs pour Windows ou autres"
    (demandé explicitement). ⚠️ AUCUN index exploitable sur
    `LENGTH(path)` -- balaie l'intégralité de `oc_filecache` (~2,5M
    lignes, voir docstring de ce fichier). Voir LONG_PATH_CACHE_TTL
    (bien plus long que CACHE_TTL) -- jamais appelé à chaque clic sans
    cache. `storage` inclus pour permettre au frontend de retrouver le
    nom de racine correspondant (voir /roots) sans requête
    supplémentaire ici."""
    return run_select(
        cur,
        """SELECT fileid, storage, path, LENGTH(path) AS path_length
           FROM oc_filecache WHERE LENGTH(path) > %s
           ORDER BY path_length DESC LIMIT %s""",
        [threshold, limit],
    )


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

SERVICE_NAME = "owncloud-api"
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
    """Racines indépendantes = les storages. Chaque entrée porte aussi
    `rootFileId` : le frontend appelle ensuite /children avec cet id
    pour obtenir le premier niveau de l'arbre (même endpoint que pour
    tout dépliage ultérieur — pas de cas particulier)."""
    cached = cache_get("owncloud:roots")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            storages = fetch_storages(cur)
            aggregates = fetch_storage_aggregates(cur)
            owner_mounts = fetch_storage_owner_mounts(cur)
            display_names = fetch_display_names(cur, [m["user_id"] for m in owner_mounts.values()])
            roots_rows = fetch_storage_roots(cur, [s["numeric_id"] for s in storages])
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base OwnCloud injoignable : {exc}"}), 503

    roots = []
    for s in storages:
        sid = s["numeric_id"]
        agg = aggregates.get(sid, {"count": 0, "totalSize": 0})
        root_row = roots_rows.get(sid)
        mount_info = owner_mounts.get(sid, {})
        user_id = mount_info.get("user_id")
        display_name = display_names.get(user_id) if user_id else None
        roots.append({
            "id": sid,
            "name": display_name or s["id"],
            "storageId": s["id"],  # identifiant technique brut, toujours present meme quand `name` est un nom humain
            "description": mount_info.get("mount_point"),
            "itemCount": agg["count"],
            "totalSize": agg["totalSize"],
            "rootFileId": root_row["fileid"] if root_row else None,
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set("owncloud:roots", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/children/<int:storage>/<int:fileid>", methods=["GET"])
def get_children(storage, fileid):
    """Le nœud demandé + ses enfants DIRECTS uniquement — jamais toute
    la sous-arborescence (voir note d'architecture en tête de fichier)."""
    cache_key = f"owncloud:children:{storage}:{fileid}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            mimetype_map = fetch_mimetype_map(cur)
            node_row = fetch_node_row(cur, fileid)
            if node_row is None:
                return jsonify({"error": f"fileid {fileid} introuvable"}), 404
            if node_row["storage"] != storage:
                # Incohérence entre l'id de storage demandé et celui réel
                # de la ligne — signalé plutôt que masqué.
                return jsonify({
                    "error": f"fileid {fileid} appartient au storage {node_row['storage']}, pas {storage}"
                }), 409
            child_rows = fetch_children_rows(cur, fileid)
            child_counts = fetch_child_counts(cur, [c["fileid"] for c in child_rows])
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base OwnCloud injoignable : {exc}"}), 503

    for c in child_rows:
        c["child_count"] = child_counts.get(c["fileid"], 0)

    body_obj = {
        "node": format_file_row(node_row, mimetype_map),
        "children": [format_file_row(c, mimetype_map) for c in child_rows],
    }
    import json as _json
    body = _json.dumps(body_obj)
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


@app.route("/long-paths", methods=["GET"])
def long_paths():
    """Chemins dépassant une longueur donnée -- livraison #354,
    "identifier les chemins trop longs pour Windows ou autres"
    (demandé explicitement, priorité signalée : problèmes de
    synchronisation des drives -- ce point précis est actionnable
    SANS nouvel accès, contrairement au reste du sujet synchronisation
    qui reste À CLARIFIER, voir owncloud/README.md).

    `threshold` (défaut 260 -- limite CLASSIQUE Windows MAX_PATH,
    voir owncloud/README.md pour le détail et les limites plus
    récentes) : longueur AU-DELÀ de laquelle un chemin est signalé.
    `limit` (défaut 200, plafonné à 1000 -- jamais un appel qui
    ramènerait des dizaines de milliers de lignes par erreur de
    paramètre)."""
    try:
        threshold = int(request.args.get("threshold", 260))
    except (TypeError, ValueError):
        return jsonify({"error": "'threshold' doit être un entier"}), 400
    try:
        limit = min(max(int(request.args.get("limit", 200)), 1), 1000)
    except (TypeError, ValueError):
        return jsonify({"error": "'limit' doit être un entier"}), 400

    cache_key = f"owncloud:long-paths:{threshold}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            rows = fetch_long_paths(cur, threshold, limit)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base OwnCloud injoignable : {exc}"}), 503

    results = [{
        "fileid": r["fileid"],
        "storage": r["storage"],
        "path": r["path"],
        "pathLength": r["path_length"],
    } for r in rows]

    import json as _json
    body = _json.dumps({"threshold": threshold, "results": results})
    cache_set(cache_key, body, ttl=LONG_PATH_CACHE_TTL)
    return app.response_class(body, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
