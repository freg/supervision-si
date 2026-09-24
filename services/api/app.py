# -*- coding: utf-8 -*-
"""services-api (livraison #584) -- « Services du hub » : feu tricolore et
redémarrage de tous les conteneurs du projet, pour la sous-tuile de
Paramétrage.

Sécurité : le socket Docker est monté (équivaut à root sur l'hôte, comme
docker-monitor-api #376 -- volontairement jamais routé par la passerelle).
Ici la route EST publiée (/api/services/) mais chaque appel exige un jeton
Keycloak VÉRIFIÉ (RS256/JWKS, même vérificateur que si-proxy-admin-api
#454) et un utilisateur de `SERVICES_ADMIN_USERS`. Périmètre : les seuls
conteneurs du projet compose (label), start/restart uniquement -- ni stop,
ni suppression, ni image. Jamais de secret dans les réponses (les
variables d'environnement des conteneurs ne sont pas lues).

Santé : pour chaque conteneur, état Docker + healthcheck s'il existe +
requête HTTP interne sur le premier port exposé (`/health`, puis `/`),
classée par lights.py. Résultats mis en cache `SERVICES_CACHE_SECONDS`.
"""
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import docker
import requests
from flask import Flask, g, jsonify, request
from flask_cors import CORS

import lights
from auth import AuthError, KeycloakVerifier, bearer_from_header

try:
    from version_endpoint import register_version_route
except ImportError:  # pragma: no cover
    register_version_route = None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("services-api")

KEYCLOAK_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "supervision-si")
JWKS_URL = os.environ.get("SERVICES_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (KEYCLOAK_INTERNAL_URL, KEYCLOAK_REALM)
ADMIN_USERS = [u for u in os.environ.get("SERVICES_ADMIN_USERS", "freg").split(",") if u.strip()]
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "supervision-si")
HTTP_TIMEOUT = float(os.environ.get("SERVICES_HTTP_TIMEOUT", "4"))
CACHE_SECONDS = int(os.environ.get("SERVICES_CACHE_SECONDS", "20"))
EXPECTED_AZP = os.environ.get("SERVICES_EXPECTED_AZP") or None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "services-api")

verifier = KeycloakVerifier(JWKS_URL, ADMIN_USERS, expected_azp=EXPECTED_AZP)
_client = None
_cache = {"at": 0, "rows": None}
_lock = threading.Lock()


def docker_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


app.docker_client = docker_client  # remplaçable dans les tests


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
    try:
        app.docker_client().ping()
        dock = True
    except Exception:  # noqa: BLE001
        dock = False
    return jsonify({"status": "ok" if dock else "degraded", "docker": dock, "project": PROJECT, "admin_users": ADMIN_USERS}), 200


# -- inventaire et santé ---------------------------------------------------
def _http_probe(host, port):
    """GET http://host:port/health puis / -> {code, ms, content, status} ou {error}."""
    last = None
    for path in ("/health", "/"):
        t0 = time.time()
        try:
            r = requests.get("http://%s:%d%s" % (host, port, path), timeout=HTTP_TIMEOUT, allow_redirects=False)
        except requests.exceptions.ConnectionError:
            return {"error": "connexion refusée"}
        except requests.exceptions.Timeout:
            return {"error": "délai dépassé (%.0f s)" % HTTP_TIMEOUT}
        except requests.exceptions.RequestException as exc:
            return {"error": str(exc)[:120]}
        ms = int((time.time() - t0) * 1000)
        ctype = (r.headers.get("content-type") or "").lower()
        out = {"code": r.status_code, "ms": ms, "path": path,
               "content": "json" if "json" in ctype else "html" if "html" in ctype else "other"}
        if out["content"] == "json":
            try:
                body = r.json()
                if isinstance(body, dict):
                    out["status"] = body.get("status") or body.get("state")
            except ValueError:
                pass
        if r.status_code != 404:
            return out
        last = out
    return last


def _row(c):
    attrs = c.attrs or {}
    labels = (attrs.get("Config") or {}).get("Labels") or {}
    service = lights.service_of(labels, c.name)
    state = (attrs.get("State") or {})
    health = ((state.get("Health") or {}).get("Status")) or None
    port = lights.exposed_port(attrs)
    http = None
    if c.status == "running" and port:
        http = _http_probe(c.name, port)
    light, text = lights.classify(c.status, health, http, port)
    return {
        "service": service, "container": c.name, "id": c.id[:12], "status": c.status, "docker_health": health,
        "started_at": state.get("StartedAt"), "restart_count": attrs.get("RestartCount", 0),
        "port": port, "http": http, "kind": lights.guess_kind(service, port, http),
        "light": light, "text": text, "protected": service in lights.PROTECTED,
        "image": (c.image.tags[0] if c.image.tags else "") if c.image else "",
    }


def _project_containers():
    return [c for c in app.docker_client().containers.list(all=True) if lights.project_of((c.attrs.get("Config") or {}).get("Labels")) == PROJECT]


def inventory(force=False):
    with _lock:
        if not force and _cache["rows"] is not None and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["rows"], _cache["at"]
        containers = _project_containers()
        with ThreadPoolExecutor(max_workers=12) as pool:
            rows = list(pool.map(_row, containers))
        rows.sort(key=lambda r: ({"red": 0, "orange": 1, "grey": 2, "green": 3}[r["light"]], r["service"]))
        _cache["rows"], _cache["at"] = rows, time.time()
        return rows, _cache["at"]


@app.route("/services", methods=["GET"])
def services():
    force = request.args.get("refresh") in ("1", "true")
    try:
        rows, at = inventory(force=force)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "Docker injoignable : %s" % exc}), 503
    return jsonify({"project": PROJECT, "at": at, "cache_seconds": CACHE_SECONDS, "summary": lights.summarize(rows),
                    "protected": list(lights.PROTECTED), "services": rows}), 200


def _find(service):
    for c in _project_containers():
        if lights.service_of((c.attrs.get("Config") or {}).get("Labels"), c.name) == service or c.name == service:
            return c
    return None


@app.route("/services/<service>/restart", methods=["POST"])
def restart(service):
    c = _find(service)
    if c is None:
        return jsonify({"error": "service « %s » introuvable dans le projet %s" % (service, PROJECT)}), 404
    action = "restart" if c.status == "running" else "start"
    try:
        c.restart(timeout=30) if action == "restart" else c.start()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    _log.warning("%s : %s (%s) par %s", PROJECT, service, action, g.user["username"])
    with _lock:
        _cache["rows"] = None
    return jsonify({"status": "ok", "service": service, "action": action}), 200


@app.route("/services/restart-red", methods=["POST"])
def restart_red():
    try:
        rows, _ = inventory(force=True)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "Docker injoignable : %s" % exc}), 503
    done, skipped, errors = [], [], {}
    for r in rows:
        if r["light"] != "red":
            continue
        if r["protected"]:
            skipped.append(r["service"])
            continue
        c = _find(r["service"])
        try:
            if c is None:
                raise RuntimeError("introuvable")
            c.restart(timeout=30) if c.status == "running" else c.start()
            done.append(r["service"])
        except Exception as exc:  # noqa: BLE001
            errors[r["service"]] = str(exc)
    _log.warning("%s : redémarrage des rouges par %s -> %s (ignorés : %s)", PROJECT, g.user["username"], done, skipped)
    with _lock:
        _cache["rows"] = None
    return jsonify({"status": "ok", "restarted": done, "skipped_protected": skipped, "errors": errors}), 200


@app.route("/services/<service>/logs", methods=["GET"])
def logs(service):
    c = _find(service)
    if c is None:
        return jsonify({"error": "service introuvable"}), 404
    try:
        tail = max(10, min(500, int(request.args.get("tail", "80"))))
    except ValueError:
        tail = 80
    try:
        text = c.logs(tail=tail, timestamps=True).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"service": service, "tail": tail, "lines": text.splitlines()[-tail:]}), 200


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=5000)
