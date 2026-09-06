"""
Front de gestion OpenLDAP -- backend Flask. `actor` tracé sur chaque
écriture pour l'audit, jamais pour bloquer une requête.

⚠️ Livraison #290 -- ÉVOLUTION du modèle de confiance initial
("groupe Keycloak 'administrateurs' vérifié côté FRONT, jamais une
deuxième couche d'autorisation ici"). Clarifié explicitement par la
personne : PAS une contradiction, une évolution voulue -- réserver
les actions d'écriture à une catégorie d'utilisateurs plus précise
que "administrateurs" (trop large), via rights-api (#283). Gating
OPT-IN (voir `_check_manage_right` plus bas) -- désactivé par
défaut, comportement identique à avant #290 tant qu'il n'est pas
explicitement activé.

Configuration -- volontairement SÉPARÉE de celle de Keycloak
(LDAP_URL/LDAP_BIND_DN/...), qui est en lecture seule
(LDAP_EDIT_MODE=READ_ONLY, voir .env.example) : ce module a besoin
d'un compte de liaison CAPABLE D'ÉCRITURE, jamais le même compte que
la fédération d'authentification.

MOT DE PASSE DE LIAISON -- demandé explicitement : JAMAIS pré-
configuré en variable d'environnement, jamais conservé côté serveur
d'une requête à l'autre. Transmis par la personne à CHAQUE accès (en-
tête `X-LDAP-Bind-Password`), utilisé UNIQUEMENT pour la durée de la
requête HTTP en cours, jamais journalisé, jamais écrit sur disque.
Seuls url/bind_dn/base_dn (des PARAMÈTRES de connexion, pas un
secret) restent configurés côté serveur."""

import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

import ldap_client
import ldap_backup
import ldif_tools

# Import DÉFENSIF -- même motif qu'ailleurs dans ce projet (voir
# dba/api/app.py) : version_endpoint.py n'existe que dans le
# conteneur Docker réel (copié depuis shared/ au build). Sans ce
# garde, tout test qui importe ce module directement casserait au
# chargement.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "ldap-admin-api")

_log = logging.getLogger("ldap_admin_app")

# Livraison #290 -- OPT-IN, vide/absent = gating désactivé
# (comportement identique à avant #290). Voir docstring du module
# pour le raisonnement complet.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif que ssh-tunnels-api (#289) -- voir ce module pour
    le détail complet du raisonnement (FAIL CLOSED, jamais fail-open,
    y compris pour admin_hub si rights-api est injoignable ou répond
    de façon inattendue)."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "ldap-admin-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur ldap-admin-api requis (groupe admin_hub, ou un octroi explicite)"

# Base de connexion -- PARAMÈTRES uniquement, jamais le mot de passe
# (voir docstring du module). Ces trois champs suffisent à savoir OÙ
# et EN QUEL NOM se connecter -- le mot de passe manquant est ce qui
# rend cette config, seule, insuffisante pour agir.
#
# Bug réel signalé (capture d'écran) : base_dn repliait jusqu'ici
# silencieusement sur LDAP_USERS_DN (Keycloak) si LDAP_ADMIN_BASE_DN
# n'était pas réglée -- avait du sens tant que cet outil ne servait
# qu'à réinitialiser des mots de passe utilisateur, mais INDUIT EN
# ERREUR maintenant que c'est un vrai navigateur d'annuaire complet :
# LDAP_USERS_DN pointe typiquement sur UNE SEULE unité organisationnelle
# (ex. ou=accounts), jamais la racine -- tout ce qui est en dehors
# (cn=admin, cn=keycloak, cn=replicator...) restait invisible sans
# qu'aucun message n'indique pourquoi. Retiré : base_dn DOIT
# désormais être réglée explicitement (typiquement la racine complète
# de l'annuaire, ex. dc=exemple,dc=fr, pour une gestion complète) --
# absente, un message d'erreur clair (503) le dit, plutôt qu'un
# repli silencieux vers la mauvaise portée.
LDAP_ADMIN_BASE_CONFIG = {
    "url": os.environ.get("LDAP_ADMIN_URL") or os.environ.get("LDAP_URL", ""),
    "bind_dn": os.environ.get("LDAP_ADMIN_BIND_DN", ""),
    "base_dn": os.environ.get("LDAP_ADMIN_BASE_DN", ""),
}

BACKUP_DIR = os.environ.get("LDAP_ADMIN_BACKUP_DIR", "/data/backups")
BACKUP_RETENTION_COUNT = int(os.environ.get("LDAP_ADMIN_BACKUP_RETENTION_COUNT", "30"))


def base_config_is_complete():
    """Les 3 PARAMÈTRES (jamais le mot de passe, fourni à part à
    chaque requête) doivent être renseignés pour que ce module ait ne
    serait-ce qu'un sens -- déploiement où il n'a jamais été
    configuré."""
    return all(LDAP_ADMIN_BASE_CONFIG.get(k) for k in ("url", "bind_dn", "base_dn"))


def bind_password_from_request():
    """Le mot de passe de liaison vient UNIQUEMENT de l'en-tête de
    CETTE requête -- jamais un repli sur une variable d'environnement
    ou une valeur mémorisée d'un appel précédent. En-tête plutôt
    qu'un paramètre d'URL (jamais un secret dans une URL, visible
    dans les journaux d'accès) -- fonctionne uniformément pour GET
    comme pour POST/PUT, contrairement à un corps de requête qui
    serait absent sur un GET."""
    return request.headers.get("X-LDAP-Bind-Password", "")


def require_ready_config():
    """Vérifie la config de base ET la présence d'un mot de passe
    dans CETTE requête -- jamais l'un sans l'autre. Renvoie soit
    (config_complète, None) soit (None, réponse_erreur)."""
    if not base_config_is_complete():
        return None, (jsonify({
            "error": "configuration LDAP incomplète -- LDAP_ADMIN_URL/BIND_DN/BASE_DN "
                     "doivent être renseignées côté serveur (voir .env.example)"
        }), 503)
    password = bind_password_from_request()
    if not password:
        return None, (jsonify({
            "error": "mot de passe de liaison requis (en-tête X-LDAP-Bind-Password) -- "
                     "jamais mémorisé côté serveur, à fournir à chaque accès"
        }), 401)
    return {**LDAP_ADMIN_BASE_CONFIG, "bind_password": password}, None


# ------------------------------------------------------------------
# Journal en memoire (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du hub (gestionnaire
# de logs, livraison #139). Meme motif EXACT que api/app.py -- ne
# capture PAS le corps des requetes ni de donnee metier (annuaire
# LDAP -- SENSITIVE_ATTRS plus bas jamais journalises via ce chemin,
# seulement ce que ce fichier journalise deja lui-meme). Tampon
# circulaire en memoire, borne (LOG_BUFFER_SIZE, defaut 200), jamais
# persiste sur disque. Seuil par defaut WARNING (pas INFO) : evite le
# bruit des logs d'acces Werkzeug.
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

SERVICE_NAME = "ldap-admin-api"
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
    return jsonify({"status": "ok", "base_config_complete": base_config_is_complete()}), 200


SENSITIVE_ATTRS = {"userpassword", "krbprincipalkey", "sambantpassword", "sambalmpassword", "authpassword"}


@app.route("/entries", methods=["GET"])
def list_entries():
    """Toutes les entrées de l'annuaire (structure ET utilisateurs) --
    demandé explicitement pour un navigateur en colonnes façon
    phpLDAPadmin/Finder (l'arbre complet depuis la racine, pas
    seulement les entrées avec un uid). Réutilise le même export
    complet que /users et les sauvegardes -- une seule façon de
    parler au serveur, jamais une deuxième requête LDAP séparée.
    Attributs sensibles (mots de passe, clés) systématiquement
    exclus de la réponse, jamais envoyés au navigateur même s'ils
    sont présents dans le LDIF exporté."""
    config, err = require_ready_config()
    if err:
        return err
    result = ldap_client.export_ldif(config)
    if not result["ok"]:
        return jsonify({"error": f"connexion LDAP échouée : {result['stderr']}"}), 502

    entries = ldif_tools.parse_ldif(result["stdout"])
    output = []
    for dn, attrs in entries.items():
        safe_attrs = {k: v for k, v in attrs.items() if k.lower() not in SENSITIVE_ATTRS}
        output.append({"dn": dn, "attrs": safe_attrs})
    return jsonify(output), 200


@app.route("/users", methods=["GET"])
def list_users():
    """Liste les entrées de l'annuaire (export complet puis filtrage
    côté serveur sur les entrées ayant un uid -- pas de requête LDAP
    filtrée séparée, réutilise le même mécanisme d'export que les
    sauvegardes, une seule façon de parler au serveur)."""
    config, err = require_ready_config()
    if err:
        return err
    result = ldap_client.export_ldif(config)
    if not result["ok"]:
        return jsonify({"error": f"connexion LDAP échouée : {result['stderr']}"}), 502

    entries = ldif_tools.parse_ldif(result["stdout"])
    users = []
    for dn, attrs in entries.items():
        uid = attrs.get("uid", [None])[0]
        if uid is None:
            continue
        users.append({
            "dn": dn,
            "uid": uid,
            "cn": attrs.get("cn", [""])[0],
            "mail": attrs.get("mail", [""])[0],
        })
    return jsonify(users), 200


@app.route("/users/<path:user_dn>/password", methods=["PUT"])
def reset_password(user_dn):
    """Réinitialisation d'un mot de passe -- sauvegarde automatique
    AVANT toute écriture (même principe qu'ailleurs dans ce projet,
    voir tickets/api/backup_manager.py), édition annulée si la
    sauvegarde échoue plutôt que risquée sans filet. Le mot de passe
    CIBLE (celui qu'on installe) en clair ne transite jamais au-delà
    de cette fonction (haché avant tout envoi réseau, voir
    ldap_client.reset_user_password) -- ne pas confondre avec le mot
    de passe de LIAISON (celui qui sert à s'authentifier auprès du
    serveur LDAP), fourni via l'en-tête à chaque requête."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    config, err = require_ready_config()
    if err:
        return err
    new_password = body.get("new_password", "")
    actor = body.get("actor", "")
    if not new_password or len(new_password) < 8:
        return jsonify({"error": "mot de passe requis, au moins 8 caractères"}), 400

    try:
        ldap_backup.create_backup(
            BACKUP_DIR, "avant-reset-mdp", config,
            ldap_client.export_ldif, retention_count=BACKUP_RETENTION_COUNT,
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"sauvegarde de sécurité impossible, réinitialisation annulée par prudence : {exc}"}), 500

    result = ldap_client.reset_user_password(config, user_dn, new_password)
    if not result["ok"]:
        return jsonify({"error": f"réinitialisation échouée : {result['stderr']}"}), 502

    app.logger.info("Mot de passe réinitialisé pour %s par %s", user_dn, actor or "(non tracé)")
    return jsonify({"status": "ok"}), 200


@app.route("/entries/<path:dn>", methods=["PUT"])
def update_entry(dn):
    """Modification générique des attributs d'une entrée -- demandé
    explicitement ("accéder et éditer tous les attributs à tous les
    niveaux, en particulier les feuilles de l'arbre" -- ex. un groupe
    comme cn=Parapheur, qui n'a jamais de uid et n'apparaissait donc
    jamais nulle part avant ce chantier). Sauvegarde automatique
    AVANT toute écriture, même principe que reset_password.

    `attr_changes` : {attribut: [nouvelles_valeurs]} -- remplace
    entièrement chaque attribut listé (voir
    ldap_client.build_modify_ldif). Attributs sensibles (mots de
    passe) explicitement REFUSÉS ici -- passer par
    PUT /users/<dn>/password, seule route garantissant le hachage
    SSHA, jamais un envoi en clair via ce point d'entrée générique."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    config, err = require_ready_config()
    if err:
        return err
    attr_changes = body.get("attr_changes", {})
    actor = body.get("actor", "")
    if not attr_changes:
        return jsonify({"error": "aucun changement fourni"}), 400

    blocked = [a for a in attr_changes if a.lower() in SENSITIVE_ATTRS]
    if blocked:
        return jsonify({
            "error": f"attribut(s) sensible(s) non modifiables ici : {', '.join(blocked)} "
                     "-- voir la réinitialisation de mot de passe dédiée"
        }), 400

    try:
        ldap_backup.create_backup(
            BACKUP_DIR, "avant-edition-attribut", config,
            ldap_client.export_ldif, retention_count=BACKUP_RETENTION_COUNT,
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"sauvegarde de sécurité impossible, modification annulée par prudence : {exc}"}), 500

    ldif_text = ldap_client.build_modify_ldif(dn, attr_changes)
    result = ldap_client.apply_ldif(config, ldif_text)
    if not result["ok"]:
        return jsonify({"error": f"modification échouée : {result['stderr']}"}), 502

    app.logger.info("Entrée modifiée %s par %s (attributs : %s)", dn, actor or "(non tracé)", ", ".join(attr_changes.keys()))
    return jsonify({"status": "ok"}), 200


@app.route("/backups", methods=["GET"])
def list_backups():
    files = ldap_backup.list_backup_files(BACKUP_DIR)
    entries = []
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        entries.append({"filename": f, "size_bytes": size})
    return jsonify(entries), 200


@app.route("/backups", methods=["POST"])
def create_backup_route():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    config, err = require_ready_config()
    if err:
        return err
    try:
        filename = ldap_backup.create_backup(
            BACKUP_DIR, "manuel", config,
            ldap_client.export_ldif, retention_count=BACKUP_RETENTION_COUNT,
        )
        return jsonify({"status": "ok", "filename": filename}), 201
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"sauvegarde échouée : {exc}"}), 500


@app.route("/backups/<path:filename>", methods=["GET"])
def get_backup_content(filename):
    """Contenu LDIF brut d'une sauvegarde -- demandé explicitement
    ("réinjectable depuis un shell") : la personne doit pouvoir
    télécharger ce fichier tel quel et l'utiliser directement avec
    ldapmodify/ldapadd, indépendamment de cette interface. Lecture
    d'un fichier déjà sur disque -- ne nécessite AUCUNE connexion
    LDAP, donc pas de mot de passe de liaison requis ici."""
    try:
        content = ldap_backup.read_backup(BACKUP_DIR, filename)
        return app.response_class(content, mimetype="text/plain")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/backups/diff", methods=["GET"])
def diff_backups():
    """Diff "façon git" entre deux sauvegardes -- demandé
    explicitement. `before`/`after` = noms de fichiers (voir
    GET /backups). Compare deux fichiers déjà sur disque -- aucune
    connexion LDAP nécessaire, aucun mot de passe requis ici non
    plus."""
    before_name = request.args.get("before", "")
    after_name = request.args.get("after", "")
    try:
        before_text = ldap_backup.read_backup(BACKUP_DIR, before_name)
        after_text = ldap_backup.read_backup(BACKUP_DIR, after_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    before_entries = ldif_tools.parse_ldif(before_text)
    after_entries = ldif_tools.parse_ldif(after_text)
    diff = ldif_tools.diff_ldif(before_entries, after_entries)
    return jsonify(diff), 200


@app.route("/apply", methods=["POST"])
def apply_ldif_route():
    """Application directe d'un LDIF -- DESTRUCTIF par nature
    (modifications réelles sur l'annuaire), demandé explicitement
    ("réinjectable depuis un shell", ce point d'entrée est
    l'équivalent web de `ldapmodify -f fichier.ldif`). Sauvegarde
    automatique AVANT, même principe que reset_password ci-dessus."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    config, err = require_ready_config()
    if err:
        return err
    ldif_text = body.get("ldif", "")
    actor = body.get("actor", "")
    if not ldif_text.strip():
        return jsonify({"error": "contenu LDIF requis"}), 400

    try:
        ldap_backup.create_backup(
            BACKUP_DIR, "avant-application-ldif", config,
            ldap_client.export_ldif, retention_count=BACKUP_RETENTION_COUNT,
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"sauvegarde de sécurité impossible, application annulée par prudence : {exc}"}), 500

    result = ldap_client.apply_ldif(config, ldif_text)
    if not result["ok"]:
        return jsonify({"error": f"application échouée : {result['stderr']}"}), 502

    app.logger.info("LDIF appliqué par %s", actor or "(non tracé)")
    return jsonify({"status": "ok", "output": result["stdout"]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
