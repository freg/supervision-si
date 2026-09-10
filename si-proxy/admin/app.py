# -*- coding: utf-8 -*-
"""si-proxy-admin-api (livraison #454) -- pont entre le hub et l'interface
de contrôle du bastion si-proxy (#453), derrière la passerelle
(`/api/si-proxy/`).

Pourquoi un pont : l'interface de contrôle du relais exige le jeton
d'administration `SI_PROXY_ADMIN_TOKEN`. Ce jeton ne doit JAMAIS être dans
le navigateur (il serait dans le bundle du hub, lisible par tout
utilisateur authentifié). Il reste ici, côté serveur ; le hub s'identifie
avec son jeton d'accès Keycloak (`Authorization: Bearer`), VÉRIFIÉ
(signature RS256, expiration) et restreint à `SI_PROXY_ADMIN_USERS`
(défaut : freg). Premier service du projet à vérifier réellement le jeton
OIDC -- le bastion le justifie.

Routes (préfixe /api/si-proxy via tls-proxy) -- toutes exigent le Bearer :
  GET  /whoami                 -> {username, name} (sonde d'accès de la tuile)
  GET  /status                 -> état du relais (proxy de /status)
  GET  /audit?limit=N          -> journal (proxy de /audit)
  GET  /summary?hours=24       -> synthèse supervision / analyse réseau
  GET  /exposure               -> inventaire d'exposition (shared/EXPOSURE.json,
                                  #455 : routes passerelle, ports directs, réseau hôte)
  POST /sessions/<id>/kill, /disable, /enable, /unban/<ip>
Sans Bearer : /health et /version seulement.
"""
import json
import logging
import os
import ssl
import urllib.error
import urllib.request

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from auth import AuthError, KeycloakVerifier, bearer_from_header
import summary as summary_mod

try:
    from version_endpoint import register_version_route
except ImportError:  # pragma: no cover
    register_version_route = None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("si-proxy-admin")

KEYCLOAK_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "supervision-si")
JWKS_URL = os.environ.get("SI_PROXY_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (KEYCLOAK_INTERNAL_URL, KEYCLOAK_REALM)
ADMIN_USERS = [u for u in os.environ.get("SI_PROXY_ADMIN_USERS", "freg").split(",") if u.strip()]
CONTROL_URL = os.environ.get("SI_PROXY_CONTROL_URL", "https://si-proxy:6452").rstrip("/")
CONTROL_CA = os.environ.get("SI_PROXY_CONTROL_CA", "/ca/ca.crt")
ADMIN_TOKEN = os.environ.get("SI_PROXY_ADMIN_TOKEN", "")
EXPECTED_AZP = os.environ.get("SI_PROXY_EXPECTED_AZP") or None
EXPOSURE_PATH = os.environ.get("SI_PROXY_EXPOSURE_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "EXPOSURE.json")

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "si-proxy-admin-api")

verifier = KeycloakVerifier(JWKS_URL, ADMIN_USERS, expected_azp=EXPECTED_AZP)


# -- accès à l'interface de contrôle du relais ---------------------------
def _ssl_context():
    ctx = ssl.create_default_context()
    if os.path.exists(CONTROL_CA):
        ctx.load_verify_locations(CONTROL_CA)
    return ctx


def control_call(method, path, timeout=8):
    """Appelle l'interface de contrôle du relais avec le jeton d'admin
    (jamais journalisé). -> (status, dict). Relais injoignable -> (503, {...})."""
    if not ADMIN_TOKEN:
        return 503, {"error": "SI_PROXY_ADMIN_TOKEN absent : pont non configuré"}
    req = urllib.request.Request(CONTROL_URL + path, method=method, headers={"X-Si-Proxy-Admin": ADMIN_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            body = {"error": "réponse illisible du relais"}
        return exc.code, body
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 503, {"error": "relais injoignable : %s" % getattr(exc, "reason", exc)}


app.control_call = control_call  # remplaçable dans les tests


# -- garde d'identité -----------------------------------------------------
PUBLIC = ("/health", "/version")


@app.before_request
def _guard():
    if request.method == "OPTIONS" or request.path in PUBLIC:
        return None
    try:
        g.user = verifier.verify(bearer_from_header(request.headers.get("Authorization")))
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status
    return None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "configured": bool(ADMIN_TOKEN), "admin_users": ADMIN_USERS}), 200


@app.route("/whoami", methods=["GET"])
def whoami():
    return jsonify({"username": g.user["username"], "name": g.user["name"]}), 200


@app.route("/status", methods=["GET"])
def status():
    code, body = app.control_call("GET", "/status")
    return jsonify(body), code


@app.route("/audit", methods=["GET"])
def audit():
    try:
        limit = max(1, min(1000, int(request.args.get("limit", "200"))))
    except ValueError:
        limit = 200
    code, body = app.control_call("GET", "/audit?limit=%d" % limit)
    return jsonify(body), code


@app.route("/summary", methods=["GET"])
def summary():
    try:
        hours = max(1, min(24 * 30, int(request.args.get("hours", "24"))))
    except ValueError:
        hours = 24
    code, st = app.control_call("GET", "/status")
    if code != 200:
        st = {"_reachable": False, "error": st.get("error")}
    _, au = app.control_call("GET", "/audit?limit=1000")
    events = au.get("audit") if isinstance(au, dict) else []
    out = summary_mod.build_summary(st, events or [], window_h=hours)
    if st.get("error"):
        out["error"] = st["error"]
    return jsonify(out), 200


@app.route("/exposure", methods=["GET"])
def exposure():
    """Inventaire d'exposition généré par scripts/render-exposure.py (copié
    au build). Absent -> réponse explicite, jamais une 500."""
    try:
        with open(EXPOSURE_PATH, encoding="utf-8") as fh:
            return jsonify(json.load(fh)), 200
    except (OSError, ValueError) as exc:
        return jsonify({"error": "inventaire d'exposition indisponible : %s" % exc, "gateway": [], "direct_ports": [], "host_network": [],
                        "counts": {"gateway_routes": 0, "direct_ports": 0, "direct_public": 0, "host_network": 0}}), 200


def _act(method, path, log_msg):
    code, body = app.control_call(method, path)
    _log.warning("%s par %s -> %s", log_msg, g.user["username"], code)
    return jsonify(body), code


@app.route("/sessions/<sid>/kill", methods=["POST"])
def kill(sid):
    if not sid.isdigit():
        return jsonify({"error": "identifiant de session invalide"}), 400
    return _act("POST", "/sessions/%s/kill" % sid, "session %s tuée" % sid)


@app.route("/disable", methods=["POST"])
def disable():
    return _act("POST", "/disable", "bastion mis en pause")


@app.route("/enable", methods=["POST"])
def enable():
    return _act("POST", "/enable", "bastion réactivé")


@app.route("/unban/<ip>", methods=["POST"])
def unban(ip):
    if len(ip) > 45 or any(c not in "0123456789abcdefABCDEF.:" for c in ip):
        return jsonify({"error": "adresse invalide"}), 400
    return _act("POST", "/unban/%s" % ip, "IP %s débannie" % ip)


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
