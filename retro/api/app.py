"""
retro-api -- livraison #243, backlog item 30 ("Rétro-ingénierie"),
demandé explicitement en urgence : "vieille application... aucune
note, développeur génial avait ses schémas en tête". Expose
`php_sql_scanner.py` (relations depuis les JOINTURES SQL),
`html_view_scanner.py` (structures de champs depuis les VUES
D'ÉCRAN, livraison #245) et, depuis la livraison #248,
`route_scanner.py` (second volet demandé à l'origine -- schéma
FONCTIONNEL de l'application, déduit des déclarations de routage
Fat-Free) via une route unique acceptant une archive ZIP du code
source à analyser.

⚠️ **Version de Fat-Free NON CONFIRMÉE** -- la personne pense qu'il
s'agit de la lignée 2.x, sans certitude. Les motifs couverts ici
(route(), Mapper, {{@var}}) sont documentés comme stables sur une
large part de l'historique F3 (recherché explicitement, y compris
la coexistence historique des syntaxes statique `F3::` et instance
`$f3->`, déjà couvertes toutes les deux) -- mais AUCUNE
documentation officielle spécifique à la lignée 2.x n'a pu être
trouvée (le site officiel n'archive plus, semble-t-il, que 3.6+).
Les résultats réels sur le code de la personne restent le meilleur
signal pour confirmer ou ajuster cette couverture.
"""
import os
import zipfile

from flask import Flask, jsonify, request
from flask_cors import CORS

import php_sql_scanner as scanner
import html_view_scanner as view_scanner
import route_scanner

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "retro-api")

# Bornes de sécurité (livraison #243) -- une archive ZIP mal formée
# ou malveillante ne doit jamais faire tourner ce service indéfiniment
# ni consommer une mémoire disproportionnée.
MAX_PHP_FILES = 5000
MAX_TOTAL_UNCOMPRESSED_SIZE = 200 * 1024 * 1024  # 200 Mo -- large marge pour une appli PHP entière, jamais un dump de données

# Extensions balayées (livraison #245) -- une vue Fat-Free peut être
# écrite en `.php` (classe View, PHP brut affiché) OU en `.html`/
# `.htm`/`.phtml` (gabarits natifs Template) selon l'époque du code
# -- la personne l'a signalé explicitement ("varié selon les époques
# de l'évolution du code"). Les DEUX scanners (SQL + vues) tournent
# sur CHAQUE fichier retenu, quelle que soit son extension -- un
# fichier `.php` peut très bien contenir À LA FOIS une requête SQL
# ET du HTML affiché directement (mélange courant en PHP ancien
# style, sans séparation stricte contrôleur/vue).
SCANNED_EXTENSIONS = (".php", ".phtml", ".html", ".htm")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/scan", methods=["POST"])
def scan_upload():
    """multipart/form-data : `file` (requis) -- une archive ZIP du
    code source à analyser (l'arborescence complète d'une appli, ou
    un sous-dossier ciblé). Chaque fichier `.php`/`.phtml`/`.html`/
    `.htm` est balayé par LES DEUX scanners -- voir
    `php_sql_scanner.scan_php_source` (relations depuis les
    jointures SQL) et `html_view_scanner.scan_view_source`
    (structures de champs depuis les formulaires et gabarits,
    livraison #245). Renvoie les relations SQL CANDIDATES
    dédupliquées, les tables identifiées via le motif Fat-Free
    `Mapper`, les formulaires trouvés (champs bruts) et les
    structures de champs fusionnées par variable de gabarit.

    **Protection contre le "zip slip"** -- un chemin d'entrée
    d'archive qui sortirait du dossier (`../../etc/passwd`) est
    IGNORÉ, jamais suivi -- ce service ne DÉCOMPRESSE d'ailleurs
    jamais sur disque, tout est lu en mémoire directement depuis
    l'archive (`zf.read()`), donc ce risque particulier est de toute
    façon structurellement écarté ici -- le filtre reste une défense
    en profondeur, pas la seule protection."""
    if "file" not in request.files:
        return jsonify({"error": "fichier requis (champ 'file', une archive ZIP du code source à analyser)"}), 400
    uploaded = request.files["file"]
    try:
        zf = zipfile.ZipFile(uploaded.stream)
    except zipfile.BadZipFile:
        return jsonify({"error": "fichier ZIP invalide ou corrompu"}), 400

    all_candidates = []
    all_mapper_tables = set()
    all_forms = []
    all_view_results = []
    all_routes = []
    scanned_files = 0
    skipped_files = []
    total_size = 0

    for info in zf.infolist():
        if info.is_dir():
            continue
        normalized = os.path.normpath(info.filename)
        if normalized.startswith("..") or os.path.isabs(normalized):
            continue  # jamais suivi hors de l'archive -- voir docstring
        if not normalized.lower().endswith(SCANNED_EXTENSIONS):
            continue
        if scanned_files >= MAX_PHP_FILES:
            skipped_files.append(normalized)
            continue
        total_size += info.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_SIZE:
            return jsonify({
                "error": f"archive trop volumineuse une fois décompressée "
                         f"(> {MAX_TOTAL_UNCOMPRESSED_SIZE // (1024 * 1024)} Mo) -- analyse interrompue",
            }), 400
        try:
            content = zf.read(info.filename).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 -- un fichier illisible individuel ne doit jamais arrêter toute l'analyse
            skipped_files.append(normalized)
            continue

        sql_result = scanner.scan_php_source(content, filename=normalized)
        all_candidates.extend(sql_result["join_candidates"])
        all_mapper_tables.update(sql_result["mapper_tables"])

        view_result = view_scanner.scan_view_source(content, filename=normalized)
        all_forms.extend(view_result["forms"])
        all_view_results.append(view_result)

        all_routes.extend(route_scanner.extract_routes(content, filename=normalized))

        scanned_files += 1

    deduped = scanner.deduplicate_candidates(all_candidates)
    merged_template_fields = view_scanner.merge_template_field_results(all_view_results)
    # Clé `None` (routes sans contrôleur identifiable -- closures,
    # fonctions globales) remplacée par un libellé lisible AVANT
    # sérialisation JSON -- `json.dumps` convertirait silencieusement
    # `None` en la chaîne "null", moins clair pour la personne que ce
    # libellé explicite.
    routes_by_controller_raw = route_scanner.group_routes_by_controller(all_routes)
    routes_by_controller = {
        (key if key is not None else "(closure ou fonction globale)"): value
        for key, value in routes_by_controller_raw.items()
    }
    return jsonify({
        "scanned_files": scanned_files,
        "skipped_files": skipped_files,
        "join_candidates": deduped,
        "mapper_tables": sorted(all_mapper_tables),
        "forms": all_forms,
        "template_fields": merged_template_fields,
        "routes": all_routes,
        "routes_by_controller": routes_by_controller,
    }), 200


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


SERVICE_NAME = "retro-api"
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
    app.run(host="0.0.0.0", port=5000)
