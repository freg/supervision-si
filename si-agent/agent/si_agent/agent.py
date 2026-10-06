"""Boucle de l'agent hôte (livraison #420) -- même architecture que
netprobe_agent.agent (configuration JSON, client HTTP signé, file locale
store-and-forward, passages réguliers), adaptée au rôle « hôte + moteur
de plugins ».

Configuration (`/etc/si-agent/agent.json`) :
    {"agent_id": "srv-01", "secret": "...", "central_url": "https://VM:6443/api/si-agent",
     "site": "siege", "host_interval_seconds": 60, "inventory_interval_seconds": 3600,
     "poll_config_seconds": 300, "flush_seconds": 30, "batch_size": 100,
     "queue_path": "/var/lib/si-agent/queue.db", "plugins_dir": "/var/lib/si-agent/plugins",
     "risk_thresholds": {}, "plugins": {"network-neighbors": {"enabled": true}},
     "ca_file": null, "insecure": false}

Échanges avec le central (préfixe /api/v1, signés HMAC, voir protocol.py) :
    GET  /agents/<id>/config        -> {version, host_interval_seconds, risk_thresholds, plugins: [{manifest, body}], remove_plugins: [id]}
    POST /agents/<id>/measurements  <- {measurements: [{task, at, ok, data, error}]}
    GET  /agents/<id>/commands      -> {commands: [{id, type, params}]}
    POST /agents/<id>/commands/<cid>/ack <- {ok, result}

Sécurisation (#422, voir control.py) : les réponses config/commands du
central sont SIGNÉES (refusées sinon), rejeu neutralisé (issued_at
monotone, identifiants de commandes mémorisés), blocage général /
individuel des sondes (configuration, commande, fichier BLOCKED local),
sondes confinées (utilisateur non privilégié, limites, session propre),
journal d'événements remonté au central (`event`), traces verbeuses
(`log_level` / --verbose, `log_file`).

Mesures produites : `host` (collecte complète), `risks` (constats),
`inventory` (outils disponibles, plugins installés), `plugin:<id>` et
`event`.
"""
import json
import logging
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

from . import control, publish as publish_lib, host, netview, plugins, protocol, review, risks
from .localqueue import LocalQueue

# #440 : sous Windows 10/11, les collecteurs viennent de winhost.py (scripts
# PowerShell livrés) ; le reste du paquet (protocole, file locale, sondes
# python/powershell, commandes) est commun.
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
if IS_WINDOWS:
    from . import winhost as _plat
    _collect_all, _collect_activity, _collect_hardware, _collect_netview = _plat.collect_all, _plat.collect_activity, _plat.collect_hardware, _plat.collect_netview
    _collect_tools = _plat.collect_tools
elif IS_MACOS:
    # #451 : sous macOS, les collecteurs viennent de machost.py (commandes
    # natives sw_vers/sysctl/vm_stat/df/launchctl/lsof/ifconfig/...) ; le
    # reste du paquet (protocole, file locale, sondes, confinement setuid)
    # est commun avec Linux.
    from . import machost as _plat
    _collect_all, _collect_activity, _collect_hardware, _collect_netview = _plat.collect_all, _plat.collect_activity, _plat.collect_hardware, _plat.collect_netview
    _collect_tools = _plat.collect_tools
else:
    _collect_all, _collect_activity, _collect_hardware, _collect_netview = host.collect_all, review.collect_activity, review.collect_hardware, netview.collect
    _collect_tools = host.collect_tools


def _euid():
    return os.geteuid() if hasattr(os, "geteuid") else -1

_log = logging.getLogger("si_agent")

if IS_WINDOWS:
    _PROGRAM_DATA = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "si-agent")
    DEFAULT_CONFIG_PATH = os.path.join(_PROGRAM_DATA, "agent.json")
    _ETC_DIR, _VAR_DIR = _PROGRAM_DATA, _PROGRAM_DATA
elif IS_MACOS:
    # conventions macOS pour un LaunchDaemon (#451)
    _PROGRAM_DATA = None
    _ETC_DIR, _VAR_DIR = "/usr/local/etc/si-agent", "/usr/local/var/lib/si-agent"
    DEFAULT_CONFIG_PATH = os.path.join(_ETC_DIR, "agent.json")
else:
    _PROGRAM_DATA = None
    _ETC_DIR, _VAR_DIR = "/etc/si-agent", "/var/lib/si-agent"
    DEFAULT_CONFIG_PATH = "/etc/si-agent/agent.json"
DEFAULTS = {
    "site": "default",
    "host_interval_seconds": 60,
    "inventory_interval_seconds": 3600,
    "netview_interval_seconds": 300,
    "poll_config_seconds": 300,
    "commands_poll_seconds": 60,
    "flush_seconds": 30,
    "batch_size": 100,
    "queue_path": os.path.join(_VAR_DIR, "queue.db"),
    "plugins_dir": os.path.join(_VAR_DIR, "plugins"),
    "risk_thresholds": {},
    "plugins": {},
    "ca_file": None,
    "ca_fingerprint": None,
    "insecure": False,
    # #422
    "state_path": os.path.join(_VAR_DIR, "state.json"),
    "block_file": os.path.join(_ETC_DIR, "BLOCKED"),
    "require_signed_responses": True,
    "plugins_user": "nobody",
    "plugin_max_memory_mb": 4096,  # #577 : RLIMIT_AS (espace d'adressage, pas la RSS) -- 512 faisait planter les binaires Go (docker : « failed to reserve page summary memory »)
    "log_level": "INFO",
    "log_file": None,
}


def load_config(path=DEFAULT_CONFIG_PATH):
    with open(path, "r") as fh:
        cfg = json.load(fh)
    for key in ("agent_id", "secret", "central_url"):
        if not cfg.get(key):
            raise ValueError("configuration : champ '%s' manquant dans %s" % (key, path))
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    cfg["central_url"] = cfg["central_url"].rstrip("/")
    return cfg


class HttpClient(object):
    """Client HTTP minimal signé (urllib), même contrat que
    netprobe_agent.agent.HttpClient : (status, dict|None), jamais
    d'exception -- une erreur réseau devient (0, None)."""

    # #474 : après une panne réseau sur le central principal, le secours est
    # utilisé ; le principal est réessayé toutes les RETRY_PRIMARY_S secondes.
    RETRY_PRIMARY_S = 600

    # #682 : au plus une régénération du faisceau de confiance par heure
    CA_REFRESH_MIN_S = 3600

    def __init__(self, base_url, device_id, secret, timeout=15, ca_file=None, insecure=False,
                 fallback_url=None, fallback_ca_file=None, clock=time.monotonic, ca_refresher=None):
        self.base_url, self.device_id, self.secret, self.timeout = base_url.rstrip("/"), device_id, secret, timeout
        self.insecure = bool(insecure)
        self.ca_file, self.ca_refresher, self._ca_refreshed_at = ca_file, ca_refresher, None
        self.ssl_context = self._context(self.base_url, ca_file, insecure)
        # #474 : central de SECOURS (ex. nom public derrière un frontal, joignable
        # depuis Internet) avec sa propre confiance TLS (fallback_ca_file ; None =
        # magasin système, ex. certificat Let's Encrypt du frontal).
        self.fallback_url = fallback_url.rstrip("/") if fallback_url else None
        self.fallback_context = self._context(self.fallback_url, fallback_ca_file, insecure) if self.fallback_url else None
        self.on_fallback = False
        self._clock = clock
        self._fallback_since = None
        # Dernière réponse brute (corps, en-têtes) -- l'agent y vérifie la
        # signature du central (#422) sans que le contrat (status, body)
        # change pour les appelants.
        self.last_raw = b""
        self.last_headers = {}
        self.clock_hint_reported = None

    @staticmethod
    def _context(base_url, ca_file, insecure):
        if not base_url:
            return None
        if base_url.lower().startswith("https"):
            if insecure:
                _log.warning("TLS non vérifié vers %s (insecure=true) -- dépannage uniquement", base_url)
                return ssl._create_unverified_context()  # noqa: SLF001
            ctx = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
            if ca_file:
                # #521 : la CA interne d'origine (#495) n'a pas d'extension keyUsage ;
                # Python 3.13 (OpenSSL 3) la refuse en mode strict (« CA cert does not
                # include key usage extension »). Avec une CA ÉPINGLÉE par l'agent la
                # vérification stricte n'ajoute rien : on la relâche pour ce seul cas,
                # jamais pour le magasin système. La bascule de CA (#496) rendra ce
                # contournement inutile.
                ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
            return ctx
        if not base_url.lower().startswith("http://127.") and not base_url.lower().startswith("http://localhost"):
            _log.warning("central en HTTP clair (%s) -- réservé au test ; utiliser https + ca_file", base_url)
        return None

    @property
    def current_url(self):
        return self.fallback_url if self.on_fallback else self.base_url

    def _targets(self):
        """Ordre d'essai : principal puis secours ; en mode secours, le
        principal est réessayé d'abord une fois le délai écoulé."""
        if not self.fallback_url:
            return [(self.base_url, self.ssl_context, False)]
        primary, fallback = (self.base_url, self.ssl_context, False), (self.fallback_url, self.fallback_context, True)
        if self.on_fallback and self._fallback_since is not None and self._clock() - self._fallback_since < self.RETRY_PRIMARY_S:
            return [fallback, primary]
        return [primary, fallback]

    def request(self, method, path, body=None):
        body_bytes = protocol.canonical_json(body) if body is not None else b""
        headers = protocol.auth_headers(self.device_id, self.secret, method, path, body_bytes)
        status, data = 0, None
        for base_url, ctx, is_fallback in self._targets():
            status, data = self._request_one(base_url, ctx, method, path, body, body_bytes, headers)
            if status != 0:
                if is_fallback != self.on_fallback:
                    _log.warning("central %s : %s", "de secours utilisé" if is_fallback else "principal de retour", base_url)
                    self.on_fallback = is_fallback
                    self._fallback_since = self._clock() if is_fallback else None
                break
        return status, data

    def send_raw(self, method, path, data=b"", timeout=120, content_type="application/octet-stream"):
        """#634 : requête signée à corps brut (morceau d'image). Le chemin signé inclut la requête (?offset=)."""
        headers = protocol.auth_headers(self.device_id, self.secret, method, path, data)
        headers["Content-Type"] = content_type
        req = urllib.request.Request(self.current_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.fallback_context if self.on_fallback else self.ssl_context) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw.decode("utf-8")) if raw else {}
                except ValueError:
                    return resp.status, None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                return exc.code, {"error": raw[:200].decode("utf-8", "replace")}

    def get_raw(self, path, timeout=120):
        """#522 : GET NON signé d'un contenu brut du central (archive de l'agent
        servie par /package), même TLS et même CA que les dépôts, central de
        secours compris. Lève en cas d'échec."""
        last = None
        for base, ctx in ((self.base_url, self.ssl_context), (self.fallback_url, self.fallback_context)):
            if not base:
                continue
            try:
                req = urllib.request.Request(base + path, headers={"User-Agent": "si-agent"})
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return resp.read()
            except Exception as exc:  # noqa: BLE001
                last = exc
        raise RuntimeError(str(last) if last else "aucune URL de central")

    def download_signed(self, path, dest, chunk=8 * 1024 * 1024, timeout=600):
        """#658 : GET signé d'un gros fichier du central écrit en continu dans `dest` (reprise par Range sur un .part)."""
        part = dest + ".part"
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = protocol.auth_headers(self.device_id, self.secret, "GET", path, b"")
        if have:
            headers["Range"] = "bytes=%d-" % have
        req = urllib.request.Request(self.current_url + path, method="GET", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=self.fallback_context if self.on_fallback else self.ssl_context) as resp:
            if have and resp.status != 206:
                have = 0
            with open(part, "ab" if have else "wb") as fh:
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    fh.write(data)
        os.replace(part, dest)
        return dest

    def _request_one(self, base_url, ctx, method, path, body, body_bytes, headers):
        req = urllib.request.Request(base_url + path, data=body_bytes if body is not None else None,
                                     method=method, headers=headers)
        started = time.monotonic()
        self.last_raw, self.last_headers = b"", {}
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                raw = resp.read()
                self.last_raw, self.last_headers = raw, dict(resp.headers.items())
                _log.debug("%s %s -> %s (%d octets, %.0f ms)", method, path, resp.status, len(raw), (time.monotonic() - started) * 1000)
                try:
                    return resp.status, json.loads(raw.decode("utf-8")) if raw else {}
                except ValueError:
                    return resp.status, None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            self.last_raw, self.last_headers = raw, dict(exc.headers.items()) if exc.headers else {}
            _log.debug("%s %s -> HTTP %s (%.0f ms)", method, path, exc.code, (time.monotonic() - started) * 1000)
            try:
                return exc.code, json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                return exc.code, None
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            hint = clock_hint(str(exc))
            _log.warning("central injoignable (%s %s) : %s%s", method, path, exc, (" -- " + hint) if hint else "")
            if hint and not self.clock_hint_reported:
                self.clock_hint_reported = hint
            if not hint and base_url == self.base_url and "CERTIFICATE_VERIFY_FAILED" in str(exc):
                self.refresh_ca()
            return 0, None

    def refresh_ca(self):
        """#682 : la chaîne du central a changé (renouvellement Let's Encrypt, autre
        racine) -- on régénère le faisceau (Windows : central-ca.ps1) et on reconstruit
        le contexte TLS ; la requête suivante l'utilise. Au plus une fois par heure."""
        if not self.ca_refresher or not self.ca_file:
            return False
        now = self._clock()
        if self._ca_refreshed_at is not None and now - self._ca_refreshed_at < self.CA_REFRESH_MIN_S:
            return False
        self._ca_refreshed_at = now
        try:
            ok = self.ca_refresher(self.base_url, self.ca_file)
        except Exception as exc:  # noqa: BLE001
            _log.warning("régénération du faisceau de confiance impossible : %s", exc)
            return False
        if not ok:
            _log.warning("régénération du faisceau de confiance échouée (%s)", self.ca_file)
            return False
        try:
            self.ssl_context = self._context(self.base_url, self.ca_file, self.insecure)
        except (OSError, ssl.SSLError) as exc:
            _log.warning("faisceau de confiance régénéré illisible (%s) : %s", self.ca_file, exc)
            return False
        _log.info("faisceau de confiance régénéré (%s)", self.ca_file)
        return True


def windows_ca_refresher(script, run=None):
    """#682 : régénérateur Windows -- relance central-ca.ps1 (déposé par
    install.ps1 -SystemCa) qui reconstruit la chaîne via le magasin Windows."""
    def refresh(central, out):
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Central", central, "-Out", out]
        if run is not None:
            return run(cmd)
        import subprocess
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120).returncode == 0
    return refresh


def clock_hint(err):
    """#626 : un certificat « pas encore valide » ou « expiré » alors que le central
    vient d'être installé trahit presque toujours l'horloge DU POSTE (double
    amorçage Windows/Linux : horloge matérielle en UTC lue comme heure locale,
    pile vide, VM restaurée). Pure."""
    e = (err or "").lower()
    if "not yet valid" in e:
        return "horloge du poste EN RETARD (certificat pas encore valide) : régler l'heure (double amorçage : RealTimeIsUniversal=1 sous Windows)"
    if "has expired" in e or "certificate expired" in e:
        return "certificat du central expiré, ou horloge du poste EN AVANCE : vérifier l'heure du poste puis le certificat"
    return None


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class Agent(object):
    def __init__(self, cfg, http=None, cmd=host.run_cmd, files=host.read_file, clock=time.time, queue=None,
                 store=None, usage=None, which=None, exists=None):
        self.cfg = cfg
        self.agent_id = cfg["agent_id"]
        self._started_at = clock()
        self._update_job = None
        self._upload_job = None
        self.http = http or HttpClient(cfg["central_url"], cfg["agent_id"], cfg["secret"],
                                       ca_file=cfg.get("ca_file"), insecure=bool(cfg.get("insecure")),
                                       fallback_url=cfg.get("central_fallback_url"), fallback_ca_file=cfg.get("fallback_ca_file"),
                                       ca_refresher=windows_ca_refresher(cfg["ca_refresh_script"])
                                       if IS_WINDOWS and cfg.get("ca_system_bundle") and cfg.get("ca_refresh_script") else None)
        self.cmd, self.files, self.clock = cmd, files, clock
        self.usage = usage or __import__("shutil").disk_usage
        self.which = which or __import__("shutil").which
        self.exists = exists or host.host_exists
        self.queue = queue or LocalQueue(cfg["queue_path"])
        self.store = store or plugins.PluginStore(cfg["plugins_dir"])
        if hasattr(self.store, "ensure_permissions"):
            n = self.store.ensure_permissions()
            if n:
                _log.info("droits des sondes normalisés (%d chemin(s)) pour l'exécution non privilégiée", n)
        self.config_version = None
        self._prev_cpu = None
        self._next_host = 0
        self._next_inventory = 0
        self._next_netview = 0
        self.last_netview = None
        from . import introspect as _intro
        self.tracker = _intro.Tracker(clock=time.time)   # #616 : empreinte propre de l'agent
        self._next_self = 0
        self._bench_until = 0.0
        self._bench_factor = 1
        self._image_job = None     # #621 : image P2V en cours {started, target_file, pid, last_report}
        self._next_startup = 0     # #613 : lanceurs au démarrage (Windows)
        self._next_watchdog = 0    # #613 : chien de garde applicatif
        self.last_startup = None
        self.last_watchdog = None
        self._next_plugin = {}
        # #547 : publication locale (serveur + dernier contenu reçu du central)
        self._publish_server = None
        self._next_publish = 0
        self.publish_payload = None
        self._last_poll = 0
        self._last_commands = 0
        self._last_flush = 0
        self._last_purge = 0
        self.last_central_contact = None
        self.last_host_data = None
        self.last_risks = []
        # #422 : état persistant (blocage, commandes vues, dernière config)
        self.state = control.load_state(cfg.get("state_path") or "")
        self.central_blocked = False
        self.central_block_reason = None
        self._auth_refused_reported = False
        if bool(cfg.get("insecure")):
            self.event("tls-insecure", "warning", "TLS non vérifié vers le central (insecure=true)")

    # -- événements (#422) ------------------------------------------------
    def event(self, kind, severity, message, details=None):
        """Journal d'exploitation / sécurité : tracé localement ET mis en
        file vers le central comme mesure `event`."""
        log = {"info": _log.info, "warning": _log.warning, "critical": _log.error}.get(severity, _log.info)
        log("événement %s : %s%s", kind, message, (" -- " + json.dumps(details, ensure_ascii=False)) if details else "")
        m = control.make_event(self.agent_id, kind, severity, message, details, now=self.clock())
        self.queue.put(m)
        return m

    def _save_state(self):
        path = self.cfg.get("state_path")
        if not path:
            return
        try:
            control.save_state(path, self.state)
        except OSError as exc:
            _log.error("état non sauvegardé (%s) : %s", path, exc)

    def _verified(self, what):
        """Vérifie la signature de la DERNIÈRE réponse du client HTTP.
        Sans en-têtes de signature et sans exigence configurée (tests,
        centraux anciens), on laisse passer en le journalisant."""
        raw = getattr(self.http, "last_raw", None)
        headers = getattr(self.http, "last_headers", None)
        if raw is None or headers is None:
            return True
        ok, why = control.verify_response(self.cfg["secret"], headers, raw)
        if ok:
            return True
        if not self.cfg.get("require_signed_responses", True) and why == "réponse non signée par le central":
            _log.debug("%s : réponse non signée acceptée (require_signed_responses=false)", what)
            return True
        self.event("central-response-rejected", "critical", "%s : %s -- ignoré" % (what, why))
        return False

    # -- blocage (#422) ----------------------------------------------------
    def local_block_file(self):
        bf = self.cfg.get("block_file")
        return bool(bf) and bool(self.exists(bf))

    def is_blocked(self):
        return control.is_blocked(self.state, self.local_block_file(), self.central_blocked)

    def block_reason(self):
        return control.block_reason(self.state, self.local_block_file(), self.central_block_reason)

    def set_blocked(self, blocked, reason=None, source="command"):
        was = bool(self.state.get("blocked"))
        self.state["blocked"] = bool(blocked)
        self.state["blocked_reason"] = reason if blocked else None
        self.state["blocked_at"] = _iso(self.clock()) if blocked else None
        self._save_state()
        if was != bool(blocked):
            self.event("blocked" if blocked else "unblocked", "warning" if blocked else "info",
                       ("blocage général des sondes (%s)" % (reason or source)) if blocked else "déblocage général des sondes (%s)" % source)
        return True

    def set_plugin_blocked(self, pid, blocked, reason=None, source="command"):
        bp = self.state.setdefault("blocked_plugins", {})
        was = pid in bp
        if blocked:
            bp[pid] = {"reason": reason, "at": _iso(self.clock()), "source": source}
        else:
            bp.pop(pid, None)
        self._save_state()
        if was != bool(blocked):
            self.event("plugin-blocked" if blocked else "plugin-unblocked", "warning" if blocked else "info",
                       "sonde %s %s (%s)" % (pid, "bloquée" if blocked else "débloquée", reason or source), {"plugin": pid})
        return True

    # -- configuration depuis le central ----------------------------------
    def refresh_config(self, force=False):
        now = self.clock()
        if not force and now - self._last_poll < self.cfg["poll_config_seconds"]:
            return False
        self._last_poll = now
        status, body = self.http.request("GET", "%s/agents/%s/config" % (protocol.API_PREFIX, self.agent_id))
        if status in (401, 403):
            _log.error("central : authentification refusée (%s) -- vérifier agent_id/secret", status)
            if not self._auth_refused_reported:
                self._auth_refused_reported = True
                self.event("central-auth-refused", "warning", "le central refuse l'authentification de cet agent (%s)" % status)
            return False
        if status != 200 or not isinstance(body, dict):
            return False
        if not self._verified("configuration"):
            return False
        self.last_central_contact = now
        self._auth_refused_reported = False
        if getattr(self.http, "clock_hint_reported", None):
            self.event("clock-skew", "warning", "le central a été injoignable pour cause d'horloge : " + self.http.clock_hint_reported)
            self.http.clock_hint_reported = None
        # Blocage déclaratif : appliqué à CHAQUE lecture, même version inchangée
        central_blocked = bool(body.get("blocked"))
        if central_blocked != self.central_blocked:
            self.central_blocked = central_blocked
            self.central_block_reason = body.get("blocked_reason")
            self.event("blocked" if central_blocked else "unblocked", "warning" if central_blocked else "info",
                       ("blocage général par le central (%s)" % (body.get("blocked_reason") or "sans motif")) if central_blocked
                       else "déblocage général par le central")
        if body.get("version") == self.config_version:
            return True
        issued = body.get("issued_at")
        if isinstance(issued, (int, float)) and issued < (self.state.get("last_config_issued_at") or 0):
            self.event("config-replayed", "critical", "configuration plus ancienne que la dernière appliquée -- rejeu ? ignorée",
                       {"issued_at": issued, "last": self.state.get("last_config_issued_at")})
            return False
        self.config_version = body.get("version")
        if isinstance(issued, (int, float)):
            self.state["last_config_issued_at"] = issued
        for key in ("host_interval_seconds", "inventory_interval_seconds", "netview_interval_seconds"):
            if isinstance(body.get(key), (int, float)) and body[key] >= 10:
                self.cfg[key] = body[key]
        # #627 : cadence de relevé des commandes imposée par le central (5 s mini) -- le central local
        # la resserre pour le parcours interactif ; le hub laisse la valeur du poste (60 s)
        if isinstance(body.get("commands_poll_seconds"), (int, float)) and body["commands_poll_seconds"] >= 5:
            self.cfg["commands_poll_seconds"] = body["commands_poll_seconds"]
        if isinstance(body.get("publish"), dict):
            self.cfg["publish"] = body["publish"]
        elif "publish" in body:
            self.cfg["publish"] = None
        if isinstance(body.get("risk_thresholds"), dict):
            self.cfg["risk_thresholds"] = body["risk_thresholds"]
        installed = 0
        for item in body.get("plugins") or []:
            manifest, script = (item or {}).get("manifest"), (item or {}).get("body")
            if not isinstance(manifest, dict) or not isinstance(script, str):
                continue
            existing = self.store.get(manifest.get("id", ""))
            if existing and existing.get("sha256") == plugins.sha256_text(script) and str(existing.get("version")) == str(manifest.get("version")) \
                    and bool(existing.get("privileged")) == bool(manifest.get("privileged")):
                changed = False
                if bool(existing.get("enabled")) != bool(manifest.get("enabled")):
                    self.store.set_enabled(manifest["id"], manifest.get("enabled")); changed = True
                if bool(existing.get("blocked")) != bool(manifest.get("blocked")):
                    self.store.set_flag(manifest["id"], "blocked", bool(manifest.get("blocked"))); changed = True
                    self.event("plugin-blocked" if manifest.get("blocked") else "plugin-unblocked", "warning" if manifest.get("blocked") else "info",
                               "sonde %s %s par le central" % (manifest["id"], "bloquée" if manifest.get("blocked") else "débloquée"), {"plugin": manifest["id"]})
                if changed:
                    _log.debug("plugin %s : drapeaux mis à jour", manifest["id"])
                continue
            if self.is_blocked():
                _log.warning("plugin %s non installé : agent bloqué (%s)", manifest.get("id"), self.block_reason())
                continue
            ok, why = self.store.install(manifest, script, source="central", secret=self.cfg["secret"])
            if ok:
                installed += 1
                self._next_plugin.pop(manifest["id"], None)
                self.event("plugin-installed", "info", "sonde %s v%s %s" % (manifest["id"], manifest.get("version"), "mise à jour" if existing else "installée"),
                           {"plugin": manifest["id"], "version": str(manifest.get("version")), "sha256": plugins.sha256_text(script),
                            "privileged": bool(manifest.get("privileged"))})
            else:
                self.event("plugin-refused", "warning", "sonde %s refusée : %s" % (manifest.get("id"), why), {"plugin": manifest.get("id")})
        for pid in body.get("remove_plugins") or []:
            if self.store.remove(str(pid)):
                self._next_plugin.pop(pid, None)
                self.event("plugin-removed", "info", "sonde %s retirée par le central" % pid, {"plugin": pid})
        self._save_state()
        self.event("config-applied", "info", "configuration %s appliquée (%d sonde(s) installée(s))" % (self.config_version, installed),
                   {"version": self.config_version, "installed": installed})
        return True

    # -- commandes du tableau de bord --------------------------------------
    def poll_commands(self, force=False):
        now = self.clock()
        if not force and now - self._last_commands < self.cfg["commands_poll_seconds"]:
            return []
        self._last_commands = now
        status, body = self.http.request("GET", "%s/agents/%s/commands" % (protocol.API_PREFIX, self.agent_id))
        if status != 200 or not isinstance(body, dict):
            return []
        if not self._verified("commandes"):
            return []
        self.last_central_contact = now
        done = []
        for c in body.get("commands") or []:
            cid = str((c or {}).get("id") or "")
            if not cid or not control.remember_command(self.state, cid):
                self.event("command-replayed", "warning", "commande %s déjà exécutée -- ignorée" % (cid or "?"), {"command": cid})
                continue
            self._save_state()
            result = self.execute_command(c)
            _log.debug("commande %s (%s) -> %s", cid, c.get("type"), json.dumps(result, ensure_ascii=False)[:300])
            self.http.request("POST", "%s/agents/%s/commands/%s/ack" % (protocol.API_PREFIX, self.agent_id, cid), result)
            done.append((c, result))
        return done

    def execute_command(self, c, deferred=False):
        ctype = (c or {}).get("type")
        params = (c or {}).get("params") or {}
        try:
            if params.get("at") and not deferred:
                # #633 : exécution différée (heure locale du poste) -- conservée dans l'état, exécutée par run_deferred()
                from . import sysctl
                due, err = sysctl.parse_at(params.get("at"), self.clock())
                if err:
                    return {"ok": False, "error": err}
                job = {"id": str(c.get("id")), "type": ctype, "params": {k: v for k, v in params.items() if k != "at"}, "due": due, "at": params.get("at")}
                self.state.setdefault("deferred", []).append(job)
                self._save_state()
                self.event("deferred", "info", "commande %s programmée pour %s" % (ctype, params.get("at")), {"command": c.get("id"), "due": _iso(due)})
                return {"ok": True, "result": {"deferred_until": _iso(due), "message": "programmé pour %s (heure du poste)" % params.get("at")}}
            if ctype == "windows_update":
                # #633 : état (synchrone) ou installation (détachée, suivie) via win/winupdate.ps1
                if not IS_WINDOWS:
                    return {"ok": False, "error": "Windows Update : Windows seulement"}
                from . import sysctl, winhost
                plan, err = sysctl.validate_update(params)
                if err:
                    return {"ok": False, "error": err}
                script = winhost.script_path("winupdate")
                if plan["action"] == "status":
                    r = self.cmd(sysctl.update_argv(winhost.POWERSHELL, script, plan), timeout=300)
                    data, err = winhost.parse_ps(r, "winupdate")
                    if data is None:
                        return {"ok": False, "error": err}
                    self._store_measure("winupdate", data)
                    return {"ok": not data.get("error"), "error": data.get("error"), "result": dict(data, message=sysctl.summarize_update(data))}
                if self._update_job:
                    return {"ok": False, "error": "une installation de mises à jour est déjà en cours"}
                out_file = os.path.join(os.path.dirname(os.path.abspath(self.cfg.get("state_path") or ".")), "winupdate-result.json")
                try:
                    os.remove(out_file)
                except OSError:
                    pass
                import subprocess
                proc = subprocess.Popen(sysctl.update_argv(winhost.POWERSHELL, script, plan, out_file), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=0x00000008 | 0x00000200)
                self._update_job = {"proc": proc, "out": out_file, "started": self.clock(), "reboot": plan["reboot"], "command": c.get("id"), "kbs": plan["kbs"]}
                self.event("update-started", "info", "installation Windows Update lancée (%s)" % (", ".join(plan["kbs"]) or "toutes les mises à jour en attente"), {"command": c.get("id")})
                return {"ok": True, "result": {"message": "installation lancée -- suivi par événements (update-finished)", "kbs": plan["kbs"], "reboot_after": plan["reboot"]}}
            if ctype == "protection":
                # #633 : pare-feu / Defender temps réel (état ou bascule) via win/protection.ps1
                if not IS_WINDOWS:
                    return {"ok": False, "error": "protection : Windows seulement"}
                from . import sysctl, winhost
                plan, err = sysctl.validate_protection(params)
                if err:
                    return {"ok": False, "error": err}
                if self.is_blocked() and not plan["status_only"]:
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                r = self.cmd(sysctl.protection_argv(winhost.POWERSHELL, winhost.script_path("protection"), plan), timeout=120)
                data, err = winhost.parse_ps(r, "protection")
                if data is None:
                    return {"ok": False, "error": err}
                self._store_measure("protection", data)
                if not plan["status_only"]:
                    self.event("command-protection", "warning", "protection : %s%s" % (", ".join("%s=%s" % (k, v) for k, v in (("pare-feu", plan["firewall"]), ("defender", plan["defender"])) if v),
                               " -- " + " ; ".join(data.get("errors")) if data.get("errors") else ""), {"command": c.get("id"), "profiles": plan["profiles"]})
                ok = not data.get("errors")
                return {"ok": ok, "error": " ; ".join(data.get("errors")) if not ok else None, "result": dict(data, message=sysctl.summarize_protection(data))}
            if ctype == "remote_desktop":
                # #636 : Bureau à distance intégré de Windows (service + pare-feu). L'admin se connecte avec SES
                # identifiants ; aucun compte créé ici. Chaque bascule est journalisée.
                if not IS_WINDOWS:
                    return {"ok": False, "error": "Bureau à distance : Windows seulement"}
                from . import sysctl, winhost
                plan, err = sysctl.validate_rdp(params)
                if err:
                    return {"ok": False, "error": err}
                if self.is_blocked() and plan["action"] != "status":
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                r = self.cmd(sysctl.rdp_argv(winhost.POWERSHELL, winhost.script_path("rdp"), plan), timeout=120)
                data, err = winhost.parse_ps(r, "rdp")
                if data is None:
                    return {"ok": False, "error": err}
                self._store_measure("rdp", data)
                if plan["action"] != "status":
                    self.event("command-rdp", "warning", "Bureau à distance %s%s" % (plan["action"], " -- " + " ; ".join(data.get("errors")) if data.get("errors") else ""), {"command": c.get("id")})
                ok = not data.get("errors")
                return {"ok": ok, "error": " ; ".join(data.get("errors")) if not ok else None, "result": dict(data, message=sysctl.summarize_rdp(data))}
            if ctype == "collect_now":
                m = self.collect_host(force=True)
                return {"ok": True, "result": {"measurements": len(m)}}
            if ctype == "block_all":
                self.set_blocked(True, params.get("reason") or "commande du central")
                return {"ok": True, "result": {"blocked": True}}
            if ctype == "unblock_all":
                self.set_blocked(False, source="commande du central")
                return {"ok": True, "result": {"blocked": self.is_blocked(), "reason": self.block_reason() if self.is_blocked() else None}}
            if ctype in ("block_plugin", "unblock_plugin"):
                pid = str(params.get("id", ""))
                if not pid:
                    return {"ok": False, "error": "params.id requis"}
                self.set_plugin_blocked(pid, ctype == "block_plugin", params.get("reason"), source="commande du central")
                return {"ok": True, "result": {"plugin": pid, "blocked": ctype == "block_plugin"}}
            if ctype == "run_plugin":
                m = self.store.get(str(params.get("id", "")))
                if m is None:
                    return {"ok": False, "error": "plugin inconnu"}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                if control.plugin_blocked(self.state, m):
                    return {"ok": False, "error": "sonde bloquée"}
                meas = self.run_one_plugin(m)
                return {"ok": bool(meas.get("ok")), "result": meas.get("data"), "error": meas.get("error")}
            if ctype in ("enable_plugin", "disable_plugin"):
                ok = self.store.set_enabled(str(params.get("id", "")), ctype == "enable_plugin")
                return {"ok": ok, "error": None if ok else "plugin inconnu"}
            if ctype == "remove_plugin":
                ok = self.store.remove(str(params.get("id", "")))
                self._next_plugin.pop(params.get("id"), None)
                return {"ok": ok, "error": None if ok else "plugin inconnu"}
            if ctype == "flush":
                return {"ok": True, "result": {"sent": self.flush(force=True)}}
            if ctype == "vm_action":
                # #572 : contrôle d'une VM / d'un conteneur Proxmox (qm / pct) depuis le hub
                from . import vmctl
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                if str(params.get("action") or "") == "import_disk":
                    res = self.import_disk(params)          # #658 : image depuis le central, décompression, importdisk, rattachement
                else:
                    res = vmctl.run(self.cmd, params)
                self.event("command-vm", "info" if res.get("ok") else "warning",
                           "VM %s : %s%s" % (params.get("vmid"), params.get("action"), "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": params})
                return res
            if ctype == "vrrp_set":
                # #656 : bascule de rôle keepalived -- priorité VRRP de l'instance (le VIP suit la priorité la plus haute)
                from . import vrrpctl
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                res = vrrpctl.run(self.cmd, params)
                self.event("command-vrrp", "info" if res.get("ok") else "warning",
                           "VRRP %s : priorité %s%s" % (params.get("instance"), params.get("priority"), "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": params})
                return res
            if ctype == "software_action":
                # #595 : installation / désinstallation d'un logiciel (gestionnaire de paquets du poste), depuis la tuile Licences
                from . import swctl
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                res = swctl.run(self.cmd, params)
                self.event("command-software", "info" if res.get("ok") else "warning",
                           "logiciel %s : %s%s" % (params.get("package"), params.get("action"), "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": params})
                return res
            if ctype == "power_action":
                # #613 : redémarrage / arrêt du poste (ou annulation), acquitté avant l'exécution
                from . import powerctl
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                armed = None
                if params.get("autologon") and params.get("action") == "reboot":
                    # #628 : réouverture de session UNE fois (AutoLogonCount) -- Windows seulement, mot de passe jamais journalisé
                    if not IS_WINDOWS:
                        return {"ok": False, "error": "autologon : Windows seulement"}
                    from . import autologon
                    plan, err = autologon.validate(params.get("autologon"))
                    if err:
                        return {"ok": False, "error": err}
                    try:
                        armed = autologon.apply(plan, self._winlogon_set)
                    except Exception as exc:  # noqa: BLE001
                        return {"ok": False, "error": "autologon : écriture Winlogon impossible (%s)" % exc}
                    self.state["autologon_pending"] = _iso(self.clock())
                    self._save_state()
                    self.event("autologon-armed", "info", "session de %s\\%s rouverte automatiquement au prochain démarrage (une fois)" % (armed["domain"], armed["user"]), {"command": c.get("id")})
                params = {k: v for k, v in params.items() if k != "autologon"}
                res = powerctl.run(self.cmd, params, platform=sys.platform, console_active=self._console_active())
                if armed and res.get("ok"):
                    res.setdefault("result", {})["autologon"] = armed
                elif armed:
                    self._autologon_cleanup(force=True)
                self.event("command-power", "warning" if res.get("ok") and params.get("action") != "cancel" else "info" if res.get("ok") else "warning",
                           "alimentation : %s%s" % (params.get("action"), "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": params})
                return res
            if ctype == "wol":
                # #613 : réveil d'un poste du même segment (paquet magique émis par cet agent)
                from . import powerctl
                res = powerctl.send_wol(params)
                self.event("command-wol", "info" if res.get("ok") else "warning",
                           "réveil %s%s" % (params.get("mac"), "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": params})
                return res
            if ctype == "startup_action":
                # #613 : activer / désactiver un lanceur au démarrage (Windows), puis recollecte
                from . import startupctl
                if not IS_WINDOWS:
                    return {"ok": False, "error": "lanceurs au démarrage : Windows seulement"}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                res = startupctl.run(self.cmd, params)
                self.event("command-startup", "info" if res.get("ok") else "warning",
                           "lanceur %s : %s%s" % (params.get("name"), "activé" if params.get("enable") else "désactivé", "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": params})
                if res.get("ok"):
                    self.collect_startup(force=True)
                return res
            if ctype == "browse":
                # #627 : lecteurs / sous-dossiers du poste, lecture seule, pour choisir une cible depuis le hub
                from . import browsectl
                import shutil as _sh
                res = browsectl.run(params, usage=_sh.disk_usage)
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "image_transfer":
                # #634 : transférer (ou reprendre) une image déjà sur le poste
                return self.start_upload(str(params.get("path") or ""), c.get("id"), delete_after=bool(params.get("delete_after")))
            if ctype == "image_host":
                # #621 : image complète du poste à chaud (Disk2vhd, VSS), détachée ; suivi dans la boucle
                res = self.start_image(params, c.get("id"))
                return res
            if ctype == "bench":
                # #616 : banc de charge -- collectes et sondes à cadence forcée pendant N minutes, introspection toutes les 30 s
                from . import introspect as _intro
                until, factor, err = _intro.plan_bench(params, self.clock())
                if err:
                    return {"ok": False, "error": err}
                if params.get("stop"):
                    self._bench_until = 0.0
                    self.event("bench-stopped", "info", "banc de charge arrêté", {"command": c.get("id")})
                    return {"ok": True, "result": {"stopped": True}}
                self._bench_until, self._bench_factor = until, factor
                self._next_plugin = {}
                self._next_host = 0; self._next_netview = 0; self._next_self = 0
                self.event("bench-started", "warning", "banc de charge : %d min, cadence ×%d (sondes et collectes)" % ((until - self.clock()) // 60, factor),
                           {"command": c.get("id"), "until": _iso(until), "factor": factor})
                return {"ok": True, "result": {"until": _iso(until), "factor": factor, "message": "banc lancé pour %d min (×%d)" % ((until - self.clock()) // 60, factor)}}
            if ctype == "watchdog_config":
                # #613 : liste des applications surveillées, persistée dans state.json
                from . import watchdog
                cfg, errors = watchdog.normalize_config(params)
                self.state["watchdog"] = cfg
                self.state["watchdog_state"] = {}
                self._save_state()
                self._next_watchdog = 0
                self.event("watchdog-config", "info", "chien de garde : %d application(s) surveillée(s)%s" % (len(cfg["apps"]), " ; ignorées : " + " ; ".join(errors) if errors else ""), {"command": c.get("id")})
                self.run_watchdog(force=True)
                return {"ok": True, "result": {"config": cfg, "errors": errors}, "error": None}
            if ctype == "update":
                # #522 : mise à jour décidée par le central (canal bêta / activation
                # générale) ; téléchargement par le même TLS, SHA-256 vérifié,
                # installeur --upgrade détaché, acquittement « démarré » avant l'arrêt
                from . import updater
                res = updater.run_update(self, dict(params, command_id=c.get("id")), fetch=self.http.get_raw)
                self.event("agent-update-started" if res.get("ok") and (res.get("result") or {}).get("started") else "agent-update-refused",
                           "info" if res.get("ok") else "warning", "mise à jour : %s" % (res.get("error") or res.get("result")), {"command": c.get("id")})
                return res
            self.event("command-unknown", "warning", "commande inconnue reçue : %s" % ctype, {"command": c.get("id")})
            return {"ok": False, "error": "commande inconnue : %s" % ctype}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # -- collecte ----------------------------------------------------------
    def collect_host(self, force=False):
        now = self.clock()
        if not force and now < self._next_host:
            return []
        _iv = float(self.cfg["host_interval_seconds"])
        if self._bench_until > now:
            from . import introspect as _intro
            _iv = _intro.forced_interval(_iv, self._bench_factor)
        self._next_host = now + _iv
        _t0 = time.time()
        data, self._prev_cpu = _collect_all(files=self.files, cmd=self.cmd, usage=self.usage, which=self.which,
                                            previous_cpu=self._prev_cpu, include_tools=False, exists=self.exists)
        # #428 : activité (processus, sessions, connexions, services actifs)
        data["activity"] = _collect_activity(cmd=self.cmd, files=self.files)
        self.tracker.record("host", time.time() - _t0)  # #616
        self.last_host_data = data
        found = risks.evaluate(data, self.cfg.get("risk_thresholds"))
        self.last_risks = found
        at = _iso(now)
        produced = [
            {"agent_id": self.agent_id, "task": "host", "at": at, "ok": not data.get("partial"),
             "data": data, "error": ("collecte partielle : " + ", ".join(data["partial"])) if data.get("partial") else None},
            {"agent_id": self.agent_id, "task": "risks", "at": at, "ok": True,
             "data": {"risks": found, "summary": risks.summarize(found)}, "error": None},
        ]
        for m in produced:
            self.queue.put(m)
        return produced

    def collect_netview(self, force=False):
        """#428 : découverte passive du réseau (interfaces, routes, voisins,
        connexions, DNS) -- mesure `netview`, jamais un paquet émis."""
        now = self.clock()
        if not force and now < self._next_netview:
            return None
        self._next_netview = now + float(self.cfg.get("netview_interval_seconds") or 300)
        data = _collect_netview(cmd=self.cmd, files=self.files)
        self.last_netview = data
        m = {"agent_id": self.agent_id, "task": "netview", "at": _iso(now), "ok": not data.get("partial"), "data": data,
             "error": ("collecte partielle : " + ", ".join(data["partial"])) if data.get("partial") else None}
        self.queue.put(m)
        return m

    def collect_self(self, force=False):
        """#616 : empreinte de l'agent lui-même (CPU, mémoire, durée des sondes) -- mesure `agent-self`,
        toutes les 60 s (30 s pendant un banc) ; résumé glissant joint à chaque mesure."""
        from . import introspect as _intro
        now = self.clock()
        bench = self._bench_until > now
        if not force and now < self._next_self:
            return None
        if self._bench_until and not bench and self._bench_factor != 1:
            self._bench_factor = 1
            self.event("bench-finished", "info", "banc de charge terminé -- voir la synthèse d'empreinte", {"summary": _intro.summarize(self.tracker.points)})
        self._next_self = now + (30 if bench else float(self.cfg.get("self_interval_seconds") or 60))
        host_load = ((self.last_host_data or {}).get("load") or {}).get("load1") if isinstance((self.last_host_data or {}).get("load"), dict) else None
        try:
            qsize = self.queue.pending_count() if hasattr(self.queue, "pending_count") else None
        except Exception:  # noqa: BLE001
            qsize = None
        point = self.tracker.snapshot(rss_bytes=_intro.read_rss(), queue_size=qsize, host_load1=host_load, bench=bench)
        m = {"agent_id": self.agent_id, "task": "agent-self", "at": _iso(now), "ok": True,
             "data": {"point": point, "summary": _intro.summarize(self.tracker.points), "bench_until": _iso(self._bench_until) if bench else None,
                      "bench_factor": self._bench_factor if bench else None}, "error": None}
        self.queue.put(m)
        return m

    def start_image(self, params, command_id=None):
        """#621 : contrôles (Windows, pas d'image en cours, BitLocker, espace), outil téléchargé et
        vérifié, disk2vhd lancé détaché ; la fin est constatée par follow_image()."""
        from . import imagectl
        if not IS_WINDOWS:
            return self.start_image_linux(params, command_id)
        if self.is_blocked():
            return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
        if self._image_job:
            return {"ok": False, "error": "une image est déjà en cours depuis %s" % _iso(self._image_job["started"])}
        plan, err = imagectl.validate(params)
        if err:
            return {"ok": False, "error": err}
        # BitLocker : une image d'un volume protégé est illisible
        r = self.cmd(["manage-bde.exe", "-status"], timeout=60)
        blocked = imagectl.bitlocker_blocks(imagectl.parse_bitlocker(getattr(r, "stdout", "") or ""), plan["drives"])
        if blocked and not plan["force"]:
            return {"ok": False, "error": "BitLocker actif sur %s : suspendre (manage-bde -protectors -disable X:) ou déchiffrer avant l'image, ou force" % ", ".join(blocked)}
        # espace cible vs espace utilisé des volumes visés
        used = 0
        for d in (plan["drives"] if plan["drives"] != ["*"] else ["C:"]):
            r = self.cmd(["fsutil.exe", "volume", "diskfree", d], timeout=30)
            u = imagectl.used_bytes(getattr(r, "stdout", "") or "")
            if u is not None:
                used += u
        if plan.get("share"):
            # #635 : montage du partage du serveur avec identifiants (WNetAddConnection2, aucune ligne de commande :
            # le mot de passe n'apparaît nulle part), démonté à la fin de l'image
            err = self._mount_share(plan["share"])
            if err:
                return {"ok": False, "error": "partage %s : %s" % (plan["share"]["unc"], err)}
        try:
            import shutil as _sh
            free_target = _sh.disk_usage(plan["target_dir"]).free
        except OSError as exc:
            self._unmount_share(plan.get("share"))
            return {"ok": False, "error": "cible inaccessible : %s" % exc}
        if not imagectl.enough_space(used or None, free_target) and not plan["force"]:
            return {"ok": False, "error": "espace insuffisant sur la cible : %d Go libres pour ~%d Go à écrire (force pour passer outre)" % (free_target // 2**30, int(used * 1.1) // 2**30)}
        # outil
        tools_dir = os.path.join(os.path.dirname(self.cfg.get("state_path") or "."), "tools")
        os.makedirs(tools_dir, exist_ok=True)
        tool = os.path.join(tools_dir, "disk2vhd64.exe")
        if not os.path.exists(tool):
            try:
                import urllib.request as _ur
                with _ur.urlopen(plan["tool_url"], timeout=120) as resp, open(tool + ".part", "wb") as fh:
                    fh.write(resp.read())
                os.replace(tool + ".part", tool)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": "téléchargement de Disk2vhd impossible (%s) : déposer disk2vhd64.exe dans %s" % (exc, tools_dir)}
        if plan["tool_sha256"]:
            import hashlib as _h
            with open(tool, "rb") as fh:
                got = _h.sha256(fh.read()).hexdigest()
            if got != plan["tool_sha256"]:
                os.remove(tool)
                return {"ok": False, "error": "empreinte de disk2vhd64.exe différente (%s) : outil refusé et supprimé" % got[:16]}
        out_file = imagectl.target_file(plan, os.environ.get("COMPUTERNAME") or self.agent_id)
        argv = imagectl.build_argv(tool, plan, out_file)
        log_path = os.path.join(tools_dir, "disk2vhd.log")
        try:
            import subprocess
            with open(log_path, "ab") as logf:
                proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
                                        creationflags=0x00000008 | 0x00000200)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": "lancement de Disk2vhd impossible : %s" % exc}
        self._image_job = {"started": self.clock(), "target_file": out_file, "pid": proc.pid, "last_report": self.clock(), "command": command_id, "proc": proc,
                           "transfer": plan["transfer"], "delete_after": plan["delete_after"], "share": plan.get("share")}
        self.event("image-started", "warning", "image du poste lancée vers %s (%s)" % (out_file, ", ".join(plan["drives"])),
                   {"command": command_id, "target": out_file, "used_bytes": used, "free_target_bytes": free_target})
        return {"ok": True, "result": {"target": out_file, "message": "image lancée (Disk2vhd, instantané VSS) -- suivi par événements", "used_bytes": used}, "error": None}

    def import_disk(self, params):
        """#658 : `source` = central:<agent>/<nom> (image reçue par le central, téléchargée ici par requête signée, reprise
        par Range) ou chemin local sur le nœud ; .zst décompressé ; `qm importdisk` ; puis le disque `unusedN` est
        rattaché (`attach`: scsi0 par défaut, sata0 conseillé pour Windows avant les pilotes VirtIO) et mis en premier au démarrage."""
        from . import vmctl
        p = dict(params or {})
        source = str(p.get("source") or p.get("path") or "")
        import_dir = str(p.get("import_dir") or "/var/lib/vz/import")
        if source.startswith("central:"):
            m = re.match(r"^central:([A-Za-z0-9._-]{1,64})/([A-Za-z0-9._-]{1,120})$", source)
            if not m:
                return {"ok": False, "error": "source : central:<agent>/<nom d'image>"}
            try:
                os.makedirs(import_dir, exist_ok=True)
                local = os.path.join(import_dir, m.group(2))
                self.http.download_signed("%s/agents/%s/images/%s/%s/download" % (protocol.API_PREFIX, self.agent_id, m.group(1), m.group(2)), local)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": "téléchargement de l'image depuis le central : %s" % exc}
            source = local
        if source.endswith(".zst"):
            r = self.cmd(["zstd", "-d", "--rm", "-q", "-f", source], timeout=vmctl.LONG_TIMEOUT)
            if getattr(r, "returncode", 1) != 0:
                return {"ok": False, "error": "décompression zstd : %s" % ((getattr(r, "stderr", "") or "")[-300:] or "échec")}
            source = source[:-4]
        res = vmctl.run(self.cmd, dict(p, action="import_disk", path=source))
        if not res.get("ok"):
            return res
        if p.get("attach", "scsi0"):
            cfg = self.cmd(["qm", "config", str(p.get("vmid"))], timeout=60)
            vol = vmctl.parse_unused(getattr(cfg, "stdout", "") or "")
            argv, err = vmctl.build_attach_argv(int(p.get("vmid")), p.get("attach", "scsi0"), vol, boot=p.get("boot", True))
            if err:
                return {"ok": False, "error": err, "result": res.get("result")}
            r2 = vmctl.interpret(self.cmd(argv, timeout=120))
            if not r2["ok"]:
                return {"ok": False, "error": "rattachement du disque : %s" % r2["error"], "result": res.get("result")}
            res.setdefault("result", {})["attached"] = {"bus": p.get("attach", "scsi0"), "volume": vol}
        if p.get("delete_after", True) and source.startswith(import_dir + "/"):
            try:
                os.remove(source)
            except OSError:
                pass
        return res

    def start_image_linux(self, params, command_id=None):
        """#658 : image à chaud d'un serveur Linux -- dd du disque système (ou `device`) compressé zstd vers `target`
        (stockage SÉPARÉ : refusé si la cible est sur le disque imagé), détachée, suivie par follow_image()."""
        from . import imagectl
        if self.is_blocked():
            return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
        if self._image_job:
            return {"ok": False, "error": "une image est déjà en cours depuis %s" % _iso(self._image_job["started"])}
        plan, err = imagectl.validate_linux(params)
        if err:
            return {"ok": False, "error": err}
        if not os.path.isdir(plan["target_dir"]):
            return {"ok": False, "error": "cible %s absente (monter le partage / le disque d'abord)" % plan["target_dir"]}
        pk = lambda dev: getattr(self.cmd(["lsblk", "-no", "pkname", dev], timeout=20), "stdout", "") or ""
        src = lambda path: (getattr(self.cmd(["findmnt", "-no", "SOURCE", path], timeout=20), "stdout", "") or "").strip().splitlines()
        root_src = src("/")
        device = plan["device"] or imagectl.parent_disk(root_src[0] if root_src else "", pk)
        if not device or not imagectl.DEVICE_RE.match(device):
            return {"ok": False, "error": "disque de la racine introuvable (findmnt/lsblk) : indiquer device"}
        tgt_src = src(plan["target_dir"])
        if tgt_src and imagectl.parent_disk(tgt_src[0], pk) == device and not plan["force"]:
            return {"ok": False, "error": "la cible %s est sur le disque imagé (%s) : utiliser un partage ou un disque séparé" % (plan["target_dir"], device)}
        if self.which("zstd") is None:
            return {"ok": False, "error": "zstd absent : apt install zstd"}
        import shutil as _sh
        try:
            used = _sh.disk_usage("/").used
            free_target = _sh.disk_usage(plan["target_dir"]).free
        except OSError as exc:
            return {"ok": False, "error": "cible inaccessible : %s" % exc}
        if not imagectl.enough_space(used, free_target, margin=0.8) and not plan["force"]:
            return {"ok": False, "error": "espace insuffisant sur la cible : %d Go libres pour ~%d Go utilisés (compressé ; force pour passer outre)" % (free_target // 2**30, used // 2**30)}
        out_file = imagectl.target_file(plan, socket.gethostname() or self.agent_id, ext="img.zst")
        argv = imagectl.build_linux_argv(device, out_file)
        log_path = os.path.join(os.path.dirname(self.cfg.get("state_path") or "."), "image-linux.log")
        try:
            import subprocess
            with open(log_path, "ab") as logf:
                proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": "lancement de dd/zstd impossible : %s" % exc}
        self._image_job = {"started": self.clock(), "target_file": out_file, "pid": proc.pid, "last_report": self.clock(), "command": command_id, "proc": proc,
                           "transfer": plan["transfer"], "delete_after": plan["delete_after"], "share": None}
        self.event("image-started", "warning", "image du serveur lancée : %s -> %s (à chaud, dd + zstd)" % (device, out_file),
                   {"command": command_id, "target": out_file, "device": device, "used_bytes": used, "free_target_bytes": free_target})
        return {"ok": True, "result": {"target": out_file, "device": device, "message": "image lancée (dd | zstd) -- suivi par événements", "used_bytes": used}, "error": None}

    def follow_image(self):
        """#621 : à chaque tour, état du travail d'image détaché."""
        job = self._image_job
        if not job:
            return
        from . import imagectl
        proc = job.get("proc")
        state, det = imagectl.follow(job, os.path.exists, lambda p: os.path.getsize(p) if os.path.exists(p) else 0,
                                     lambda pid: proc is not None and proc.poll() is None, self.clock())
        if state == "progress":
            job["last_report"] = self.clock()
            self.event("image-progress", "info", "image en cours : %.1f Go écrits en %d min" % (det["bytes"] / 2**30, det["seconds"] // 60), dict(det, target=job["target_file"]))
        elif state == "finished":
            self._image_job = None
            self._unmount_share(job.get("share"))
            self.event("image-finished", "info", "image terminée : %.1f Go en %d min -> %s" % (det["bytes"] / 2**30, det["seconds"] // 60, job["target_file"]),
                       dict(det, target=job["target_file"], command=job.get("command"), proxmox=imagectl.PROXMOX_RUNBOOK))
            if job.get("transfer"):
                self.start_upload(job["target_file"], job.get("command"), delete_after=job.get("delete_after"))
        elif state in ("failed", "stalled"):
            if state == "stalled" and proc is not None:
                try:
                    proc.kill()
                except OSError:
                    pass
            self._image_job = None
            self._unmount_share(job.get("share"))
            self.event("image-failed", "critical", "image échouée : %s" % det["reason"], dict(det, target=job["target_file"], command=job.get("command")))

    def _console_active(self):
        """Une session interactive sur la console (Windows : console_user ; ailleurs : tty)."""
        d = self.last_host_data or {}
        if (d.get("accounts") or {}).get("console_user"):
            return True
        return any((s.get("tty") or "") in ("console", "tty1", "tty2") for s in ((d.get("activity") or {}).get("sessions") or []))

    def collect_startup(self, force=False):
        """#613 : lanceurs au démarrage (Windows) -- mesure `startup`, toutes les 30 min."""
        if not IS_WINDOWS:
            return None
        now = self.clock()
        if not force and now < self._next_startup:
            return None
        self._next_startup = now + float(self.cfg.get("startup_interval_seconds") or 1800)
        from . import winhost, startupctl
        data, err = winhost.run_ps(self.cmd, "startup", timeout=120)
        if data is None:
            m = {"agent_id": self.agent_id, "task": "startup", "at": _iso(now), "ok": False, "data": None, "error": err}
        else:
            items = data.get("items") or []
            data["summary"] = startupctl.summarize(items)
            m = {"agent_id": self.agent_id, "task": "startup", "at": _iso(now), "ok": not data.get("partial"), "data": data,
                 "error": ("collecte partielle : " + ", ".join(data["partial"])) if data.get("partial") else None}
        self.last_startup = m
        self.queue.put(m)
        return m

    def run_watchdog(self, force=False):
        """#613 : chien de garde applicatif -- relance les applications absentes,
        événements `app-restarted` / `app-down` / `app-recovered`, mesure `watchdog`."""
        from . import watchdog
        cfg = self.state.get("watchdog") or {}
        if not cfg.get("apps"):
            return None
        now = self.clock()
        if not force and now < self._next_watchdog:
            return None
        self._next_watchdog = now + float(cfg.get("interval_seconds") or watchdog.DEFAULT_INTERVAL)
        r = self.cmd(watchdog.process_list_argv(sys.platform), timeout=30)
        if getattr(r, "returncode", -1) != 0:
            self.event("watchdog-error", "warning", "liste des processus indisponible : %s" % ((r.stderr or "")[:200] or r.returncode))
            return None
        running = watchdog.parse_process_list(r.stdout, sys.platform)
        actions, st, meas = watchdog.evaluate(cfg, running, now, self.state.get("watchdog_state") or {})
        self.state["watchdog_state"] = st
        self._save_state()
        for a in actions:
            if a["action"] == "restart":
                ok, err = self._spawn_detached(a["command"], a.get("cwd"))
                self.event("app-restarted" if ok else "app-restart-failed", "warning", "%s : %s (tentative %d)%s" % (a["label"], "relancée" if ok else "relance impossible", a["attempt"], " -- %s" % err if err else ""), a)
            elif a["action"] == "down-alert":
                self.event("app-down", "critical", "%s : arrêtée, %s" % (a["label"], a["reason"]), a)
            elif a["action"] == "recovered":
                self.event("app-recovered", "info", "%s : de nouveau en service (arrêt %d s)" % (a["label"], a["down_for"]), a)
        m = {"agent_id": self.agent_id, "task": "watchdog", "at": _iso(now), "ok": True, "data": meas, "error": None}
        self.last_watchdog = m
        self.queue.put(m)
        return m

    def _spawn_detached(self, command, cwd=None):
        """Lance une application sans l'attendre ni la rattacher à l'agent."""
        import subprocess
        try:
            kw = {"cwd": cwd or None, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if IS_WINDOWS:
                kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                subprocess.Popen(command, shell=True, **kw)
            else:
                kw["start_new_session"] = True
                subprocess.Popen(command, shell=True, **kw)
            return True, None
        except (OSError, ValueError) as exc:
            return False, str(exc)

    def collect_inventory(self, force=False):
        now = self.clock()
        if not force and now < self._next_inventory:
            return None
        self._next_inventory = now + float(self.cfg["inventory_interval_seconds"])
        tools = _collect_tools(self.which)
        hardware = _collect_hardware(cmd=self.cmd, files=self.files)  # #428
        installed = [{k: v for k, v in m.items() if k != "path"} for m in self.store.list()]
        for m in installed:
            m["effective_enabled"] = plugins.is_enabled(m, self.cfg.get("plugins"))
            m["effective_blocked"] = control.plugin_blocked(self.state, m)
        m = {"agent_id": self.agent_id, "task": "inventory", "at": _iso(now), "ok": True,
             "data": {"tools": tools, "hardware": hardware, "plugins": installed, "agent_version": __import__("si_agent").__version__,
                      "config_version": self.config_version, "blocked": self.is_blocked(),
                      "blocked_reason": self.block_reason() if self.is_blocked() else None,
                      "blocked_plugins": sorted((self.state.get("blocked_plugins") or {}).keys()),
                      "insecure_tls": bool(self.cfg.get("insecure")), "plugins_user": self._plugins_user_effective(),
                      "log_level": self.cfg.get("log_level"), "platform": "windows" if IS_WINDOWS else ("macos" if IS_MACOS else "linux"),
                      "python": sys.version.split()[0],
                      "watchdog": self.state.get("watchdog") or {"interval_seconds": 60, "apps": []}}, "error": None}  # #613
        self.queue.put(m)
        return m

    def _plugins_user_effective(self):
        """Utilisateur d'exécution des sondes non privilégiées : `plugins_user`
        s'il existe et si l'agent est root ; sinon l'utilisateur courant."""
        user = self.cfg.get("plugins_user")
        if not user or _euid() != 0 or not self._lookup_user(user):
            return None
        return user

    @staticmethod
    def _lookup_user(name):
        try:
            import pwd
            p = pwd.getpwnam(name)
            return (p.pw_uid, p.pw_gid)
        except (KeyError, ImportError):
            return None

    def _confinement(self, manifest):
        """Paramètres de confinement d'une sonde (voir control.py) ; None
        pour un exécuteur injecté (tests) qui n'exécute rien de réel."""
        if self.cmd is not host.run_cmd:
            return None
        if IS_WINDOWS:
            # #440 : pas de setuid/rlimit sous Windows -- environnement propre,
            # dossier de la sonde, délai (tue le processus) ; documenté.
            return {"env": control.plugin_env(self.agent_id, self.cfg.get("site"), manifest["id"], manifest.get("env"), base_env=os.environ),
                    "preexec_fn": None, "cwd": os.path.dirname(manifest.get("path") or "") or None}
        run_as = control.resolve_run_user(manifest, self.cfg.get("plugins_user"), _euid(), self._lookup_user)
        return {"env": control.plugin_env(self.agent_id, self.cfg.get("site"), manifest["id"], manifest.get("env")),
                "preexec_fn": control.make_preexec(int(manifest.get("timeout_seconds") or 60),
                                                   int(manifest.get("max_memory_mb") or self.cfg.get("plugin_max_memory_mb") or 0),
                                                   run_as=run_as),
                "cwd": os.path.dirname(manifest.get("path") or "") or None}

    def run_one_plugin(self, manifest):
        env = {"SI_AGENT_ID": self.agent_id, "SI_AGENT_SITE": str(self.cfg.get("site") or "")}
        confine = self._confinement(manifest)
        _log.debug("sonde %s : lancement (%s, privilégiée=%s, utilisateur=%s)", manifest["id"], manifest.get("runner"),
                   bool(manifest.get("privileged")), (confine or {}).get("preexec_fn") and self._plugins_user_effective())
        _t0 = time.time()
        meas = plugins.run_plugin(manifest, self.cmd, now=self.clock(), env=env, confine=confine,
                                  python=sys.executable if IS_WINDOWS else "python3")
        meas["agent_id"] = self.agent_id
        self.tracker.record("plugin:%s" % manifest["id"], time.time() - _t0, ok=bool(meas.get("ok")))  # #616
        self.queue.put(meas)
        if not meas.get("ok"):
            self.event("plugin-failed", "warning", "sonde %s en échec : %s" % (manifest["id"], (meas.get("error") or "")[:200]),
                       {"plugin": manifest["id"]})
        else:
            _log.debug("sonde %s : ok en %s s", manifest["id"], ((meas.get("data") or {}).get("_plugin") or {}).get("duration_seconds"))
        return meas

    def run_plugins(self):
        now = self.clock()
        produced = []
        if self.is_blocked():
            _log.debug("sondes non exécutées : agent bloqué (%s)", self.block_reason())
            return produced
        for m in self.store.list():
            if not plugins.is_enabled(m, self.cfg.get("plugins")):
                continue
            if control.plugin_blocked(self.state, m):
                continue
            if self._next_plugin.get(m["id"], 0) > now:
                continue
            # Échéance fixée AVANT l'exécution : un plugin lent garde son rythme.
            _iv = float(m.get("interval_seconds", 3600))
            if self._bench_until > now:  # #616 : banc de charge, cadence forcée
                from . import introspect as _intro
                _iv = _intro.forced_interval(_iv, self._bench_factor)
            self._next_plugin[m["id"]] = now + _iv
            produced.append(self.run_one_plugin(m))
        return produced

    # -- publication locale (#547) -------------------------------------------
    def publish_tick(self):
        """Sert sur le LAN du site le tableau préparé par le central : serveur
        démarré / arrêté selon la configuration signée, contenu relevé toutes
        les `interval_seconds` par le canal signé (jamais de clé sur le poste)."""
        pub = self.cfg.get("publish") or {}
        enabled = bool(pub.get("enabled")) and not self.is_blocked()
        srv = self._publish_server
        if not enabled:
            if srv:
                srv.stop(); self._publish_server = None
                self.event("publish-stopped", "info", "publication locale arrêtée")
            return
        port, title = int(pub.get("port") or 8081), pub.get("title") or "État du réseau"
        if srv and (srv.port != port or srv.title != title):
            srv.stop(); srv = self._publish_server = None
        if not srv:
            try:
                srv = self._publish_server = publish_lib.PublishServer(port, title, clock=time.time)
                srv.start()
                srv.set_payload(self.publish_payload)
                self.event("publish-started", "info", "publication locale sur le port %d (%s)" % (port, title))
            except OSError as exc:
                self._publish_server = None
                if self.clock() >= self._next_publish:
                    self.event("publish-failed", "warning", "publication locale impossible sur le port %d : %s" % (port, exc))
                    self._next_publish = self.clock() + 300
                return
        now = self.clock()
        if now < self._next_publish:
            return
        self._next_publish = now + float(pub.get("interval_seconds") or 60)
        status, body = self.http.request("GET", "%s/agents/%s/publish" % (protocol.API_PREFIX, self.agent_id))
        if status != 200 or not isinstance(body, dict) or not self._verified("publication"):
            return
        if body.get("enabled"):
            body["received_at"] = time.time()
            self.publish_payload = body
            srv.set_payload(body)

    # -- envoi ---------------------------------------------------------------
    def flush(self, force=False):
        now = self.clock()
        if not force and now - self._last_flush < self.cfg["flush_seconds"]:
            return 0
        self._last_flush = now
        sent = 0
        while True:
            batch = self.queue.pending(limit=self.cfg["batch_size"])
            if not batch:
                break
            ids = [m.pop("_id") for m in batch]
            status, body = self.http.request(
                "POST", "%s/agents/%s/measurements" % (protocol.API_PREFIX, self.agent_id), {"measurements": batch})
            if status in (200, 201):
                self.queue.mark_sent(ids)
                self.last_central_contact = self.clock()
                sent += len(ids)
                continue
            self.queue.mark_attempt(ids)
            if status == 400:
                _log.error("lot rejeté par le central (400) : %s -- abandonné", (body or {}).get("error"))
                self.queue.mark_sent(ids)
                continue
            break
        return sent

    # -- #635 : partage du serveur monté le temps de l'image ------------------
    def _mount_share(self, share):
        """WNetAddConnection2W sans lettre de lecteur : le chemin UNC devient accessible à ce compte (SYSTEM)."""
        if not IS_WINDOWS:
            return "montage de partage : Windows seulement"
        try:
            import ctypes
            from ctypes import wintypes

            class NETRESOURCE(ctypes.Structure):
                _fields_ = [("dwScope", wintypes.DWORD), ("dwType", wintypes.DWORD), ("dwDisplayType", wintypes.DWORD), ("dwUsage", wintypes.DWORD),
                            ("lpLocalName", wintypes.LPWSTR), ("lpRemoteName", wintypes.LPWSTR), ("lpComment", wintypes.LPWSTR), ("lpProvider", wintypes.LPWSTR)]
            nr = NETRESOURCE(); nr.dwType = 1; nr.lpRemoteName = share["unc"]  # RESOURCETYPE_DISK
            rc = ctypes.windll.mpr.WNetAddConnection2W(ctypes.byref(nr), share["password"], share["user"], 0)
            if rc == 1219:  # déjà une session avec d'autres identifiants : on la coupe et on réessaie
                ctypes.windll.mpr.WNetCancelConnection2W(share["unc"], 0, True)
                rc = ctypes.windll.mpr.WNetAddConnection2W(ctypes.byref(nr), share["password"], share["user"], 0)
            if rc != 0:
                return {5: "accès refusé", 53: "chemin réseau introuvable", 67: "nom de partage introuvable", 86: "mot de passe incorrect", 1326: "identifiants refusés",
                        1219: "conflit de session existante"}.get(rc, "code WNet %d" % rc)
            return None
        except Exception as exc:  # noqa: BLE001
            return str(exc)

    def _unmount_share(self, share):
        if not share or not IS_WINDOWS:
            return
        try:
            import ctypes
            ctypes.windll.mpr.WNetCancelConnection2W(share["unc"], 0, True)
        except Exception:  # noqa: BLE001
            pass

    # -- #634 : transfert de l'image vers le central --------------------------
    def start_upload(self, path, command_id=None, delete_after=False):
        from . import uploadctl
        import threading
        if self._upload_job and self._upload_job.get("state") == "running":
            return {"ok": False, "error": "un transfert est déjà en cours"}
        name = uploadctl.safe_name(path)
        if not name or not os.path.isfile(path):
            return {"ok": False, "error": "fichier introuvable : %s" % path}
        total = os.path.getsize(path)
        job = {"path": path, "name": name, "total": total, "sent": 0, "state": "running", "error": None, "started": self.clock(),
               "last_report": self.clock(), "command": command_id, "delete_after": bool(delete_after), "sha256": None}
        self._upload_job = job
        threading.Thread(target=self._upload_worker, args=(job,), daemon=True, name="si-agent-upload").start()
        self.event("image-upload-started", "info", "transfert de %s vers le central (%.1f Go)" % (name, total / 2**30), {"command": command_id, "file": path, "bytes": total})
        return {"ok": True, "result": {"file": path, "bytes": total, "message": "transfert lancé -- suivi par événements"}}

    def _upload_worker(self, job):
        """Fil à part : reprise (GET status), morceaux signés (PUT), clôture (POST complete)."""
        from . import uploadctl
        base = "%s/agents/%s/images/%s" % (protocol.API_PREFIX, self.agent_id, job["name"])
        try:
            st, body = self.http.request("GET", base + "/status")
            offset = int((body or {}).get("size") or 0) if st == 200 else 0
            if offset > job["total"]:
                offset = 0
            with open(job["path"], "rb") as fh:
                def read(pos, n):
                    fh.seek(pos)
                    return fh.read(n)
                h = uploadctl.prefix_digest(read, offset)
                job["sent"] = offset
                for pos, n in uploadctl.plan_chunks(job["total"], offset):
                    data = read(pos, n)
                    h.update(data)
                    for attempt in range(5):
                        st, body = self.http.send_raw("PUT", "%s?offset=%d" % (base, pos), data, timeout=300)
                        if st in (200, 201):
                            break
                        if st == 409 and isinstance(body, dict) and "size" in body:
                            raise RuntimeError("décalage de reprise : %s" % body.get("error"))
                        time.sleep(5 * (attempt + 1))
                    else:
                        raise RuntimeError("morceau à %d refusé (%s %s)" % (pos, st, (body or {}).get("error") if isinstance(body, dict) else ""))
                    job["sent"] = pos + n
            job["sha256"] = h.hexdigest()
            st, body = self.http.request("POST", base + "/complete", {"size": job["total"], "sha256": job["sha256"]})
            if st not in (200, 201):
                raise RuntimeError("clôture refusée (%s %s)" % (st, (body or {}).get("error") if isinstance(body, dict) else ""))
            job["state"] = "finished"
        except Exception as exc:  # noqa: BLE001
            job["state"] = "failed"; job["error"] = str(exc)

    def follow_upload(self):
        job = self._upload_job
        if not job:
            return
        from . import uploadctl
        now = self.clock()
        if job["state"] == "running":
            if now - job["last_report"] >= 300:
                job["last_report"] = now
                p = uploadctl.progress(job["sent"], job["total"], job["started"], now)
                self.event("image-upload-progress", "info", "transfert %s : %.0f %% (%s Mbit/s, reste ~%s min)" % (job["name"], p["percent"], p["rate_mbps"], (p["eta_seconds"] or 0) // 60), dict(p, command=job["command"]))
            return
        self._upload_job = None
        if job["state"] == "finished":
            self.event("image-upload-finished", "info", "transfert terminé : %s (%.1f Go en %d min, sha256 %s)" % (job["name"], job["total"] / 2**30, (now - job["started"]) // 60, job["sha256"][:12]),
                       {"command": job["command"], "file": job["path"], "bytes": job["total"], "sha256": job["sha256"], "seconds": int(now - job["started"])})
            if job.get("delete_after"):
                try:
                    os.remove(job["path"])
                    self.event("image-deleted", "info", "image locale supprimée après transfert : %s" % job["path"], {"command": job["command"]})
                except OSError as exc:
                    self.event("image-delete-failed", "warning", "suppression locale impossible : %s" % exc, {"command": job["command"]})
        else:
            self.event("image-upload-failed", "warning", "transfert échoué : %s (relancer image_transfer, il reprend où il s'est arrêté)" % job["error"],
                       {"command": job["command"], "file": job["path"], "sent": job["sent"]})

    def _store_measure(self, task, data, ok=True, error=None):
        m = {"agent_id": self.agent_id, "task": task, "at": _iso(self.clock()), "ok": ok, "data": data, "error": error}
        self.queue.put(m)
        return m

    def run_deferred(self):
        """#633 : exécute les commandes différées arrivées à échéance."""
        jobs = self.state.get("deferred") or []
        if not jobs:
            return
        now = self.clock()
        due = [j for j in jobs if j.get("due", 0) <= now]
        if not due:
            return
        self.state["deferred"] = [j for j in jobs if j not in due]
        self._save_state()
        for j in due:
            self.event("deferred-run", "info", "exécution de la commande %s programmée pour %s" % (j["type"], j.get("at")), {"command": j["id"]})
            res = self.execute_command({"id": j["id"], "type": j["type"], "params": j["params"]}, deferred=True)
            self.event("deferred-done" if res.get("ok") else "deferred-failed", "info" if res.get("ok") else "warning",
                       "commande différée %s : %s" % (j["type"], (res.get("result") or {}).get("message") if res.get("ok") else res.get("error")), {"command": j["id"]})

    def follow_update(self):
        """#633 : fin de l'installation Windows Update détachée."""
        job = self._update_job
        if not job:
            return
        proc = job["proc"]
        if proc.poll() is None and not os.path.exists(job["out"]):
            if self.clock() - job["started"] > 4 * 3600:
                proc.kill(); self._update_job = None
                self.event("update-failed", "warning", "installation Windows Update sans résultat après 4 h -- arrêtée", {"command": job["command"]})
            return
        data = None
        try:
            with open(job["out"], encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            if proc.poll() is None:
                return  # fichier en cours d'écriture
        self._update_job = None
        from . import sysctl
        if data is None:
            self.event("update-failed", "warning", "installation Windows Update terminée sans résultat (code %s)" % proc.poll(), {"command": job["command"]})
            return
        self._store_measure("winupdate", data)
        inst = data.get("install") or {}
        ok = not data.get("error") and inst.get("result") in (2, 3, None)
        self.event("update-finished" if ok else "update-failed", "info" if ok else "warning", "Windows Update : %s" % sysctl.summarize_update(data),
                   {"command": job["command"], "seconds": int(self.clock() - job["started"]), "reboot_required": inst.get("reboot_required")})
        if ok and job.get("reboot") and inst.get("reboot_required"):
            from . import powerctl
            res = powerctl.run(self.cmd, {"action": "reboot", "delay_seconds": 60, "force": True, "message": "Redémarrage après mises à jour Windows (supervision)"}, platform=sys.platform, console_active=False)
            self.event("command-power", "warning", "redémarrage après mises à jour : %s" % (res.get("result", {}).get("message") if res.get("ok") else res.get("error")), {"command": job["command"]})

    # -- #628 : Winlogon (autologon une fois) ---------------------------------
    def _winlogon_set(self, name, kind, value):
        import winreg
        from . import autologon
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, autologon.WINLOGON_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD if kind == "dword" else winreg.REG_SZ, int(value) if kind == "dword" else str(value))

    def _autologon_cleanup(self, force=False):
        """Au démarrage suivant (ou si le redémarrage a échoué) : retirer le mot de passe et
        l'autologon si le compteur est consommé. Winlogon le fait normalement lui-même."""
        if not IS_WINDOWS or not (force or self.state.get("autologon_pending")):
            return None
        try:
            import winreg
            from . import autologon
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, autologon.WINLOGON_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                def get(name):
                    try:
                        return winreg.QueryValueEx(k, name)[0]
                    except OSError:
                        return None

                def delete(name):
                    try:
                        winreg.DeleteValue(k, name)
                    except OSError:
                        pass
                if force:
                    delete("DefaultPassword"); delete("AutoLogonCount"); winreg.SetValueEx(k, "AutoAdminLogon", 0, winreg.REG_SZ, "0")
                    r = {"cleaned": True, "remaining": 0}
                else:
                    r = autologon.cleanup(get, delete, lambda n, kind, v: winreg.SetValueEx(k, n, 0, winreg.REG_SZ, str(v)))
        except Exception as exc:  # noqa: BLE001
            _log.warning("autologon : nettoyage Winlogon impossible : %s", exc)
            return None
        if r.get("remaining"):
            return r
        self.state.pop("autologon_pending", None)
        self._save_state()
        self.event("autologon-cleared", "info", "autologon une fois : %s" % ("traces retirées par l'agent" if r.get("cleaned") else "déjà nettoyé par Windows"))
        return r

    def maintenance(self):
        now = self.clock()
        if self.state.get("autologon_pending") and now - self._started_at > 120:
            self._autologon_cleanup()
        if now - self._last_purge > 3600:
            self._last_purge = now
            self.queue.purge_sent()

    def status(self):
        # `--status` tourne dans un autre processus que le service : les
        # derniers risques se lisent dans la file locale, pas en mémoire.
        last = self.last_risks
        last_at = None
        if not last:
            rows = self.queue.latest(task="risks", limit=1)
            if rows and rows[0].get("data"):
                last = rows[0]["data"].get("risks") or []
                last_at = rows[0].get("at")
        return {
            "agent_id": self.agent_id,
            "site": self.cfg.get("site"),
            "central_url": self.cfg.get("central_url"),
            "central_in_use": getattr(self.http, "current_url", self.cfg.get("central_url")),
            "on_fallback": bool(getattr(self.http, "on_fallback", False)),
            "config_version": self.config_version,
            "host_interval_seconds": self.cfg.get("host_interval_seconds"),
            "plugins": [{"id": m["id"], "version": m.get("version"), "enabled": plugins.is_enabled(m, self.cfg.get("plugins")),
                         "source": m.get("source"), "present": m.get("present")} for m in self.store.list()],
            "queue": self.queue.stats(),
            "last_central_contact": self.last_central_contact,
            "last_risks": risks.summarize(last) if last is not None else None,
            "last_risks_at": last_at,
            "last_risks_items": [r.get("message") for r in (last or [])][:20],
            "blocked": self.is_blocked(),
            "blocked_reason": self.block_reason() if self.is_blocked() else None,
            "blocked_plugins": sorted((self.state.get("blocked_plugins") or {}).keys()),
            "plugins_user": self._plugins_user_effective(),
            "insecure_tls": bool(self.cfg.get("insecure")),
            "recent_events": [{"at": e["at"], "kind": (e.get("data") or {}).get("kind"), "severity": (e.get("data") or {}).get("severity"),
                               "message": (e.get("data") or {}).get("message")} for e in self.queue.latest(task="event", limit=10)],
        }

    def run_once(self):
        self.refresh_config(force=True)
        out = self.collect_host(force=True)
        nv = self.collect_netview(force=True)
        if nv:
            out.append(nv)
        inv = self.collect_inventory(force=True)
        if inv:
            out.append(inv)
        su = self.collect_startup(force=True)
        if su:
            out.append(su)
        out.extend(self.run_plugins())
        me = self.collect_self(force=True)
        if me:
            out.append(me)
        return out

    def run_forever(self, sleep=time.sleep):
        _log.info("si-agent %s démarré (site %s, central %s)", self.agent_id, self.cfg.get("site"), self.cfg["central_url"])
        self.event("agent-started", "info", "agent démarré (v%s)" % __import__("si_agent").__version__,
                   {"version": __import__("si_agent").__version__, "blocked": self.is_blocked(), "plugins_user": self._plugins_user_effective()})
        try:  # #522 : issue d'une mise à jour lancée avant ce redémarrage
            from . import updater
            pending = updater.check_pending(updater.pending_path(self.cfg.get("state_path")), __import__("si_agent").__version__)
            if pending:
                self.event(pending[0], pending[1], pending[2], pending[3])
        except Exception as exc:  # noqa: BLE001
            _log.warning("marqueur de mise à jour illisible : %s", exc)
        self.refresh_config(force=True)
        self.flush(force=True)
        last_local_block = self.local_block_file()
        _stall_next = 0.0
        while True:
            try:
                # #576 : mise à jour lancée mais jamais aboutie (installeur en échec avant de relancer l'agent)
                if self.clock() >= _stall_next:
                    _stall_next = self.clock() + 60
                    from . import updater as _upd
                    st = _upd.check_stalled(_upd.pending_path(self.cfg.get("state_path")), __import__("si_agent").__version__, now=self.clock())
                    if st:
                        self.event(st[0], st[1], st[2], st[3])
                lb = self.local_block_file()
                if lb != last_local_block:
                    last_local_block = lb
                    self.event("blocked" if lb else "unblocked", "warning" if lb else "info",
                               "fichier BLOCKED local %s" % ("présent : blocage général" if lb else "retiré"))
                self.refresh_config()
                self.collect_host()
                self.collect_netview()
                self.collect_inventory()
                self.collect_startup()
                self.run_watchdog()
                self.follow_image()
                self.follow_update()
                self.follow_upload()
                self.run_deferred()
                self.run_plugins()
                self.collect_self()
                self.poll_commands()
                self.publish_tick()
                self.flush()
                self.maintenance()
            except Exception as exc:  # noqa: BLE001 -- la boucle ne meurt jamais
                _log.exception("erreur dans la boucle : %s", exc)
            sleep(1)


def setup_logging(cfg, verbose=False):
    """Niveau depuis `log_level` (ou --verbose = DEBUG) ; `log_file`
    optionnel en rotation (5 x 2 Mo) en plus du journal systemd."""
    level = logging.DEBUG if verbose else getattr(logging, str(cfg.get("log_level") or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers:
        h.setLevel(level)
    if cfg.get("log_file"):
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(cfg["log_file"], maxBytes=2 * 1024 * 1024, backupCount=5)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        fh.setLevel(level)
        root.addHandler(fh)
    _log.debug("traces au niveau %s", logging.getLevelName(level))


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="si-agent -- agent hôte de supervision-si")
    parser.add_argument("--config", default=os.environ.get("SI_AGENT_CONFIG", DEFAULT_CONFIG_PATH))
    parser.add_argument("--once", action="store_true", help="un passage complet (collecte, inventaire, plugins, envoi) puis sortie")
    parser.add_argument("--collect", action="store_true", help="affiche la collecte hôte, les risques, la vue réseau passive et le matériel en JSON, sans envoi ni configuration")
    parser.add_argument("--status", action="store_true", help="affiche l'état local et sort")
    parser.add_argument("-v", "--verbose", action="store_true", help="traces DEBUG (requêtes, sondes, commandes)")
    parser.add_argument("--block", nargs="?", const="blocage local", metavar="MOTIF", help="blocage général local des sondes, puis sortie")
    parser.add_argument("--unblock", action="store_true", help="lève le blocage général local, puis sortie")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.collect:
        data, _ = _collect_all()
        data["activity"] = _collect_activity()
        print(json.dumps({"host": data, "risks": risks.evaluate(data), "summary": risks.summarize(risks.evaluate(data)),
                          "netview": _collect_netview(), "hardware": _collect_hardware()},
                         indent=2, ensure_ascii=False))
        return 0
    cfg = load_config(args.config)
    setup_logging(cfg, verbose=args.verbose)
    agent = Agent(cfg)
    if args.status:
        print(json.dumps(agent.status(), indent=2, ensure_ascii=False))
        return 0
    if args.block or args.unblock:
        agent.set_blocked(bool(args.block), args.block, source="ligne de commande")
        print("bloqué" if agent.is_blocked() else "débloqué", "--", agent.block_reason() if agent.is_blocked() else "")
        return 0
    if args.once:
        for m in agent.run_once():
            print(json.dumps({k: v for k, v in m.items() if k != "data"}, ensure_ascii=False))
        print("envoyées :", agent.flush(force=True))
        return 0
    # #629 : une seule instance par configuration (l'installeur relancé laissait tourner l'ancienne,
    # qui parlait au central avec un secret périmé -> 401 en boucle)
    lock = acquire_instance_lock(cfg.get("state_path") or cfg.get("queue_path") or args.config)
    if lock is None:
        _log.error("une autre instance de si-agent tourne déjà pour cette configuration -- sortie")
        return 3
    agent.run_forever()
    return 0


def acquire_instance_lock(anchor_path):
    """Verrou exclusif sur <état>.lock : None si une autre instance le tient."""
    path = os.path.join(os.path.dirname(os.path.abspath(anchor_path)), "si-agent.lock")
    try:
        fh = open(path, "a+")
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.seek(0); fh.truncate(); fh.write(str(os.getpid())); fh.flush()
        return fh
    except OSError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
