"""
nebula-api -- livraison #196, second "besoin immédiat" de la demande
GLPI (#192) : "importer les données d'un site sous nebula.zyxel.com".
Voir nebula_client.py pour le détail complet (recherche API,
prérequis bloquants : licence Nebula Pro Pack + clé obtenue via un
dossier support Zyxel, jamais en libre-service).

Cette livraison couvre la CONNEXION et la CONSULTATION (organisations,
sites, appareils d'un site) -- PAS ENCORE l'import vers GLPI
(volontairement laissé pour une étape suivante, une fois la connexion
elle-même validée en conditions réelles par la personne -- empiler un
import NON TESTÉ sur une connexion NON TESTÉE aurait démultiplié le
risque sans bénéfice réel avant un premier retour concret).

**⚠️ Jamais testé contre une vraie API Nebula** -- voir
nebula_client.py.
"""
import logging
import os
import sqlite3
import time

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import nebula_client as nebula
import csv_import

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "nebula-api")

_log = logging.getLogger("nebula_app")

# Branchement rights-api -- livraison #314, item 38 du backlog.
# Ce module ne configure JAMAIS Nebula lui-même (connexion et
# consultation seulement -- voir docstring en tête de fichier) --
# les routes d'écriture ici touchent UNIQUEMENT le cache LOCAL
# (import de CSV exportés depuis Nebula, suppression de lots
# importés). Un import falsifié ou une suppression pourrait quand
# même induire en erreur (données fausses insérées silencieusement,
# voir la trouvaille documentée sur _import_csv_route -- ou un
# import légitime supprimé sans que personne le remarque). Gardé sur
# les 3 routes d'import (mutualisées via _import_csv_route) et les 2
# routes de suppression -- jamais la consultation.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-313) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "nebula-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur nebula-api requis (groupe admin_hub, ou un octroi explicite)"

NEBULA_API_KEY = os.environ.get("NEBULA_API_KEY", "").strip() or None
NEBULA_BASE_URL = os.environ.get("NEBULA_BASE_URL", "").strip() or None

# Archivage des fichiers CSV importés (livraison #237, demandé
# explicitement) -- appel CONTENEUR-À-CONTENEUR vers ged-api, même
# motif que NEBULA_API_INTERNAL_URL/SNMP_API_INTERNAL_URL déjà
# utilisés ailleurs dans ce projet (glpi/api/app.py).
GED_API_INTERNAL_URL = os.environ.get("GED_API_INTERNAL_URL", "http://ged-api:5000").rstrip("/")

# Stockage des imports CSV (livraison #200, "note et évolution
# nebula" -- "import et présentation des csv sur le modèle
# ci-joint"). Premier stockage PERSISTANT de ce module (jusqu'ici
# purement passe-plat vers l'API Nebula, #196, sans base). Voir
# csv_import.py pour le détail du format réel et nebula/README.md
# pour le contexte complet (pourquoi le CSV en complément de l'API).
DB_PATH = os.environ.get("NEBULA_DB_PATH", "/data/nebula.db")

SCHEMA = """
-- Chaque import ajoute des lignes, JAMAIS un remplacement en place --
-- permet une vue "historique dans le temps" (statistiques d'usage,
-- apparition/disparition d'appareils) plutôt qu'un simple miroir de
-- l'état courant. `imported_at` + la clé naturelle (mac_address pour
-- devices/clients, name pour sites) permettent de retrouver la
-- DERNIÈRE valeur connue (voir _latest_by, plus bas) sans empêcher
-- de retracer l'historique complet au besoin.
CREATE TABLE IF NOT EXISTS nebula_sites_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT, name TEXT NOT NULL, tags TEXT, devices_count INTEGER,
    usage TEXT, usage_bytes INTEGER, clients_count INTEGER,
    offline_devices INTEGER, percent_offline TEXT, template TEXT,
    imported_at TEXT NOT NULL, source_filename TEXT
);
CREATE INDEX IF NOT EXISTS idx_nebula_sites_name ON nebula_sites_import(name);

CREATE TABLE IF NOT EXISTS nebula_devices_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT, device_type TEXT, model TEXT, site TEXT,
    mac_address TEXT NOT NULL, tags TEXT, clients_count INTEGER,
    usage TEXT, usage_bytes INTEGER, name TEXT,
    imported_at TEXT NOT NULL, source_filename TEXT
);
CREATE INDEX IF NOT EXISTS idx_nebula_devices_mac ON nebula_devices_import(mac_address);

CREATE TABLE IF NOT EXISTS nebula_clients_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT, name TEXT, mac_address TEXT NOT NULL, ipv4_address TEXT,
    connected_to TEXT, manufacturer TEXT, os TEXT, policy TEXT, band TEXT,
    rx_rate TEXT, tx_rate TEXT, ssid_name TEXT, signal_strength TEXT,
    last_seen TEXT, imported_at TEXT NOT NULL, source_filename TEXT
);
CREATE INDEX IF NOT EXISTS idx_nebula_clients_mac ON nebula_clients_import(mac_address);

-- Un lot = UN import (un fichier déposé une fois) -- demandé
-- explicitement (livraison #237, backlog item 16) : une sélection +
-- un bouton "Supprimer" au-delà du simple "annuler le tout dernier
-- import" déjà livré en #235. `ged_document_id` : id Mayan du fichier
-- CSV original archivé dans la GED (livraison #237, best-effort --
-- NULL si l'archivage a échoué, jamais bloquant pour l'import
-- lui-même, voir `_import_csv_route`). Supprimer un lot retire les
-- LIGNES importées (table type par type) mais garde VOLONTAIREMENT
-- le document archivé dans la GED -- l'archivage sert justement à
-- garder une trace même après suppression des données parsées.
CREATE TABLE IF NOT EXISTS nebula_import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_type TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    ged_document_id INTEGER,
    ged_archive_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_nebula_batches_type ON nebula_import_batches(import_type);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


try:
    ensure_schema()
except Exception as exc:  # noqa: BLE001 -- la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Migration au démarrage reportée : %s", exc)


def _connect():
    """Lève nebula.NebulaError si .env n'est pas encore renseigné --
    même motif que _connect() dans glpi/api/app.py (#192)."""
    if not NEBULA_API_KEY:
        raise nebula.NebulaError("NEBULA_API_KEY non configuré -- voir nebula/README.md pour les prérequis (licence Pro Pack + clé obtenue via le support Zyxel)")
    return nebula.NebulaClient(NEBULA_API_KEY, base_url=NEBULA_BASE_URL)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/test-connection", methods=["GET"])
def test_connection():
    """Vérifie la connexion en listant les organisations -- l'appel
    le plus simple et le moins risqué de l'API (lecture seule, aucun
    paramètre). Premier appel à faire après configuration -- voir
    nebula/README.md pour les prérequis à réunir AVANT d'essayer."""
    try:
        client = _connect()
        orgs = client.list_organizations()
    except nebula.NebulaError as exc:
        return jsonify({"error": str(exc)}), 502
    non_pro = [o["name"] for o in orgs if o.get("mode") != "PRO"]
    return jsonify({
        "status": "ok", "organizations": orgs,
        "warning": f"organisations SANS licence Pro Pack (API indisponible pour elles) : {', '.join(non_pro)}" if non_pro else None,
    }), 200


@app.route("/organizations", methods=["GET"])
def list_organizations():
    try:
        client = _connect()
        return jsonify(client.list_organizations()), 200
    except nebula.NebulaError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/organizations/<org_id>/sites", methods=["GET"])
def list_sites(org_id):
    try:
        client = _connect()
        return jsonify(client.list_sites(org_id)), 200
    except nebula.NebulaError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/organizations/<org_id>/sites/<site_id>/devices", methods=["GET"])
def list_site_devices(org_id, site_id):
    """Appareils Nebula d'UN site précis -- filtrage côté client
    (voir nebula_client.devices_for_site, l'API elle-même ne propose
    pas cet endpoint isolé)."""
    try:
        client = _connect()
        return jsonify(client.devices_for_site(org_id, site_id)), 200
    except nebula.NebulaError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/sites/<site_id>/online-status", methods=["GET"])
def site_online_status(site_id):
    """Statut EN LIGNE de chaque appareil du site -- backlog item 49
    (2026-09-05, "les bornes plantent-elles réellement ?"), voir
    nebula_client.get_online_status pour le détail complet du format
    ([{"devId", "currentStatus"}, ...]). `type` en paramètre de
    requête (optionnel -- AP/SW/GW/FIREWALL/WWAN/SCR/GWH/ACCY, voir
    doc officielle) filtre CÔTÉ SERVEUR sur un type d'appareil
    précis, contrairement à `/devices` ci-dessus qui filtre côté
    client faute d'endpoint Nebula dédié -- ici l'API le supporte
    nativement, jamais réinventé.

    ⚠️ Comme le reste de ce module, JAMAIS testé contre une vraie API
    Nebula (licence Pro Pack + clé non self-service requises, voir
    nebula/README.md) -- route exposant fidèlement
    nebula_client.get_online_status, déjà écrite et documentée
    depuis #196, jamais branchée à une route HTTP jusqu'à cette
    livraison."""
    device_type = request.args.get("type")
    try:
        client = _connect()
        return jsonify(client.get_online_status(site_id, device_type=device_type)), 200
    except nebula.NebulaError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/sites/<site_id>/clients", methods=["GET"])
def site_clients(site_id):
    """Clients RÉSEAU connectés (pas les appareils Nebula eux-mêmes,
    voir list_site_devices ci-dessus). `period` en paramètre de
    requête (défaut 2h, voir nebula_client.get_site_clients)."""
    period = request.args.get("period", "2h")
    try:
        client = _connect()
        return jsonify(client.get_site_clients(site_id, period=period)), 200
    except nebula.NebulaError as exc:
        return jsonify({"error": str(exc)}), 502


# ------------------------------------------------------------------
# Import des exports CSV du portail web Nebula (livraison #200) --
# voir csv_import.py pour le détail du format. Trois routes
# symétriques (sites/devices/clients), même motif à chaque fois :
# fichier en multipart/form-data (champ `file`), parsé, inséré tel
# quel (jamais de déduplication À L'IMPORT -- voir docstring du
# schéma : chaque import est un NOUVEL horodatage, la déduplication
# se fait à la LECTURE via _latest_by).
# ------------------------------------------------------------------
def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _archive_csv_to_ged(file_bytes, filename, import_type, imported_at):
    """Archive le fichier CSV original dans la GED (livraison #237,
    demandé explicitement -- "fichiers à rendre visible dans l'espace
    fichiers du hub/ged"). BEST-EFFORT, jamais bloquant pour l'import
    lui-même (déjà réussi à ce stade côté nebula-api) -- renvoie
    (document_id, error) : l'un des deux est toujours `None`. Lié à
    l'entité `nebula-import` (linked_type polymorphe déjà existant
    côté ged-api, #158) via `linked_id` = `<type>:<imported_at>`,
    identifiant unique de CE lot précis."""
    try:
        resp = requests.post(
            f"{GED_API_INTERNAL_URL}/documents",
            files={"file": (filename, file_bytes, "text/csv")},
            data={
                "name": f"Nebula {import_type} -- {filename} ({imported_at})",
                "linked_type": "nebula-import",
                "linked_id": f"{import_type}:{imported_at}",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, f"appel à ged-api échoué : {exc}"
    if resp.status_code not in (200, 201, 202):
        return None, f"ged-api a répondu {resp.status_code} : {resp.text[:300]}"
    try:
        body = resp.json()
    except ValueError:
        return None, "réponse de ged-api illisible (pas du JSON valide)"
    document_id = body.get("id")
    if document_id is None:
        return None, "réponse de ged-api sans identifiant de document"
    return document_id, None


def _import_csv_route(parse_fn, table, columns, expected_type, type_labels):
    """`expected_type`/`type_labels` (livraison #235) -- vérifie que
    le fichier envoyé correspond BIEN au type attendu par l'onglet
    actif AVANT d'insérer quoi que ce soit. **Trouvaille réelle** :
    un export Devices importé via l'onglet Sites ne provoquait AUCUNE
    erreur (les deux formats ont une colonne "Name") -- des données
    FAUSSES étaient insérées silencieusement, jamais détectées avant
    ce correctif. Voir `csv_import.detect_csv_type`.

    Protégée par rights-api (#314) -- `groups` lu depuis
    `request.form` (multipart, jamais un corps JSON ici)."""
    allowed, error = _check_manage_right({"groups": request.form.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "fichier requis (champ 'file', multipart/form-data)"}), 400
    uploaded = request.files["file"]
    file_bytes = uploaded.read()

    detected_type = csv_import.detect_csv_type(file_bytes)
    if detected_type is None:
        return jsonify({"error": "colonnes non reconnues -- ce fichier ne ressemble à aucun export Nebula connu (Sites/Appareils/Clients), import annulé"}), 400
    if detected_type != expected_type:
        return jsonify({
            "error": f"ce fichier ressemble à un export « {type_labels[detected_type]} », pas « {type_labels[expected_type]} » -- "
                     f"import annulé, utilisez l'onglet « {type_labels[detected_type]} » pour ce fichier",
        }), 400

    try:
        rows = parse_fn(file_bytes)
    except Exception as exc:  # noqa: BLE001 -- fichier malformé -- jamais un 500 nu
        return jsonify({"error": f"lecture du fichier échouée : {exc}"}), 400

    now = _now_iso()
    conn = get_connection()
    try:
        cur = conn.cursor()
        placeholders = ", ".join(["?"] * (len(columns) + 2))
        col_names = ", ".join(columns + ["imported_at", "source_filename"])
        for row in rows:
            values = [row.get(col) for col in columns] + [now, uploaded.filename]
            cur.execute(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", values)

        ged_document_id, ged_error = _archive_csv_to_ged(file_bytes, uploaded.filename, expected_type, now)
        cur.execute(
            """INSERT INTO nebula_import_batches
               (import_type, imported_at, source_filename, row_count, ged_document_id, ged_archive_error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [expected_type, now, uploaded.filename, len(rows), ged_document_id, ged_error],
        )
        batch_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({
        "status": "ok", "imported": len(rows), "imported_at": now, "batch_id": batch_id,
        "ged_document_id": ged_document_id, "ged_archive_error": ged_error,
    }), 201


SITES_COLUMNS = ["status", "name", "tags", "devices_count", "usage", "usage_bytes", "clients_count", "offline_devices", "percent_offline", "template"]
DEVICES_COLUMNS = ["status", "device_type", "model", "site", "mac_address", "tags", "clients_count", "usage", "usage_bytes", "name"]
CLIENTS_COLUMNS = ["status", "name", "mac_address", "ipv4_address", "connected_to", "manufacturer", "os", "policy", "band", "rx_rate", "tx_rate", "ssid_name", "signal_strength", "last_seen"]


TYPE_LABELS = {"sites": "Sites", "devices": "Appareils", "clients": "Clients"}


@app.route("/import/sites", methods=["POST"])
def import_sites_csv():
    return _import_csv_route(csv_import.parse_sites_csv, "nebula_sites_import", SITES_COLUMNS, "sites", TYPE_LABELS)


@app.route("/import/devices", methods=["POST"])
def import_devices_csv():
    return _import_csv_route(csv_import.parse_devices_csv, "nebula_devices_import", DEVICES_COLUMNS, "devices", TYPE_LABELS)


@app.route("/import/clients", methods=["POST"])
def import_clients_csv():
    return _import_csv_route(csv_import.parse_clients_csv, "nebula_clients_import", CLIENTS_COLUMNS, "clients", TYPE_LABELS)


def _latest_by(table, key_column, columns):
    """Une ligne par valeur DISTINCTE de `key_column` -- la plus
    RÉCEMMENT importée (id le plus grand, jamais un tri par
    `imported_at` qui pourrait être ambigu en cas d'imports dans la
    même seconde). Utilisé par défaut en lecture (voir routes
    GET ci-dessous) -- `?history=true` bascule sur TOUT l'historique."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM {table} WHERE id IN (SELECT MAX(id) FROM {table} GROUP BY {key_column}) ORDER BY {key_column}"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _all_history(table, order_column):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table} ORDER BY {order_column}, imported_at DESC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@app.route("/imported/sites", methods=["GET"])
def get_imported_sites():
    """Par défaut : dernier import connu par site. `?history=true` :
    tout l'historique des imports (permet de suivre l'évolution de
    l'usage/des clients dans le temps)."""
    if request.args.get("history") == "true":
        return jsonify(_all_history("nebula_sites_import", "name")), 200
    return jsonify(_latest_by("nebula_sites_import", "name", SITES_COLUMNS)), 200


@app.route("/imported/devices", methods=["GET"])
def get_imported_devices():
    if request.args.get("history") == "true":
        return jsonify(_all_history("nebula_devices_import", "mac_address")), 200
    return jsonify(_latest_by("nebula_devices_import", "mac_address", DEVICES_COLUMNS)), 200


@app.route("/imported/clients", methods=["GET"])
def get_imported_clients():
    if request.args.get("history") == "true":
        return jsonify(_all_history("nebula_clients_import", "mac_address")), 200
    return jsonify(_latest_by("nebula_clients_import", "mac_address", CLIENTS_COLUMNS)), 200


IMPORT_TABLES = {"sites": "nebula_sites_import", "devices": "nebula_devices_import", "clients": "nebula_clients_import"}


@app.route("/imported/<type_name>", methods=["DELETE"])
def delete_imported(type_name):
    """Annule un import -- demandé explicitement après une confusion
    réelle entre onglets (livraison #235, voir csv_import.detect_csv_type
    pour la prévention ajoutée en amont de ce correctif). `type_name`
    validé contre IMPORT_TABLES (whitelist fermée) avant toute
    utilisation dans du SQL -- jamais le segment d'URL brut.
    `?imported_at=X` (le timestamp renvoyé par la route POST
    correspondante) : supprime UNIQUEMENT ce lot précis -- le cas le
    plus courant, annuler ce qu'on vient tout juste d'importer par
    erreur. Sans paramètre : vide TOUT l'historique de ce type.

    Protégée par rights-api (#314)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    table = IMPORT_TABLES.get(type_name)
    if table is None:
        return jsonify({"error": f"type inconnu '{type_name}' -- attendu : sites, devices, clients"}), 400
    imported_at = request.args.get("imported_at")
    conn = get_connection()
    try:
        cur = conn.cursor()
        if imported_at:
            cur.execute(f"DELETE FROM {table} WHERE imported_at = ?", [imported_at])
        else:
            cur.execute(f"DELETE FROM {table}")
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "deleted": deleted}), 200


@app.route("/import-batches", methods=["GET"])
def list_import_batches():
    """Historique des lots d'import (livraison #237, demandé
    explicitement -- "une sélection et un bouton [Supprimer]") --
    UN lot = UN import (un fichier déposé une fois), au-delà du
    simple "annuler le tout dernier import" (#235). `?type=X`
    (sites/devices/clients) requis."""
    import_type = request.args.get("type")
    if import_type not in IMPORT_TABLES:
        return jsonify({"error": "paramètre 'type' requis -- attendu : sites, devices, clients"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            # `id DESC` en critère SECONDAIRE -- `imported_at` seul
            # (résolution à la SECONDE, voir now_iso()) ne distingue
            # pas deux imports survenus dans la même seconde --
            # trouvaille réelle en testant (deux imports rapides dans
            # le même test se retrouvaient dans un ordre arbitraire).
            # `id`, auto-incrémenté, reflète TOUJOURS l'ordre réel
            # d'insertion, sans cette ambiguïté.
            "SELECT * FROM nebula_import_batches WHERE import_type = ? ORDER BY imported_at DESC, id DESC",
            [import_type],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/import-batches", methods=["DELETE"])
def delete_import_batches():
    """Supprime UN OU PLUSIEURS lots sélectionnés -- corps JSON
    `{"batch_ids": [1, 2, 3]}`. Retire les LIGNES importées (table
    type par type, via `imported_at`+`source_filename`, la clé
    naturelle d'un lot) ET l'enregistrement du lot lui-même -- mais
    GARDE volontairement le document archivé dans la GED (voir
    `_archive_csv_to_ged` -- l'archivage sert justement à conserver
    une trace même après suppression des données parsées).

    Protégée par rights-api (#314)."""
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    batch_ids = body.get("batch_ids")
    if not isinstance(batch_ids, list) or not batch_ids:
        return jsonify({"error": "'batch_ids' requis (liste non vide d'identifiants de lot)"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        deleted_batches = 0
        deleted_rows_total = 0
        errors = []
        for batch_id in batch_ids:
            cur.execute("SELECT * FROM nebula_import_batches WHERE id = ?", [batch_id])
            batch = cur.fetchone()
            if batch is None:
                errors.append(f"lot #{batch_id} introuvable -- ignoré")
                continue
            table = IMPORT_TABLES[batch["import_type"]]
            cur.execute(
                f"DELETE FROM {table} WHERE imported_at = ? AND source_filename = ?",
                [batch["imported_at"], batch["source_filename"]],
            )
            deleted_rows_total += cur.rowcount
            cur.execute("DELETE FROM nebula_import_batches WHERE id = ?", [batch_id])
            deleted_batches += 1
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "deleted_batches": deleted_batches, "deleted_rows": deleted_rows_total, "errors": errors}), 200


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


SERVICE_NAME = "nebula-api"
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
