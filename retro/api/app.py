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
import hmac
import logging
import os
import re
import zipfile

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests as _requests

import php_sql_scanner as scanner
import html_view_scanner as view_scanner
import route_scanner
import journeys
import journeys_store as jstore
import ui_spec

_log = logging.getLogger("retro_app")

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

# ---- Parcours applicatifs (#441) ---------------------------------------------------
# Stockage (retro-api était sans état), jeton partagé avec l'agent relais
# (`X-Relay-Token`, comparaison en temps constant ; vide = ingestion
# refusée), dba-api pour lire le journal général MySQL de l'application.
DATA_DIR = os.environ.get("RETRO_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "retro.db")
RELAY_TOKEN = os.environ.get("RETRO_RELAY_TOKEN", "").strip()
DBA_API_INTERNAL_URL = os.environ.get("DBA_API_INTERNAL_URL", "http://dba-api:5000").rstrip("/")
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None
_CLASS_PATTERN = re.compile(r"^\s*(?:abstract\s+|final\s+)?class\s+(\w+)", re.M)
try:
    jstore.ensure_schema(DB_PATH)
except OSError as exc:  # dossier absent en dev : les routes /journeys renverront une erreur claire
    _log.warning("base des parcours indisponible (%s) : %s", DB_PATH, exc)


def _check_manage_right(body):
    """Même motif que les autres services (#294) : fail-closed ; sans
    RIGHTS_API_URL, ouvert (comportement historique de retro-api)."""
    if not RIGHTS_API_URL:
        return True, None
    groups = (body or {}).get("groups") or []
    try:
        resp = _requests.post(f"{RIGHTS_API_URL}/check", json={"groups": groups, "resource_type": "retro-api", "resource_id": None, "action": "manage"}, timeout=5)
    except _requests.RequestException:
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = bool(resp.json().get("allowed", False))
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    return allowed, None if allowed else "droit 'manage' sur retro-api requis"


def _relay_authorized():
    token = request.headers.get("X-Relay-Token", "")
    return bool(RELAY_TOKEN) and hmac.compare_digest(token, RELAY_TOKEN)


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
    file_tables, classes = {}, {}
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
        # #441 : tables par fichier et classes par fichier, pour rapprocher un
        # écran parcouru (route -> contrôleur -> fichier) de ses tables
        if sql_result["mapper_tables"]:
            file_tables[normalized] = sorted(sql_result["mapper_tables"])
        for cls in _CLASS_PATTERN.findall(content):
            classes.setdefault(cls, normalized)

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
    result = {
        "scanned_files": scanned_files,
        "skipped_files": skipped_files,
        "join_candidates": deduped,
        "mapper_tables": sorted(all_mapper_tables),
        "forms": all_forms,
        "template_fields": merged_template_fields,
        "routes": all_routes,
        "routes_by_controller": routes_by_controller,
        "file_tables": file_tables,
        "classes": classes,
    }
    # #441 : `app=<libellé>` (query ou champ de formulaire) conserve ce scan
    # comme référence de code de l'application, pour les parcours.
    app_label = (request.args.get("app") or request.form.get("app") or "").strip()
    if app_label:
        try:
            jstore.save_scan(DB_PATH, app_label, {k: v for k, v in result.items() if k != "forms"})
            result["saved_for_app"] = app_label
        except Exception as exc:  # noqa: BLE001
            result["saved_for_app"] = None
            result["save_error"] = str(exc)
    return jsonify(result), 200


# ------------------------------------------------------------------
# Parcours applicatifs (#441) : applications, parcours, événements du
# relais, carte fonctionnelle, requêtes SQL réellement exécutées.
# ------------------------------------------------------------------

@app.route("/apps", methods=["GET"])
def apps_list():
    return jsonify({"apps": jstore.list_apps(DB_PATH), "relay_token_configured": bool(RELAY_TOKEN)}), 200


@app.route("/apps", methods=["POST"])
def apps_upsert():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label = (body.get("label") or "").strip()
    if not label or len(label) > 80:
        return jsonify({"error": "'label' requis (80 caractères max.)"}), 400
    a = jstore.upsert_app(DB_PATH, label, base_url=(body.get("base_url") or "").strip() or None,
                          dba_connection_id=body.get("dba_connection_id"), dba_database=body.get("dba_database"))
    return jsonify(a), 200


@app.route("/apps/<label>", methods=["GET"])
def apps_get(label):
    a = jstore.get_app(DB_PATH, label, with_scan=request.args.get("scan") == "1")
    if a is None:
        return jsonify({"error": "application inconnue"}), 404
    return jsonify(a), 200


@app.route("/apps/<label>", methods=["DELETE"])
def apps_delete(label):
    allowed, error = _check_manage_right(request.get_json(silent=True) or {})
    if not allowed:
        return jsonify({"error": error}), 403
    return (jsonify({"deleted": True}), 200) if jstore.delete_app(DB_PATH, label) else (jsonify({"error": "application inconnue"}), 404)


@app.route("/apps/<label>/map", methods=["GET"])
def apps_map(label):
    """Carte fonctionnelle AGRÉGÉE sur tous les parcours terminés ou en
    cours de l'application : écrans ↔ routes ↔ tables."""
    a = jstore.get_app(DB_PATH, label, with_scan=True)
    if a is None:
        return jsonify({"error": "application inconnue"}), 404
    steps, m = _app_steps(label, a)
    return jsonify({"app": label, "has_scan": a["has_scan"], "journeys": len(jstore.list_journeys(DB_PATH, app=label)), **m}), 200


def _app_steps(label, a):
    """Toutes les étapes de tous les parcours d'une application (avec le
    SQL collecté), et la carte fonctionnelle."""
    steps = []
    for j in jstore.list_journeys(DB_PATH, app=label):
        s = journeys.build_steps(jstore.get_events(DB_PATH, j["id"]), a.get("base_url"))
        journeys.attribute_queries(s, jstore.get_queries(DB_PATH, j["id"]))
        for st in s:
            st["journey_id"] = j["id"]
        steps.extend(s)
    return steps, journeys.functional_map(steps, a.get("scan"), a.get("base_url"))


def fetch_columns(dba_url, conn_id, database, tables, http=None):
    """{table: colonnes} via dba-api (best-effort : une table illisible est
    simplement absente)."""
    http = http or _requests.get
    out = {}
    for t in tables:
        try:
            resp = http(f"{dba_url}/connections/{conn_id}/tables/{t}/columns", params={"database": database} if database else None, timeout=15)
            data = resp.json()
            if resp.status_code == 200 and isinstance(data, list):
                out[t] = data
        except (_requests.RequestException, ValueError):
            continue
    return out


@app.route("/apps/<label>/ui-spec", methods=["GET"])
def apps_ui_spec(label):
    """#444 : spécification de l'interface générée. Enregistrée si elle
    existe (choix manuels conservés) ; `?regenerate=1` la recalcule
    depuis les parcours, la carte et les colonnes réelles (dba-api), en
    gardant les choix manuels de la version précédente."""
    a = jstore.get_app(DB_PATH, label, with_scan=True)
    if a is None:
        return jsonify({"error": "application inconnue"}), 404
    existing = jstore.get_ui_spec(DB_PATH, label)
    if existing and request.args.get("regenerate") != "1":
        return jsonify({**existing, "saved": True}), 200
    steps, fmap = _app_steps(label, a)
    columns = {}
    if a.get("dba_connection_id"):
        columns = fetch_columns(DBA_API_INTERNAL_URL, a["dba_connection_id"], a.get("dba_database"), sorted(fmap.get("tables") or {}))
    spec = ui_spec.build_ui_spec(steps, fmap, columns, label, existing=existing)
    spec["dba_connection_id"], spec["dba_database"] = a.get("dba_connection_id"), a.get("dba_database")
    spec["generated_at"] = jstore.now_iso()
    jstore.save_ui_spec(DB_PATH, label, spec)
    return jsonify({**spec, "saved": True, "regenerated": True}), 200


@app.route("/apps/<label>/ui-spec", methods=["PUT"])
def apps_ui_spec_put(label):
    """Enregistre une spec modifiée à la main (table d'un écran, colonnes,
    titres, écrans masqués) -- les marqueurs `*_manual` protègent ces
    choix lors d'une régénération."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    spec = body.get("spec")
    if not isinstance(spec, dict) or not isinstance(spec.get("screens"), list):
        return jsonify({"error": "'spec' : objet {screens: [...]} attendu"}), 400
    if not jstore.save_ui_spec(DB_PATH, label, spec):
        return jsonify({"error": "application inconnue"}), 404
    return jsonify({"saved": True, "screens": len(spec["screens"])}), 200


@app.route("/journeys", methods=["GET"])
def journeys_list():
    return jsonify({"journeys": jstore.list_journeys(DB_PATH, app=request.args.get("app"))}), 200


@app.route("/journeys", methods=["POST"])
def journeys_create():
    """Depuis le hub (droit manage) OU depuis le relais (jeton) : {app,
    name, tester, base_url}."""
    body = request.get_json(silent=True) or {}
    if not _relay_authorized():
        allowed, error = _check_manage_right(body)
        if not allowed:
            return jsonify({"error": error}), 403
    appl = (body.get("app") or "").strip()
    if not appl:
        return jsonify({"error": "'app' requis"}), 400
    branch = body.get("branch_step")
    try:
        branch = int(branch) if branch not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "'branch_step' entier attendu"}), 400
    j = jstore.create_journey(DB_PATH, appl, name=(body.get("name") or "").strip() or None, tester=(body.get("tester") or "").strip() or None,
                              base_url=(body.get("base_url") or "").strip() or None, parent_id=(body.get("parent_id") or "").strip() or None,
                              branch_step=branch, kind=body.get("kind") or "recorded")
    if j is None:
        return jsonify({"error": "parcours parent inconnu"}), 404
    return jsonify(j), 201


def _journey_detail(j):
    a = jstore.get_app(DB_PATH, j["app"], with_scan=True) or {}
    steps = journeys.build_steps(jstore.get_events(DB_PATH, j["id"]), a.get("base_url"))
    journeys.attribute_queries(steps, jstore.get_queries(DB_PATH, j["id"]))
    for st in steps:
        st["annotation"] = (j.get("annotations") or {}).get(str(st["n"]))
    fmap = journeys.functional_map(steps, a.get("scan"), a.get("base_url"))
    return {**j, "base_url": a.get("base_url"), "has_scan": bool(a.get("has_scan")), "steps": steps, "map": fmap}


@app.route("/journeys/<jid>", methods=["GET"])
def journeys_get(jid):
    j = jstore.get_journey(DB_PATH, jid)
    if j is None:
        return jsonify({"error": "parcours inconnu"}), 404
    return jsonify(_journey_detail(j)), 200


@app.route("/journeys/<jid>", methods=["DELETE"])
def journeys_delete(jid):
    allowed, error = _check_manage_right(request.get_json(silent=True) or {})
    if not allowed:
        return jsonify({"error": error}), 403
    return (jsonify({"deleted": True}), 200) if jstore.delete_journey(DB_PATH, jid) else (jsonify({"error": "parcours inconnu"}), 404)


@app.route("/journeys/<jid>/events", methods=["POST"])
def journeys_events(jid):
    """Ingestion par l'agent relais : {events: [{seq?, at, kind, data}]},
    jeton `X-Relay-Token` obligatoire. Idempotent sur `seq`."""
    if not _relay_authorized():
        return jsonify({"error": "jeton de relais absent ou invalide (RETRO_RELAY_TOKEN)"}), 401
    body = request.get_json(silent=True) or {}
    events = body.get("events")
    if not isinstance(events, list):
        return jsonify({"error": "'events' : liste attendue"}), 400
    if len(events) > 2000:
        return jsonify({"error": "lot trop grand (2000 événements max.)"}), 400
    r, err = jstore.add_events(DB_PATH, jid, events)
    if err:
        return jsonify({"error": err}), 404 if "inconnu" in err else 409
    return jsonify(r), 200


@app.route("/journeys/<jid>/end", methods=["POST"])
def journeys_end(jid):
    body = request.get_json(silent=True) or {}
    if not _relay_authorized():
        allowed, error = _check_manage_right(body)
        if not allowed:
            return jsonify({"error": error}), 403
    if not jstore.end_journey(DB_PATH, jid, notes=body.get("notes")):
        return jsonify({"error": "parcours inconnu"}), 404
    return jsonify(jstore.get_journey(DB_PATH, jid)), 200


@app.route("/journeys/<jid>/annotate", methods=["POST"])
def journeys_annotate(jid):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    try:
        step = int(body.get("step"))
    except (TypeError, ValueError):
        return jsonify({"error": "'step' entier requis"}), 400
    ann = jstore.annotate(DB_PATH, jid, step, (body.get("text") or "").strip())
    if ann is None:
        return jsonify({"error": "parcours inconnu"}), 404
    return jsonify({"annotations": ann}), 200


@app.route("/journeys/<jid>/script", methods=["GET"])
def journeys_script(jid):
    """#443 : script de rejeu (navigate / click / fill / submit / expect /
    mark) dérivé des étapes -- lu par le relais pour l'extension."""
    j = jstore.get_journey(DB_PATH, jid)
    if j is None:
        return jsonify({"error": "parcours inconnu"}), 404
    a = jstore.get_app(DB_PATH, j["app"]) or {}
    steps = journeys.build_steps(jstore.get_events(DB_PATH, jid), a.get("base_url"))
    return jsonify({"journey_id": jid, "app": j["app"], "name": j["name"], "base_url": a.get("base_url"), "steps": len(steps),
                    "script": journeys.replay_script(steps)}), 200


@app.route("/journeys/<jid>/replay", methods=["POST"])
def journeys_replay(jid):
    """#443 : prépare un rejeu -- crée le parcours enfant (kind=replay, même
    application) qui recevra les événements du rejeu, et renvoie le script.
    Relais (jeton) ou hub (manage)."""
    body = request.get_json(silent=True) or {}
    if not _relay_authorized():
        allowed, error = _check_manage_right(body)
        if not allowed:
            return jsonify({"error": error}), 403
    j = jstore.get_journey(DB_PATH, jid)
    if j is None:
        return jsonify({"error": "parcours inconnu"}), 404
    a = jstore.get_app(DB_PATH, j["app"]) or {}
    steps = journeys.build_steps(jstore.get_events(DB_PATH, jid), a.get("base_url"))
    child = jstore.create_journey(DB_PATH, j["app"], name="rejeu de %s" % (j["name"] or jid), tester=(body.get("tester") or "").strip() or None,
                                  parent_id=jid, branch_step=None, kind="replay")
    return jsonify({"journey": child, "base_url": a.get("base_url"), "script": journeys.replay_script(steps)}), 201


@app.route("/journeys/<jid>/compare/<other>", methods=["GET"])
def journeys_compare(jid, other):
    """#443 : deux parcours alignés étape par étape (écran, statut,
    formulaires, en-têtes, tableaux, requêtes secondaires, tables SQL)."""
    ja, jb = jstore.get_journey(DB_PATH, jid), jstore.get_journey(DB_PATH, other)
    if ja is None or jb is None:
        return jsonify({"error": "parcours inconnu"}), 404
    out = []
    for j in (ja, jb):
        a = jstore.get_app(DB_PATH, j["app"]) or {}
        steps = journeys.build_steps(jstore.get_events(DB_PATH, j["id"]), a.get("base_url"))
        journeys.attribute_queries(steps, jstore.get_queries(DB_PATH, j["id"]))
        out.append(steps)
    return jsonify({"a": {"id": ja["id"], "name": ja["name"], "kind": ja["kind"]}, "b": {"id": jb["id"], "name": jb["name"], "kind": jb["kind"]},
                    **journeys.compare_journeys(out[0], out[1])}), 200


def fetch_general_log(dba_url, conn_id, database, since, until, http=None):
    """Requêtes du journal général MySQL (`mysql.general_log`, `log_output=TABLE`)
    entre deux instants, via dba-api. (liste [{at, sql, user, thread_id}], erreur)."""
    http = http or _requests.post
    sql = ("SELECT event_time, user_host, thread_id, argument FROM mysql.general_log "
           "WHERE command_type = 'Query' AND event_time >= '%s' AND event_time < '%s' ORDER BY event_time LIMIT 20000"
           % (since.replace("T", " ").rstrip("Z"), until.replace("T", " ").rstrip("Z")))
    try:
        resp = http(f"{dba_url}/connections/{conn_id}/sql", json={"sql": sql, "database": database or None, "groups": ["admin_hub"]}, timeout=60)
    except _requests.RequestException as exc:
        return None, f"dba-api injoignable : {exc}"
    try:
        data = resp.json()
    except ValueError:
        return None, "réponse de dba-api illisible"
    if resp.status_code != 200 or "error" in data:
        return None, "dba-api : %s" % (data.get("error") or resp.status_code)
    cols = data.get("columns") or []
    out = []
    for row in data.get("rows") or []:
        r = dict(zip(cols, row))
        arg = r.get("argument")
        if isinstance(arg, (bytes, bytearray)):
            arg = arg.decode("utf-8", "replace")
        out.append({"at": str(r.get("event_time") or ""), "sql": str(arg or ""), "user": r.get("user_host"), "thread_id": str(r.get("thread_id") or "")})
    return out, None


@app.route("/journeys/<jid>/queries/collect", methods=["POST"])
def journeys_collect_queries(jid):
    """« Analyse bdd » : lit le journal général MySQL de l'application
    (connexion dba-api de l'application, ou `dba_connection_id` /
    `dba_database` du corps) entre le début et la fin du parcours, et
    rattache chaque requête à son étape. Prérequis côté MySQL :
    `SET GLOBAL general_log = 'ON', log_output = 'TABLE'` pendant le test
    (à couper après : volumineux)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    j = jstore.get_journey(DB_PATH, jid)
    if j is None:
        return jsonify({"error": "parcours inconnu"}), 404
    a = jstore.get_app(DB_PATH, j["app"]) or {}
    conn_id = body.get("dba_connection_id") or a.get("dba_connection_id")
    database = body.get("dba_database") or a.get("dba_database")
    if not conn_id:
        return jsonify({"error": "aucune connexion dba-api : renseigner dba_connection_id (application ou requête)"}), 400
    until = j.get("ended_at") or jstore.now_iso()
    queries, err = fetch_general_log(DBA_API_INTERNAL_URL, conn_id, database, j["started_at"], until)
    if err:
        return jsonify({"error": err}), 502
    n = jstore.replace_queries(DB_PATH, jid, queries)
    detail = _journey_detail(jstore.get_journey(DB_PATH, jid))
    attributed = sum(len(s.get("queries") or []) for s in detail["steps"])
    return jsonify({"collected": n, "attributed": attributed, "steps": len(detail["steps"]), "tables": len(detail["map"]["tables"])}), 200


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
