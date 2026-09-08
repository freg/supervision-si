"""si-agent-api -- central des agents hôtes Linux (livraison #421,
backlog 63). Deux faces :

  - face TABLEAU DE BORD (hub, non signée, même niveau de confiance que
    les autres API de module : LAN + passerelle) : flotte, enrôlement,
    catalogue de plugins, affectations, commandes, mesures, risques ;
  - face AGENTS (signée HMAC, préfixe /api/v1, contrat décrit dans
    si-agent/README.md) : configuration, commandes + acquittement, dépôt
    des mesures.

Le protocole et la validation/signature des plugins sont des COPIES de
si-agent/agent/si_agent/{protocol,plugins}.py (voir Dockerfile) -- jamais
une seconde implémentation ici.
"""
import logging
import os
import re
import shlex
import threading
import time

import requests

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

try:
    import si_agent_protocol as protocol
    import si_agent_control as control
except ImportError:  # dépôt de développement
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import control, protocol  # noqa: E402
    import si_agent.plugins as _plugins  # noqa: E402
    _sys.modules.setdefault("si_agent_plugins", _plugins)
    _sys.modules.setdefault("si_agent_control", control)

import store  # noqa: E402
import notify  # noqa: E402

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    make_shared_log_handler = read_shared_log_buffer = _MemcacheClient = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "si-agent-api")

_log = logging.getLogger("si_agent_api")
# Verbosité (#422) : SI_AGENT_LOG_LEVEL=DEBUG trace chaque requête de la face
# agents (identifiant, chemin, statut, durée) et chaque action du tableau
# de bord ; les refus d'authentification sont TOUJOURS journalisés (WARNING)
# et deviennent des événements.
logging.basicConfig(level=getattr(logging, os.environ.get("SI_AGENT_LOG_LEVEL", "INFO").upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = os.environ.get("SI_AGENT_DB_PATH", "/data/si-agent.db")
OFFLINE_AFTER_SECONDS = int(os.environ.get("SI_AGENT_OFFLINE_SECONDS", "300"))
RETENTION_DAYS = int(os.environ.get("SI_AGENT_RETENTION_DAYS", "90"))
PUBLIC_URL = os.environ.get("SI_AGENT_PUBLIC_URL", "").rstrip("/")
CA_FILE = os.environ.get("SI_AGENT_CA_FILE", "/ca/ca.crt")
EVENTS_RETENTION_DAYS = int(os.environ.get("SI_AGENT_EVENTS_RETENTION_DAYS", "365"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))
SERVICE_NAME = "si-agent-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

store.ensure_schema(DB_PATH)


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


if make_shared_log_handler and _MemcacheClient:
    logging.getLogger().addHandler(make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL))


def _purge_loop():
    while True:
        time.sleep(3600)
        try:
            n = store.purge_measurements(DB_PATH, RETENTION_DAYS)
            if n:
                _log.info("purge : %d mesure(s) au-delà de %d jours", n, RETENTION_DAYS)
            n = store.purge_events(DB_PATH, EVENTS_RETENTION_DAYS)
            if n:
                _log.info("purge : %d événement(s) au-delà de %d jours", n, EVENTS_RETENTION_DAYS)
        except Exception as exc:  # noqa: BLE001
            _log.warning("purge impossible : %s", exc)


def _event(kind, severity, message, agent_id=None, details=None, source="central"):
    """Journalise (base + traces) et notifie si la sévérité le mérite."""
    ev = store.add_event(DB_PATH, kind, severity, message, agent_id=agent_id, details=details, source=source)
    if ev:
        notify.dispatch(DB_PATH, ev)
    return ev


def watchdog_tick():
    """Transitions en ligne / hors ligne -> événements (et notifications)."""
    for agent_id, state in store.online_transitions(DB_PATH, OFFLINE_AFTER_SECONDS):
        _event("agent-offline" if state == "offline" else "agent-online", "warning" if state == "offline" else "info",
               "agent %s %s" % (agent_id, "ne répond plus (hors ligne)" if state == "offline" else "de nouveau en ligne"), agent_id=agent_id)


def _watchdog_loop():
    while True:
        time.sleep(30)
        try:
            watchdog_tick()
        except Exception as exc:  # noqa: BLE001
            _log.warning("chien de garde : %s", exc)


if os.environ.get("SI_AGENT_PURGE_THREAD", "1") == "1":
    threading.Thread(target=_purge_loop, daemon=True).start()
    threading.Thread(target=_watchdog_loop, daemon=True).start()


# ============================================================
# Face tableau de bord
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME}), 200


@app.route("/status", methods=["GET"])
def status_route():
    agents = store.fleet(DB_PATH, offline_after_seconds=OFFLINE_AFTER_SECONDS)
    counts = {"online": 0, "offline": 0, "never": 0}
    risk_counts = {"critical": 0, "warning": 0, "info": 0}
    for a in agents:
        counts[a["online"]] = counts.get(a["online"], 0) + 1
        for k, v in (a.get("risks") or {}).get("counts", {}).items():
            risk_counts[k] = risk_counts.get(k, 0) + (v or 0)
    fb = store.fleet_block(DB_PATH)
    return jsonify({"agents": len(agents), "contact": counts, "risks": risk_counts,
                    "plugins": len(store.list_plugins(DB_PATH)), "offline_after_seconds": OFFLINE_AFTER_SECONDS,
                    "retention_days": RETENTION_DAYS, "public_url": PUBLIC_URL or None,
                    "fleet_blocked": bool(fb.get("blocked")), "fleet_block_reason": fb.get("reason"), "fleet_blocked_at": fb.get("at"),
                    "agents_blocked": sum(1 for a in agents if a["blocked"]),
                    "insecure_agents": [a["agent_id"] for a in agents if a.get("insecure_tls")],
                    "ca": _ca_info(), "notifications": notify.describe(),
                    "log_level": logging.getLevelName(logging.getLogger().level)}), 200


def _ca_info():
    try:
        with open(CA_FILE, "rb") as fh:
            pem = fh.read()
        import ssl as _ssl
        import hashlib as _hashlib
        der = _ssl.PEM_cert_to_DER_cert(pem.decode("utf-8"))
        return {"available": True, "sha256": _hashlib.sha256(der).hexdigest(), "path": CA_FILE}
    except (OSError, ValueError):
        return {"available": False, "sha256": None, "path": CA_FILE}


@app.route("/ca", methods=["GET"])
def ca_route():
    """Certificat de l'autorité interne (PEM) pour l'amorçage TLS des agents
    (install.sh --ca-fingerprint) : public par nature, l'EMPREINTE affichée
    dans la tuile fait foi côté hôte."""
    try:
        with open(CA_FILE, "rb") as fh:
            pem = fh.read()
    except OSError:
        return jsonify({"error": "certificat de l'autorité indisponible (SI_AGENT_CA_FILE)"}), 404
    return pem, 200, {"Content-Type": "application/x-pem-file"}


@app.route("/fleet", methods=["GET"])
def fleet_route():
    return jsonify({"agents": store.fleet(DB_PATH, site=request.args.get("site"), offline_after_seconds=OFFLINE_AFTER_SECONDS)}), 200


@app.route("/netview", methods=["GET"])
def netview_route():
    """#432 : vue réseau passive de chaque agent (dernière mesure netview)."""
    return jsonify({"netviews": store.latest_netviews(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/risks", methods=["GET"])
def risks_route():
    return jsonify({"risks": store.fleet_risks(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/agents", methods=["GET"])
def list_agents_route():
    return jsonify({"agents": store.list_agents(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/agents", methods=["POST"])
def create_agent_route():
    body = request.get_json(silent=True) or {}
    try:
        created = store.create_agent(DB_PATH, body.get("agent_id", ""), body.get("site", ""), label=body.get("label"),
                                     host_interval_seconds=body.get("host_interval_seconds"),
                                     risk_thresholds=body.get("risk_thresholds"), notes=body.get("notes"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    created["install_command"] = _install_command(created["agent_id"], created["secret"], created["site"])
    _event("agent-enrolled", "info", "agent %s enrôlé (site %s)" % (created["agent_id"], created["site"]), agent_id=created["agent_id"])
    return jsonify(created), 201


@app.route("/agents/<agent_id>", methods=["GET"])
def get_agent_route(agent_id):
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    a["latest"] = store.latest_per_task(DB_PATH, agent_id)
    a["plugins"] = store.agent_plugins(DB_PATH, agent_id)
    a["commands"] = store.list_commands(DB_PATH, agent_id, limit=20)
    cfg = store.config_for_agent(DB_PATH, agent_id)
    a["config_version"] = cfg["version"] if cfg else None
    a["config_applied"] = bool(cfg and a.get("last_config_version") == cfg["version"])
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["PUT"])
def update_agent_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        a = store.update_agent(DB_PATH, agent_id, label=body.get("label"), active=body.get("active"), site=body.get("site"),
                               host_interval_seconds=body.get("host_interval_seconds"),
                               risk_thresholds=body.get("risk_thresholds"), notes=body.get("notes"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    if body.get("active") is not None:
        _event("agent-activated" if body["active"] else "agent-deactivated", "info" if body["active"] else "warning",
               "agent %s %s" % (agent_id, "réactivé" if body["active"] else "désactivé (requêtes refusées)"), agent_id=agent_id)
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["DELETE"])
def delete_agent_route(agent_id):
    purge = request.args.get("purge", "false").lower() == "true"
    if not store.delete_agent(DB_PATH, agent_id, purge_measurements=purge):
        return jsonify({"error": "agent inconnu"}), 404
    _event("agent-deleted", "warning", "agent %s supprimé" % agent_id, agent_id=agent_id)
    return jsonify({"deleted": agent_id, "measurements_purged": purge}), 200


@app.route("/agents/<agent_id>/rotate-secret", methods=["POST"])
def rotate_secret_route(agent_id):
    a = store.rotate_secret(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    a["install_command"] = _install_command(a["agent_id"], a["secret"], a["site"])
    _event("secret-rotated", "warning", "secret de l'agent %s renouvelé -- réinstallation requise" % agent_id, agent_id=agent_id)
    return jsonify(a), 200


# -- blocage général et individuel (#422) ------------------------------------

def _queue_block_command(agent_id, ctype, params=None):
    """Le blocage est DÉCLARATIF (configuration, relue toutes les 5 min) ET
    IMMÉDIAT (commande relevée toutes les minutes)."""
    try:
        store.create_command(DB_PATH, agent_id, ctype, params or {})
    except ValueError:
        pass


@app.route("/block", methods=["POST"])
def block_fleet_route():
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or "blocage général de la flotte"
    store.set_setting(DB_PATH, "fleet_block", {"blocked": True, "reason": reason, "at": store.now_iso()})
    for a in store.list_agents(DB_PATH):
        _queue_block_command(a["agent_id"], "block_all", {"reason": reason})
    _event("fleet-blocked", "critical", "BLOCAGE GÉNÉRAL des sondes sur toute la flotte : %s" % reason, details={"reason": reason})
    return jsonify(store.fleet_block(DB_PATH)), 200


@app.route("/unblock", methods=["POST"])
def unblock_fleet_route():
    store.set_setting(DB_PATH, "fleet_block", {"blocked": False, "reason": None, "at": None})
    for a in store.list_agents(DB_PATH):
        if not a["blocked"]:
            _queue_block_command(a["agent_id"], "unblock_all")
    _event("fleet-unblocked", "warning", "blocage général levé")
    return jsonify(store.fleet_block(DB_PATH)), 200


@app.route("/agents/<agent_id>/block", methods=["POST"])
def block_agent_route(agent_id):
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or "blocage depuis le tableau de bord"
    if not store.set_agent_blocked(DB_PATH, agent_id, True, reason):
        return jsonify({"error": "agent inconnu"}), 404
    _queue_block_command(agent_id, "block_all", {"reason": reason})
    _event("agent-blocked", "warning", "sondes de l'agent %s bloquées : %s" % (agent_id, reason), agent_id=agent_id)
    return jsonify(store.get_agent(DB_PATH, agent_id)), 200


@app.route("/agents/<agent_id>/unblock", methods=["POST"])
def unblock_agent_route(agent_id):
    if not store.set_agent_blocked(DB_PATH, agent_id, False):
        return jsonify({"error": "agent inconnu"}), 404
    if not store.fleet_block(DB_PATH).get("blocked"):
        _queue_block_command(agent_id, "unblock_all")
    _event("agent-unblocked", "info", "sondes de l'agent %s débloquées" % agent_id, agent_id=agent_id)
    return jsonify(store.get_agent(DB_PATH, agent_id)), 200


# -- journal d'événements (#422) ----------------------------------------------

@app.route("/events", methods=["GET"])
def events_route():
    return jsonify({"events": store.list_events(
        DB_PATH, agent_id=request.args.get("agent"), severity=request.args.get("severity"), kind=request.args.get("kind"),
        since=request.args.get("since"), limit=request.args.get("limit", 200, type=int), min_severity=request.args.get("min_severity"))}), 200


@app.route("/events/summary", methods=["GET"])
def events_summary_route():
    hours = max(1, min(request.args.get("hours", 24, type=int), 24 * 30))
    return jsonify(store.events_summary(DB_PATH, hours=hours, offline_after_seconds=OFFLINE_AFTER_SECONDS)), 200


@app.route("/notifications/test", methods=["POST"])
def notifications_test_route():
    body = request.get_json(silent=True) or {}
    ev = {"id": None, "at": store.now_iso(), "agent_id": None, "site": None, "source": "central", "kind": "notification-test",
          "severity": body.get("severity") or "warning", "message": body.get("message") or "test de notification depuis le hub", "details": {}}
    return jsonify(notify.send_all(ev, force=True)), 200


def _install_command(agent_id, secret, site):
    central = PUBLIC_URL or "https://<VM>:6443/api/si-agent"
    ca = _ca_info()
    tls = (" --ca-fingerprint %s" % ca["sha256"]) if ca.get("sha256") else " --ca /chemin/ca.crt"
    return "sudo ./install.sh --agent %s --secret %s --central %s --site %s%s" % (
        shlex.quote(agent_id), shlex.quote(secret), shlex.quote(central), shlex.quote(site or "default"), tls)


def _install_command_docker(agent_id, secret, site):
    """Variante conteneur (#430, archive si-agent-agent-<version>.tar.gz)."""
    return _install_command(agent_id, secret, site).replace("sudo ./install.sh", "sudo ./docker/deploy-docker.sh", 1)


def _install_command_macos(agent_id, secret, site):
    """Variante macOS (#451, même archive) : install-macos.sh installe un
    LaunchDaemon (compte root, au démarrage)."""
    return _install_command(agent_id, secret, site).replace("sudo ./install.sh", "sudo ./install-macos.sh", 1)


def _ps_quote(s):
    """Guillemets doubles : compris par PowerShell ET par cmd.exe (les
    simples restent littéraux sous cmd) ; l'identifiant, le secret et
    l'URL ne contiennent ni `"` ni `$` (retirés par prudence)."""
    return '"' + re.sub(r'["$`]', "", str(s)) + '"'


def _install_command_windows(agent_id, secret, site):
    """Variante Windows 10/11 (#440, même archive). #446 : passe par
    `powershell -ExecutionPolicy Bypass -File` -- un poste Windows refuse
    les scripts par défaut (politique Restricted) et un double-clic ouvre
    le .ps1 dans le Bloc-notes ; `windows/install.cmd` fait la même chose
    avec élévation automatique en administrateur."""
    central = PUBLIC_URL or "https://<VM>:6443/api/si-agent"
    ca = _ca_info()
    tls = (" -CaFingerprint %s" % ca["sha256"]) if ca.get("sha256") else " -Ca C:\\chemin\\ca.crt"
    return "powershell -NoProfile -ExecutionPolicy Bypass -File .\\windows\\install.ps1 -Agent %s -Secret %s -Central %s -Site %s%s" % (
        _ps_quote(agent_id), _ps_quote(secret), _ps_quote(central), _ps_quote(site or "default"), tls)


def _ascii(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()


def _install_cmd_windows(agent_id, secret, site):
    """#446 bis : fichier `.cmd` SILENCIEUX propre à l'agent -- valeurs
    incluses, élévation UAC, install.ps1 sans question (sortie dans un
    journal), « OK » à la fin puis le fichier s'efface (il contient le
    secret) ; en erreur, le journal est affiché et la fenêtre reste
    ouverte. À déposer à la racine de l'archive décompressée (à côté du
    dossier windows) et double-cliquer. ASCII seul (cmd.exe lit la page de
    code OEM) ; l'empreinte de la CA interne est obligatoire (jamais
    `-Insecure` en silence)."""
    ca = _ca_info()
    if not ca.get("sha256"):
        return None
    central = _ascii(PUBLIC_URL or "https://<VM>:6443/api/si-agent")
    aid, sec, st = _ascii(agent_id), _ascii(secret), _ascii(site or "default")
    for v in (aid, sec, central, st):
        if re.search(r'["%!^&<>|]', v):
            return None
    lines = [
        "@echo off",
        "rem si-agent -- installation silencieuse de l'agent %s (fichier genere par le central, contient le secret : s'efface apres succes)." % aid,
        "rem A placer a la racine de l'archive si-agent-agent-<version> decompressee (a cote de windows\\), puis double-cliquer (UAC demande une fois).",
        "setlocal",
        'cd /d "%~dp0"',
        'set "PS1=%~dp0windows\\install.ps1"',
        'if not exist "%PS1%" set "PS1=%~dp0install.ps1"',
        'if not exist "%PS1%" ( echo ERREUR : install.ps1 introuvable -- placer ce fichier a la racine de l\'archive decompressee. & pause & exit /b 1 )',
        "net session >nul 2>&1",
        'if not "%errorlevel%"=="0" (',
        '  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath \'%~f0\' -Verb RunAs"',
        "  exit /b",
        ")",
        'set "LOG=%TEMP%\\si-agent-install.log"',
        'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%%PS1%%" -Agent "%s" -Secret "%s" -Central "%s" -Site "%s" -CaFingerprint %s > "%%LOG%%" 2>&1' % (aid, sec, central, st, ca["sha256"]),
        'if not "%errorlevel%"=="0" goto :erreur',
        "echo OK - agent %s installe et demarre (journal : %%LOG%%)" % aid,
        "timeout /t 10 >nul",
        '(goto) 2>nul & del "%~f0"',
        ":erreur",
        "echo ERREUR (code %errorlevel%) - journal %LOG% :",
        'type "%LOG%"',
        "pause",
        "exit /b 1",
    ]
    return "\r\n".join(lines) + "\r\n"


@app.route("/agents/<agent_id>/install.cmd", methods=["GET"])
def install_cmd_route(agent_id):
    """Le `.cmd` silencieux de l'agent (même exposition du secret que
    /install : réservée au hub). 409 sans CA interne."""
    a = store.get_agent(DB_PATH, agent_id, with_secret=True)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    body = _install_cmd_windows(agent_id, a["secret"], a["site"])
    if body is None:
        return jsonify({"error": "CA interne absente (empreinte requise pour une installation silencieuse) ou caractère interdit dans l'identifiant, le site ou l'URL"}), 409
    return Response(body, mimetype="text/plain", headers={"Content-Disposition": 'attachment; filename="si-agent-install-%s.cmd"' % re.sub(r"[^A-Za-z0-9_.-]", "_", agent_id)})


@app.route("/agents/<agent_id>/install", methods=["GET"])
def install_route(agent_id):
    """Secret + commande d'installation prête à coller sur l'hôte -- la
    seule lecture qui renvoie le secret (même logique que
    netprobe /provision)."""
    a = store.get_agent(DB_PATH, agent_id, with_secret=True)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "secret": a["secret"], "site": a["site"],
                    "central_url": PUBLIC_URL or None,
                    "install_command": _install_command(agent_id, a["secret"], a["site"]),
                    "install_command_docker": _install_command_docker(agent_id, a["secret"], a["site"]),
                    "install_command_windows": _install_command_windows(agent_id, a["secret"], a["site"]),
                    "install_command_macos": _install_command_macos(agent_id, a["secret"], a["site"]),
                    "install_cmd_available": _install_cmd_windows(agent_id, a["secret"], a["site"]) is not None,
                    "agent_json": {"agent_id": agent_id, "secret": a["secret"], "site": a["site"],
                                   "central_url": PUBLIC_URL or "https://<VM>:6443/api/si-agent"}}), 200


@app.route("/agents/<agent_id>/measurements", methods=["GET"])
def agent_measurements_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "measurements": store.list_measurements(
        DB_PATH, agent_id, task=request.args.get("task"), limit=request.args.get("limit", 200, type=int),
        since=request.args.get("since"))}), 200


@app.route("/agents/<agent_id>/latest", methods=["GET"])
def agent_latest_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "latest": store.latest_per_task(DB_PATH, agent_id)}), 200


@app.route("/agents/<agent_id>/config-preview", methods=["GET"])
def config_preview_route(agent_id):
    """Ce que l'agent recevra (sans les corps de scripts ni signatures)."""
    cfg = store.config_for_agent(DB_PATH, agent_id)
    if cfg is None:
        return jsonify({"error": "agent inconnu"}), 404
    cfg["plugins"] = [{k: v for k, v in p["manifest"].items() if k != "signature"} for p in cfg["plugins"]]
    return jsonify(cfg), 200


# -- plugins : catalogue et affectations --------------------------------

@app.route("/plugins", methods=["GET"])
def list_plugins_route():
    return jsonify({"plugins": store.list_plugins(DB_PATH)}), 200


@app.route("/plugins", methods=["POST"])
def create_plugin_route():
    body = request.get_json(silent=True) or {}
    manifest = body.get("manifest") if isinstance(body.get("manifest"), dict) else {
        k: body.get(k) for k in ("id", "version", "runner", "entry", "interval_seconds", "timeout_seconds", "args", "description",
                                 "privileged", "max_memory_mb") if k in body}
    try:
        p = store.upsert_plugin(DB_PATH, manifest, body.get("body"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _event("plugin-catalogued", "warning" if p.get("privileged") else "info",
           "sonde %s v%s enregistrée au catalogue%s" % (p["id"], p["version"], " (PRIVILÉGIÉE : tourne en root)" if p.get("privileged") else ""),
           details={"plugin": p["id"], "version": p["version"], "sha256": p["sha256"], "privileged": p.get("privileged"), "assigned_agents": p.get("assigned_agents", 0)})
    return jsonify(p), 201


@app.route("/plugins/<plugin_id>", methods=["GET"])
def get_plugin_route(plugin_id):
    p = store.get_plugin(DB_PATH, plugin_id, with_body=request.args.get("body", "false").lower() == "true")
    if p is None:
        return jsonify({"error": "plugin inconnu"}), 404
    return jsonify(p), 200


@app.route("/plugins/<plugin_id>", methods=["DELETE"])
def delete_plugin_route(plugin_id):
    if not store.delete_plugin(DB_PATH, plugin_id):
        return jsonify({"error": "plugin inconnu"}), 404
    _event("plugin-uncatalogued", "warning", "sonde %s retirée du catalogue (désinstallation chez les agents affectés)" % plugin_id, details={"plugin": plugin_id})
    return jsonify({"deleted": plugin_id}), 200


@app.route("/agents/<agent_id>/plugins", methods=["GET"])
def agent_plugins_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "plugins": store.agent_plugins(DB_PATH, agent_id)}), 200


@app.route("/agents/<agent_id>/plugins/<plugin_id>", methods=["PUT"])
def assign_plugin_route(agent_id, plugin_id):
    body = request.get_json(silent=True) or {}
    existing = {p["id"]: p for p in store.agent_plugins(DB_PATH, agent_id)}
    prev = existing.get(plugin_id)
    try:
        res = store.assign_plugin(DB_PATH, agent_id, plugin_id, enabled=body.get("enabled", prev["enabled"] if prev else True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if res is None:
        return jsonify({"error": "agent inconnu"}), 404
    if "blocked" in body:
        blocked = bool(body["blocked"])
        store.set_plugin_blocked(DB_PATH, agent_id, plugin_id, blocked, body.get("reason"))
        if not prev or prev["blocked"] != blocked:
            _queue_block_command(agent_id, "block_plugin" if blocked else "unblock_plugin", {"id": plugin_id, "reason": body.get("reason")})
            _event("plugin-blocked" if blocked else "plugin-unblocked", "warning" if blocked else "info",
                   "sonde %s %s sur l'agent %s%s" % (plugin_id, "bloquée" if blocked else "débloquée", agent_id, (" : " + body["reason"]) if body.get("reason") else ""),
                   agent_id=agent_id, details={"plugin": plugin_id})
        res = store.agent_plugins(DB_PATH, agent_id)
    elif prev is None:
        _event("plugin-assigned", "info", "sonde %s affectée à l'agent %s" % (plugin_id, agent_id), agent_id=agent_id, details={"plugin": plugin_id})
    return jsonify({"agent_id": agent_id, "plugins": res}), 200


@app.route("/agents/<agent_id>/plugins/<plugin_id>", methods=["DELETE"])
def unassign_plugin_route(agent_id, plugin_id):
    if not store.unassign_plugin(DB_PATH, agent_id, plugin_id):
        return jsonify({"error": "affectation inconnue"}), 404
    _event("plugin-unassigned", "info", "sonde %s retirée de l'agent %s" % (plugin_id, agent_id), agent_id=agent_id, details={"plugin": plugin_id})
    return jsonify({"agent_id": agent_id, "plugins": store.agent_plugins(DB_PATH, agent_id)}), 200


# -- commandes -------------------------------------------------------------

@app.route("/agents/<agent_id>/commands", methods=["GET"])
def list_commands_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "commands": store.list_commands(
        DB_PATH, agent_id, status=request.args.get("status"), limit=request.args.get("limit", 50, type=int))}), 200


@app.route("/agents/<agent_id>/commands", methods=["POST"])
def create_command_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        c = store.create_command(DB_PATH, agent_id, body.get("type"), body.get("params"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if c is None:
        return jsonify({"error": "agent inconnu"}), 404
    _log.info("commande %s (%s) créée pour %s", c["id"], c["type"], agent_id)
    if c["type"] in control.BLOCK_COMMANDS:
        _event("command-block", "warning", "commande %s envoyée à l'agent %s" % (c["type"], agent_id), agent_id=agent_id, details={"command": c["id"], "params": c["params"]})
    return jsonify(c), 201


@app.route("/commands/<cid>", methods=["GET"])
def get_command_route(cid):
    c = store.get_command(DB_PATH, cid)
    if c is None:
        return jsonify({"error": "commande inconnue"}), 404
    return jsonify(c), 200


# ============================================================
# Face agents (signée)
# ============================================================

def _signed_path():
    """Chemin tel que l'agent l'a signé : tls-proxy retire `/api/si-agent`,
    l'agent signe `/api/v1/agents/<id>/config` et Flask voit ce chemin."""
    qs = request.query_string.decode("utf-8") if request.query_string else ""
    return request.path + ("?" + qs if qs else "")


_auth_failures = {}


def _verify_agent(agent_id):
    header_id = request.headers.get(protocol.HEADER_ID)
    info, why = None, None
    if not header_id:
        why = "en-tête %s absent" % protocol.HEADER_ID
    elif header_id != agent_id:
        why = "identifiant signataire différent de l'URL"
    else:
        info = store.get_secret(DB_PATH, agent_id)
        if info is None:
            why = "agent inconnu ou désactivé"
        else:
            ok, reason = protocol.verify(info["secret"], request.method, _signed_path(), request.headers, request.get_data())
            if not ok:
                info, why = None, reason
    if info is None:
        _log.warning("face agents : refus %s %s pour %s depuis %s -- %s", request.method, request.path, agent_id, _client_ip(), why)
        # un événement par (agent, motif) et par 10 min -- jamais une tempête
        key = (agent_id, why)
        last = _auth_failures.get(key, 0)
        if time.time() - last > 600:
            _auth_failures[key] = time.time()
            _event("auth-refused", "warning", "requête refusée pour l'agent %s : %s (depuis %s)" % (agent_id, why, _client_ip()),
                   agent_id=agent_id if store.get_agent(DB_PATH, agent_id) else None, details={"path": request.path, "ip": _client_ip(), "reason": why})
        return None, why
    _log.debug("face agents : %s %s par %s depuis %s", request.method, request.path, agent_id, _client_ip())
    return info, None


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _signed_json(secret, payload, status=200):
    """Réponse JSON SIGNÉE avec le secret de l'agent (voir control.py) :
    l'agent n'applique une configuration / une commande que si cette
    signature est valide."""
    raw = protocol.canonical_json(payload)
    headers = control.response_headers(secret, raw)
    headers["Content-Type"] = "application/json; charset=utf-8"
    return raw, status, headers


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/config", methods=["GET"])
def agent_config_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    cfg = store.config_for_agent(DB_PATH, agent_id)
    prev = store.get_agent(DB_PATH, agent_id)
    conn = store._connect(DB_PATH)
    try:
        store.touch_agent(conn, agent_id, _client_ip(), config_version=cfg["version"])
        conn.commit()
    finally:
        conn.close()
    if prev and prev.get("last_config_version") != cfg["version"]:
        _log.info("agent %s : configuration %s servie (%d sonde(s)%s)", agent_id, cfg["version"], len(cfg["plugins"]), ", BLOQUÉ" if cfg["blocked"] else "")
    return _signed_json(info["secret"], cfg)


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/commands", methods=["GET"])
def agent_commands_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    conn = store._connect(DB_PATH)
    try:
        store.touch_agent(conn, agent_id, _client_ip())
        conn.commit()
    finally:
        conn.close()
    return _signed_json(info["secret"], {"commands": store.pending_commands_for_agent(DB_PATH, agent_id)})


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/commands/<cid>/ack", methods=["POST"])
def agent_ack_route(agent_id, cid):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    result = request.get_json(silent=True) or {}
    if not store.ack_command(DB_PATH, agent_id, cid, result):
        return _signed_json(info["secret"], {"error": "commande inconnue ou déjà acquittée"}, 404)
    c = store.get_command(DB_PATH, cid) or {}
    _log.info("agent %s : commande %s (%s) acquittée ok=%s", agent_id, cid, c.get("type"), bool(result.get("ok")))
    if not result.get("ok"):
        _event("command-failed", "warning", "commande %s (%s) en échec sur %s : %s" % (cid, c.get("type"), agent_id, result.get("error")),
               agent_id=agent_id, details={"command": cid, "type": c.get("type")})
    elif c.get("type") in control.BLOCK_COMMANDS:
        _event("command-acked", "info", "commande %s appliquée par %s" % (c.get("type"), agent_id), agent_id=agent_id, details={"command": cid})
    return _signed_json(info["secret"], {"acked": cid})


NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")


def relay_capture_measurements(agent_id, info, items, post=None):
    """#436 : chaque mesure `plugin:capture-relay` réussie (pcap en base64,
    bornée par le plugin) est versée dans network-agent-api
    (`POST /capture/upload`, site de l'agent, segment = nom d'hôte). Le pcap
    n'est PAS conservé ici (la mesure stockée le contient déjà ; purge par
    rétention). Échec = événement, jamais un refus de la mesure."""
    if not NETWORK_AGENT_API_URL:
        return 0
    post = post or (lambda url, payload: requests.post(url, json=payload, timeout=60))
    done = 0
    agent = store.get_agent(DB_PATH, agent_id) or {}
    for m in items:
        if not isinstance(m, dict) or m.get("task") != "plugin:capture-relay" or not m.get("ok"):
            continue
        data = m.get("data") or {}
        if not isinstance(data, dict) or not data.get("pcap_base64"):
            continue
        payload = {"site": agent.get("site") or info.get("site") or "relais", "segment": agent.get("hostname") or agent_id,
                   "cidr": data.get("cidr"), "pcap_base64": data["pcap_base64"], "source": "si-agent %s (%s)" % (agent_id, data.get("interface"))}
        try:
            r = post(NETWORK_AGENT_API_URL + "/capture/upload", payload)
            if r.status_code == 200:
                done += 1
                _log.info("relais d'exploration : %s -> %s paquet(s) versés (segment %s)", agent_id, (r.json() or {}).get("packets"), payload["segment"])
            else:
                _event("capture-relay-failed", "warning", "relais d'exploration refusé par network-agent-api (%s) pour %s" % (r.status_code, agent_id), agent_id=agent_id,
                       details={"status": r.status_code, "error": (r.json() or {}).get("error") if r.content else None})
        except Exception as exc:  # noqa: BLE001 -- jamais bloquant
            _event("capture-relay-failed", "warning", "relais d'exploration impossible pour %s : %s" % (agent_id, exc), agent_id=agent_id, details={})
    return done


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/measurements", methods=["POST"])
def agent_measurements_ingest_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    body = request.get_json(silent=True) or {}
    items = body.get("measurements")
    if not isinstance(items, list):
        return jsonify({"error": "'measurements' (liste) attendu"}), 400
    if len(items) > 5000:
        return jsonify({"error": "lot trop volumineux (max 5000)"}), 400
    accepted, duplicates, rejected, events = store.ingest_measurements(DB_PATH, agent_id, items, ip=_client_ip())
    relay_capture_measurements(agent_id, info, items)  # #436 : relais d'exploration vers network-agent-api
    _log.debug("agent %s : %d mesure(s) acceptée(s), %d doublon(s), %d rejet(s), %d événement(s)", agent_id, accepted, duplicates, len(rejected), len(events))
    for ev in events:
        notify.dispatch(DB_PATH, dict(ev, source="agent", details={}))
    if rejected and not accepted and not duplicates and items:
        return _signed_json(info["secret"], {"error": "aucune mesure valide", "rejected": rejected[:10]}, 400)
    return _signed_json(info["secret"], {"accepted": accepted, "duplicates": duplicates, "rejected": rejected[:10]}, 201)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
