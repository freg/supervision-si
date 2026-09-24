# -*- coding: utf-8 -*-
"""cisco-api (livraison #508) -- supervision et commande de base des
switchs/routeurs Cisco (Catalyst 3750 / 2970 sous IOS, Nexus 3064PQ sous
NX-OS -- et tout IOS/NX-OS proche) par SSH. Même patron que mikrotik
(#485) : registre versionné `cisco/switches.json` (jamais d'identifiant
dedans), identifiants dans le coffre des accès (#498, genre ssh), page
servie sous /cisco/ par tls-proxy, tuile de la thématique Réseau.

Trois buts demandés :
 1. superviser -- disponibilité (SSH joignable, uptime), état (version,
    capteurs), charge (CPU, mémoire), interfaces, alertes dérivées,
    journal (show logging) ;
 2. sauvegarder / restaurer les configurations -- `show running-config`
    archivé et versionné dans /data/configs/<switch>/, différence entre
    deux versions et avec la configuration courante, restauration par
    réapplication en mode configuration (fusion) avec aperçu obligatoire,
    puis `write memory` ; sauvegarde automatique périodique ;
 3. agir en cas d'urgence -- shutdown / no shutdown d'un port
    (err-disabled, port à isoler), sauvegarde de la configuration
    (write memory), redémarrage différé annulable (`reload in N`,
    `reload cancel`), commande `show` libre pour diagnostiquer.
    Chaque geste est journalisé (/data/actions.log : qui, quoi, résultat)
    et demande le nom du switch en confirmation.

Routes (préfixe /cisco/) :
  GET  /, /health, /switches
  GET  /switches/<n>/summary | interfaces | logs | configs | configs/<id> | configs/diff?a=&b=  | actions
  POST /switches/<n>/configs/backup
  POST /switches/<n>/configs/<id>/restore     {confirm: <nom>, dry_run: bool, write: bool}
  POST /switches/<n>/interfaces/<port>/shutdown | no-shutdown   {confirm}
  POST /switches/<n>/reload      {confirm, in_minutes (défaut 5) | cancel: true}
  POST /switches/<n>/write       {confirm}
  POST /switches/<n>/show        {command}   (show … seulement)
"""
import difflib
import hashlib
import json
import logging
import os
import re
import threading
import time

import requests
from flask import Flask, jsonify, request, send_from_directory

import parsers
try:
    import registry_edit  # #592 (shared/, copié par le Dockerfile)
except ImportError:  # tests hors conteneur : shared/ du dépôt
    import sys as _sys
    _sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
    import registry_edit
from ssh_client import CiscoError, CiscoSession
try:
    from notify_client import notify as _notify, register_actions as _register_actions  # #590 (shared/, copié par le Dockerfile)
except ImportError:  # tests hors conteneur
    def _notify(*a, **k):
        return None

    def _register_actions(*a, **k):
        return None

_register_actions([
    {"id": "cisco.backup", "label": "Sauvegarde de configuration", "severity": "info"},
    {"id": "cisco.restore", "label": "Restauration de configuration", "severity": "critical"},
    {"id": "cisco.interface", "label": "Interface modifiée (shut / no shut / vlan)", "severity": "warning"},
    {"id": "cisco.write", "label": "Configuration écrite (write memory)", "severity": "warning"},
    {"id": "cisco.reload", "label": "Redémarrage planifié / annulé", "severity": "critical"},
])

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("cisco")

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
REGISTRY = os.environ.get("CISCO_REGISTRY", os.path.join(HERE, "switches.json"))
# #585 : registre LOCAL (hors dépôt, jamais écrasé par un déploiement) qui
# remplace l'exemple versionné s'il existe : cisco/switches.local.json.
REGISTRY_LOCAL = os.environ.get("CISCO_REGISTRY_LOCAL", os.path.join(HERE, "switches.local.json"))
DATA_DIR = os.environ.get("CISCO_DATA_DIR", "/data")
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "").rstrip("/")
CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
if CREDENTIALS_TOKEN == "change-me":
    CREDENTIALS_TOKEN = ""
SSH_TIMEOUT = int(os.environ.get("CISCO_SSH_TIMEOUT", "15"))
BACKUP_INTERVAL_H = float(os.environ.get("CISCO_BACKUP_INTERVAL_HOURS", "24") or 0)
KEEP_CONFIGS = int(os.environ.get("CISCO_KEEP_CONFIGS", "60"))
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PORT_RE = re.compile(r"^[A-Za-z][A-Za-z-]*\d+(?:/\d+){0,3}(?:\.\d+)?$")

app = Flask(__name__, static_folder=None)
os.makedirs(DATA_DIR, exist_ok=True)
try:
    from version_endpoint import register_version_route
    register_version_route(app, "cisco")
except Exception:  # noqa: BLE001
    pass

# Fabrique de session : remplacée par un faux en test.
SESSION_FACTORY = CiscoSession
_cred_cache = {}


# ---------------------------------------------------------------- registre / coffre

def registry_path():
    return REGISTRY_LOCAL if os.path.exists(REGISTRY_LOCAL) else REGISTRY


def load_registry():
    path = registry_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        log.warning("registre illisible (%s) : %s", path, exc)
        return []
    out = []
    for s in data.get("switches") or []:
        if not isinstance(s, dict) or not s.get("name") or not s.get("host") or not NAME_RE.match(str(s["name"])):
            continue
        proto = (s.get("transport") or "ssh").lower()  # #579 : "telnet" pour les vieux IOS sans SSH (patte interne)
        if proto not in ("ssh", "telnet"):
            proto = "ssh"
        out.append({"name": s["name"], "host": s["host"], "port": int(s.get("port") or (23 if proto == "telnet" else 22)), "platform": (s.get("platform") or "ios").lower(),
                    "credential": s.get("credential") or "cisco", "site": s.get("site"), "description": s.get("description"),
                    "enable_credential": s.get("enable_credential"), "transport": proto})
    return out


def switch_or_404(name):
    for s in load_registry():
        if s["name"] == name:
            return s
    return None


def credentials_for(name):
    now = time.monotonic()
    hit = _cred_cache.get(name)
    if hit and hit[0] > now:
        return hit[1], hit[2]
    if not CREDENTIALS_API_URL or not CREDENTIALS_TOKEN:
        raise CiscoError("coffre des accès non configuré côté cisco-api (CREDENTIALS_INTERNAL_TOKEN)")
    try:
        resp = requests.get("%s/credentials/reveal/%s" % (CREDENTIALS_API_URL, name), timeout=5,
                            headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "cisco-api"})
    except requests.RequestException as exc:
        raise CiscoError("coffre des accès injoignable (%s)" % exc.__class__.__name__)
    if resp.status_code == 404:
        raise CiscoError("accès « %s » absent du coffre -- à créer dans la tuile Accès d'équipements (genre cisco, ssh ou telnet)" % name)
    if resp.status_code != 200:
        raise CiscoError("coffre des accès : refus %s" % resp.status_code)
    body = resp.json() or {}
    user, pwd = body.get("username") or "", body.get("password") or ""
    if not user or not pwd:
        raise CiscoError("accès « %s » incomplet dans le coffre" % name)
    _cred_cache[name] = (now + 60, user, pwd)
    return user, pwd


def session_for(sw):
    user, pwd = credentials_for(sw["credential"])
    enable = None
    if sw.get("enable_credential"):
        enable = credentials_for(sw["enable_credential"])[1]
    s = SESSION_FACTORY(sw["host"], user, pwd, port=sw["port"], timeout=SSH_TIMEOUT, enable_password=enable, protocol=sw.get("transport") or "ssh")
    s.platform = sw["platform"]
    return s


# ---------------------------------------------------------------- archives de configuration

def config_dir(name):
    d = os.path.join(DATA_DIR, "configs", name)
    os.makedirs(d, exist_ok=True)
    return d


def list_configs(name):
    d = config_dir(name)
    out = []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".cfg"):
            continue
        meta = {}
        try:
            with open(os.path.join(d, f + ".json"), encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            pass
        out.append({"id": f[:-4], "size": os.path.getsize(os.path.join(d, f)), **meta})
    return out


def read_config(name, cid):
    if not re.match(r"^[0-9T\-]+Z?$", cid or ""):
        return None
    p = os.path.join(config_dir(name), cid + ".cfg")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def save_config(name, content, source="manuel", by=None):
    """Archive si différente de la dernière (hors lignes volatiles) -> (id, created)."""
    digest = hashlib.sha256(parsers.strip_volatile(content).encode("utf-8")).hexdigest()
    existing = list_configs(name)
    if existing and existing[-1].get("sha256") == digest:
        return existing[-1]["id"], False
    cid = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    d = config_dir(name)
    with open(os.path.join(d, cid + ".cfg"), "w", encoding="utf-8") as fh:
        fh.write(content)
    with open(os.path.join(d, cid + ".cfg.json"), "w", encoding="utf-8") as fh:
        json.dump({"at": cid, "source": source, "by": by, "sha256": digest, "lines": content.count("\n")}, fh)
    # rétention : on garde les KEEP_CONFIGS plus récentes
    for old in existing[:-KEEP_CONFIGS] if KEEP_CONFIGS > 0 else []:
        for ext in (".cfg", ".cfg.json"):
            try:
                os.remove(os.path.join(d, old["id"] + ext))
            except OSError:
                pass
    return cid, True


def unified_diff(a, b, label_a="a", label_b="b"):
    return "".join(difflib.unified_diff(parsers.strip_volatile(a).splitlines(True), parsers.strip_volatile(b).splitlines(True),
                                        fromfile=label_a, tofile=label_b))


def journal(name, action, by, ok, detail=None):
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "switch": name, "action": action, "by": by or "?", "ok": bool(ok), "detail": (detail or "")[:500]}
    with open(os.path.join(DATA_DIR, "actions.log"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log.info("action %s sur %s par %s : %s", action, name, by or "?", "ok" if ok else "échec")
    return entry


def read_journal(name=None, limit=100):
    p = os.path.join(DATA_DIR, "actions.log")
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if name is None or e.get("switch") == name:
                out.append(e)
    return out[-limit:]


def _confirmed(body, sw):
    return (body or {}).get("confirm") == sw["name"]


def _by():
    return (request.get_json(silent=True) or {}).get("login") or request.headers.get("X-Forwarded-User") or "?"


# ---------------------------------------------------------------- routes

@app.route("/cisco/", methods=["GET"])
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/cisco/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "switches": len(load_registry()), "credentials": bool(CREDENTIALS_API_URL and CREDENTIALS_TOKEN),
                    "backup_interval_hours": BACKUP_INTERVAL_H}), 200


@app.route("/cisco/switches", methods=["GET"])
def switches():
    out = []
    for s in load_registry():
        cfgs = list_configs(s["name"])
        state = _state_cache.get(s["name"]) or {}
        out.append({**s, "configs": len(cfgs), "last_backup": cfgs[-1]["at"] if cfgs else None,
                    "last_seen": state.get("at"), "reachable": state.get("reachable"), "alerts": state.get("alerts")})
    return jsonify({"switches": out}), 200


_state_cache = {}


def collect_summary(sw):
    """#581 : chaque relevé est indépendant -- une commande que l'équipement refuse
    (vieux routeur sans « show interfaces status », journal désactivé…) est notée
    dans `unavailable`, jamais transformée en « injoignable » : la session est
    ouverte, l'équipement répond."""
    unavailable = []

    def attempt(label, fn, default):
        try:
            return fn()
        except CiscoError as exc:
            unavailable.append("%s : %s" % (label, exc))
            return default

    with session_for(sw) as s:
        plat = sw["platform"]
        version = attempt("show version", lambda: parsers.parse_version(s.show("show version")), {})
        plat = version.get("platform") or plat
        if plat == "nxos":
            res = attempt("show system resources", lambda: s.show("show system resources"), "")
            cpu, mem = parsers.parse_cpu(res, "nxos"), parsers.parse_memory(res, "nxos")
            env = attempt("show environment", lambda: parsers.parse_environment(s.show("show environment")), [])
        else:
            cpu = attempt("show processes cpu", lambda: parsers.parse_cpu(s.show("show processes cpu | include CPU")), {})
            mem = attempt("show memory statistics", lambda: parsers.parse_memory(s.show("show memory statistics")), {})
            env = attempt("show env all", lambda: parsers.parse_environment(s.show("show env all")), None)
            if env is None:
                env = attempt("show environment", lambda: parsers.parse_environment(s.show("show environment")), [])
        ifaces = attempt("show interfaces status", lambda: parsers.parse_interfaces_status(s.show("show interfaces status" if plat != "nxos" else "show interface status")), None)
        if ifaces is None or not ifaces:
            ifaces = attempt("show ip interface brief", lambda: parsers.parse_ip_interface_brief(s.show("show ip interface brief")), ifaces or [])
        logs = attempt("show logging", lambda: parsers.parse_logging(s.show("show logging", timeout=SSH_TIMEOUT * 2), 100), [])
    summary = {"version": version, "cpu": cpu, "memory": mem, "environment": env, "platform": plat, "unavailable": unavailable}
    al = parsers.alerts(summary, ifaces, logs)
    summary["alerts"] = al
    summary["interfaces"] = ifaces
    summary["logs"] = logs
    summary["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _state_cache[sw["name"]] = {"at": summary["at"], "reachable": True, "alerts": len(al)}
    return summary


@app.route("/cisco/credentials", methods=["GET"])
def credential_names():
    """#592 : noms des accès du coffre (jamais de secret) pour le formulaire."""
    if not (CREDENTIALS_API_URL and CREDENTIALS_TOKEN):
        return jsonify({"credentials": [], "error": "coffre non configuré"}), 200
    try:
        resp = requests.get("%s/credentials/list" % CREDENTIALS_API_URL, timeout=5)
        items = resp.json().get("credentials", []) if resp.status_code == 200 else []
    except (requests.RequestException, ValueError):
        items = []
    return jsonify({"credentials": [{"name": c.get("name"), "kind": c.get("kind"), "username": c.get("username")} for c in items if c.get("name")]}), 200


@app.route("/cisco/switches", methods=["POST"])
def switch_save():
    """#592 : ajout / modification d'un équipement depuis la tuile -> switches.local.json."""
    body = request.get_json(silent=True) or {}
    entry, errors = registry_edit.validate_common(body, ("ssh", "telnet"), {"ssh": 22, "telnet": 23})
    platform = str(body.get("platform") or "ios").lower()
    if platform not in ("ios", "nxos"):
        errors.append("platform : ios ou nxos")
    else:
        entry["platform"] = platform
    en = str(body.get("enable_credential") or "").strip()
    if en:
        if not registry_edit.NAME_RE.match(en):
            errors.append("accès enable invalide")
        else:
            entry["enable_credential"] = en
    if errors:
        return jsonify({"error": "entrée refusée", "errors": errors}), 400
    items, _ = registry_edit.read_items(REGISTRY_LOCAL, REGISTRY, "switches")
    items = [i for i in items if not str(i.get("name", "")).startswith("exemple")]
    items, what = registry_edit.upsert(items, entry)
    try:
        registry_edit.write_items(REGISTRY_LOCAL, "switches", items)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    log.warning("registre : équipement %s %s (%s, %s)", entry["name"], "modifié" if what == "updated" else "ajouté", entry["host"], entry["transport"])
    return jsonify({"status": "ok", "action": what, "switch": entry, "path": REGISTRY_LOCAL}), 200


@app.route("/cisco/switches/<name>", methods=["DELETE"])
def switch_delete(name):
    items, _ = registry_edit.read_items(REGISTRY_LOCAL, REGISTRY, "switches")
    items, ok = registry_edit.remove(items, name)
    if not ok:
        return jsonify({"error": "équipement inconnu"}), 404
    try:
        registry_edit.write_items(REGISTRY_LOCAL, "switches", items)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    log.warning("registre : équipement %s retiré", name)
    return jsonify({"status": "ok"}), 200


@app.route("/cisco/switches/<name>/summary", methods=["GET"])
def summary_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    try:
        return jsonify(collect_summary(sw)), 200
    except CiscoError as exc:
        _state_cache[name] = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "reachable": False, "alerts": None}
        return jsonify({"error": str(exc), "reachable": False}), 502


@app.route("/cisco/switches/<name>/interfaces", methods=["GET"])
def interfaces_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    try:
        with session_for(sw) as s:
            rows = parsers.parse_interfaces_status(s.show("show interfaces status" if sw["platform"] != "nxos" else "show interface status"))
        return jsonify({"interfaces": rows}), 200
    except CiscoError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/cisco/switches/<name>/logs", methods=["GET"])
def logs_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    try:
        with session_for(sw) as s:
            logs = parsers.parse_logging(s.show("show logging", timeout=SSH_TIMEOUT * 2), int(request.args.get("limit") or 200))
        return jsonify({"logs": logs}), 200
    except CiscoError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/cisco/switches/<name>/show", methods=["POST"])
def show_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    cmd = ((request.get_json(silent=True) or {}).get("command") or "").strip()
    if not re.match(r"^show\s+[\w\s|/.\-:]+$", cmd) or "|" in cmd and not re.search(r"\|\s*(include|exclude|begin|section)\b", cmd):
        return jsonify({"error": "seule une commande « show … » (avec | include/exclude/begin/section) est acceptée"}), 400
    try:
        with session_for(sw) as s:
            out = s.show(cmd, timeout=SSH_TIMEOUT * 2)
        return jsonify({"command": cmd, "output": out}), 200
    except CiscoError as exc:
        return jsonify({"error": str(exc)}), 502


# --- configurations

@app.route("/cisco/switches/<name>/configs", methods=["GET"])
def configs_route(name):
    if not switch_or_404(name):
        return jsonify({"error": "switch inconnu"}), 404
    return jsonify({"configs": list_configs(name)}), 200


@app.route("/cisco/switches/<name>/configs/backup", methods=["POST"])
def backup_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    try:
        with session_for(sw) as s:
            content = s.show("show running-config", timeout=SSH_TIMEOUT * 3)
    except CiscoError as exc:
        journal(name, "backup", _by(), False, str(exc))
        return jsonify({"error": str(exc)}), 502
    cid, created = save_config(name, content, "manuel", _by())
    journal(name, "backup", _by(), True, "%s (%s)" % (cid, "nouvelle version" if created else "identique à la précédente"))
    if created:
        _notify("cisco.backup", "%s : nouvelle sauvegarde %s" % (name, cid), "Équipement %s (%s) : %d ligne(s)." % (name, sw["host"], content.count("\n")), {"switch": name, "version": cid})
    return jsonify({"id": cid, "created": created, "lines": content.count("\n")}), 200


@app.route("/cisco/switches/<name>/configs/diff", methods=["GET"])
def diff_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    a, b = request.args.get("a"), request.args.get("b")
    ca = read_config(name, a) if a else None
    if a and ca is None:
        return jsonify({"error": "version a introuvable"}), 404
    if b == "running" or not b:
        try:
            with session_for(sw) as s:
                cb = s.show("show running-config", timeout=SSH_TIMEOUT * 3)
        except CiscoError as exc:
            return jsonify({"error": str(exc)}), 502
        label_b = "running-config"
    else:
        cb = read_config(name, b)
        if cb is None:
            return jsonify({"error": "version b introuvable"}), 404
        label_b = b
    if ca is None:
        cfgs = list_configs(name)
        if not cfgs:
            return jsonify({"error": "aucune sauvegarde à comparer"}), 404
        a, ca = cfgs[-1]["id"], read_config(name, cfgs[-1]["id"])
    d = unified_diff(ca, cb, a, label_b)
    return jsonify({"a": a, "b": label_b, "diff": d, "identical": not d.strip()}), 200


@app.route("/cisco/switches/<name>/configs/<cid>", methods=["GET"])
def config_route(name, cid):
    if not switch_or_404(name):
        return jsonify({"error": "switch inconnu"}), 404
    c = read_config(name, cid)
    if c is None:
        return jsonify({"error": "version introuvable"}), 404
    return jsonify({"id": cid, "content": c}), 200


@app.route("/cisco/switches/<name>/configs/<cid>/restore", methods=["POST"])
def restore_route(name, cid):
    """Restauration par FUSION : les lignes de la version archivée qui
    diffèrent de la configuration courante sont réappliquées en mode
    configuration (blocs `interface …` complets, puis le reste). Aperçu
    (`dry_run`) obligatoire avant : la réponse liste ce qui serait envoyé.
    Ce n'est pas un `configure replace` (qui exige un fichier sur la
    flash) : les lignes présentes sur l'équipement mais absentes de la
    sauvegarde ne sont PAS retirées -- dit clairement dans l'aperçu."""
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    body = request.get_json(silent=True) or {}
    saved = read_config(name, cid)
    if saved is None:
        return jsonify({"error": "version introuvable"}), 404
    try:
        with session_for(sw) as s:
            running = s.show("show running-config", timeout=SSH_TIMEOUT * 3)
            plan = restore_plan(saved, running)
            if body.get("dry_run", True) is not False:
                return jsonify({"dry_run": True, "lines": plan, "count": len(plan), "removed_not_handled": removed_lines(saved, running)}), 200
            if not _confirmed(body, sw):
                return jsonify({"error": "confirmation requise : confirm = nom du switch"}), 400
            if not plan:
                journal(name, "restore " + cid, _by(), True, "rien à réappliquer")
                return jsonify({"applied": 0, "errors": [], "written": False}), 200
            save_config(name, running, "avant restauration", _by())
            errors = s.configure(plan, timeout=SSH_TIMEOUT)
            written = False
            if body.get("write", True) and not errors:
                s.write_memory(timeout=SSH_TIMEOUT)
                written = True
    except CiscoError as exc:
        journal(name, "restore " + cid, _by(), False, str(exc))
        return jsonify({"error": str(exc)}), 502
    journal(name, "restore " + cid, _by(), not errors, "%d ligne(s), %d erreur(s), write=%s" % (len(plan), len(errors), written))
    _notify("cisco.restore", "%s : restauration de la version %s (%d ligne(s), %d erreur(s))" % (name, cid, len(plan), len(errors)),
            "Équipement %s (%s)\nLignes appliquées : %d\nErreurs : %s\nÉcrit en mémoire : %s" % (name, sw["host"], len(plan), errors or "aucune", written), {"switch": name, "version": cid})
    return jsonify({"applied": len(plan), "errors": errors, "written": written}), 200 if not errors else 207


def _blocks(config):
    """Configuration -> liste de (entête, [lignes indentées]) ; les lignes
    de premier niveau sont des blocs à entête seule."""
    blocks, cur = [], None
    for line in parsers.strip_volatile(config).splitlines():
        if not line.strip() or line.strip() == "!" or line.startswith("end"):
            cur = None
            continue
        if line.startswith(" "):
            if cur is None:
                cur = ["", []]
                blocks.append(cur)
            cur[1].append(line.rstrip())
        else:
            cur = [line.rstrip(), []]
            blocks.append(cur)
    return blocks


def restore_plan(saved, running):
    """Lignes à envoyer pour que la configuration courante contienne ce que
    la sauvegarde contient (fusion, pur)."""
    run_blocks = {h: set(body) for h, body in _blocks(running)}
    plan = []
    for head, body in _blocks(saved):
        if not head:
            continue
        if head not in run_blocks:
            plan.append(head)
            plan.extend(body)
            if body:
                plan.append(" exit")
            continue
        missing = [l for l in body if l not in run_blocks[head]]
        if missing:
            plan.append(head)
            plan.extend(missing)
            plan.append(" exit")
    return plan


def removed_lines(saved, running):
    """Lignes présentes sur l'équipement mais absentes de la sauvegarde (non
    retirées par la fusion -- affichées pour que l'opérateur le sache)."""
    saved_blocks = {h: set(body) for h, body in _blocks(saved)}
    out = []
    for head, body in _blocks(running):
        if not head:
            continue
        if head not in saved_blocks:
            out.append(head)
        else:
            out.extend("%s > %s" % (head, l.strip()) for l in body if l not in saved_blocks[head])
    return out[:200]


# --- urgence

@app.route("/cisco/switches/<name>/interfaces/<path:port>/<action>", methods=["POST"])
def port_action_route(name, port, action):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    if action not in ("shutdown", "no-shutdown") or not PORT_RE.match(port):
        return jsonify({"error": "action ou port invalide"}), 400
    body = request.get_json(silent=True) or {}
    if not _confirmed(body, sw):
        return jsonify({"error": "confirmation requise : confirm = nom du switch"}), 400
    lines = ["interface " + port, " shutdown" if action == "shutdown" else " no shutdown"]
    try:
        with session_for(sw) as s:
            errors = s.configure(lines)
    except CiscoError as exc:
        journal(name, "%s %s" % (action, port), _by(), False, str(exc))
        return jsonify({"error": str(exc)}), 502
    journal(name, "%s %s" % (action, port), _by(), not errors, json.dumps(errors, ensure_ascii=False) if errors else "")
    _notify("cisco.interface", "%s : %s sur %s" % (name, action, port), "Équipement %s (%s), port %s : %s. Erreurs : %s" % (name, sw["host"], port, action, errors or "aucune"), {"switch": name, "port": port, "action": action})
    return jsonify({"port": port, "action": action, "errors": errors}), 200 if not errors else 207


@app.route("/cisco/switches/<name>/write", methods=["POST"])
def write_route(name):
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    if not _confirmed(request.get_json(silent=True) or {}, sw):
        return jsonify({"error": "confirmation requise : confirm = nom du switch"}), 400
    try:
        with session_for(sw) as s:
            s.write_memory()
    except CiscoError as exc:
        journal(name, "write memory", _by(), False, str(exc))
        return jsonify({"error": str(exc)}), 502
    journal(name, "write memory", _by(), True)
    _notify("cisco.write", "%s : configuration écrite en mémoire" % name, "Équipement %s (%s) : write memory depuis le hub." % (name, sw["host"]), {"switch": name})
    return jsonify({"written": True}), 200


@app.route("/cisco/switches/<name>/reload", methods=["POST"])
def reload_route(name):
    """Redémarrage DIFFÉRÉ (défaut 5 min, borné 1-60) annulable par
    {cancel: true} -- jamais de reload immédiat depuis le hub."""
    sw = switch_or_404(name)
    if not sw:
        return jsonify({"error": "switch inconnu"}), 404
    body = request.get_json(silent=True) or {}
    if not _confirmed(body, sw):
        return jsonify({"error": "confirmation requise : confirm = nom du switch"}), 400
    try:
        with session_for(sw) as s:
            if body.get("cancel"):
                out = s.run("reload cancel")
                journal(name, "reload cancel", _by(), True, out[:200])
                _notify("cisco.reload", "%s : redémarrage annulé" % name, "Équipement %s (%s)." % (name, sw["host"]), {"switch": name})
                return jsonify({"cancelled": True, "output": out}), 200
            minutes = max(1, min(int(body.get("in_minutes") or 5), 60))
            if body.get("write", True):
                s.write_memory()
            s._chan.send("reload in %d\n" % minutes)
            out = s._read_until(re.compile(r"(?i)\[confirm\]|Proceed with reload|[#]\s*$"), SSH_TIMEOUT)
            if "confirm" in out.lower() or "Proceed" in out:
                s._chan.send("\n")
                out += s._expect_prompt()
    except CiscoError as exc:
        journal(name, "reload", _by(), False, str(exc))
        return jsonify({"error": str(exc)}), 502
    journal(name, "reload in %d" % minutes, _by(), True, out[-200:])
    _notify("cisco.reload", "%s : redémarrage planifié dans %s min" % (name, minutes), "Équipement %s (%s)." % (name, sw["host"]), {"switch": name, "minutes": minutes})
    return jsonify({"scheduled_in_minutes": minutes, "output": out[-500:]}), 200


@app.route("/cisco/switches/<name>/actions", methods=["GET"])
def actions_route(name):
    if not switch_or_404(name):
        return jsonify({"error": "switch inconnu"}), 404
    return jsonify({"actions": read_journal(name)}), 200


# ---------------------------------------------------------------- sauvegarde périodique

def backup_all():
    for sw in load_registry():
        try:
            with session_for(sw) as s:
                content = s.show("show running-config", timeout=SSH_TIMEOUT * 3)
            cid, created = save_config(sw["name"], content, "automatique")
            if created:
                journal(sw["name"], "backup auto", "cisco-api", True, cid)
        except CiscoError as exc:
            journal(sw["name"], "backup auto", "cisco-api", False, str(exc))


def _backup_loop():
    while True:
        time.sleep(BACKUP_INTERVAL_H * 3600)
        try:
            backup_all()
        except Exception as exc:  # noqa: BLE001
            log.warning("sauvegarde automatique : %s", exc)


if BACKUP_INTERVAL_H > 0 and os.environ.get("CISCO_BACKUP_THREAD", "1") == "1":
    # un seul worker gunicorn (Dockerfile) : pas de doublon
    threading.Thread(target=_backup_loop, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
