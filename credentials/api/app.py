# -*- coding: utf-8 -*-
"""credentials-api — accès de gestion des équipements (livraison #498).

Demandé explicitement : « une gestion des user/password des routeurs et
autres accès de gestion d'équipement, et retirer du .env les clés
mikrotik : ça doit être géré dans les secrets du hub ».

Un seul coffre pour les identifiants que des SERVICES du hub utilisent
eux-mêmes (API RouterOS, SSH d'équipements, pages HTTP de gestion,
communautés SNMP…) -- distinct du coffre-fort de codes (`vault/`), chiffré
de bout en bout et destiné aux HUMAINS : ici le serveur doit pouvoir
déchiffrer, sinon aucun relevé automatique n'est possible.

Deux faces, deux niveaux de confiance :

  - GESTION (navigateur, posture LAN comme ups-monitor) :
        GET  /credentials/                  page du hub
        GET  /credentials/status            chiffrement configuré ? nombre d'accès
        GET  /credentials/list              fiches SANS mot de passe (has_password seulement)
        POST /credentials/list              créer {name, kind, username, password, notes}
        PUT  /credentials/list/<name>       modifier (password absent = inchangé)
        DELETE /credentials/list/<name>
        GET  /credentials/audit             journal des révélations (qui, quoi, quand -- jamais la valeur)
        POST /credentials/reencrypt         rechiffre les valeurs encore en clair
    Le mot de passe n'est JAMAIS renvoyé par ces routes, même au créateur.

  - RÉVÉLATION (services internes seulement, réseau Docker) :
        GET  /credentials/reveal/<name>     -> {username, password}
    Exige l'en-tête X-Credentials-Token égal à CREDENTIALS_INTERNAL_TOKEN
    (jamais transmis au navigateur : tls-proxy ne publie pas ce chemin,
    et la route répond 404 si le jeton n'est pas configuré). L'en-tête
    X-Credentials-Consumer (nom du service) est journalisé.
"""
import hmac
import logging
import os
import re

from flask import Flask, jsonify, request, send_from_directory

import credential_crypto
import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("credentials")

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
DATA_DIR = os.environ.get("CREDENTIALS_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "credentials.db")
INTERNAL_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
if INTERNAL_TOKEN in ("change-me",):
    INTERNAL_TOKEN = ""

app = Flask(__name__)
store.ensure_schema(DB_PATH)

try:
    from version_endpoint import register_version_route
    register_version_route(app, "credentials")
except ImportError:
    pass


def _bad(msg, code=400):
    return jsonify({"error": msg}), code


# ---------------------------------------------------------------- pages

@app.route("/credentials/", methods=["GET"])
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/credentials/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "credentials"}), 200


@app.route("/credentials/status", methods=["GET"])
def status():
    items = store.list_credentials(DB_PATH)
    return jsonify({
        "encryption_configured": credential_crypto.is_configured(),
        "reveal_enabled": bool(INTERNAL_TOKEN),
        "count": len(items),
        "clear_count": sum(1 for i in items if i["has_password"] and not i["password_encrypted"]),
        "kinds": list(store.KINDS),
    }), 200


# ---------------------------------------------------------------- gestion

@app.route("/credentials/list", methods=["GET"])
def list_all():
    return jsonify({"credentials": store.list_credentials(DB_PATH)}), 200


def _validate(body, require_password):
    name = (body.get("name") or "").strip()
    if not re.match(store.NAME_RE, name):
        return None, "nom invalide (lettres, chiffres, . _ - ; 64 caractères max ; ex. mikrotik, sw-agence)"
    kind = (body.get("kind") or "other").strip().lower()
    if kind not in store.KINDS:
        return None, "genre inconnu : %s (attendu : %s)" % (kind, ", ".join(store.KINDS))
    username = (body.get("username") or "").strip()
    password = body.get("password")
    if require_password and not password:
        return None, "mot de passe requis"
    if password and not credential_crypto.is_configured():
        return None, ("chiffrement non configuré : CREDENTIALS_PASSPHRASE absente -- aucun mot de passe n'est "
                      "stocké en clair ici (voir credentials/README.md)")
    return {"name": name, "kind": kind, "username": username, "password": password, "notes": (body.get("notes") or "").strip()}, None


@app.route("/credentials/list", methods=["POST"])
def create():
    body = request.get_json(silent=True) or {}
    values, err = _validate(body, require_password=True)
    if err:
        return _bad(err, 503 if "chiffrement" in err else 400)
    if store.get_credential(DB_PATH, values["name"]):
        return _bad("un accès « %s » existe déjà (modifier plutôt)" % values["name"], 409)
    try:
        item = store.upsert(DB_PATH, values["name"], values["kind"], values["username"], values["password"], values["notes"])
    except ValueError as exc:
        return _bad(str(exc), 503)
    log.info("accès créé : %s (%s)", item["name"], item["kind"])
    return jsonify(item), 201


@app.route("/credentials/list/<name>", methods=["PUT"])
def update(name):
    body = dict(request.get_json(silent=True) or {})
    body["name"] = name
    if not store.get_credential(DB_PATH, name):
        return _bad("accès inconnu : %s" % name, 404)
    values, err = _validate(body, require_password=False)
    if err:
        return _bad(err, 503 if "chiffrement" in err else 400)
    try:
        item = store.upsert(DB_PATH, name, values["kind"], values["username"], values["password"], values["notes"],
                            keep_password=not values["password"])
    except ValueError as exc:
        return _bad(str(exc), 503)
    log.info("accès modifié : %s (mot de passe %s)", name, "changé" if values["password"] else "inchangé")
    return jsonify(item), 200


@app.route("/credentials/list/<name>", methods=["DELETE"])
def remove(name):
    if not store.delete(DB_PATH, name):
        return _bad("accès inconnu : %s" % name, 404)
    log.info("accès supprimé : %s", name)
    return jsonify({"status": "ok", "deleted": name}), 200


@app.route("/credentials/audit", methods=["GET"])
def audit():
    return jsonify({"reveals": store.audit(DB_PATH, request.args.get("limit", 200))}), 200


@app.route("/credentials/reencrypt", methods=["POST"])
def reencrypt():
    if not credential_crypto.is_configured():
        return _bad("chiffrement non configuré", 503)
    n = store.reencrypt_all(DB_PATH)
    log.info("rechiffrement : %d accès", n)
    return jsonify({"status": "ok", "reencrypted": n}), 200


# ---------------------------------------------------------------- révélation (services internes)

@app.route("/credentials/reveal/<name>", methods=["GET"])
def reveal(name):
    """Réservé aux services du réseau Docker : jeton interne obligatoire.
    Sans jeton configuré, la route N'EXISTE PAS (404) -- jamais un coffre
    ouvert par défaut. Un mauvais jeton = 403, journalisé sans la valeur."""
    if not INTERNAL_TOKEN:
        return _bad("révélation désactivée (CREDENTIALS_INTERNAL_TOKEN non configuré)", 404)
    if request.headers.get("X-Forwarded-For") or request.headers.get("X-Forwarded-Proto"):
        # passé par la passerelle (tls-proxy pose ces en-têtes) : un
        # navigateur, jamais un service interne -- la route n'existe pas.
        log.warning("révélation refusée (requête via passerelle) : %s", name)
        return _bad("route interne", 404)
    given = request.headers.get("X-Credentials-Token", "")
    consumer = (request.headers.get("X-Credentials-Consumer") or request.remote_addr or "?")[:80]
    if not given or not hmac.compare_digest(given, INTERNAL_TOKEN):
        log.warning("révélation refusée (jeton invalide) : %s par %s", name, consumer)
        return _bad("jeton interne invalide", 403)
    try:
        username, password = store.reveal(DB_PATH, name, consumer)
    except KeyError:
        return _bad("accès inconnu : %s -- à créer dans la tuile Accès d'équipements" % name, 404)
    except ValueError as exc:
        return _bad(str(exc), 503)
    return jsonify({"name": name, "username": username, "password": password}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
