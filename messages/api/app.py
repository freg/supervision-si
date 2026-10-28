"""#903 : « blog » du hub -- tuile Messages. Déposer un mot pour tout le monde ou pour soi, permanent ou à durée de vie
automatique, et l'effacer. Sert aussi à se passer une commande d'un poste à l'autre sans la recopier à vue.

Authentification : jeton Keycloak du hub (comme les autres services). Tout utilisateur CONNECTÉ peut écrire et lire
(pas de restriction par groupe) ; seuls l'auteur -- et les administrateurs -- suppriment. Routes :
  GET  /messages                  -> messages visibles par l'appelant
  POST /messages                  {corps, titre?, portee: tous|moi, format: texte|commande, duree_s?} -> message créé
  DELETE /messages/<id>           -> suppression (auteur ou administrateur)
  GET  /health
"""
import logging
import os
import time

from flask import Flask, g, jsonify, request
from flask_cors import CORS

import store
from auth import AuthError, KeycloakVerifier, bearer_from_header

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("messages")

DB_PATH = os.environ.get("MESSAGES_DB", "/data/messages.sqlite")
KEYCLOAK_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "supervision-si")
JWKS_URL = os.environ.get("MESSAGES_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (KEYCLOAK_INTERNAL_URL, KEYCLOAK_REALM)
ADMIN_GROUPS = set(g_.strip() for g_ in os.environ.get("MESSAGES_ADMIN_GROUPS", "administrateurs").split(",") if g_.strip())
DUREES = {"1h": 3600, "1j": 86400, "1s": 604800, "permanent": None}

app = Flask(__name__)
CORS(app, supports_credentials=True)
# allowed_users=["*"] : tout utilisateur authentifié est accepté (le blog est ouvert à tous les connectés)
verifier = KeycloakVerifier(JWKS_URL, ["*"], what="la messagerie du hub")


@app.before_request
def _guard():
    if request.method == "OPTIONS" or request.path == "/health":
        return None
    try:
        g.user = verifier.verify(bearer_from_header(request.headers.get("Authorization")))
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status
    return None


def _conn():
    return store.connect(DB_PATH)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/messages", methods=["GET"])
def liste():
    conn = _conn()
    try:
        msgs = store.lister(conn, g.user["username"])
    finally:
        conn.close()
    return jsonify({"messages": msgs, "moi": g.user["username"], "admin": bool(ADMIN_GROUPS & set(g.user.get("groups") or []))}), 200


@app.route("/messages", methods=["POST"])
def creer():
    b = request.get_json(silent=True) or {}
    duree = b.get("duree_s")
    if isinstance(duree, str):
        duree = DUREES.get(duree, None)
    conn = _conn()
    try:
        m = store.creer(conn, g.user["username"], g.user.get("name"), b.get("corps") or "", titre=b.get("titre") or "",
                        portee=b.get("portee") or "tous", fmt=b.get("format") or "texte", duree_s=duree)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()
    _log.info("message %s par %s (portée %s, %s)", m["id"][:8], g.user["username"], m["portee"], "permanent" if not m["expire"] else "expire")
    return jsonify(m), 201


@app.route("/messages/<mid>", methods=["DELETE"])
def supprimer(mid):
    conn = _conn()
    try:
        ok, motif = store.supprimer(conn, mid, g.user["username"], est_admin=bool(ADMIN_GROUPS & set(g.user.get("groups") or [])))
    finally:
        conn.close()
    if not ok:
        return jsonify({"error": motif}), 404 if motif == "introuvable" else 403
    return jsonify({"supprime": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
