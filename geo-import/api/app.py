"""
API de dépôt/import/corrélation de shapefiles — écrit dans la base
PostGIS de staging locale (`geo-postgres`, service dédié de ce projet,
distincte de toute base PostGIS externe existante). Contrairement à la
quasi-totalité des autres modules de ce projet, ce service est en
ÉCRITURE : il crée des tables dans la base de staging.

CONVENTION DE NOMMAGE : un "shapefile" est un format multi-fichiers
(.shp/.shx/.dbf/.prj au minimum) — l'upload attendu est une archive .zip
contenant cet ensemble, jamais un .shp seul.

REPROJECTION SYSTÉMATIQUE vers EPSG:4326 (WGS84) à l'import.

PHILOSOPHIE DE L'OUTIL — reformulée après discussion avec la personne
(contexte complet : écosystème de 25 ans, applications cloisonnées par
métier interne, connaissance d'architecture souvent non documentée
mais retrouvable dans des documents de prestataires). L'objectif n'est
PAS un ETL classique qui fusionnerait des données automatiquement, mais
un outil d'EXPLORATION DE CORRÉLATIONS "à la data science" : attaquer
un datalake hétérogène sans le modifier, faire émerger des liens
candidats (jamais imposés), laisser le jugement humain trancher.

Trois stratégies de corrélation (`/correlate`) entre deux couches
quelconques de la base de staging :
- **Sémantique** : similarité de libellés via `pg_trgm` (score 0–1,
  plus robuste que la seule distance de Levenshtein sur des noms
  réordonnés/partiels).
- **Géographique** : proximité spatiale via `ST_DWithin`/`ST_Distance`
  (cast `::geography` pour une distance en mètres réels, pas en degrés).
- **Temporelle** : recoupement de fenêtres de dates entre deux colonnes.

Chaque corrélation renvoie des CANDIDATS classés par score, jamais un
merge automatique — la matérialisation (`/correlate/materialize`) reste
un geste explicite et nommé, dans l'esprit de "Figer cette vue comme
source" déjà établi ailleurs dans ce projet (aucune source d'origine
n'est jamais modifiée).

CONNECTEURS — pont progressif vers les autres métiers/modules, sans
jamais les court-circuiter (toujours via leur API HTTP existante,
jamais un accès direct à leur base). Premier connecteur : `geolocations`
(table déjà transversale, alimentée par Fusion IP/MAC ET OwnCloud) —
`/connectors/geolocations/sync` la matérialise en table PostGIS
interrogeable spatialement, gratuit pour la corrélation dès qu'elle
est synchronisée. Ajouter un futur connecteur (IPAM, Zenoss...) suit
le même schéma : une fonction de récupération + une route de sync,
jamais un système de plugin générique prématuré tant qu'il n'y a
qu'un seul exemple concret à généraliser.
"""
import logging as _logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "geo-import-api")

_log = _logging.getLogger("geo_import_app")

# Branchement rights-api -- livraison #318, item 38 du backlog. Ce
# module est EXPLICITEMENT en écriture (voir docstring en tête de
# fichier) -- import de shapefiles, fusion de couches, synchronisation
# depuis pixel-grid-api. Gardé sur ces 3 routes -- jamais /correlate
# (confirmé PUREMENT lecture : uniquement des SELECT, aucune écriture,
# malgré le verbe POST utilisé pour transmettre stratégie/options en
# corps de requête) ni /layers//layers/<x>/columns.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-317) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "geo-import-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur geo-import-api requis (groupe admin_hub, ou un octroi explicite)"

GEO_DB_HOST = os.environ.get("GEO_DB_HOST", "geo-postgres")
GEO_DB_PORT = int(os.environ.get("GEO_DB_PORT", "5432"))
GEO_DB_NAME = os.environ.get("GEO_DB_NAME", "geo")
GEO_DB_USER = os.environ.get("GEO_DB_USER", "geo")
GEO_DB_PASSWORD = os.environ.get("GEO_DB_PASSWORD", "")

UPLOAD_MAX_BYTES = int(os.environ.get("GEO_IMPORT_MAX_MB", "200")) * 1024 * 1024
TARGET_SRID = "EPSG:4326"

REQUIRED_SHAPEFILE_EXTENSIONS = {".shp", ".shx", ".dbf"}
RECOMMENDED_SHAPEFILE_EXTENSIONS = {".prj"}

# Premier connecteur transversal -- voir docstring du module.
PIXEL_GRID_API_URL = os.environ.get("PIXEL_GRID_API_URL", "http://pixel-grid-api:5000").rstrip("/")
CONNECTOR_TIMEOUT_SECONDS = float(os.environ.get("GEO_CONNECTOR_TIMEOUT_SECONDS", "10"))

# Garde-fou sur les jointures exploratoires (semantique/temporelle) qui
# comparent CHAQUE ligne de A a CHAQUE ligne de B (produit cartesien) --
# une jointure geographique utilise l'index spatial via ST_DWithin et
# n'a pas ce cout, mais les deux autres strategies peuvent devenir tres
# lentes sur de gros volumes sans cette limite.
MAX_CROSS_JOIN_PRODUCT = int(os.environ.get("GEO_MAX_CROSS_JOIN_PRODUCT", "500000"))
MAX_CORRELATION_RESULTS = 200


# ------------------------------------------------------------------
# Connexion PostGIS de staging — même contrat que get_connection()
# dans les autres modules (dual-backend non nécessaire ici : ce
# service est neuf, PostgreSQL/PostGIS uniquement, pas d'héritage
# SQLite à respecter).
# ------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(
        host=GEO_DB_HOST, port=GEO_DB_PORT, dbname=GEO_DB_NAME,
        user=GEO_DB_USER, password=GEO_DB_PASSWORD,
    )


def pg_dsn():
    """Chaîne de connexion au format attendu par ogr2ogr (option -f
    PostgreSQL "PG:...") — séparée de get_connection() qui sert psycopg2,
    car ogr2ogr tourne en sous-processus, pas dans ce process Python."""
    return (
        f"PG:host={GEO_DB_HOST} port={GEO_DB_PORT} dbname={GEO_DB_NAME} "
        f"user={GEO_DB_USER} password={GEO_DB_PASSWORD}"
    )


# ------------------------------------------------------------------
# Fonctions pures — validation, nommage, construction de commandes.
# Testables sans GDAL ni PostgreSQL réels.
# ------------------------------------------------------------------

def find_shapefile_sets(paths):
    """paths : chemins RELATIFS complets trouvés dans l'archive (pas
    seulement leur nom de base) — une copie d'un dossier de travail
    QGIS contient presque toujours plusieurs jeux de shapefiles
    organisés en sous-dossiers (un jeu par type d'objet : chambres,
    fourreaux, câbles...), jamais un seul fichier à plat à la racine.
    Regroupe par (dossier, nom de base) pour ne jamais confondre deux
    fichiers de même nom dans des dossiers différents, puis ne retient
    que les jeux complets (.shp+.shx+.dbf). Un jeu incomplet (ex. un
    .shp sans .dbf, fichier orphelin ou copie partielle) est écarté
    silencieusement du résultat mais signalé dans `skipped` — jamais
    une exception, ni un blocage de l'import des jeux valides à cause
    d'un jeu voisin incomplet."""
    by_key = {}
    for p in paths:
        dirpath = os.path.dirname(p)
        filename = os.path.basename(p)
        base, ext = os.path.splitext(filename)
        if not base:
            continue
        key = (dirpath, base.lower())
        by_key.setdefault(key, {"base_display": base, "files": {}})
        by_key[key]["files"][ext.lower()] = p

    sets, skipped = [], []
    for (dirpath, _base_lower), info in sorted(by_key.items()):
        files = info["files"]
        if ".shp" not in files:
            continue  # pas un jeu shapefile (fichier annexe : .qgs, image, etc.)
        missing = [ext for ext in REQUIRED_SHAPEFILE_EXTENSIONS if ext not in files]
        if missing:
            skipped.append(f"{info['base_display']} : {', '.join(missing)} manquant(s), ignoré")
            continue
        warnings = []
        if ".prj" not in files:
            warnings.append(f"{info['base_display']} : .prj manquant — système de coordonnées inconnu")
        sets.append({"shp_path": files[".shp"], "base_name": info["base_display"], "warnings": warnings})

    return {"sets": sets, "skipped": skipped}


_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]")


def sanitize_layer_name(raw_name):
    """Nom de fichier/couche arbitraire -> identifiant PostgreSQL sûr.
    JAMAIS de nom de table construit par interpolation directe d'un nom
    fourni par la personne (même logique que RAW_EDITABLE_TABLES/liste
    blanche ailleurs dans ce projet, adaptée ici : on ne valide pas contre
    une liste connue à l'avance puisque le nom est créé à la volée, mais
    on le nettoie strictement plutôt que de le faire confiance tel quel).
    Toujours un résultat exploitable, même sur une entrée vide/exotique
    (repli sur "couche" + suffixe)."""
    base = os.path.splitext(raw_name or "")[0]
    base = base.strip().lower()
    base = base.replace("-", "_").replace(" ", "_")
    base = _IDENTIFIER_RE.sub("", base)
    base = base.strip("_")
    if not base:
        base = "couche"
    if base[0].isdigit():
        base = f"c_{base}"
    return base[:63]  # limite de longueur d'un identifiant PostgreSQL


def build_ogr2ogr_import_command(shp_path, table_name, dsn, mode="overwrite"):
    """Construit la liste d'arguments pour subprocess.run — jamais une
    chaîne shell (pas de risque d'injection shell, chaque argument reste
    un élément de liste séparé). `mode` : "overwrite" (remplace la table
    si elle existe déjà) ou "append" (ajoute à une table existante, même
    structure attendue)."""
    cmd = [
        "ogr2ogr", "-f", "PostgreSQL", dsn, shp_path,
        "-nln", table_name,
        "-t_srs", TARGET_SRID,
        "-lco", "GEOMETRY_NAME=geom",
        "-lco", "FID=gid",
    ]
    cmd.append("-overwrite" if mode == "overwrite" else "-append")
    return cmd


def parse_ogr2ogr_output(returncode, stdout, stderr):
    """Interprète le résultat d'un subprocess ogr2ogr. ogr2ogr peut
    renvoyer 0 tout en émettant des avertissements sur stderr (ex:
    troncature d'attribut) -- ceux-ci sont remontés comme `warnings`,
    pas comme un échec. Ne lève jamais."""
    if returncode != 0:
        message = (stderr or stdout or "").strip() or f"ogr2ogr a échoué (code {returncode})"
        return {"success": False, "error": message, "warnings": []}
    warnings = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    return {"success": True, "error": None, "warnings": warnings}


def build_fusion_sql(source_layers, target_layer, common_columns):
    """SQL de fusion : UNION ALL des colonnes communes + géométrie,
    avec une colonne source_layer ajoutée pour tracer la provenance.
    `common_columns` : déjà calculées par l'appelant (introspection
    information_schema) — cette fonction reste pure, ne fait aucun accès
    base elle-même. Identifiants déjà passés par sanitize_layer_name par
    l'appelant -- pas revalidés ici, mais la liste `common_columns` doit
    elle aussi être filtrée en amont contre les colonnes réellement
    présentes (jamais une colonne arbitraire fournie par un appel API).

    Un `gid` neuf est généré pour la table fusionnée (row_number()) —
    les `gid` originaux de chaque couche source se chevauchent presque
    toujours (chacune numérotée indépendamment depuis 1), les conserver
    tels quels donnerait une fausse impression de clé unique alors que
    plusieurs lignes fusionnées partageraient la même valeur."""
    cols_sql = ", ".join(f'"{c}"' for c in common_columns)
    selects = "\nUNION ALL\n".join(
        f'SELECT {cols_sql}, \'{layer}\' AS source_layer FROM "{layer}"' for layer in source_layers
    )
    return (
        f'CREATE TABLE "{target_layer}" AS\n'
        f'SELECT row_number() OVER () AS gid, merged.*\n'
        f'FROM (\n{selects}\n) AS merged;'
    )


# ------------------------------------------------------------------
# Moteur de corrélation — trois stratégies, toujours exploratoires
# (candidats classés, jamais un merge automatique). Voir docstring du
# module pour la philosophie. Chaque build_*_sql reste PURE : ne fait
# aucun accès base, prend en entrée des noms déjà validés par
# l'appelant (existence de couche/colonne vérifiée avant construction
# du SQL — même principe que build_fusion_sql).
# ------------------------------------------------------------------

CORRELATION_STRATEGIES = {"semantic", "geographic", "temporal"}


def estimate_join_size(count_a, count_b):
    """Produit cartésien estimé — sert de garde-fou avant une jointure
    exploratoire (semantic/temporal) qui compare chaque ligne de A à
    chaque ligne de B. La stratégie geographic n'en a pas besoin (passe
    par l'index spatial via ST_DWithin, jamais un produit cartésien
    complet)."""
    return (count_a or 0) * (count_b or 0)


def build_semantic_correlation_sql(layer_a, layer_b, column_a, column_b, threshold, limit):
    """pg_trgm.similarity() -- score 0 (aucun rapport) a 1 (identique).
    Produit cartesien filtre par le seuil : reste correct mais peut
    etre lent sur de gros volumes, d'ou estimate_join_size() en amont
    cote appelant."""
    return (
        f'SELECT a.gid AS a_id, b.gid AS b_id, '
        f'a."{column_a}"::text AS a_label, b."{column_b}"::text AS b_label, '
        f'similarity(a."{column_a}"::text, b."{column_b}"::text) AS score '
        f'FROM "{layer_a}" a CROSS JOIN "{layer_b}" b '
        f'WHERE similarity(a."{column_a}"::text, b."{column_b}"::text) >= %s '
        f'ORDER BY score DESC LIMIT %s'
    ), (threshold, limit)


def build_geographic_correlation_sql(layer_a, layer_b, max_distance_m, limit):
    """Cast ::geography obligatoire pour une distance en METRES reels
    -- une comparaison en ::geometry brute donnerait une distance en
    degres, correcte pour trier mais pas pour un seuil metrique
    exploitable par un humain. ST_DWithin utilise l'index spatial
    (GIST, cree automatiquement par ogr2ogr sur la colonne geom)."""
    return (
        f'SELECT a.gid AS a_id, b.gid AS b_id, '
        f'ST_Distance(a.geom::geography, b.geom::geography) AS score '
        f'FROM "{layer_a}" a JOIN "{layer_b}" b '
        f'ON ST_DWithin(a.geom::geography, b.geom::geography, %s) '
        f'ORDER BY score ASC LIMIT %s'
    ), (max_distance_m, limit)


def build_temporal_correlation_sql(layer_a, layer_b, column_a, column_b, window_days, limit):
    """Ecart en jours (valeur absolue) entre deux colonnes de date/heure
    -- score croissant = moins bon (contrairement a semantic ou plus
    haut = meilleur), voir score_direction dans la reponse de /correlate."""
    diff_expr = (
        f'ABS(EXTRACT(EPOCH FROM (a."{column_a}"::timestamp - b."{column_b}"::timestamp)) / 86400.0)'
    )
    return (
        f'SELECT a.gid AS a_id, b.gid AS b_id, '
        f'a."{column_a}"::text AS a_label, b."{column_b}"::text AS b_label, '
        f'{diff_expr} AS score '
        f'FROM "{layer_a}" a CROSS JOIN "{layer_b}" b '
        f'WHERE {diff_expr} <= %s '
        f'ORDER BY score ASC LIMIT %s'
    ), (window_days, limit)


SCORE_DIRECTION = {"semantic": "higher_better", "geographic": "lower_better", "temporal": "lower_better"}


# ------------------------------------------------------------------
# Connecteur geolocations (pixel-grid-api) — voir docstring du module.
# ------------------------------------------------------------------

def parse_geolocations_response(data):
    """data : reponse brute de GET {pixel-grid-api}/geolocations.
    Ne retient que les positions reellement resolues (mapped=true) et
    exclut l'entree de repli (is_default=true, sans localisation reelle
    associee) -- ni l'une ni l'autre n'est correlable spatialement.
    Ne leve jamais : forme inattendue -> liste vide."""
    if not isinstance(data, dict):
        return []
    entries = data.get("geolocations")
    if not isinstance(entries, list):
        return []
    result = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if not e.get("mapped") or e.get("is_default"):
            continue
        lat, lon = e.get("latitude"), e.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        loc = e.get("localisation")
        if not loc:
            continue
        result.append({"localisation": str(loc), "latitude": lat, "longitude": lon})
    return result


# ------------------------------------------------------------------
# Journal en mémoire (/logs) — même bloc que les autres services.
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Client Memcached -- livraison #145, nécessaire au tampon de logs
# PARTAGÉ ci-dessous (ce service tourne avec 2 workers Gunicorn,
# processus séparés, mémoire NON partagée). Recréé à chaque appel
# (même motif établi ailleurs dans ce projet, voir api/app.py).
# ------------------------------------------------------------------
from pymemcache.client.base import Client as _MemcacheClient

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# ------------------------------------------------------------------
# Journal PARTAGE (/logs) -- stocke dans Memcached (voir
# shared/log_buffer.py), PAS un tampon en memoire de processus.
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "geo-import-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
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
# Routes
# ------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({"status": "ok"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "degraded", "error": str(exc)}), 200


@app.route("/layers", methods=["GET"])
def list_layers():
    """Liste les couches déjà importées — s'appuie sur la vue standard
    PostGIS `geometry_columns` plutôt que sur une table maison, pour
    rester cohérent avec ce que n'importe quel autre outil PostGIS
    (dont QGIS/GeoServer) verrait de la même base."""
    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base de staging injoignable : {exc}"}), 503
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT f_table_name AS name, type AS geometry_type, srid,
                          coord_dimension
                   FROM geometry_columns
                   WHERE f_table_schema = 'public'
                   ORDER BY f_table_name"""
            )
            layers = cur.fetchall()
        return jsonify({"layers": layers}), 200
    finally:
        conn.close()


@app.route("/import", methods=["POST"])
def import_shapefile():
    """Protégée par rights-api (#318) -- `groups` lu depuis
    `request.form` (multipart, jamais un corps JSON ici)."""
    allowed, error = _check_manage_right({"groups": request.form.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "fichier 'file' (archive .zip) requis"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "nom de fichier vide"}), 400

    requested_name = request.form.get("layer_name", "").strip()
    mode = request.form.get("mode", "overwrite")
    if mode not in ("overwrite", "append"):
        return jsonify({"error": "'mode' doit être 'overwrite' ou 'append'"}), 400

    workdir = tempfile.mkdtemp(prefix="geoimport_")
    try:
        zip_path = os.path.join(workdir, "upload.zip")
        upload.save(zip_path)

        try:
            with zipfile.ZipFile(zip_path) as zf:
                # Chemins RELATIFS COMPLETS (pas juste le nom de base) --
                # une copie de dossier de travail QGIS place presque
                # toujours ses shapefiles dans des sous-dossiers, jamais
                # à plat à la racine de l'archive.
                paths = [n for n in zf.namelist() if not n.endswith("/")]
                zf.extractall(workdir)
        except zipfile.BadZipFile:
            return jsonify({"error": "archive .zip invalide ou corrompue"}), 400

        discovery = find_shapefile_sets(paths)
        sets = discovery["sets"]
        if not sets:
            return jsonify({
                "error": "aucun jeu de shapefile complet (.shp+.shx+.dbf) trouvé dans l'archive",
                "details": discovery["skipped"],
            }), 400

        # Le nom personnalisé ne s'applique que si l'archive ne contient
        # QU'UN SEUL jeu -- avec plusieurs jeux (cas d'une copie de
        # dossier de travail QGIS complet), chacun garde son propre nom :
        # impossible de tous les nommer pareil sans collision, et
        # généralement pas souhaitable (chambres/fourreaux/câbles sont
        # des couches distinctes, pas des doublons à fusionner ici).
        single = len(sets) == 1

        results = []
        for s in sets:
            table_name = sanitize_layer_name(requested_name) if (single and requested_name) else sanitize_layer_name(s["base_name"])
            shp_full_path = os.path.join(workdir, s["shp_path"])

            cmd = build_ogr2ogr_import_command(shp_full_path, table_name, pg_dsn(), mode)
            # Traces DEBUG (livraison #224, audit rétroactif) --
            # RÈGLE ABSOLUE : `cmd` contient le DSN PostgreSQL, qui
            # inclut le mot de passe EN CLAIR (voir pg_dsn()) --
            # JAMAIS logger `cmd` tel quel, seulement les éléments
            # sûrs (table, mode, chemin du fichier).
            app.logger.debug("import ogr2ogr : démarré (table=%s, mode=%s, shapefile=%s, jamais le DSN/mot de passe ici)",
                             table_name, mode, shp_full_path)
            start = time.monotonic()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=110)
            except subprocess.TimeoutExpired:
                app.logger.debug("import ogr2ogr : ÉCHEC -- délai dépassé (>110s) pour la table %s", table_name)
                results.append({"layer": table_name, "ok": False, "error": "import trop long (>110s)", "warnings": []})
                continue
            except FileNotFoundError:
                app.logger.debug("import ogr2ogr : ÉCHEC -- binaire ogr2ogr introuvable")
                return jsonify({"error": "ogr2ogr introuvable dans le conteneur (gdal-bin manquant ?)"}), 500
            elapsed_ms = int((time.monotonic() - start) * 1000)

            parsed = parse_ogr2ogr_output(proc.returncode, proc.stdout, proc.stderr)
            app.logger.debug("import ogr2ogr : terminé en %d ms (table=%s, code retour=%s, %s)",
                             elapsed_ms, table_name, proc.returncode, "succès" if parsed["success"] else "échec")
            results.append({
                "layer": table_name,
                "ok": parsed["success"],
                "error": parsed["error"],
                "warnings": s["warnings"] + parsed["warnings"],
            })

        return jsonify({"imported": results, "skipped": discovery["skipped"]}), 200
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@app.route("/fusion", methods=["POST"])
def fusion():
    """Protégée par rights-api (#318)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    source_layers_raw = body.get("source_layers")
    target_layer_raw = body.get("target_layer", "")

    if not isinstance(source_layers_raw, list) or len(source_layers_raw) < 2:
        return jsonify({"error": "'source_layers' doit contenir au moins 2 couches"}), 400

    target_layer = sanitize_layer_name(target_layer_raw)
    if not target_layer or target_layer == "couche":
        return jsonify({"error": "nom de couche cible invalide ou vide"}), 400

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base de staging injoignable : {exc}"}), 503

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Existence réelle de chaque couche source -- jamais un nom
            # fourni par l'appel API utilisé tel quel dans le SQL de
            # fusion sans être d'abord vérifié contre ce que la base
            # connaît vraiment (même esprit que les listes blanches
            # ailleurs dans ce projet).
            cur.execute(
                "SELECT f_table_name FROM geometry_columns WHERE f_table_schema = 'public'"
            )
            known_layers = {row["f_table_name"] for row in cur.fetchall()}

            source_layers = [sanitize_layer_name(s) for s in source_layers_raw]
            unknown = [s for s in source_layers if s not in known_layers]
            if unknown:
                return jsonify({"error": f"couche(s) inconnue(s) : {', '.join(unknown)}"}), 400

            # colonnes communes à TOUTES les couches sources (jamais une
            # colonne absente d'une source comblée par une valeur
            # inventée -- voir en-tête du module)
            common_columns = None
            for layer in source_layers:
                cur.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = %s
                         AND column_name NOT IN ('geom', 'gid')""",
                    (layer,),
                )
                cols = {row["column_name"] for row in cur.fetchall()}
                common_columns = cols if common_columns is None else (common_columns & cols)

            common_columns = sorted(common_columns or [])
            sql = build_fusion_sql(source_layers, target_layer, ["geom"] + common_columns)

            cur.execute(f'DROP TABLE IF EXISTS "{target_layer}"')
            cur.execute(sql)
            conn.commit()

        return jsonify({
            "layer": target_layer,
            "sources": source_layers,
            "common_columns": common_columns,
        }), 200
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        return jsonify({"error": f"échec de la fusion : {exc}"}), 502
    finally:
        conn.close()


@app.route("/layers/<layer_name>/columns", methods=["GET"])
def layer_columns(layer_name):
    """Colonnes non-géométriques d'une couche — le frontend les utilise
    pour construire les sélecteurs de colonne des stratégies
    semantic/temporal (les colonnes d'un shapefile importé sont
    arbitraires, jamais supposées à l'avance)."""
    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base de staging injoignable : {exc}"}), 503
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT 1 FROM geometry_columns WHERE f_table_schema = 'public' AND f_table_name = %s",
                (layer_name,),
            )
            if not cur.fetchone():
                return jsonify({"error": f"couche '{layer_name}' inconnue"}), 404
            cur.execute(
                """SELECT column_name, data_type FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = %s
                     AND column_name NOT IN ('geom', 'gid')
                   ORDER BY column_name""",
                (layer_name,),
            )
            columns = cur.fetchall()
        return jsonify({"layer": layer_name, "columns": columns}), 200
    finally:
        conn.close()


@app.route("/correlate", methods=["POST"])
def correlate():
    body = request.get_json(silent=True) or {}
    layer_a = sanitize_layer_name(body.get("layer_a", ""))
    layer_b = sanitize_layer_name(body.get("layer_b", ""))
    strategy = body.get("strategy")
    options = body.get("options") or {}

    if strategy not in CORRELATION_STRATEGIES:
        return jsonify({"error": f"'strategy' doit être l'une de : {', '.join(sorted(CORRELATION_STRATEGIES))}"}), 400
    if not layer_a or not layer_b or layer_a == "couche" or layer_b == "couche":
        return jsonify({"error": "'layer_a' et 'layer_b' requis"}), 400

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base de staging injoignable : {exc}"}), 503

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT f_table_name FROM geometry_columns WHERE f_table_schema = 'public' AND f_table_name IN (%s, %s)",
                (layer_a, layer_b),
            )
            known = {row["f_table_name"] for row in cur.fetchall()}
            missing = [l for l in (layer_a, layer_b) if l not in known]
            if missing:
                return jsonify({"error": f"couche(s) inconnue(s) : {', '.join(missing)}"}), 400

            def known_columns(layer):
                cur.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = %s""",
                    (layer,),
                )
                return {row["column_name"] for row in cur.fetchall()}

            if strategy == "semantic":
                column_a, column_b = options.get("column_a"), options.get("column_b")
                threshold = float(options.get("threshold", 0.3))
                if column_a not in known_columns(layer_a) or column_b not in known_columns(layer_b):
                    return jsonify({"error": "'column_a'/'column_b' doivent être des colonnes existantes des couches choisies"}), 400
                cur.execute(f'SELECT COUNT(*) AS n FROM "{layer_a}"')
                count_a = cur.fetchone()["n"]
                cur.execute(f'SELECT COUNT(*) AS n FROM "{layer_b}"')
                count_b = cur.fetchone()["n"]
                if estimate_join_size(count_a, count_b) > MAX_CROSS_JOIN_PRODUCT:
                    return jsonify({"error": f"trop de lignes pour une corrélation exploratoire ({count_a}×{count_b} > {MAX_CROSS_JOIN_PRODUCT}) — réduisez le périmètre des couches"}), 400
                sql, params = build_semantic_correlation_sql(layer_a, layer_b, column_a, column_b, threshold, MAX_CORRELATION_RESULTS)

            elif strategy == "geographic":
                max_distance_m = float(options.get("max_distance_m", 50))
                sql, params = build_geographic_correlation_sql(layer_a, layer_b, max_distance_m, MAX_CORRELATION_RESULTS)

            else:  # temporal
                column_a, column_b = options.get("column_a"), options.get("column_b")
                window_days = float(options.get("window_days", 30))
                if column_a not in known_columns(layer_a) or column_b not in known_columns(layer_b):
                    return jsonify({"error": "'column_a'/'column_b' doivent être des colonnes existantes des couches choisies"}), 400
                cur.execute(f'SELECT COUNT(*) AS n FROM "{layer_a}"')
                count_a = cur.fetchone()["n"]
                cur.execute(f'SELECT COUNT(*) AS n FROM "{layer_b}"')
                count_b = cur.fetchone()["n"]
                if estimate_join_size(count_a, count_b) > MAX_CROSS_JOIN_PRODUCT:
                    return jsonify({"error": f"trop de lignes pour une corrélation exploratoire ({count_a}×{count_b} > {MAX_CROSS_JOIN_PRODUCT}) — réduisez le périmètre des couches"}), 400
                sql, params = build_temporal_correlation_sql(layer_a, layer_b, column_a, column_b, window_days, MAX_CORRELATION_RESULTS)

            cur.execute(sql, params)
            candidates = cur.fetchall()

        return jsonify({
            "candidates": candidates,
            "count": len(candidates),
            "truncated": len(candidates) >= MAX_CORRELATION_RESULTS,
            "score_direction": SCORE_DIRECTION[strategy],
        }), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"échec de la corrélation : {exc}"}), 502
    finally:
        conn.close()


@app.route("/connectors/geolocations/sync", methods=["POST"])
def sync_geolocations_connector():
    """Matérialise la table `geolocations` de pixel-grid-api (déjà
    transversale : alimentée par Fusion IP/MAC ET OwnCloud) en table
    PostGIS interrogeable spatialement — TOUJOURS via l'API HTTP de
    pixel-grid, jamais un accès direct à sa base (dont le backend peut
    être SQLite ou PostgreSQL selon la config, invisible d'ici et sans
    que ça devrait importer).

    Protégée par rights-api (#318)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    app.logger.debug("sync_geolocations_connector : démarré -- GET %s/geolocations", PIXEL_GRID_API_URL)
    start = time.monotonic()
    try:
        response = requests.get(f"{PIXEL_GRID_API_URL}/geolocations", timeout=CONNECTOR_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("sync_geolocations_connector : ÉCHEC réseau après %d ms -- %s", elapsed_ms, exc)
        return jsonify({"error": f"pixel-grid-api injoignable : {exc}"}), 502
    except ValueError:
        app.logger.debug("sync_geolocations_connector : ÉCHEC -- réponse non-JSON")
        return jsonify({"error": "réponse de pixel-grid-api illisible (pas du JSON)"}), 502
    elapsed_ms = int((time.monotonic() - start) * 1000)
    app.logger.debug("sync_geolocations_connector : succès en %d ms", elapsed_ms)

    rows = parse_geolocations_response(data)

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base de staging injoignable : {exc}"}), 503

    try:
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS "connector_geolocations"')
            cur.execute(
                'CREATE TABLE "connector_geolocations" ('
                'gid SERIAL PRIMARY KEY, localisation TEXT, '
                'geom geometry(Point, 4326))'
            )
            for row in rows:
                cur.execute(
                    'INSERT INTO "connector_geolocations" (localisation, geom) '
                    'VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))',
                    (row["localisation"], row["longitude"], row["latitude"]),
                )
            # geometry_columns est une VUE PostGIS (depuis la 2.0), qui
            # introspecte automatiquement pg_catalog pour toute colonne
            # de type geometry -- rien a y inserer manuellement, la
            # table ci-dessus y apparait deja d'elle-meme.
            conn.commit()
        return jsonify({"layer": "connector_geolocations", "synced": len(rows)}), 200
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        return jsonify({"error": f"échec de la synchronisation : {exc}"}), 502
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
