"""
API d'administration multi-SGBD — connexions à des bases PostgreSQL,
MySQL, SQLite gérées en dehors de ce projet (l'écosystème DBA plus
large de la personne), pas seulement les bases DE ce projet. Distinct
et complémentaire de l'onglet "Gestion base" du frontend Supervision
SI (qui reste l'outil dédié aux bases internes CE projet, liste
blanche stricte) — voir dba/README.md pour la distinction complète.

Gestion de schéma = du SQL libre (CREATE/ALTER/DROP TABLE ne sont que
des instructions SQL) -- pas de routes dédiées séparées, /sql couvre
déjà ce besoin. Le navigateur de lignes reste un raccourci de confort
pour le cas courant (parcourir une table), pas une limite.
"""

import os
import logging
import sqlite3
import subprocess
import tempfile
import time

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

from connectors import get_connector
# Import DÉFENSIF -- version_endpoint.py n'existe que dans le
# conteneur Docker réel (copié depuis shared/ au build, comme
# theme.css/preferences.js pour les fronts). Sans ce garde, tout
# test qui importe ce module directement (sans passer par le build
# complet) casserait au chargement -- bug réel rencontré : plusieurs
# harnais de test existants, sans rapport avec /version, important
# app.py directement.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "dba-api")
# Plafond dur sur la taille d'un envoi -- 2 Go, généreux pour une vraie
# sauvegarde "--all-databases" tout en évitant un envoi non borné
# (accidentel ou malveillant) de saturer le disque du conteneur.
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

_log = logging.getLogger("dba_api_app")

# Livraison #292 -- suite du backlog item 38, quatrième service
# branché après ssh-tunnels-api (#289), ldap-admin-api (#290),
# vault-admin-api (#291). Candidat particulièrement sensible :
# /connections/<id>/sql exécute du SQL LIBRE contre des bases
# EXTERNES à ce projet, potentiellement de production. Aucune
# décision explicite préexistante trouvée dans ce module contraire
# à ce branchement (contrairement à vault/LDAP) -- procédé
# directement, même motif éprouvé trois fois déjà. OPT-IN,
# vide/absent = gating désactivé (comportement identique à avant
# #292).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif que ssh-tunnels-api (#289)/ldap-admin-api (#290)/
    vault-admin-api (#291) -- FAIL CLOSED, jamais fail-open, y
    compris pour admin_hub si rights-api est injoignable ou répond
    de façon inattendue."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "dba-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur dba-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("DBA_DB_PATH", "/data/dba.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    engine TEXT NOT NULL,
    host TEXT,
    port INTEGER,
    username TEXT,
    password TEXT,
    database_name TEXT,
    file_path TEXT,
    created_at TEXT NOT NULL
);
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
except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Migration au démarrage reportée : %s", exc)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_connection_from_env(label, engine, prefix, default_port):
    """
    Crée ou met à jour une connexion "amorcée" depuis des variables
    d'environnement (HUB_SGBD_MYSQL_*/HUB_SGBD_POSTGRES_*, voir .env)
    — demandé explicitement par la personne après avoir écarté l'idée
    de réutiliser les identifiants IPAM/Optick/Zenoss/etc. (réservés à
    leurs modules respectifs, jamais à mélanger avec ceci).

    Reconnue par son LIBELLÉ RÉSERVÉ (jamais un identifiant technique
    séparé — plus simple, et le libellé affiché suffit à signaler que
    cette connexion est amorcée depuis .env plutôt que créée à la
    main) : IDEMPOTENT, un redémarrage du conteneur ne duplique
    jamais cette entrée, mais met à jour ses identifiants si le .env
    a changé entre-temps -- comportement volontairement différent
    d'un simple "créer si absent", pour rester cohérent avec les
    autres mécanismes d'amorçage déjà établis dans ce projet (realm
    Keycloak, entre autres).
    """
    host = (os.environ.get(f"{prefix}_HOST") or "").strip()
    if not host:
        return  # rien à amorcer -- comportement par défaut inchangé, la personne ajoute à la main comme avant
    port = os.environ.get(f"{prefix}_PORT") or default_port
    username = os.environ.get(f"{prefix}_USER") or ""
    password = os.environ.get(f"{prefix}_PASSWORD") or ""
    database_name = os.environ.get(f"{prefix}_DATABASE") or None

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM connections WHERE label = ?", [label])
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """INSERT INTO connections
                   (label, engine, host, port, username, password, database_name, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [label, engine, host, port, username, password, database_name, now_iso()],
            )
        else:
            cur.execute(
                """UPDATE connections SET engine = ?, host = ?, port = ?, username = ?, password = ?, database_name = ?
                   WHERE id = ?""",
                [engine, host, port, username, password, database_name, row[0]],
            )
        conn.commit()
    finally:
        conn.close()


def seed_connections_from_env():
    seed_connection_from_env("MySQL (HUB_SGBD, .env)", "mysql", "HUB_SGBD_MYSQL", 3306)
    seed_connection_from_env("PostgreSQL (HUB_SGBD, .env)", "postgres", "HUB_SGBD_POSTGRES", 5432)


try:
    seed_connections_from_env()
except Exception as exc:  # noqa: BLE001 — même prudence qu'ensure_schema() ci-dessus
    app.logger.warning("Amorçage des connexions HUB_SGBD reporté : %s", exc)


# Champs jamais renvoyés tels quels dans une liste/lecture de
# connexion — le mot de passe ne doit apparaître qu'au moment précis
# où il sert à se connecter (get_connector), jamais dans une réponse
# JSON de listing, même dans cet outil interne : une fuite accidentelle
# vers la console navigateur ou un journal HTTP reste évitable à peu
# de frais.
def _connection_row_public(row):
    d = dict(row)
    d.pop("password", None)
    d["has_password"] = bool(row["password"])
    return d


@app.route("/connections", methods=["GET"])
def list_connections():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM connections ORDER BY label")
        return jsonify([_connection_row_public(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


REQUIRED_FIELDS_BY_ENGINE = {
    "sqlite": ["file_path"],
    "postgres": ["host", "username"],
    "mysql": ["host", "username"],
}


@app.route("/connections", methods=["POST"])
def create_connection():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label = (body.get("label") or "").strip()
    engine = body.get("engine")
    if not label:
        return jsonify({"error": "label requis"}), 400
    if engine not in REQUIRED_FIELDS_BY_ENGINE:
        return jsonify({"error": f"moteur '{engine}' non pris en charge (attendus : {list(REQUIRED_FIELDS_BY_ENGINE)})"}), 400
    missing = [f for f in REQUIRED_FIELDS_BY_ENGINE[engine] if not body.get(f)]
    if missing:
        return jsonify({"error": f"champs requis manquants pour {engine} : {missing}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO connections
               (label, engine, host, port, username, password, database_name, file_path, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                label, engine, body.get("host"), body.get("port"), body.get("username"),
                body.get("password"), body.get("database_name"), body.get("file_path"), now_iso(),
            ],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": cur.lastrowid}), 201
    finally:
        conn.close()


EDITABLE_FIELDS = ["label", "engine", "host", "port", "username", "password", "database_name", "file_path"]


@app.route("/connections/<int:conn_id>", methods=["PUT"])
def update_connection(conn_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    fields = {k: v for k, v in body.items() if k in EDITABLE_FIELDS}
    if not fields:
        return jsonify({"error": f"aucun champ valide fourni (attendus : {EDITABLE_FIELDS})"}), 400
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE connections SET {set_clause} WHERE id = ?", [*fields.values(), conn_id])
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "connexion introuvable"}), 404
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/connections/<int:conn_id>", methods=["DELETE"])
def delete_connection(conn_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM connections WHERE id = ?", [conn_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


def _load_connection_row(conn_id):
    """Renvoie la ligne BRUTE (mot de passe inclus — usage interne
    uniquement, jamais renvoyée telle quelle à l'API) ou None."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM connections WHERE id = ?", [conn_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@app.route("/connections/<int:conn_id>/test", methods=["POST"])
def test_connection(conn_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    try:
        connector = get_connector(row)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    ok, message = connector.test_connection()
    return jsonify({"ok": ok, "message": message}), 200


@app.route("/connections/<int:conn_id>/databases", methods=["GET"])
def list_databases(conn_id):
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    try:
        connector = get_connector(row)
        return jsonify(connector.list_databases()), 200
    except Exception as exc:  # noqa: BLE001 — erreur du driver externe, traduite ici
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables", methods=["GET"])
def list_tables(conn_id):
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    try:
        connector = get_connector(row)
        return jsonify(connector.list_tables(database)), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/columns", methods=["GET"])
def get_table_columns(conn_id, table):
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    try:
        connector = get_connector(row)
        return jsonify(connector.get_table_columns(table, database)), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/rows", methods=["GET"])
def browse_rows(conn_id, table):
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    limit = min(int(request.args.get("limit", 50)), 500)  # plafond dur -- jamais un dump complet accidentel d'une table de production
    offset = int(request.args.get("offset", 0))
    try:
        connector = get_connector(row)
        return jsonify(connector.browse_rows(table, database, limit, offset)), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/rows", methods=["PUT"])
def update_table_row(conn_id, table):
    """Modification d'une ligne existante -- demandé explicitement
    (édition de cellule avec validation par ligne). Jamais la clé
    primaire (déduite via get_table_columns, jamais fournie par la
    personne) -- colonnes à modifier validées contre le VRAI schéma
    de la table avant toute écriture, jamais une colonne inconnue ou
    non éditable passée telle quelle au connecteur."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    pk_value = body.get("pk_value")
    updates = body.get("updates") or {}
    if pk_value is None:
        return jsonify({"error": "pk_value requis"}), 400
    if not isinstance(updates, dict) or not updates:
        return jsonify({"error": "au moins un champ à modifier requis"}), 400

    try:
        connector = get_connector(row)
        columns = connector.get_table_columns(table, database)
        pk_column = next((c["name"] for c in columns if c["primary_key"]), None)
        if pk_column is None:
            return jsonify({"error": "cette table n'a pas de clé primaire identifiable, édition impossible"}), 400
        editable = {c["name"] for c in columns if not c["primary_key"]}
        invalid = sorted(set(updates) - editable)
        if invalid:
            return jsonify({"error": f"colonne(s) non éditable(s) ou inconnue(s) : {invalid}"}), 400

        affected = connector.update_row(table, pk_column, pk_value, updates, database)
        if affected == 0:
            return jsonify({"error": "ligne introuvable (peut-être supprimée ou modifiée entre-temps)"}), 404
        return jsonify({"status": "ok"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/rows", methods=["POST"])
def insert_table_row(conn_id, table):
    """Ajout d'une ligne -- demandé explicitement. Sert aussi à
    "dupliquer" une ligne existante côté interface : la personne
    envoie simplement les valeurs de la ligne à copier, sans sa clé
    primaire (exclue naturellement, jamais transmise ici) -- une
    nouvelle clé est générée par le SGBD comme pour n'importe quel
    ajout normal, jamais une route séparée nécessaire pour ce cas.
    Colonnes validées contre le vrai schéma avant toute écriture,
    même principe que la modification."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    values = body.get("values") or {}
    if not isinstance(values, dict) or not values:
        return jsonify({"error": "au moins un champ requis"}), 400

    try:
        connector = get_connector(row)
        columns = connector.get_table_columns(table, database)
        pk_column = next((c["name"] for c in columns if c["primary_key"]), None)
        editable = {c["name"] for c in columns if not c["primary_key"]}
        invalid = sorted(set(values) - editable)
        if invalid:
            return jsonify({"error": f"colonne(s) inconnue(s) ou non autorisée(s) ici : {invalid}"}), 400

        new_id = connector.insert_row(table, values, pk_column, database)
        return jsonify({"status": "ok", "pk_value": new_id}), 201
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/rows", methods=["DELETE"])
def delete_table_rows(conn_id, table):
    """Suppression d'une ou plusieurs lignes d'un coup -- demandé
    explicitement (sélection multiple, opérations en lot)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    pk_values = body.get("pk_values") or []
    if not isinstance(pk_values, list) or not pk_values:
        return jsonify({"error": "pk_values requis (au moins une valeur)"}), 400

    try:
        connector = get_connector(row)
        columns = connector.get_table_columns(table, database)
        pk_column = next((c["name"] for c in columns if c["primary_key"]), None)
        if pk_column is None:
            return jsonify({"error": "cette table n'a pas de clé primaire identifiable, suppression impossible"}), 400

        affected = connector.delete_rows(table, pk_column, pk_values, database)
        return jsonify({"status": "ok", "affected_rows": affected}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/columns", methods=["POST"])
def add_table_column(conn_id, table):
    """Ajoute une colonne à une table existante -- demandé
    explicitement (modification de schéma)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    name = (body.get("name") or "").strip()
    column_type = (body.get("type") or "").strip()
    nullable = body.get("nullable", True)
    if not name or not column_type:
        return jsonify({"error": "nom et type de colonne requis"}), 400

    try:
        connector = get_connector(row)
        connector.add_column(table, name, column_type, nullable, database)
        return jsonify({"status": "ok"}), 201
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/columns/<column>", methods=["DELETE"])
def drop_table_column(conn_id, table, column):
    """Supprime une colonne -- demandé explicitement. Jamais la clé
    primaire (même prudence que pour l'édition/suppression de
    lignes) -- casserait la table entière, refusé explicitement
    plutôt que de laisser faire."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")

    try:
        connector = get_connector(row)
        columns = connector.get_table_columns(table, database)
        col_info = next((c for c in columns if c["name"] == column), None)
        if col_info is None:
            return jsonify({"error": "colonne introuvable"}), 404
        if col_info["primary_key"]:
            return jsonify({"error": "impossible de supprimer la clé primaire depuis cette interface"}), 400

        connector.drop_column(table, column, database)
        return jsonify({"status": "ok"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/tables/<table>/columns/<column>", methods=["PUT"])
def modify_table_column(conn_id, table, column):
    """Renomme et/ou modifie le type/la nullabilité d'une colonne --
    demandé explicitement. `new_name`/`new_type`/`nullable` tous
    optionnels (fournir n'importe quelle combinaison). Jamais la clé
    primaire, même prudence que pour la suppression."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    database = request.args.get("database")
    new_name = (body.get("new_name") or "").strip() or None
    new_type = (body.get("new_type") or "").strip() or None
    nullable = body.get("nullable")  # None si absent -- signifie "ne pas toucher"
    if new_name is None and new_type is None and nullable is None:
        return jsonify({"error": "aucune modification fournie (new_name, new_type ou nullable)"}), 400

    try:
        connector = get_connector(row)
        columns = connector.get_table_columns(table, database)
        col_info = next((c for c in columns if c["name"] == column), None)
        if col_info is None:
            return jsonify({"error": "colonne introuvable"}), 404
        if col_info["primary_key"]:
            return jsonify({"error": "impossible de modifier la clé primaire depuis cette interface"}), 400

        if new_type is not None or nullable is not None:
            connector.modify_column(table, column, new_type, nullable, database)
        if new_name is not None and new_name != column:
            connector.rename_column(table, column, new_name, database)
        return jsonify({"status": "ok"}), 200
    except NotImplementedError as exc:
        return jsonify({"error": str(exc)}), 501
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/connections/<int:conn_id>/sql", methods=["POST"])
def execute_sql(conn_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    sql = (body.get("sql") or "").strip()
    if not sql:
        return jsonify({"error": "sql requis"}), 400
    database = body.get("database")
    try:
        connector = get_connector(row)
        return jsonify(connector.execute_sql(sql, database)), 200
    except Exception as exc:  # noqa: BLE001 — erreur SQL de la personne (syntaxe...) ou du driver, les deux légitimement renvoyées telles quelles ici
        return jsonify({"error": str(exc)}), 400


@app.route("/connections/<int:conn_id>/import-mysql-dump", methods=["POST"])
def import_mysql_dump(conn_id):
    """
    Importe une sauvegarde `mysqldump --all-databases` (ou tout dump
    mysqldump classique) en s'appuyant sur le client `mysql` officiel
    plutôt que de tenter de parser/rejouer le SQL nous-mêmes -- un
    fichier de ce type peut contenir des points-virgules dans des
    littéraux de chaîne, des commentaires, des changements de
    DELIMITER pour les routines stockées... Le client officiel gère
    déjà tout ça correctement, le réinventer serait fragile et risqué
    pour un outil censé restaurer des données réelles.

    SÉCURITÉ DES IDENTIFIANTS : jamais en argument de ligne de
    commande (visible via `ps aux` à quiconque partage la machine),
    jamais non plus en variable d'environnement MYSQL_PWD
    (déconseillée par MySQL lui-même, visible via /proc/<pid>/environ
    sur certains systèmes) -- passés via --defaults-extra-file, un
    fichier temporaire à permissions restrictives (0600, propriétaire
    seul), supprimé immédiatement après usage, y compris en cas
    d'erreur (bloc finally).

    NON VÉRIFIÉ CONTRE UN VRAI SERVEUR MYSQL dans cet environnement de
    développement (aucun client mysql, aucun serveur accessible, pas
    de réseau sortant pour en installer un) -- la logique de gestion
    des fichiers temporaires, permissions et nettoyage est testée
    réellement ; l'invocation du client mysql lui-même ne l'est que
    par simulation (mock).
    """
    # Livraison #292 -- cette route reçoit un envoi MULTIPART (fichier),
    # jamais de corps JSON -- `groups` transmis comme champ de
    # formulaire ordinaire (valeurs séparées par des virgules), pas
    # dans un body JSON comme les autres routes de ce module.
    groups_field = request.form.get("groups", "")
    groups = [g.strip() for g in groups_field.split(",") if g.strip()]
    allowed, error = _check_manage_right({"groups": groups})
    if not allowed:
        return jsonify({"error": error}), 403
    row = _load_connection_row(conn_id)
    if row is None:
        return jsonify({"error": "connexion introuvable"}), 404
    if row["engine"] != "mysql":
        return jsonify({"error": "l'import mysqldump n'est disponible que pour les connexions MySQL"}), 400

    uploaded = request.files.get("file")
    if uploaded is None or uploaded.filename == "":
        return jsonify({"error": "fichier requis (champ 'file')"}), 400

    dump_fd, dump_path = tempfile.mkstemp(suffix=".sql")
    cnf_fd, cnf_path = tempfile.mkstemp(suffix=".cnf")
    try:
        os.close(dump_fd)
        uploaded.save(dump_path)

        os.close(cnf_fd)
        os.chmod(cnf_path, 0o600)  # avant d'écrire le mot de passe dedans -- jamais une fenêtre où le fichier est lisible par d'autres
        with open(cnf_path, "w", encoding="utf-8") as f:
            f.write("[client]\n")
            f.write(f"user={row['username']}\n")
            f.write(f"password={row['password'] or ''}\n")

        cmd = [
            "mysql",
            f"--defaults-extra-file={cnf_path}",
            "-h", row["host"],
            "-P", str(row["port"] or 3306),
            # Corrigé une seconde fois : "default-mysql-client" (voir
            # Dockerfile) résout vers le client MARIADB sur Debian,
            # pas MySQL officiel -- --ssl-mode=DISABLED (syntaxe
            # MySQL 5.7.11+) y était rejeté avec "unknown variable"
            # (signalé par la personne). --skip-ssl est le flag
            # LEGACY, universellement supporté par les DEUX clients
            # (MySQL et MariaDB, anciennes et récentes versions) --
            # plus sûr ici que de parier sur laquelle des deux
            # syntaxes récentes serait reconnue.
            "--skip-ssl",
        ]
        with open(dump_path, "rb") as dump_file:
            result = subprocess.run(
                cmd,
                stdin=dump_file,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min -- voie SYNCHRONE, une très grosse sauvegarde pourrait dépasser ce délai (voir docstring/README)
            )

        if result.returncode != 0:
            return jsonify({"error": result.stderr.strip() or "échec de l'import (voir sortie standard)", "output": result.stdout}), 502
        return jsonify({"status": "ok", "output": result.stdout}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"error": "délai dépassé (30 minutes) -- sauvegarde probablement trop volumineuse pour cette voie synchrone"}), 504
    except FileNotFoundError:
        return jsonify({"error": "client 'mysql' introuvable dans ce conteneur -- voir dba/api/Dockerfile"}), 500
    finally:
        # Nettoyage systématique, y compris en cas d'erreur -- le
        # fichier d'identifiants SURTOUT ne doit jamais traîner.
        for path in (dump_path, cnf_path):
            try:
                os.remove(path)
            except OSError:
                pass


# ------------------------------------------------------------------
# Journal en memoire (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du hub (gestionnaire
# de logs, livraison #139). Meme motif EXACT que api/app.py -- ne
# capture PAS le corps des requetes ni de donnee metier, seulement ce
# que ce fichier journalise deja lui-meme plus les exceptions non
# gerees que Flask/Werkzeug journalisent nativement en ERROR. Tampon
# circulaire en memoire, borne (LOG_BUFFER_SIZE, defaut 200), jamais
# persiste sur disque -- perdu au redemarrage du conteneur. Seuil par
# defaut WARNING (pas INFO) : evite le bruit des logs d'acces
# Werkzeug (une ligne par requete HTTP, y compris le polling de
# /logs lui-meme).
# ------------------------------------------------------------------
# Client Memcached -- livraison #145, nécessaire au tampon de logs
# PARTAGÉ ci-dessous (ce service tourne avec 2 workers Gunicorn,
# processus séparés, mémoire NON partagée). Recréé à chaque appel
# (même motif établi ailleurs dans ce projet, voir api/app.py) --
# évite de garder une connexion morte si Memcached redémarre.
from pymemcache.client.base import Client as _MemcacheClient

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py pour le raisonnement complet) -- PAS un tampon
# en memoire de processus.
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "dba-api"
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
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
