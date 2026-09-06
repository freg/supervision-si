"""
Service ADMINISTRATIF SÉPARÉ du coffre-fort — lecture de l'archive des
clés de récupération (voir vault/api/app.py, table
recovery_key_archive), réservée aux membres du groupe Keycloak
"maitre_clefs". Volontairement un PROCESSUS DISTINCT de vault-api, pas
juste des routes protégées dans la même application : une frontière
de sécurité plus nette, jamais exposé par la passerelle publique
(tls-proxy) ni référencé dans son routage — seul un accès DIRECT au
port de ce service (voir docker-compose.yml, VAULT_ADMIN_LAN_PORT)
peut l'atteindre. Partage le même fichier SQLite que vault-api
(VAULT_DB_PATH, même volume monté dans les deux conteneurs).

TROIS COUCHES DE PROTECTION, JAMAIS UNE SEULE :
1. RÉSEAU — ce port n'est JAMAIS routé par tls-proxy/Apache vers
   l'extérieur (discipline de déploiement, pas quelque chose que ce
   code peut garantir à lui seul si le port venait à être mal exposé
   par erreur en amont).
2. APPLICATIF — vérification explicite de l'IP source contre des
   plages LAN configurées (VAULT_ADMIN_ALLOWED_CIDRS), EN PLUS de (1)
   -- défense en profondeur si (1) était un jour mal configuré.
3. CRYPTOGRAPHIQUE — la VRAIE protection de fond : ce que cette API
   renvoie n'est qu'un blob chiffré, INUTILISABLE sans avoir
   légitimement déverrouillé la clé privée du compte maître_principal
   (partagée aux membres de maitre_clefs via le mécanisme de
   collection déjà existant, voir vault/README.md) -- même un accès
   direct à cette API ne donne RIEN d'exploitable seul.

Journalisation et email d'alerte sur CHAQUE tentative d'accès,
autorisée ou refusée -- une tentative refusée (hors LAN) est en soi un
signal à ne pas perdre.

`actor_login` est auto-déclaré (paramètre de requête), comme partout
ailleurs dans ce projet ("le login transmis est celui déjà connu du
front appelant") -- cohérent avec la posture de confiance établie,
la vraie protection restant la couche 3 ci-dessus, jamais ce champ
seul.
"""

import ipaddress
import os
import smtplib
import sqlite3
import time
from email.mime.text import MIMEText

from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import requests
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

_log = logging.getLogger("vault_admin_app")

# Livraison #291 -- ÉVOLUTION confirmée explicitement par la personne
# (même clarification que pour ldap-admin-api, #290) : PAS une
# contradiction avec "toute la protection réelle reste dans
# vault-admin-api (LAN + acteur déclaré + journalisation)" -- une
# COUCHE SUPPLÉMENTAIRE, réservant la gestion des rôles (dont
# is_system_master, accès PERMANENT à chaque collection) à une
# catégorie d'utilisateurs plus précise. OPT-IN, vide/absent =
# gating désactivé (comportement identique à avant #291). Portée
# volontairement LIMITÉE à POST /users/<login>/roles -- les routes
# de lecture de l'archive de récupération gardent leur protection
# cryptographique de fond (voir docstring du module, "TROIS COUCHES"),
# jamais touchées ici.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif que ssh-tunnels-api (#289) et ldap-admin-api
    (#290) -- FAIL CLOSED, jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable ou répond de façon
    inattendue."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "vault-admin-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur vault-admin-api requis (groupe admin_hub, ou un octroi explicite)"

# DOIT rester identique, caractère pour caractère (y compris l'emoji),
# à MASTER_KEY_ESCROW_COLLECTION_NAME dans vault/portal/src/vaultOps.js
# -- aucun moyen de partager cette constante entre Python et JS dans
# ce projet (pas d'outillage monorepo), donc une copie manuelle,
# jamais dérivée automatiquement. Si l'une change, l'autre DOIT être
# mise à jour dans le même mouvement.
ESCROW_COLLECTION_NAME = "🔑 Clé maître (accès secours maitre_clefs)"
CORS(app)
if register_version_route:
    register_version_route(app, "vault-admin-api")

DB_PATH = os.environ.get("VAULT_DB_PATH", "/data/vault.db")

# Reprend EXACTEMENT le schéma des tables qui concernent ce service --
# jamais une redéfinition divergente de vault/api/app.py (source de
# vérité pour users/collections/secrets), seulement ce qui est propre
# à celui-ci.
SCHEMA = """
CREATE TABLE IF NOT EXISTS recovery_key_archive (
    login TEXT PRIMARY KEY,
    wrapped_recovery_key_for_master TEXT NOT NULL,
    archived_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_login TEXT NOT NULL,
    action TEXT NOT NULL,
    target_login TEXT,
    source_ip TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    at TEXT NOT NULL
);
"""

DEFAULT_ALLOWED_CIDRS = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"


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


def get_allowed_networks():
    raw = os.environ.get("VAULT_ADMIN_ALLOWED_CIDRS", DEFAULT_ALLOWED_CIDRS)
    networks = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            app.logger.warning("VAULT_ADMIN_ALLOWED_CIDRS : plage ignorée (invalide) : %s", part)
    return networks


def is_ip_allowed(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in net for net in get_allowed_networks())


def send_alert_email(subject, body):
    """Ne bloque JAMAIS l'opération elle-même en cas d'échec d'envoi
    (SMTP mal configuré, injoignable...) -- seulement journalisé côté
    serveur. Perdre la notification est regrettable, bloquer un accès
    par ailleurs légitime (ou la visibilité sur un accès refusé) le
    serait bien davantage."""
    host = os.environ.get("VAULT_ADMIN_SMTP_HOST")
    to_addr = os.environ.get("VAULT_ADMIN_SMTP_TO")
    if not host or not to_addr:
        app.logger.debug("send_alert_email : canal NON CONFIGURÉ -- ignoré (pas une erreur)")
        return
    port = int(os.environ.get("VAULT_ADMIN_SMTP_PORT", "587"))
    user = os.environ.get("VAULT_ADMIN_SMTP_USER") or None
    password = os.environ.get("VAULT_ADMIN_SMTP_PASSWORD") or None
    from_addr = os.environ.get("VAULT_ADMIN_SMTP_FROM") or (user or "vault-admin@localhost")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    # Traces DEBUG (livraison #223, audit rétroactif) -- RÈGLE
    # ABSOLUE : le mot de passe SMTP n'apparaît JAMAIS dans une trace,
    # seule sa PRÉSENCE (booléen).
    app.logger.debug("send_alert_email : démarré vers %s:%s (identifiants SMTP présents=%s, jamais leur valeur ici)", host, port, bool(user))
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_addr], msg.as_string())
        app.logger.debug("send_alert_email : succès")
    except Exception as exc:  # noqa: BLE001 — voir docstring : ne jamais bloquer sur un échec d'envoi
        app.logger.warning("Envoi de l'email d'alerte échoué : %s", exc)


def log_and_notify(actor_login, action, target_login, source_ip, allowed):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO admin_access_log (actor_login, action, target_login, source_ip, allowed, at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [actor_login, action, target_login, source_ip, int(allowed), now_iso()],
        )
        conn.commit()
    finally:
        conn.close()

    status = "AUTORISÉ" if allowed else "REFUSÉ (hors plage LAN configurée)"
    send_alert_email(
        f"[Coffre-fort] Accès maître_clefs {status}",
        (
            f"Action : {action}\n"
            f"Acteur déclaré : {actor_login}\n"
            f"Cible : {target_login or '-'}\n"
            f"IP source : {source_ip}\n"
            f"Statut : {status}\n"
            f"Horodatage (UTC) : {now_iso()}\n"
        ),
    )


def require_lan_and_actor(action, target_login=None):
    """Vérifie la provenance LAN et journalise/notifie systématiquement
    -- retourne (actor_login, response_si_refuse). response_si_refuse
    est None si l'accès est autorisé, sinon un tuple Flask (jsonify, code)
    à renvoyer tel quel."""
    source_ip = request.remote_addr or "inconnue"
    actor_login = (request.args.get("actor") or "").strip()

    if not actor_login:
        return None, (jsonify({"error": "paramètre 'actor' requis"}), 400)

    allowed = is_ip_allowed(source_ip)
    log_and_notify(actor_login, action, target_login, source_ip, allowed)

    if not allowed:
        return None, (jsonify({"error": "accès réservé au réseau local"}), 403)
    return actor_login, None


@app.route("/recovery-archive", methods=["GET"])
def list_recovery_archive():
    _actor, refused = require_lan_and_actor("list_recovery_archive")
    if refused:
        return refused
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT login, archived_at FROM recovery_key_archive ORDER BY login")
        # Jamais le blob chiffré lui-même dans le LISTING -- seulement
        # pour qui une entrée existe, cohérent avec la liste d'accès
        # d'une collection normale qui n'expose pas non plus
        # wrapped_key. Voir /recovery-archive/<login> pour la
        # récupération réelle du blob.
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/recovery-archive/<login>", methods=["GET"])
def get_recovery_archive_entry(login):
    _actor, refused = require_lan_and_actor("get_recovery_archive_entry", target_login=login)
    if refused:
        return refused
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM recovery_key_archive WHERE login = ?", [login])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "aucune clé de récupération archivée pour cet utilisateur"}), 404
        return jsonify(dict(row)), 200
    finally:
        conn.close()


@app.route("/access-log", methods=["GET"])
def get_access_log():
    """Consultation du journal lui-même -- réservée aux mêmes
    conditions (LAN + acteur déclaré), journalisée comme les autres
    actions (consulter qui a consulté quoi reste une action à tracer)."""
    _actor, refused = require_lan_and_actor("get_access_log")
    if refused:
        return refused
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin_access_log ORDER BY at DESC LIMIT 500")
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/users", methods=["GET"])
def list_users_with_roles():
    """Liste complète des comptes coffre AVEC leurs rôles -- pour
    l'écran de gestion super-utilisateur (jamais exposé côté
    vault-api public, qui ne renvoie que login+clé publique). LAN
    uniquement, comme le reste de cette API."""
    _actor, refused = require_lan_and_actor("list_users_with_roles")
    if refused:
        return refused
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT login, is_read_only, is_recovery_controller, is_system_master, created_at FROM users ORDER BY login"
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/users/<login>/roles", methods=["POST"])
def set_user_roles(login):
    """Modifie les rôles d'un compte -- action sensible (accorder ou
    retirer un accès permanent/de contrôle), même garde-fou LAN +
    acteur déclaré + journalisation que le reste de cette API. Chaque
    champ optionnel : n'écrit QUE ce qui est explicitement fourni,
    jamais un rôle réinitialisé par erreur faute d'avoir été
    mentionné dans la requête."""
    actor, refused = require_lan_and_actor("set_user_roles", target_login=login)
    if refused:
        return refused

    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    fields = {}
    for key in ["is_read_only", "is_recovery_controller", "is_system_master"]:
        if key in body:
            fields[key] = 1 if body[key] else 0
    if not fields:
        return jsonify({"error": "aucun rôle fourni"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE login = ?", [login])
        if cur.fetchone() is None:
            return jsonify({"error": "utilisateur introuvable"}), 404
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        cur.execute(f"UPDATE users SET {set_clause} WHERE login = ?", [*fields.values(), login])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/escrow-status", methods=["GET"])
def get_escrow_status():
    """Existe-t-il DÉJÀ une collection de séquestre maître_clefs, peu
    importe qui y a accès ? Distinct de "cette personne y a-t-elle
    accès" (voir usurpMaitrePrincipal côté front) -- une question
    volontairement PUBLIQUE (juste un booléen, aucune donnée sensible)
    pour permettre à l'interface de distinguer "personne n'a jamais
    initialisé le séquestre" (à amorcer) de "le séquestre existe, vous
    n'y avez juste pas encore accès" (à demander à quelqu'un qui
    l'a) -- bug réel trouvé en testant : le message d'erreur générique
    ne faisait pas cette distinction, laissant croire à tort à un
    problème de groupe Keycloak."""
    _actor, refused = require_lan_and_actor("get_escrow_status")
    if refused:
        return refused
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM collections WHERE name = ?", [ESCROW_COLLECTION_NAME])
        exists = cur.fetchone() is not None
        return jsonify({"exists": exists}), 200
    finally:
        conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# Manquait ici jusqu'à cette livraison (#351, backlog item 8) --
# trouvé en vérifiant que memory-api archive réellement TOUS les
# services du projet. COMPLÉMENTAIRE à la journalisation
# d'accès/email déjà existante (voir en-tête du fichier) -- SÉPARÉE,
# stockée en base pour l'audit de sécurité -- jamais un remplacement,
# juste les diagnostics Python standard (WARNING+) en plus.
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


SERVICE_NAME = "vault-admin-api"
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
