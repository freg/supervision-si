"""accounts-api (livraison #557) -- gestion des comptes et des groupes du
hub en pilotant Keycloak (API Admin REST), tuile « Comptes et groupes ».

Modèle de confiance : comme rights-api et les autres services, l'appelant
transmet ses GROUPES dans la requête (le hub, authentifié par OIDC, les lit
dans le jeton) ; toute écriture exige `administrateurs` ou `admin_hub` (`groups` du corps =
groupes de l'appelant ; les groupes À DONNER à un compte s'appellent
`member_of`, jamais confondus)
(refus par défaut, y compris si le corps est absent). Jamais de mot de
passe renvoyé ni journalisé -- seul l'identifiant du compte touché et
l'auteur sont tracés.
"""
import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

import kc
import demo  # #608 : utilisateurs de démonstration
import events as ev  # #612 : journal des connexions

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "accounts-api")
log = logging.getLogger("accounts")
log.setLevel(logging.INFO)

# Journal partagé (memcached) comme les autres services, lu par la tuile Journaux.
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = read_shared_log_buffer = None
try:
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    _MemcacheClient = None
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


SERVICE_NAME = "accounts-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
if make_shared_log_handler and _MemcacheClient:
    logging.getLogger().addHandler(make_shared_log_handler(SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level="INFO"))


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if (read_shared_log_buffer and _MemcacheClient) else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200
ADMIN_GROUPS = {g.strip() for g in os.environ.get("ACCOUNTS_ADMIN_GROUPS", "administrateurs,admin_hub").split(",") if g.strip()}
LDAP_EDIT_MODE = os.environ.get("LDAP_EDIT_MODE", "READ_ONLY")
_kc = None


def client():
    global _kc
    if _kc is None:
        _kc = kc.Keycloak()
    return _kc


def _body():
    return request.get_json(silent=True) or {}


def _admin(body):
    groups = set(body.get("groups") or [])
    return bool(groups & ADMIN_GROUPS)


def _who(body):
    return body.get("user") or (body.get("groups") or ["?"])[0]


def _forbidden():
    return jsonify({"error": "réservé aux groupes %s" % ", ".join(sorted(ADMIN_GROUPS))}), 403


@app.errorhandler(kc.KeycloakError)
def _kc_error(exc):
    return jsonify({"error": str(exc)}), 502


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/info", methods=["GET"])
def info():
    return jsonify({"realm": client().realm, "service_client_id": client().client_id, "ldap_edit_mode": LDAP_EDIT_MODE, "ldap_writable": LDAP_EDIT_MODE.upper() == "WRITABLE", "admin_groups": sorted(ADMIN_GROUPS)}), 200


# ---- #608 : utilisateurs de démonstration (comptes Keycloak locaux, préfixe demo-) ----
DEMO_PROFILES = demo.profiles(os.environ.get("ACCOUNTS_DEMO_PROFILES"))


def _demo_state():
    return demo.state(DEMO_PROFILES, client().users(search="demo-"))


@app.route("/demo", methods=["GET"])
def demo_get():
    st = _demo_state()
    return jsonify({"users": st, "summary": demo.summary(st), "mail_domain": demo.DEMO_MAIL_DOMAIN}), 200


@app.route("/demo/enable", methods=["POST"])
def demo_enable():
    """Crée les comptes manquants (groupes créés au besoin), réactive les autres,
    (re)génère les mots de passe si `reset_passwords` ; les mots de passe ne sont
    renvoyés que dans CETTE réponse, jamais stockés."""
    b = _body()
    if not _admin(b):
        return _forbidden()
    reset = bool(b.get("reset_passwords"))
    kcl = client()
    existing_groups = {g["name"] for g in kcl.groups()}
    out = []
    for s in _demo_state():
        for g in s["groups"]:
            if g not in existing_groups:
                kcl.create_group(g); existing_groups.add(g)
        pw = None
        if not s["exists"]:
            pw = demo.generate_password()
            u = kcl.create_user(s["username"], email="%s@%s" % (s["username"], demo.DEMO_MAIL_DOMAIN), first_name=s["first_name"], last_name=s["last_name"], enabled=True, groups=s["groups"], password=pw, temporary=False)
        else:
            u = kcl.update_user(s["id"], enabled=True)
            if set(s["groups"]) != set(s["groups_current"]):
                kcl.set_groups(s["id"], s["groups"])
            if reset:
                pw = demo.generate_password()
                kcl.set_password(s["id"], pw, temporary=False)
        out.append({"username": s["username"], "groups": s["groups"], "password": pw, "enabled": True, "id": u.get("id") if isinstance(u, dict) else s["id"]})
    log.warning("démo : comptes activés par %s (%s)", _who(b), ", ".join(x["username"] for x in out))
    return jsonify({"users": out, "summary": demo.summary(_demo_state())}), 200


@app.route("/demo/disable", methods=["POST"])
def demo_disable():
    b = _body()
    if not _admin(b):
        return _forbidden()
    kcl = client()
    n = 0
    for s in _demo_state():
        if s["exists"]:
            kcl.update_user(s["id"], enabled=False)
            try:
                kcl.logout(s["id"])  # sessions ouvertes fermées : la démo s'arrête vraiment
            except kc.KeycloakError:
                pass
            n += 1
    log.warning("démo : %d compte(s) désactivé(s) par %s", n, _who(b))
    return jsonify({"disabled": n, "summary": demo.summary(_demo_state())}), 200


@app.route("/demo", methods=["DELETE"])
def demo_delete():
    b = _body()
    if not _admin(b):
        return _forbidden()
    kcl = client()
    n = 0
    for s in _demo_state():
        if s["exists"]:
            kcl.delete_user(s["id"]); n += 1
    log.warning("démo : %d compte(s) supprimé(s) par %s", n, _who(b))
    return jsonify({"deleted": n}), 200


# ---- #612 : journal des connexions (événements Keycloak du realm) ----
@app.route("/events", methods=["GET"])
def events_get():
    kind = request.args.get("kind", "")            # '' | errors | <TYPE>
    query = request.args.get("q", "")
    limit = min(max(request.args.get("limit", 300, type=int), 1), 1000)
    c = client()
    cfg = ev.config_state(c.events_config())
    rows = ev.normalize(c.events(types=ev.SHOWN_TYPES, max_results=limit)) if cfg["enabled"] else []
    shown = ev.filter_rows(rows, kind, query)
    return jsonify({"events": shown, "summary": ev.summary(rows), "config": cfg, "types": ev.SHOWN_TYPES,
                    "labels": {t: ev.label_type(t) for t in ev.SHOWN_TYPES}}), 200


@app.route("/events/enable", methods=["POST"])
def events_enable():
    body = request.get_json(silent=True) or {}
    if not _admin(body):
        return _forbidden()
    c = client()
    cfg, changed = ev.config_plan(c.events_config())
    if changed:
        c.set_events_config(cfg)
        log.info("conservation des événements Keycloak activée (%s j) par %s", ev.EXPIRATION_DAYS, _who(body))
    return jsonify({"changed": changed, "config": ev.config_state(cfg)}), 200


@app.route("/groups", methods=["GET"])
def groups():
    return jsonify({"groups": client().groups()}), 200


@app.route("/groups", methods=["POST"])
def create_group():
    b = _body()
    if not _admin(b):
        return _forbidden()
    g = client().create_group(b.get("name"))
    log.info("groupe créé %s par %s", g and g["name"], _who(b))
    return jsonify({"group": g}), 201


@app.route("/groups/<group_id>", methods=["DELETE"])
def delete_group(group_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    client().delete_group(group_id)
    log.info("groupe %s supprimé par %s", group_id, _who(b))
    return jsonify({"ok": True}), 200


@app.route("/groups/<group_id>/members", methods=["GET"])
def group_members(group_id):
    return jsonify({"members": client().group_members(group_id)}), 200


@app.route("/users", methods=["GET"])
def users():
    return jsonify({"users": client().users(request.args.get("search") or None)}), 200


@app.route("/users", methods=["POST"])
def create_user():
    b = _body()
    if not _admin(b):
        return _forbidden()
    # `groups` = groupes de l'APPELANT (droits) ; `member_of` = groupes du compte créé
    u = client().create_user(b.get("username"), b.get("email"), b.get("first_name"), b.get("last_name"), b.get("enabled", True),
                             b.get("member_of") or [], b.get("password") or None, b.get("temporary", True))
    log.info("compte %s créé par %s (groupes %s)", u["username"], _who(b), ",".join(u["groups"]))
    return jsonify({"user": u}), 201


@app.route("/users/<user_id>", methods=["PUT"])
def update_user(user_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    u = client().update_user(user_id, email=b.get("email"), first_name=b.get("first_name"), last_name=b.get("last_name"), enabled=b.get("enabled"))
    log.info("compte %s modifié par %s", u["username"], _who(b))
    return jsonify({"user": u}), 200


@app.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    client().delete_user(user_id)
    log.info("compte %s supprimé par %s", user_id, _who(b))
    return jsonify({"ok": True}), 200


@app.route("/users/<user_id>/groups", methods=["PUT"])
def set_user_groups(user_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    names = client().set_groups(user_id, b.get("member_of") or [])  # `groups` = appelant
    log.info("groupes de %s = %s par %s", user_id, ",".join(names), _who(b))
    return jsonify({"groups": names}), 200


@app.route("/users/<user_id>/password", methods=["PUT"])
def set_password(user_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    client().set_password(user_id, b.get("password"), b.get("temporary", True))
    log.info("mot de passe de %s réinitialisé par %s (temporaire=%s)", user_id, _who(b), bool(b.get("temporary", True)))
    return jsonify({"ok": True}), 200


@app.route("/users/<user_id>/send-reset", methods=["POST"])
def send_reset(user_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    client().send_reset_email(user_id)
    return jsonify({"ok": True}), 200


@app.route("/users/<user_id>/logout", methods=["POST"])
def logout(user_id):
    b = _body()
    if not _admin(b):
        return _forbidden()
    client().logout(user_id)
    return jsonify({"ok": True}), 200
