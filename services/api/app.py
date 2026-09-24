# -*- coding: utf-8 -*-
"""services-api (livraison #584) -- « Services du hub » : feu tricolore et
redémarrage de tous les conteneurs du projet, pour la sous-tuile de
Paramétrage. #586 : « tour de contrôle » -- registres JSON éditables et
importables, import d'une livraison (zip) avec plan de reconstruction
calculé et exécuté par un conteneur « runner » détaché, auto-réparation
des services rouges, journal (voir tower.py et services/README.md).

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
import hashlib
import json
import logging
import os
import secrets
import socket
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import docker
import requests
from flask import Flask, g, jsonify, request
from flask_cors import CORS

import lights
import tower
try:
    from notify_client import notify as _notify, register_actions as _register_actions  # #590
except ImportError:  # tests hors conteneur
    def _notify(*a, **k):
        return None

    def _register_actions(*a, **k):
        return None

_register_actions([
    {"id": "tower.delivery.applied", "label": "Livraison appliquée", "severity": "info"},
    {"id": "tower.job.failed", "label": "Job de reconstruction en échec", "severity": "critical"},
    {"id": "tower.job.done", "label": "Job terminé", "severity": "info"},
    {"id": "tower.heal.restart", "label": "Service relancé automatiquement", "severity": "warning"},
    {"id": "tower.heal.gave-up", "label": "Auto-réparation : abandon (intervention requise)", "severity": "critical"},
    {"id": "tower.service.restart", "label": "Service redémarré à la main", "severity": "info"},
    {"id": "tower.config", "label": "Configuration (registre) modifiée", "severity": "info"},
    {"id": "tower.host.disk", "label": "Espace disque de l'hôte du hub", "severity": "critical"},
    {"id": "tower.host.load", "label": "Charge / mémoire de l'hôte du hub", "severity": "warning"},
    {"id": "tower.host.prune", "label": "Nettoyage Docker effectué", "severity": "info"},
])
HOST_ROOT = os.environ.get("SERVICES_HOST_ROOT", "/host")  # #593 : racine de l'hôte montée en lecture seule
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
# #589 : groupes Keycloak admis (droits gérés dans le hub, tuile Comptes et groupes) -- défaut : administrateurs
ADMIN_GROUPS = [g.strip() for g in os.environ.get("SERVICES_ADMIN_GROUPS", "administrateurs").split(",") if g.strip()]
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "supervision-si")
HTTP_TIMEOUT = float(os.environ.get("SERVICES_HTTP_TIMEOUT", "4"))
CACHE_SECONDS = int(os.environ.get("SERVICES_CACHE_SECONDS", "20"))
EXPECTED_AZP = os.environ.get("SERVICES_EXPECTED_AZP") or None
# #586 : autres projets compose surveillés (la passerelle : tls-proxy, keycloak)
EXTRA_PROJECTS = [p.strip() for p in os.environ.get("SERVICES_EXTRA_PROJECTS", "supervision-si-gateway").split(",") if p.strip()]
# #586 : le dépôt, monté AU MÊME CHEMIN que sur l'hôte (les chemins relatifs
# de docker-compose.yml se résolvent alors pareil dans le runner).
PROJECT_DIR = (os.environ.get("SERVICES_PROJECT_DIR") or "").rstrip("/")
HOST_IP = os.environ.get("SERVICES_HOST_IP") or ""
DATA_DIR = os.path.join(PROJECT_DIR, "services", "data") if PROJECT_DIR else ""
HEAL_INTERVAL = int(os.environ.get("SERVICES_HEAL_INTERVAL", "60"))
MAX_ZIP_BYTES = int(os.environ.get("SERVICES_MAX_ZIP_MB", "1500")) * 1024 * 1024
DEFAULT_SETTINGS = {"auto_heal": True, "auto_apply": True, "heal_threshold": 3, "heal_max_per_hour": 3, "ignored": []}

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "services-api")

verifier = KeycloakVerifier(JWKS_URL, ADMIN_USERS, expected_azp=EXPECTED_AZP, allowed_groups=ADMIN_GROUPS, what="la tour de contrôle")
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
PUBLIC = ("/health", "/version", "/host/public")


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
    return jsonify({"status": "ok" if dock else "degraded", "docker": dock, "project": PROJECT, "admin_users": ADMIN_USERS, "admin_groups": ADMIN_GROUPS}), 200


# -- inventaire et santé ---------------------------------------------------
def _tcp_open(host, port):
    """-> (ouvert, raison). #588 : distingue un port fermé (refus) d'un port
    ouvert qui ne parle pas HTTP (Postgres, MySQL, relais TLS...)."""
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=HTTP_TIMEOUT):
            return True, int((time.time() - t0) * 1000)
    except ConnectionRefusedError:
        return False, "connexion refusée"
    except socket.timeout:
        return False, "délai dépassé (%.0f s)" % HTTP_TIMEOUT
    except OSError as exc:
        return False, str(exc)[:80]


def _http_probe(host, port):
    """TCP puis GET http://host:port/health puis / -> {code, ms, content, status},
    {tcp_only, ms} (port ouvert, pas HTTP) ou {error}."""
    ok, info = _tcp_open(host, port)
    if not ok:
        return {"error": info}
    last = None
    for path in ("/health", "/"):
        t0 = time.time()
        try:
            r = requests.get("http://%s:%d%s" % (host, port, path), timeout=HTTP_TIMEOUT, allow_redirects=False)
        except requests.exceptions.ConnectionError:
            return {"tcp_only": True, "ms": info}  # connexion acceptée puis fermée / protocole non HTTP
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
    hard = lights.hard_red(c.status, health)  # #588 : seule une panne dure déclenche l'auto-réparation
    ignored = service in (_settings().get("ignored") or [])
    if ignored:
        light, text = "grey", "non surveillé (%s) -- réglage « Automatismes »" % text
    return {
        "ignored": ignored, "project": labels.get("com.docker.compose.project"), "hard": hard,
        "service": service, "container": c.name, "id": c.id[:12], "status": c.status, "docker_health": health,
        "started_at": state.get("StartedAt"), "restart_count": attrs.get("RestartCount", 0),
        "port": port, "http": http, "kind": lights.guess_kind(service, port, http),
        "light": light, "text": text, "protected": service in lights.PROTECTED,
        "image": (c.image.tags[0] if c.image.tags else "") if c.image else "",
    }


def _project_containers(projects=None):
    wanted = set(projects or [PROJECT] + EXTRA_PROJECTS)
    return [c for c in app.docker_client().containers.list(all=True) if lights.project_of((c.attrs.get("Config") or {}).get("Labels")) in wanted]


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
    _notify("tower.service.restart", "%s : %s par %s" % (service, action, g.user["username"]), "Tour de contrôle : conteneur %s (%s)." % (service, action), {"service": service, "user": g.user["username"]})
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



# =============================================================================
# #586 -- tour de contrôle
# =============================================================================
def _need_project():
    if not PROJECT_DIR or not os.path.isdir(PROJECT_DIR):
        return jsonify({"error": "dépôt non monté dans services-api (SERVICES_PROJECT_DIR) : redéployer avec le docker-compose.yml de #586"}), 503
    return None


def _owner():
    try:
        st = os.stat(PROJECT_DIR)
        return st.st_uid, st.st_gid
    except OSError:
        return None


def _write(rel, data, mode=None):
    """Écriture atomique dans le dépôt, propriétaire = celui du dépôt."""
    path = os.path.join(PROJECT_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp-%s" % (path, secrets.token_hex(3))
    with open(tmp, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    if mode:
        os.chmod(tmp, mode)
    own = _owner()
    if own:
        try:
            os.chown(tmp, *own)
        except OSError:
            pass
    os.replace(tmp, path)


def _read(rel):
    try:
        with open(os.path.join(PROJECT_DIR, rel), "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _data(*parts):
    path = os.path.join(DATA_DIR, *parts)
    os.makedirs(os.path.dirname(path) if parts else DATA_DIR, exist_ok=True)
    return path


# -- réglages et journal -------------------------------------------------------
_settings_cache = {"at": 0, "value": None}


def _settings():
    if not DATA_DIR:
        return dict(DEFAULT_SETTINGS)
    if _settings_cache["value"] is not None and time.time() - _settings_cache["at"] < 5:
        return _settings_cache["value"]
    try:
        with open(os.path.join(DATA_DIR, "settings.json"), encoding="utf-8") as fh:
            v = dict(DEFAULT_SETTINGS, **json.load(fh))
    except (OSError, ValueError):
        v = dict(DEFAULT_SETTINGS)
    _settings_cache.update(at=time.time(), value=v)
    return v


def event(kind, text, **extra):
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": kind, "text": text}
    rec.update(extra)
    _log.info("tour : %s -- %s", kind, text)
    action = {"delivery-applied": "tower.delivery.applied", "job-failed": "tower.job.failed", "heal-restart": "tower.heal.restart",
              "heal-gave-up": "tower.heal.gave-up", "config": "tower.config"}.get(kind)
    if action:  # #590 : chaque événement notable part vers notify-api (file, jamais bloquant)
        _notify(action, text, "Tour de contrôle du hub -- %s\n%s" % (kind, json.dumps(extra, ensure_ascii=False)), extra)
    if DATA_DIR:
        try:
            with open(_data("events.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return rec


@app.route("/settings", methods=["GET"])
def get_settings():
    return jsonify(_settings()), 200


@app.route("/settings", methods=["PUT"])
def put_settings():
    err = _need_project()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    cur = _settings()
    new = dict(cur)
    for k in ("auto_heal", "auto_apply"):
        if k in body:
            new[k] = bool(body[k])
    for k, lo, hi in (("heal_threshold", 1, 30), ("heal_max_per_hour", 0, 20)):
        if k in body:
            try:
                new[k] = max(lo, min(hi, int(body[k])))
            except (TypeError, ValueError):
                return jsonify({"error": "%s : entier attendu" % k}), 400
    if "ignored" in body:
        new["ignored"] = sorted({x for x in body.get("ignored") or [] if isinstance(x, str) and tower.SERVICE_RE.match(x)})
    _write(os.path.relpath(_data("settings.json"), PROJECT_DIR), json.dumps(new, indent=2, ensure_ascii=False))
    _settings_cache["value"] = None
    event("settings", "réglages modifiés par %s" % g.user["username"], changes={k: new[k] for k in new if new.get(k) != cur.get(k)})
    with _lock:
        _cache["rows"] = None
    return jsonify(new), 200


@app.route("/events", methods=["GET"])
def events():
    try:
        limit = max(10, min(1000, int(request.args.get("limit", "200"))))
    except ValueError:
        limit = 200
    out = []
    if DATA_DIR and os.path.exists(os.path.join(DATA_DIR, "events.jsonl")):
        with open(os.path.join(DATA_DIR, "events.jsonl"), encoding="utf-8") as fh:
            lines = fh.readlines()[-limit:]
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return jsonify({"events": out}), 200


# -- configurations JSON -------------------------------------------------------
@app.route("/configs", methods=["GET"])
def configs():
    err = _need_project()
    if err:
        return err
    out = []
    for cid, spec in tower.CONFIGS.items():
        local = _read(spec["path"])
        out.append({"id": cid, "label": spec["label"], "path": spec["path"], "example": spec["example"], "consumer": spec["consumer"],
                    "key": spec["key"], "fields": spec["fields"], "local": local is not None})
    return jsonify({"configs": out}), 200


@app.route("/configs/<cid>", methods=["GET"])
def config_get(cid):
    err = _need_project()
    if err:
        return err
    spec = tower.CONFIGS.get(cid)
    if not spec:
        return jsonify({"error": "configuration inconnue"}), 404
    raw, source = _read(spec["path"]), "local"
    if raw is None:
        raw, source = _read(spec["example"]), "exemple"
    try:
        data = json.loads(raw.decode("utf-8")) if raw else {spec["key"]: []}
        items = tower.items_of(cid, data)
    except ValueError as exc:
        return jsonify({"error": "fichier %s illisible : %s" % (spec["path"] if source == "local" else spec["example"], exc)}), 500
    return jsonify({"id": cid, "source": source, "path": spec["path"], "items": items}), 200


@app.route("/configs/<cid>", methods=["PUT"])
def config_put(cid):
    err = _need_project()
    if err:
        return err
    spec = tower.CONFIGS.get(cid)
    if not spec:
        return jsonify({"error": "configuration inconnue"}), 404
    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "JSON attendu"}), 400
    data = body.get("data", body) if isinstance(body, dict) and "data" in body else body
    doc, errors, warnings = tower.validate_config(cid, data)
    if errors:
        return jsonify({"error": "configuration refusée", "errors": errors, "warnings": warnings}), 400
    old = _read(spec["path"])
    if old is not None:
        _write(os.path.relpath(_data("config-history", "%s-%s.json" % (cid, time.strftime("%Y%m%d-%H%M%S"))), PROJECT_DIR), old)
    _write(spec["path"], json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    n = len(doc[spec["key"]])
    event("config", "%s : %d entrée(s) enregistrée(s) par %s" % (spec["label"], n, g.user["username"]), config=cid)
    return jsonify({"status": "ok", "count": n, "warnings": warnings, "path": spec["path"]}), 200


# -- jobs (conteneur runner détaché) --------------------------------------------
def _self_image():
    img = os.environ.get("SERVICES_RUNNER_IMAGE")
    if img:
        return img
    return app.docker_client().containers.get(socket.gethostname()).image.id


def launch_job(kind, label, steps, user, extra=None):
    """Écrit le script, lance un conteneur runner (même image, socket Docker,
    dépôt au même chemin) qui l'exécute et écrit journal + code retour. Le
    runner survit à la reconstruction de services-api elle-même."""
    jid = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
    jobs = os.path.dirname(_data("jobs", "x"))
    script = ["set -uo pipefail", "cd %s" % json.dumps(PROJECT_DIR)]
    if HOST_IP:
        script.append("export HOST_IP=%s" % json.dumps(HOST_IP))
    script.append('echo "tour de contrôle -- job %s (%s) lancé par %s"' % (jid, kind, user))
    for st in steps:
        script.append('echo; echo "▶ %s"; echo "$ %s"' % (st["label"].replace('"', "'"), st["cmd"].replace('"', "'")))
        script.append('%s || { rc=$?; echo "✗ échec (code $rc)"; exit $rc; }' % st["cmd"])
    script.append('echo; echo "✓ terminé"')
    base = os.path.join(jobs, jid)
    _write(os.path.relpath(base + ".sh", PROJECT_DIR), "\n".join(script) + "\n")
    meta = {"id": jid, "kind": kind, "label": label, "steps": steps, "user": user, "at": time.time()}
    meta.update(extra or {})
    _write(os.path.relpath(base + ".json", PROJECT_DIR), json.dumps(meta, ensure_ascii=False, indent=2))
    cmd = "bash %s > %s 2>&1; echo $? > %s" % (json.dumps(base + ".sh"), json.dumps(base + ".log"), json.dumps(base + ".rc"))
    try:
        app.docker_client().containers.run(
            _self_image(), ["bash", "-c", cmd], detach=True, auto_remove=True, working_dir=PROJECT_DIR,
            name="tower-job-%s" % jid, labels={"supervision-si.tower-job": jid},
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}, PROJECT_DIR: {"bind": PROJECT_DIR, "mode": "rw"}},
            environment={"HOST_IP": HOST_IP} if HOST_IP else {})
    except Exception as exc:  # noqa: BLE001
        _write(os.path.relpath(base + ".log", PROJECT_DIR), "runner non lancé : %s\n" % exc)
        _write(os.path.relpath(base + ".rc", PROJECT_DIR), "125\n")
        event("job-failed", "%s : runner non lancé (%s)" % (label, exc), job=jid)
        return meta
    event("job", "%s -- lancé par %s" % (label, user), job=jid, job_kind=kind)
    return meta


def job_status(jid):
    base = os.path.join(DATA_DIR, "jobs", jid)
    try:
        with open(base + ".json", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    rc = None
    try:
        with open(base + ".rc", encoding="utf-8") as fh:
            rc = int(fh.read().strip() or "1")
    except (OSError, ValueError):
        pass
    if rc is not None:
        meta["status"], meta["rc"] = ("done" if rc == 0 else "failed"), rc
    else:
        running = False
        try:
            running = bool(app.docker_client().containers.list(filters={"label": "supervision-si.tower-job=%s" % jid}))
        except Exception:  # noqa: BLE001
            running = True
        meta["status"] = "running" if running else "lost"
    return meta


@app.route("/jobs", methods=["GET"])
def jobs_list():
    if not DATA_DIR or not os.path.isdir(os.path.join(DATA_DIR, "jobs")):
        return jsonify({"jobs": []}), 200
    ids = sorted({f.rsplit(".", 1)[0] for f in os.listdir(os.path.join(DATA_DIR, "jobs")) if f.endswith(".json")}, reverse=True)[:30]
    return jsonify({"jobs": [j for j in (job_status(i) for i in ids) if j]}), 200


@app.route("/jobs/<jid>", methods=["GET"])
def job_get(jid):
    if not tower.re.match(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$", jid):
        return jsonify({"error": "job inconnu"}), 404
    meta = job_status(jid)
    if not meta:
        return jsonify({"error": "job inconnu"}), 404
    try:
        with open(os.path.join(DATA_DIR, "jobs", jid + ".log"), encoding="utf-8", errors="replace") as fh:
            meta["log"] = fh.read().splitlines()[-600:]
    except OSError:
        meta["log"] = []
    return jsonify(meta), 200


def _running_main():
    return sorted({lights.service_of((c.attrs.get("Config") or {}).get("Labels"), c.name)
                   for c in _project_containers([PROJECT]) if c.status == "running"})


@app.route("/services/<service>/rebuild", methods=["POST"])
def rebuild(service):
    err = _need_project()
    if err:
        return err
    if service == "tls-proxy":
        steps = tower.GATEWAY_RELOAD
    else:
        if service not in _running_main() and _find(service) is None:
            return jsonify({"error": "service « %s » inconnu" % service}), 404
        steps = tower.rebuild_steps([service])
    if not steps:
        return jsonify({"error": "nom de service invalide"}), 400
    return jsonify(launch_job("rebuild", "reconstruction de %s" % service, steps, g.user["username"])), 200


@app.route("/gateway/reload", methods=["POST"])
def gateway_reload():
    err = _need_project()
    if err:
        return err
    return jsonify(launch_job("gateway", "rechargement de la passerelle", tower.GATEWAY_RELOAD, g.user["username"])), 200


# -- livraisons ----------------------------------------------------------------
def _compose_paths():
    import yaml  # dépendance de la tour seulement
    raw = _read("docker-compose.yml")
    services = (yaml.safe_load(raw.decode("utf-8")) or {}).get("services") or {} if raw else {}

    def read_file(rel):
        b = _read(rel)
        return b.decode("utf-8", "replace") if b else None
    return tower.service_paths(services, "", read_file)


def _sha(b):
    return hashlib.sha1(b).hexdigest()


def analyze_zip(path):
    with zipfile.ZipFile(path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > 60000 or sum(i.file_size for i in infos) > 3 * MAX_ZIP_BYTES:
            raise ValueError("archive trop volumineuse")
        prefix = tower.strip_prefix([i.filename for i in infos])
        buckets = {"added": [], "changed": [], "unchanged": 0, "protected": [], "kept": [], "unsafe": []}
        number = None
        for i in infos:
            rel = tower.safe_member(i.filename, prefix)
            if rel is None:
                buckets["unsafe"].append(i.filename)
                continue
            data = zf.read(i)
            if rel == "shared/DELIVERY_NUMBER":
                number = data.decode("utf-8", "replace").strip()
            local = _read(rel)
            kind = tower.classify(rel, _sha(data), _sha(local) if local is not None else None)
            if kind == "unchanged":
                buckets["unchanged"] += 1
            else:
                buckets[kind].append(rel)
    return prefix, number, buckets


@app.route("/deliveries", methods=["GET"])
def deliveries():
    cur = (_read("shared/DELIVERY_NUMBER") or b"").decode().strip() if PROJECT_DIR else ""
    out = []
    inc = os.path.join(DATA_DIR, "incoming") if DATA_DIR else ""
    if inc and os.path.isdir(inc):
        for f in sorted(os.listdir(inc), reverse=True):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(inc, f), encoding="utf-8") as fh:
                        out.append(json.load(fh))
                except (OSError, ValueError):
                    pass
    return jsonify({"current": cur, "project_dir": PROJECT_DIR, "deliveries": out[:10]}), 200


@app.route("/deliveries", methods=["POST"])
def delivery_upload():
    err = _need_project()
    if err:
        return err
    f = request.files.get("file")
    if not f or not (f.filename or "").lower().endswith(".zip"):
        return jsonify({"error": "fichier .zip attendu (champ « file »)"}), 400
    did = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
    zpath = _data("incoming", did + ".zip")
    f.save(zpath)
    if os.path.getsize(zpath) > MAX_ZIP_BYTES:
        os.remove(zpath)
        return jsonify({"error": "archive trop volumineuse"}), 413
    try:
        prefix, number, b = analyze_zip(zpath)
    except (zipfile.BadZipFile, ValueError) as exc:
        os.remove(zpath)
        return jsonify({"error": "archive refusée : %s" % exc}), 400
    current = (_read("shared/DELIVERY_NUMBER") or b"").decode().strip()
    try:
        plan = tower.plan_for_changes(b["changed"] + b["added"], _compose_paths(), _running_main())
    except Exception as exc:  # noqa: BLE001
        plan = {"steps": [], "error": "plan non calculé : %s" % exc}
    rec = {"id": did, "name": f.filename, "at": time.time(), "user": g.user["username"], "number": number, "current": current,
           "downgrade": bool(number and current and number.isdigit() and current.isdigit() and int(number) < int(current)),
           "prefix": prefix, "added": b["added"], "changed": b["changed"], "unchanged": b["unchanged"], "protected": b["protected"],
           "kept": b["kept"], "unsafe": b["unsafe"], "plan": plan, "applied": False}
    _write(os.path.relpath(_data("incoming", did + ".json"), PROJECT_DIR), json.dumps(rec, ensure_ascii=False, indent=1))
    event("delivery-analyzed", "livraison %s (%s → %s) : %d modifié(s), %d ajouté(s)" % (f.filename, current or "?", number or "?", len(b["changed"]), len(b["added"])), delivery=did)
    return jsonify(rec), 200


@app.route("/deliveries/<did>/apply", methods=["POST"])
def delivery_apply(did):
    err = _need_project()
    if err:
        return err
    if not tower.re.match(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$", did):
        return jsonify({"error": "livraison inconnue"}), 404
    meta_path, zpath = _data("incoming", did + ".json"), _data("incoming", did + ".zip")
    try:
        with open(meta_path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return jsonify({"error": "livraison inconnue"}), 404
    body = request.get_json(silent=True) or {}
    if rec.get("applied"):
        return jsonify({"error": "livraison déjà appliquée"}), 409
    if rec.get("downgrade") and not body.get("allow_downgrade"):
        return jsonify({"error": "livraison plus ancienne que la version en place (%s < %s) : confirmer le retour arrière" % (rec.get("number"), rec.get("current"))}), 409
    todo = set(rec["changed"]) | set(rec["added"])
    written = 0
    with zipfile.ZipFile(zpath) as zf:
        for i in zf.infolist():
            rel = tower.safe_member(i.filename, rec.get("prefix") or "")
            if rel in todo:
                mode = (i.external_attr >> 16) & 0o777
                _write(rel, zf.read(i), mode or None)
                written += 1
    try:
        plan = tower.plan_for_changes(sorted(todo), _compose_paths(), _running_main())
    except Exception as exc:  # noqa: BLE001
        plan = {"steps": [], "error": "plan non calculé : %s" % exc}
    rec.update(applied=True, applied_at=time.time(), applied_by=g.user["username"], written=written, plan=plan)
    job = None
    if plan.get("steps"):
        job = launch_job("delivery", "livraison %s" % (rec.get("number") or rec["name"]), plan["steps"], g.user["username"], {"delivery": did})
        rec["job"] = job["id"]
    _write(os.path.relpath(meta_path, PROJECT_DIR), json.dumps(rec, ensure_ascii=False, indent=1))
    try:
        os.remove(zpath)
    except OSError:
        pass
    event("delivery-applied", "livraison %s appliquée par %s : %d fichier(s) écrit(s), %d étape(s)" % (rec.get("number") or rec["name"], g.user["username"], written, len(plan.get("steps") or [])), delivery=did)
    return jsonify(rec), 200


# -- auto-réparation -----------------------------------------------------------
_heal_state = {}


def heal_once(now=None):
    st = _settings()
    if not st.get("auto_heal"):
        return []
    rows, _ = inventory(force=True)
    global _heal_state
    todo, _heal_state, evs = tower.heal_decide(_heal_state, rows, now or time.time(), st.get("heal_threshold", 3), st.get("heal_max_per_hour", 3), st.get("ignored"))
    for e in evs:
        event(e["event"], "%s : %s" % (e["service"], e.get("text") or ""), service=e["service"])
    for svc in todo:
        c = _find(svc)
        try:
            c.restart(timeout=30) if c.status == "running" else c.start()
        except Exception as exc:  # noqa: BLE001
            event("heal-error", "%s : %s" % (svc, exc), service=svc)
    if todo:
        with _lock:
            _cache["rows"] = None
    return todo


def check_jobs():
    """#590 : un job terminé (fichier .rc écrit par le runner) est notifié une
    fois (marqueur .notified) -- échec = critique."""
    jobs = os.path.join(DATA_DIR, "jobs") if DATA_DIR else ""
    if not jobs or not os.path.isdir(jobs):
        return []
    out = []
    for f in sorted(os.listdir(jobs)):
        if not f.endswith(".rc") or os.path.exists(os.path.join(jobs, f[:-3] + ".notified")):
            continue
        jid = f[:-3]
        meta = job_status(jid) or {"label": jid}
        rc = meta.get("rc", 1)
        try:
            with open(os.path.join(jobs, jid + ".log"), encoding="utf-8", errors="replace") as fh:
                tail = "\n".join(fh.read().splitlines()[-25:])
        except OSError:
            tail = ""
        event("job-failed" if rc else "job-done", "%s : %s (code %s)" % (meta.get("label"), "échec" if rc else "terminé", rc), job=jid)
        if not rc:
            _notify("tower.job.done", "%s : terminé" % meta.get("label"), tail, {"job": jid})
        try:
            with open(os.path.join(jobs, jid + ".notified"), "w") as fh:
                fh.write(time.strftime("%Y-%m-%dT%H:%M:%S"))
        except OSError:
            pass
        out.append(jid)
    return out


def _heal_loop():
    while True:
        time.sleep(HEAL_INTERVAL)
        try:
            check_jobs()
            check_host()
            heal_once()
        except Exception as exc:  # noqa: BLE001
            _log.warning("auto-réparation : %s", exc)


if os.environ.get("SERVICES_HEAL_THREAD", "1") == "1":
    threading.Thread(target=_heal_loop, name="auto-heal", daemon=True).start()


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=5000)


# =============================================================================
# #593 -- santé de l'hôte : charge, mémoire, espace disque, Docker
# =============================================================================
_host_cache = {"at": 0, "value": None}
_host_state = {"disk": "green", "load": "green"}
FS_TYPES = ("ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "f2fs", "jfs", "reiserfs", "vfat", "ntfs")


def _mounts():
    """Points de montage réels de l'hôte vus sous HOST_ROOT (bind récursif)."""
    out = []
    try:
        with open("/proc/self/mounts", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                target, fstype = parts[1], parts[2]
                if fstype not in FS_TYPES:
                    continue
                if target == HOST_ROOT or target.startswith(HOST_ROOT + "/"):
                    out.append((target[len(HOST_ROOT):] or "/", target, fstype))
    except OSError:
        pass
    if not out and os.path.isdir(HOST_ROOT):
        out.append(("/", HOST_ROOT, "?"))
    return out


def host_health(force=False):
    if not force and _host_cache["value"] and time.time() - _host_cache["at"] < 30:
        return _host_cache["value"]
    disks = []
    for mount, path, fstype in _mounts():
        try:
            st = os.statvfs(path)
        except OSError:
            continue
        total, free = st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
        if total <= 0:
            continue
        used = total - st.f_bfree * st.f_frsize
        disks.append({"mount": mount, "fstype": fstype, "total": total, "used": used, "free": free, "pct": int(round(100.0 * used / total))})
    disks.sort(key=lambda d: d["mount"])
    load, cpus, mem_pct, mem = [], os.cpu_count() or 1, None, {}
    try:
        with open("/proc/loadavg") as fh:
            load = [float(x) for x in fh.read().split()[:3]]
    except (OSError, ValueError):
        pass
    try:
        info = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                info[k] = int(v.split()[0]) * 1024
        mem = {"total": info.get("MemTotal", 0), "available": info.get("MemAvailable", 0)}
        if mem["total"]:
            mem_pct = int(round(100.0 * (mem["total"] - mem["available"]) / mem["total"]))
    except (OSError, ValueError):
        pass
    docker_df = {}
    try:
        df = app.docker_client().df()
        def _sum(key, size="Size"):
            items = df.get(key) or []
            return sum(int(i.get(size) or 0) for i in items)
        images = df.get("Images") or []
        unused = [i for i in images if not i.get("Containers")]
        docker_df = {"images": _sum("Images"), "images_unused": sum(int(i.get("Size") or 0) for i in unused), "images_count": len(images), "images_unused_count": len(unused),
                     "containers": _sum("Containers", "SizeRw"), "volumes": sum(int(((v.get("UsageData") or {}).get("Size")) or 0) for v in (df.get("Volumes") or [])),
                     "build_cache": sum(int(b.get("Size") or 0) for b in (df.get("BuildCache") or []) if not b.get("InUse"))}
    except Exception as exc:  # noqa: BLE001
        docker_df = {"error": str(exc)[:120]}
    summary = lights.host_summary(disks, load, cpus, mem_pct)
    out = {"at": time.time(), "disks": disks, "load": load, "cpus": cpus, "mem": dict(mem, pct=mem_pct), "docker": docker_df,
           "light": summary["light"], "text": summary["text"], "problems": summary["problems"], "root_mounted": os.path.isdir(HOST_ROOT)}
    _host_cache.update(at=time.time(), value=out)
    return out


@app.route("/host", methods=["GET"])
def host():
    return jsonify(host_health(force=request.args.get("refresh") in ("1", "true"))), 200


@app.route("/host/public", methods=["GET"])
def host_public():
    """Bandeau d'alerte du hub (#593) : lampe et texte seulement, sans détail
    ni chiffres -- visible par tout utilisateur connecté au hub."""
    h = host_health()
    return jsonify({"light": h["light"], "text": h["text"] if h["light"] != "green" else "", "at": h["at"]}), 200


@app.route("/host/prune", methods=["POST"])
def host_prune():
    """Nettoyage Docker : images non utilisées par un conteneur, cache de
    build, conteneurs arrêtés HORS projet compose (jamais les volumes)."""
    body = request.get_json(silent=True) or {}
    freed, done = 0, {}
    cli = app.docker_client()
    try:
        if body.get("images", True):
            r = cli.images.prune(filters={"dangling": False})
            done["images"] = len(r.get("ImagesDeleted") or [])
            freed += int(r.get("SpaceReclaimed") or 0)
        if body.get("build_cache", True):
            r = cli.api.prune_builds()
            done["build_cache"] = len(r.get("CachesDeleted") or [])
            freed += int(r.get("SpaceReclaimed") or 0)
        if body.get("containers", False):
            r = cli.containers.prune()
            done["containers"] = len(r.get("ContainersDeleted") or [])
            freed += int(r.get("SpaceReclaimed") or 0)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)[:200], "done": done, "freed": freed}), 500
    _host_cache["value"] = None
    event("host-prune", "nettoyage Docker par %s : %s libérés (%s)" % (g.user["username"], lights.human(freed), done))
    _notify("tower.host.prune", "nettoyage Docker : %s libérés" % lights.human(freed), "Par %s -- %s" % (g.user["username"], done), {"freed": freed, "done": done})
    return jsonify({"status": "ok", "freed": freed, "freed_text": lights.human(freed), "done": done, "host": host_health(force=True)}), 200


def check_host():
    """Fil de surveillance (#593) : événement + notification à chaque changement d'état (jamais répété)."""
    h = host_health(force=True)
    order = {"green": 0, "orange": 1, "red": 2}
    disk = max((d["light"] for d in h["disks"]), key=lambda x: order[x], default="green")
    other = "green"
    if h["load"]:
        other = lights.load_light(h["load"][0], h["load"][1], h["cpus"])
    if h["mem"].get("pct") is not None:
        other = max(other, lights.mem_light(h["mem"]["pct"]), key=lambda x: order[x])
    changes = []
    for key, new, action in (("disk", disk, "tower.host.disk"), ("load", other, "tower.host.load")):
        old = _host_state.get(key, "green")
        if new != old:
            _host_state[key] = new
            text = h["text"] if new != "green" else "retour à la normale (%s)" % key
            event("host-" + new, "%s : %s" % (key, text))
            if new == "red" or (new == "orange" and old == "green") or (new == "green" and old == "red"):
                _notify(action, "hôte du hub : %s" % text, "Détail : %s" % json.dumps({k: h[k] for k in ("disks", "load", "cpus", "mem")}, ensure_ascii=False, default=str)[:3000],
                        {"state": new}, severity="critical" if new == "red" else "warning" if new == "orange" else "info")
            changes.append((key, old, new))
    return changes
