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
import urllib.parse
import urllib.request

from . import control, publish as publish_lib, host, localview, netview, plugins, protocol, review, risks
from .localqueue import LocalQueue

# #440 : sous Windows 10/11, les collecteurs viennent de winhost.py (scripts
# PowerShell livrés) ; le reste du paquet (protocole, file locale, sondes
# python/powershell, commandes) est commun.
IS_WINDOWS = sys.platform == "win32"
FOND_SEUIL_S = 120   # #925 : sonde dont le délai dépasse 2 min -> exécutée en tâche de fond (Windows)
FOND_MAX = 2         # #925 : sondes longues simultanées au plus
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
    "remote_shell": "off",       # #919 : commandes à distance (off / lecture / intervention), réglé par le central
    "remote_shell_max": None,    # #919 : plafond fixé sur le poste (agent.json) -- l'administrateur local a le dernier mot
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
    # #819 : vue locale de transparence (page en lecture seule sur le poste), fermée par défaut
    "local_view": {},
}


class _TapQueue(object):
    """#819 : file vers le central, doublée d'un enregistreur pour la vue locale (rien d'autre ne change)."""

    def __init__(self, queue, recorder):
        self._q, self._rec = queue, recorder

    def put(self, measurement):
        try:
            self._rec.record(measurement)
        except Exception:  # noqa: BLE001 -- la vue ne doit jamais gêner l'envoi
            pass
        return self._q.put(measurement)

    def put_many(self, measurements):
        return sum(1 for m in measurements if self.put(m))

    def __getattr__(self, name):
        return getattr(self._q, name)


def uninstall_hint():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if IS_WINDOWS:
        return 'powershell -NoProfile -ExecutionPolicy Bypass -File "%s"' % os.path.join(base, "uninstall.ps1")
    if IS_MACOS:
        return "voir README-DEPLOIEMENT.md, désinstallation macOS"
    return "systemctl disable --now si-agent (ou docker rm -f si-agent)"


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

    def get_raw_signed(self, path, timeout=120):
        """#748 : GET signé -> (statut, en-têtes, octets) ; 204/4xx renvoyés sans exception."""
        headers = protocol.auth_headers(self.device_id, self.secret, "GET", path, b"")
        req = urllib.request.Request(self.current_url + path, method="GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.fallback_context if self.on_fallback else self.ssl_context) as resp:
                return resp.status, dict(resp.headers.items()), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()) if exc.headers else {}, b""

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


def plugin_python(executable, is_windows=False, run_as_root=True):
    """#690 : interpréteur des sondes Python = celui de l'agent (≥ 3.7, ex. Python
    autonome d'un hôte Debian 9) et non le `python3` système (3.5 : « unexpected
    keyword argument 'text' »). Repli sur `python3` seulement si l'interpréteur est
    dans un dossier personnel qu'un utilisateur de confinement ne pourrait pas lire."""
    if not executable:
        return "python3"
    if is_windows or run_as_root:
        return executable
    return "python3" if executable.startswith(("/root/", "/home/")) else executable


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
        self.recorder = localview.Recorder()   # #819 : dernières mesures mises en file, pour la vue locale
        self.queue = _TapQueue(queue or LocalQueue(cfg["queue_path"]), self.recorder)
        self._local_view = None
        self._lv_key = None
        self._lv_retry = 0
        self._lv_next = 0
        self._lv_pending = None
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
        self._audit_job = None      # #687 : audit extérieur en cours (point d'observation)
        self._next_power_sched = 0  # #684 : redémarrage planifié / relance des applications
        self.last_startup = None
        self.last_watchdog = None
        self._next_plugin = {}
        self._sauvegarde = None      # #930 : sauvegarde confs+montages en tâche de fond
        self._acces = None           # #928 : test d'accès aux services en tâche de fond (secret en mémoire seulement)
        self._fond = {}              # #925 : sondes longues en tâche de fond {id: thread}
        self._fond_autorise = IS_WINDOWS or bool(cfg.get("plugins_background"))
        self._charge = None          # #916 : test de charge en tâche de fond (live + stop pendant l'exécution)
        self._shell = {}             # #919 : commandes à distance en cours / à pousser {id: Tache}
        self._shell_file = []        # #926 : commandes à distance en file (au-delà de 3 simultanées) [params]
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
        if "remote_shell" in body:                      # #919 : mode des commandes à distance réglé dans le hub
            from . import remoteshell as _rs
            self.cfg["remote_shell"] = body["remote_shell"] if body["remote_shell"] in _rs.MODES else "off"
        if isinstance(body.get("local_view"), dict):   # #819 : le central peut ouvrir / régler la vue locale
            self.cfg["local_view"] = dict(self.cfg.get("local_view") or {}, **body["local_view"])
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
        interval = self.cfg["commands_poll_seconds"]
        fast = getattr(self, "_fast_poll", None)          # #709 : relevé accéléré pendant une session interactive du hub
        if fast and now < fast[1]:
            interval = min(interval, fast[0])
        if not force and now - self._last_commands < interval:
            return []
        self._last_commands = now
        status, body = self.http.request("GET", "%s/agents/%s/commands" % (protocol.API_PREFIX, self.agent_id))
        if status != 200 or not isinstance(body, dict):
            return []
        if not self._verified("commandes"):
            return []
        self.last_central_contact = now
        fp = body.get("fast_poll")
        if isinstance(fp, dict) and isinstance(fp.get("seconds"), (int, float)) and isinstance(fp.get("for"), (int, float)):
            self._fast_poll = (max(2.0, float(fp["seconds"])), now + max(0.0, min(900.0, float(fp["for"]))))
        else:
            self._fast_poll = None
        done = []
        for c in body.get("commands") or []:
            cid = str((c or {}).get("id") or "")
            if not cid or not control.remember_command(self.state, cid):
                self.event("command-replayed", "warning", "commande %s déjà exécutée -- ignorée" % (cid or "?"), {"command": cid})
                if cid:     # #755 : acquittée quand même, sinon le central la renvoie à chaque relève (une alerte par minute)
                    self.http.request("POST", "%s/agents/%s/commands/%s/ack" % (protocol.API_PREFIX, self.agent_id, cid),
                                      {"ok": True, "error": None, "result": {"replayed": True, "message": "déjà exécutée lors d'une relève précédente (acquittement perdu) ; non rejouée"}})
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
                if m.get("id") == "poste-charge":          # #916 : test de charge en tâche de fond -> la boucle reste libre (live + stop pendant l'exécution)
                    return self._charge_lancer(m, params.get("args"))
                if self._en_fond(m):                       # #925 : sonde longue -> la boucle reste libre (commandes, config)
                    return self._fond_lancer(m, params.get("args"))
                meas = self.run_one_plugin(m, args=params.get("args"))
                return {"ok": bool(meas.get("ok")), "result": meas.get("data"), "error": meas.get("error")}
            if ctype == "shell":                        # #919 : analyse technique à distance (PowerShell)
                return self._shell_commande(params)
            if ctype == "acces-services":               # #928 : temps d'accès aux services (brut + authentifié)
                return self._acces_services_lancer(params)
            if ctype == "sauvegarde-poste":             # #930 : sauvegarde des confs logicielles et des montages
                return self._sauvegarde_lancer(params)
            if ctype == "stop_plugin":
                # #913/#916 : arrêt d'un test de charge -- pose la sentinelle lue par le plugin ENTRE blocs/itérations.
                # poste-charge tournant en tâche de fond (#916), la boucle traite ce stop PENDANT le test -> arrêt effectif en cours de route.
                if str(params.get("id", "")) != "poste-charge":
                    return {"ok": False, "error": "stop_plugin : seul poste-charge est géré"}
                try:
                    with open(os.path.join(self._charge_dir(), "poste-charge.stop"), "w", encoding="utf-8") as fh:
                        fh.write("stop")
                    return {"ok": True, "result": {"stop": True}}
                except OSError as e:
                    return {"ok": False, "error": str(e)[:200]}
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
                vue = dict(params, argv="(%d élément(s), masqués)" % len(params.get("argv") or [])) if params.get("argv") else params   # #825 : jeton d'enrôlement
                self.event("command-vm", "info" if res.get("ok") else "warning",
                           "VM %s : %s%s" % (params.get("vmid"), params.get("action"), "" if res.get("ok") else " -- %s" % res.get("error")), {"command": c.get("id"), "params": vue})
                return res
            if ctype == "emulation":
                # #831 : émulateurs Raspberry (conteneur armv6 / arm64, machine QEMU complète) et Android sur cet hôte
                from . import emulctl
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                vue = dict(params, ligne="(masquée)") if params.get("ligne") else params
                res = emulctl.run(self.cmd, params)
                self.event("command-emulation", "info" if res.get("ok") else "warning",
                           "émulation %s %s : %s" % (params.get("action"), params.get("instance") or params.get("profil") or "", "ok" if res.get("ok") else res.get("error")),
                           {"command": c.get("id"), "params": vue})
                return res
            if ctype == "orchestration":
                # #832 : k3s / Nomad sur cet hôte (installer, rejoindre, déployer, échelle, supprimer, quota, état + TTL)
                from . import orchctl
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                res = orchctl.run(self.cmd, params)
                self.event("command-orchestration", "info" if res.get("ok") else "warning",
                           "orchestration %s %s %s : %s" % (params.get("action"), params.get("moteur") or "", params.get("nom") or "", "ok" if res.get("ok") else res.get("error")),
                           {"command": c.get("id"), "params": orchctl.masquer(params)})
                return res
            if ctype == "banc_modele":
                # #826 : modèle de VM du banc d'installation (image cloud vérifiée -> template Proxmox)
                from . import bancmod
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                res = bancmod.run(self.cmd, params)
                self.event("command-banc", "info" if res.get("ok") else "warning",
                           "modèle de banc %s (vmid %s) : %s" % (params.get("recette"), params.get("vmid"), "prêt" if res.get("ok") else res.get("error")), {"command": c.get("id")})
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
            if ctype == "sbom":
                # #699 : inventaire logiciel (syft) -> central -> vuln-api ; relevé périodique mémorisé
                if "schedule_days" in params:
                    self.state["sbom_schedule_days"] = max(0.0, min(90.0, float(params.get("schedule_days") or 0)))
                if params.get("install"):
                    self.state["sbom_install"] = True
                if "images" in params:                  # #711 : images Docker des conteneurs en service
                    self.state["sbom_images"] = bool(params.get("images"))
                self._save_state()
                started = self.start_sbom(install=bool(self.state.get("sbom_install")), command_id=c.get("id")) if params.get("now") else False
                return {"ok": True, "result": {"schedule_days": self.state.get("sbom_schedule_days", 0), "started": started,
                                               "running": bool(getattr(self, "_sbom_running", False)), "last_at": self.state.get("sbom_last_at"),
                                               "last": self.state.get("sbom_last")}}
            if ctype == "ollama":
                # #746 : modèles Ollama de l'hôte (état, téléchargement détaché, suppression, chargement, essai)
                from . import ollamactl
                url = ollamactl.base_url(self.cfg)
                res = ollamactl.run_action(params, url, pull_state=getattr(self, "_ollama_pull", None),
                                           start_pull=lambda m: self.start_ollama_pull(url, m, c.get("id")))
                if res.get("ok") and params.get("action") in ("delete", "load", "unload", "test"):
                    self._next_plugin.pop("ollama", None)   # la sonde ollama remonte l'état tout de suite
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "p2v":
                # #748 : virtualisation directe pilotée par les deux agents (préparation source / cible, lecture relais, nettoyage)
                res = self.p2v_action(params, c.get("id"))
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "hostops":
                # #756 : gestes encadrés (liste fermée, listes blanches d'agent.json, motif, audit) -- pas un shell
                from . import hostops
                if IS_WINDOWS:
                    return {"ok": False, "error": "gestes encadrés : hôtes Linux seulement"}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                if params.get("action") == "catalogue":
                    return {"ok": True, "result": hostops.catalogue(self.cfg)}

                def runner(argv, timeout):
                    r = self.cmd(argv, timeout=timeout)
                    return getattr(r, "returncode", 1), getattr(r, "stdout", "") or "", getattr(r, "stderr", "") or ""
                import shutil as _sh
                res = hostops.run(params, self.cfg, runner, which=_sh.which)
                if params.get("action") in hostops.WRITE:
                    self.event("hostops", "info" if res.get("ok") else "warning", "geste %s %s%s" % (params.get("action"), params.get("unit") or params.get("container") or params.get("dir") or "",
                               "" if res.get("ok") else " -- " + str(res.get("error"))), {"command": c.get("id"), "actor": params.get("actor"), "reason": params.get("reason")})
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "edge":
                # #776 : proxy d'entrée (HAProxy) du couple interchangeable -- configuration fabriquée ici, vérifiée, rechargée
                if IS_WINDOWS:
                    return {"ok": False, "error": "proxy d'entrée : Linux seulement"}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                import subprocess as _sp
                from . import edgectl

                def _erun(argv):
                    try:
                        r = _sp.run(argv, capture_output=True, text=True, timeout=60)
                        return r.returncode, r.stdout or "", r.stderr or ""
                    except Exception as exc:  # noqa: BLE001
                        return 1, "", str(exc)
                res = edgectl.run(params, _erun)
                if params.get("action") == "apply":
                    self.event("edge", "info" if res.get("ok") else "warning", "proxy d'entrée : configuration %s%s" % (
                        "appliquée" if res.get("changed") else "inchangée", "" if res.get("ok") else " -- " + str(res.get("error"))), {"command": c.get("id"), "digest": res.get("digest")})
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype in ("wifi_config", "collecteur"):
                # #807 : configuration radio d'une sonde (interfaces, SSID) ; relais vers le collecteur du site (mini-PC)
                if IS_WINDOWS:
                    return {"ok": False, "error": "%s : Linux seulement" % ctype}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                if ctype == "collecteur":
                    from . import collectctl
                    return collectctl.run(params)
                import subprocess as _sp
                from . import wificonf

                def _wrun(args):
                    try:
                        p = _sp.run(args, capture_output=True, text=True, timeout=60)
                        return p.returncode, p.stdout, p.stderr
                    except (OSError, _sp.SubprocessError) as exc:
                        return 127, "", str(exc)
                res = wificonf.run(params, _wrun)
                if (params or {}).get("action") == "appliquer":
                    self.event("wifi-config", "info" if res.get("ok") else "warning", "configuration radio %s%s" % (
                        "appliquée" if res.get("ok") else "appliquée avec erreurs", "" if res.get("ok") else " -- " + str(res.get("error"))), {"command": c.get("id")})
                return res
            if ctype == "navigateur":
                # #798 : navigateur de l'hôte (écran web publié par le bastion, automate Playwright local)
                if IS_WINDOWS:
                    return {"ok": False, "error": "navigateur de l'hôte : Linux seulement"}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                from . import navctl
                return navctl.run(params, navctl.http_local)
            if ctype == "latency":
                # #775 : latence des IP publiques vue d'ici, ou d'un hôte joint par SSH (compte personnel, rebond, sudo)
                if IS_WINDOWS:
                    return {"ok": False, "error": "mesures de latence : hôtes Linux / macOS seulement"}
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                import subprocess as _sp
                from . import latctl

                def _lrun(argv, inp, timeout):
                    try:
                        r = _sp.run(argv, input=inp, capture_output=True, text=True, timeout=timeout)
                        return r.returncode, r.stdout or "", r.stderr or ""
                    except Exception as exc:  # noqa: BLE001
                        return 1, "", str(exc)
                return latctl.run(params, _lrun)
            if ctype == "migstep":
                # #774 : étape de la tuile « Migration 2026-2027 » (copie, vérification), détachée (systemd-run), pilotée par le hub
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                import subprocess as _sp
                from . import migctl

                def _runner(argv):
                    try:
                        r = _sp.run(argv, capture_output=True, text=True, timeout=120)
                        return r.returncode, r.stdout or "", r.stderr or ""
                    except Exception as exc:  # noqa: BLE001
                        return 1, "", str(exc)
                res = migctl.run(params, _runner)
                self.event("migration", "info" if res.get("ok") else "warning", "migration %s %s%s" % (
                    params.get("action"), (params.get("step") or {}).get("id") or params.get("id") or "", "" if res.get("ok") else " -- " + str(res.get("error"))),
                    {"command": c.get("id"), "actor": params.get("actor")})
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "xfer":
                # #750 : rapatriement d'un CT / d'une VM depuis un nœud Proxmox distant (export, vérification, destruction par tranches)
                if self.is_blocked():
                    return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
                res = self.xfer_action(params, c.get("id"))
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "mail":
                # #697 : tuile Serveur de messagerie -- boîtes, historique, quarantaine, lecture, libération (mailctl)
                from . import mailctl
                res = mailctl.run_action(params)
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "browse":
                # #627 : lecteurs / sous-dossiers du poste, lecture seule, pour choisir une cible depuis le hub
                from . import browsectl
                import shutil as _sh
                res = browsectl.run(params, usage=_sh.disk_usage)
                return {"ok": res.get("ok", False), "error": res.get("error"), "result": res}
            if ctype == "image_transfer":
                # #634 : transférer (ou reprendre) une image déjà sur le poste ; #751 : vers le récepteur LAN si push_url
                self._upload_push = self._push_target(params)
                return self.start_upload(str(params.get("path") or ""), c.get("id"), delete_after=bool(params.get("delete_after")))
            if ctype == "image_host":
                # #621 : image complète du poste à chaud (Disk2vhd, VSS), détachée ; suivi dans la boucle
                self._upload_bwlimit = float(params.get("bwlimit_mbps") or 0)   # #748 : débit du transfert qui suivra
                self._upload_push = self._push_target(params)                     # #751 : récepteur LAN du nœud (sinon central)
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
            if ctype == "ext_audit":
                # #687 : audit extérieur non intrusif -- seulement sur un point d'observation déclaré
                if not self.cfg.get("audit_enabled"):
                    return {"ok": False, "error": "cet agent n'est pas un point d'observation (audit_enabled absent de agent.json)"}
                if self._audit_job and self._audit_job.get("thread") and self._audit_job["thread"].is_alive():
                    return {"ok": False, "error": "un audit est déjà en cours"}
                import threading
                from . import extaudit
                targets = [t for t in (params.get("targets") or []) if isinstance(t, dict) and t.get("host")][:10]
                job = {"command": c.get("id"), "targets": targets, "results": None, "started": self.clock()}

                def work(job=job):
                    job["results"] = [extaudit.audit_target(t) for t in job["targets"]]
                job["thread"] = threading.Thread(target=work, daemon=True)
                self._audit_job = job
                job["thread"].start()
                self.event("ext-audit-started", "info", "audit extérieur lancé : %s" % ", ".join(t["host"] for t in targets), {"command": c.get("id")})
                return {"ok": True, "result": {"message": "audit lancé sur %d cible(s), résultat dans la section Audit" % len(targets)}}
            if ctype == "power_schedule":
                # #684 : redémarrage planifié (+ relance des applications de la session console)
                from . import powersched
                cfg, errors = powersched.normalize(params)
                if errors and params.get("enabled", True) is not False:
                    return {"ok": False, "error": " ; ".join(errors)}
                self.state["power_schedule"] = cfg
                self._save_state()
                self._next_power_sched = 0
                self._next_inventory = 0   # le hub voit la planification au prochain inventaire
                self.event("power-schedule", "info", "redémarrage planifié : %s" % (
                    "%s à %s (jours %s)%s" % (cfg["action"], cfg["time"], cfg["days"], ", relance des applications" if cfg["relaunch"] else "")
                    if cfg["enabled"] else "désactivé"), {"command": c.get("id"), "config": cfg})
                return {"ok": True, "result": {"config": cfg}, "error": None}
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
                ok, err = self._spawn_app(a["command"], a.get("cwd"), a.get("session"))
                self.event("app-restarted" if ok else "app-restart-failed", "warning", "%s : %s (tentative %d)%s" % (a["label"], "relancée" if ok else "relance impossible", a["attempt"], " -- %s" % err if err else ""), a)
            elif a["action"] == "down-alert":
                self.event("app-down", "critical", "%s : arrêtée, %s" % (a["label"], a["reason"]), a)
            elif a["action"] == "recovered":
                self.event("app-recovered", "info", "%s : de nouveau en service (arrêt %d s)" % (a["label"], a["down_for"]), a)
        m = {"agent_id": self.agent_id, "task": "watchdog", "at": _iso(now), "ok": True, "data": meas, "error": None}
        self.last_watchdog = m
        self.queue.put(m)
        return m

    def follow_audit(self):
        """#687 : audit terminé (fil séparé) -> mesure `ext-audit` + événement résumé."""
        job = self._audit_job
        if not job or job.get("results") is None:
            return None
        self._audit_job = None
        res = job["results"]
        tot = {"critical": 0, "warning": 0, "info": 0}
        for r in res:
            for k, n in (r.get("score") or {}).items():
                tot[k] = tot.get(k, 0) + n
        m = {"agent_id": self.agent_id, "task": "ext-audit", "at": _iso(self.clock()), "ok": True,
             "data": {"targets": res, "summary": tot, "command": job["command"], "duration_seconds": int(self.clock() - job["started"])}, "error": None}
        self.queue.put(m)
        self.event("ext-audit", "warning" if tot["critical"] else "info",
                   "audit extérieur : %d cible(s), %d critique(s), %d avertissement(s)" % (len(res), tot["critical"], tot["warning"]),
                   {"command": job["command"], "summary": tot})
        return m

    def run_power_schedule(self, now_dt=None):
        """#684 : toutes les 30 s -- relance en attente (après redémarrage), puis
        créneau du redémarrage planifié."""
        from . import powersched
        now = self.clock()
        if now < self._next_power_sched and now_dt is None:
            return None
        self._next_power_sched = now + 30
        pending = self.state.get("relaunch_pending")
        if pending and now - self._started_at >= 60:
            self._relaunch(pending, now)
        cfg = self.state.get("power_schedule")
        key = powersched.due(cfg, now_dt or __import__("datetime").datetime.fromtimestamp(now), self.state.get("power_schedule_last"))
        if not key or self.is_blocked():
            return None
        self.state["power_schedule_last"] = key
        apps = []
        if cfg.get("relaunch") and IS_WINDOWS:
            r = self.cmd(powersched.snapshot_argv(), timeout=60)
            apps = powersched.pick_apps(powersched.parse_processes(r.stdout if r.returncode == 0 else ""))
            if apps:
                self.state["relaunch_pending"] = {"at": now, "apps": apps}
        self._save_state()
        from . import powerctl
        res = powerctl.run(self.cmd, {"action": cfg["action"], "delay_seconds": cfg["delay_seconds"], "force": True, "message": cfg["message"]},
                           platform=sys.platform, console_active=self._console_active())
        if not res.get("ok"):
            self.state.pop("relaunch_pending", None)
            self._save_state()
        self.event("host-reboot" if res.get("ok") else "host-reboot-failed", "warning",
                   "%s planifié %s%s" % (cfg["action"], "dans %d s" % cfg["delay_seconds"] if res.get("ok") else "impossible",
                                        " -- %d application(s) à relancer : %s" % (len(apps), ", ".join(a["name"] for a in apps)) if apps else
                                        "" if res.get("ok") else " -- %s" % res.get("error")),
                   {"apps": apps, "schedule": cfg})
        return res

    def _relaunch(self, pending, now):
        """#684 : relance des applications notées avant le redémarrage, dans la
        session console ; attend qu'un utilisateur soit connecté (abandon après
        RELAUNCH_GIVE_UP_S)."""
        from . import powersched
        results, waiting = [], False
        for a in pending.get("apps") or []:
            ok, err = self._spawn_app(a["command"], None, "console")
            if not ok and err and "aucun utilisateur" in err:
                waiting = True
                break
            results.append({"name": a.get("name"), "ok": ok, "error": err})
        if waiting:
            if now - float(pending.get("at") or now) < powersched.RELAUNCH_GIVE_UP_S:
                return None
            self.event("host-boot", "warning", "redémarré ; relance abandonnée : aucun utilisateur connecté sur la console",
                       {"apps": pending.get("apps")})
        else:
            ko = [r for r in results if not r["ok"]]
            self.event("host-boot", "warning" if ko else "info",
                       "redémarré ; %d/%d application(s) relancée(s)%s" % (len(results) - len(ko), len(results),
                                                                         " -- échecs : " + ", ".join("%s (%s)" % (r["name"], r["error"]) for r in ko) if ko else ""),
                       {"results": results})
        self.state.pop("relaunch_pending", None)
        self._save_state()
        return results

    def _spawn_app(self, command, cwd=None, session="console"):
        """#683 : sous Windows, l'agent (service SYSTEM) est en session 0 -- une
        application graphique lancée là est invisible. En mode « console », on la
        lance dans la session de l'utilisateur ouvert sur la console ; sans
        utilisateur connecté, échec explicite (pas de lancement invisible)."""
        if IS_WINDOWS and session != "service":
            from . import winsession
            if winsession.current_session_id() == 0:
                ok, err, sid = winsession.spawn_in_console(command, cwd)
                return ok, err if not ok else None
        return self._spawn_detached(command, cwd)

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
                      "watchdog": self.state.get("watchdog") or {"interval_seconds": 60, "apps": []},
                      "power_schedule": self.state.get("power_schedule"), "relaunch_pending": bool(self.state.get("relaunch_pending")),
                      "audit_enabled": bool(self.cfg.get("audit_enabled"))}, "error": None}  # #613
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
                    "preexec_fn": None, "cwd": os.path.dirname(manifest.get("path") or "") or None,
                    "encoding": "auto"}   # #920 : sortie décodée UTF-8 puis OEM (et non la page ANSI : « relevÃ© »)
        run_as = control.resolve_run_user(manifest, self.cfg.get("plugins_user"), _euid(), self._lookup_user)
        return {"env": control.plugin_env(self.agent_id, self.cfg.get("site"), manifest["id"], manifest.get("env")),
                "preexec_fn": control.make_preexec(int(manifest.get("timeout_seconds") or 60),
                                                   int(manifest.get("max_memory_mb") or self.cfg.get("plugin_max_memory_mb") or 0),
                                                   run_as=run_as),
                "cwd": os.path.dirname(manifest.get("path") or "") or None, "run_as": run_as}

    def _charge_dir(self):
        # #913 : dossier (écrivable par l'agent) des fichiers de suivi/arrêt du test de charge -- la racine des données
        # (parent de plugins_dir ; sous Windows C:\\ProgramData\\si-agent).
        d = self.cfg.get("plugins_dir") or "."
        return os.path.dirname(d) or d

    def _charge_pousser_live(self, live_path):
        # #913 : lit le fichier --live (NDJSON écrit par poste-charge) et pousse la courbe de tension au central
        # (mesure plugin:poste-charge-live). Appelé APRÈS le test (exécution synchrone) -> courbe disponible au résultat.
        ech = []
        try:
            with open(live_path, encoding="utf-8") as fh:
                for ligne in fh:
                    ligne = ligne.strip()
                    if ligne:
                        try:
                            ech.append(json.loads(ligne))
                        except ValueError:
                            pass
        except OSError:
            return
        if not ech:
            return
        self.queue.put({"task": "plugin:poste-charge-live", "at": _iso(self.clock()), "ok": True, "agent_id": self.agent_id,
                        "data": {"echantillons": ech[-500:], "fini": any(e.get("phase") == "fini" for e in ech)}})

    def _charge_lancer(self, manifest, args=None):
        # #916 : lance poste-charge dans un thread dédié pour que la boucle principale reste libre --
        # elle pousse la courbe de tension (live) au central et traite stop_plugin PENDANT le test.
        import threading
        st = getattr(self, "_charge", None)
        if st and st.get("thread") is not None and st["thread"].is_alive():
            return {"ok": False, "error": "un test de charge est déjà en cours"}
        live_path = os.path.join(self._charge_dir(), "poste-charge.live.ndjson")
        st = {"live_path": live_path, "t0": self.clock(), "pushed_at": 0.0, "done": False, "final_pushed": False, "thread": None}

        def work():
            try:
                self.run_one_plugin(manifest, args=args)   # bloquant ICI : prépare --live/--stop, exécute, pousse résultat + courbe finale
            except Exception:  # noqa: BLE001
                _log.warning("poste-charge (fond) : exécution en échec", exc_info=True)
            finally:
                st["done"] = True

        t = threading.Thread(target=work, name="si-agent-charge", daemon=True)
        st["thread"] = t
        self._charge = st
        t.start()
        self.event("charge-started", "info", "test de charge lancé en tâche de fond", {"args": list(args or [])})
        return {"ok": True, "result": {"started": True}}

    def charge_tick(self):
        # #916 : appelée à chaque tour de boucle. Tant qu'un test de charge tourne en fond, pousse la courbe de
        # tension (mesure plugin:poste-charge-live) toutes les ~2 s en forçant l'envoi -> observation en streaming depuis le hub.
        st = getattr(self, "_charge", None)
        if not st:
            return
        now = self.clock()
        alive = st.get("thread") is not None and st["thread"].is_alive()
        if (now - st.get("pushed_at", 0.0) >= 2.0) or (st.get("done") and not st.get("final_pushed")):
            st["pushed_at"] = now
            try:
                self._charge_pousser_live(st["live_path"])
                self.flush(force=True)
            except Exception:  # noqa: BLE001
                _log.debug("poste-charge : poussée du suivi direct en cours impossible", exc_info=True)
            if st.get("done"):
                st["final_pushed"] = True
        if st.get("done") and not alive:
            self._charge = None   # résultat final + courbe finale déjà poussés par run_one_plugin dans le thread

    # -- #930 : sauvegarde des configurations logicielles et des montages d'un poste Windows ----------------------
    def _sauvegarde_lancer(self, params):
        """Produit un jeu de sauvegarde (confs registre + dossiers AppData + remonter.cmd + manifeste -> archive) et
        l'écrit sur clé USB / partage UNC. Les identifiants UNC (injectés par le hub depuis le coffre) restent en
        mémoire et passent par l'environnement du processus PowerShell -- jamais sur une ligne de commande ni en
        trace. Tâche de fond ; pousse la mesure `sauvegarde-poste` à la fin. Un seul test à la fois."""
        import os as _os
        import threading
        from . import sauvegarde as bk, winhost
        if not IS_WINDOWS and self.cmd is host.run_cmd:
            return {"ok": False, "error": "sauvegarde de poste : Windows seulement"}
        confs = params.get("confs")
        if not isinstance(confs, list) or not confs:
            return {"ok": False, "error": "params.confs (liste non vide) requis"}
        st = getattr(self, "_sauvegarde", None)
        if st is not None and st.is_alive():
            return {"ok": False, "error": "une sauvegarde est déjà en cours"}
        montages = params.get("montages") if isinstance(params.get("montages"), dict) else {}
        dest = params.get("destinations") if isinstance(params.get("destinations"), dict) else {}
        usb = str((dest.get("usb") or "")).strip() or None
        unc = dest.get("unc") if isinstance(dest.get("unc"), dict) else None
        unc_user = unc.pop("user", None) if unc else None          # retirés des params -> jamais poussés/tracés
        unc_secret = unc.pop("secret", None) if unc else None
        if unc and (unc_user or unc_secret):
            unc["avec_identifiants"] = True
        ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime(self.clock()))
        racine = _os.path.join(self._charge_dir(), "sauvegarde")
        travail = _os.path.join(racine, ts)
        archive = _os.path.join(racine, "sauvegarde-%s-%s.zip" % (self.agent_id, ts))

        def work():
            data, env = None, {}
            try:
                _os.makedirs(travail, exist_ok=True)
                with open(_os.path.join(travail, "remonter.cmd"), "w", encoding="utf-8") as fh:
                    fh.write(bk.script_remontage(montages))
                with open(_os.path.join(travail, "manifeste.json"), "w", encoding="utf-8") as fh:
                    json.dump(bk.manifeste(self.agent_id, confs, montages, _iso(self.clock())), fh, ensure_ascii=False, indent=2)
                script = bk.construire_script_capture(confs, travail, archive, usb=usb, unc=unc)
                sp = _os.path.join(travail, "capture.ps1")
                with open(sp, "w", encoding="utf-8-sig") as fh:
                    fh.write(script)
                if unc and unc.get("avec_identifiants"):
                    env = {"SI_BK_UNC_USER": str(unc_user or ""), "SI_BK_UNC_PASS": str(unc_secret or "")}
                interp = winhost.POWERSHELL
                argv = [interp, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", sp]
                confine = {"env": dict(_os.environ, **env), "encoding": "auto", "cwd": travail} if self.cmd is host.run_cmd else None
                r = self.cmd(argv, timeout=900, confined=confine) if confine else self.cmd(argv, timeout=900, env=env)
                data = bk.extraire_json(getattr(r, "stdout", "") or "") or {"erreurs": ["sortie illisible du script de capture (code %s)" % getattr(r, "returncode", "?")]}
            except Exception as exc:  # noqa: BLE001 -- ne jamais remonter un secret
                _log.warning("sauvegarde de poste : échec", exc_info=True)
                data = {"erreurs": ["échec : %s" % type(exc).__name__]}
            finally:
                try:
                    import shutil as _sh
                    _sh.rmtree(travail, ignore_errors=True)
                    try:
                        _os.remove(archive)        # copie locale retirée (déjà écrite sur USB/UNC) -- #931 : conservée pour la remontée hub
                    except OSError:
                        pass
                except Exception:  # noqa: BLE001
                    pass
            data.setdefault("montages", bk.manifeste(self.agent_id, confs, montages)["montages"])
            al = bk.constats(data)
            self.queue.put({"task": "sauvegarde-poste", "at": _iso(self.clock()),
                            "ok": not any(x.get("severity") == "critical" for x in al),
                            "agent_id": self.agent_id, "data": dict(data, alerts=al)})
            for a in al:
                try:
                    self.event("sauvegarde", a.get("severity") or "info", a.get("message") or "", {"code": a.get("code")})
                except Exception:  # noqa: BLE001
                    pass

        t = threading.Thread(target=work, name="si-agent-sauvegarde", daemon=True)
        self._sauvegarde = t
        t.start()
        self.event("sauvegarde", "info", "sauvegarde du poste lancée (%d application(s))" % len(confs), {"confs": len(confs)})
        return {"ok": True, "result": {"started": True, "confs": len(confs)}}

    # -- #928 : test d'accès aux services de l'entreprise (brut + authentifié) ------------------------------------
    def _acces_services_lancer(self, params):
        """Mesure en TÂCHE DE FOND le temps d'accès aux sites de service (le secret, injecté par le hub depuis le
        coffre, reste en mémoire : jamais de sous-processus, de fichier ni de trace). Pousse la mesure `acces-services`
        à la fin ; la boucle principale l'envoie au central. Un seul test à la fois."""
        import threading
        from . import accesservices
        cibles = params.get("cibles")
        if not isinstance(cibles, list) or not cibles:
            return {"ok": False, "error": "params.cibles (liste non vide) requis"}
        st = getattr(self, "_acces", None)
        if st is not None and st.is_alive():
            return {"ok": False, "error": "un test d'accès aux services est déjà en cours"}
        try:
            timeout = max(2.0, min(60.0, float(params.get("timeout") or accesservices.TIMEOUT)))
        except (TypeError, ValueError):
            timeout = accesservices.TIMEOUT
        n = len(cibles)

        def work():
            try:
                data = accesservices.mesurer(cibles, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 -- ne jamais remonter un secret dans l'erreur
                _log.warning("test d'accès aux services : échec", exc_info=True)
                data = {"at": _iso(self.clock()), "sites": [], "alerts": [
                    {"code": "acces-services-erreur", "severity": "warning", "message": "test en échec : %s" % type(exc).__name__}]}
            self.queue.put({"task": "acces-services", "at": _iso(self.clock()),
                            "ok": not any(x.get("severity") == "critical" for x in data.get("alerts") or []),
                            "agent_id": self.agent_id, "data": data})
            for al in data.get("alerts") or []:
                try:
                    self.event("acces-services", al.get("severity") or "info", al.get("message") or "", {"code": al.get("code")})
                except Exception:  # noqa: BLE001
                    pass

        t = threading.Thread(target=work, name="si-agent-acces-services", daemon=True)
        self._acces = t
        t.start()
        self.event("acces-services", "info", "test d'accès aux services lancé (%d site(s))" % n, {"sites": n})
        return {"ok": True, "result": {"started": True, "sites": n}}

    # -- #919 : commandes à distance (analyse technique depuis le hub) ---------------------------------------------
    def _shell_commande(self, params):
        from . import remoteshell as rs
        action = str(params.get("action") or "run")
        tid = str(params.get("id") or "")
        if not tid or not all(c.isalnum() or c in "-_" for c in tid) or len(tid) > 40:
            return {"ok": False, "error": "params.id invalide"}
        if action == "stop":
            for p in list(self._shell_file):            # #926 : encore en file -> retirée, jamais exécutée
                if str(p.get("id")) == tid:
                    self._shell_file.remove(p)
                    self.queue.put({"task": "shell:%s" % tid, "at": _iso(self.clock()), "ok": True, "agent_id": self.agent_id,
                                    "data": {"id": tid, "titre": p.get("titre"), "mode": p.get("mode"), "statut": "interrompu",
                                             "code": None, "motif": "retirée de la file avant exécution", "debut": None, "fin": None,
                                             "sortie": "", "tronque": False}})
                    return {"ok": True, "result": {"stopped": tid, "file": True}}
            t = self._shell.get(tid)
            if t is None or t.termine:
                return {"ok": False, "error": "aucune commande %s en cours" % tid}
            t.arreter()
            self.event("remote-shell-stopped", "info", "commande à distance « %s » interrompue depuis le hub" % t.titre, {"id": tid})
            return {"ok": True, "result": {"stopped": tid}}
        if action != "run":
            return {"ok": False, "error": "params.action : run ou stop"}
        mode = str(params.get("mode") or "lecture")
        permis = rs.mode_autorise(self.cfg.get("remote_shell"), self.cfg.get("remote_shell_max"))
        if mode not in ("lecture", "intervention") or rs.rang(mode) > rs.rang(permis):
            return {"ok": False, "error": "commandes à distance : mode « %s » non autorisé sur ce poste (autorisé : %s%s)"
                    % (mode, permis, ", plafonné par agent.json" if self.cfg.get("remote_shell_max") in rs.MODES else "")}
        if self.is_blocked():
            return {"ok": False, "error": "agent bloqué (%s)" % self.block_reason()}
        script = str(params.get("script") or "")
        if not script.strip() or len(script) > 20000:
            return {"ok": False, "error": "script vide ou trop long (20 000 caractères au plus)"}
        if tid in self._shell or any(str(p.get("id")) == tid for p in self._shell_file):
            return {"ok": False, "error": "commande %s déjà reçue" % tid}
        interp = rs.interpreteur()
        if not interp:
            return {"ok": False, "error": "PowerShell introuvable sur ce poste"}
        if self._shell_occupees() >= rs.EN_COURS_MAX:
            # #926 : au-delà de 3 simultanées, mise en FILE (avant : refusée -> 4 analyses lancées d'un coup = 1 échec)
            if len(self._shell_file) >= rs.FILE_MAX:
                return {"ok": False, "error": "file des commandes à distance pleine (%d) : réessayer plus tard" % rs.FILE_MAX}
            self._shell_file.append(dict(params, mode=mode))
            return {"ok": True, "result": {"queued": tid, "position": len(self._shell_file), "mode": mode}}
        return self._shell_demarrer(params, mode, interp)

    def _shell_occupees(self):
        return sum(1 for t in self._shell.values() if not t.termine)

    def _shell_demarrer(self, params, mode, interp):
        from . import remoteshell as rs
        tid, script = str(params.get("id")), str(params.get("script") or "")
        t = rs.Tache(tid, script, mode=mode, titre=params.get("titre"), delai=params.get("delai"),
                     dossier=os.path.join(self._charge_dir(), "shell"), fmt=params.get("format") or "texte",
                     analyse=params.get("analyse"), interp=interp, clock=time.time)
        t.pousse_version, t.pousse_at = -1, None
        self._shell[tid] = t
        t.demarrer()
        self.event("remote-shell", "warning" if mode == "intervention" else "info",
                   "commande à distance « %s » lancée depuis le hub (mode %s)" % (t.titre, mode),
                   {"id": tid, "mode": mode, "sha256": rs.empreinte(script), "par": params.get("par")})
        return {"ok": True, "result": {"started": tid, "mode": mode}}

    def shell_tick(self):
        """#919 : pousse au central la sortie des commandes à distance (au plus une mesure par seconde et par
        commande -- la file locale dédoublonne sur (tâche, instant)), puis oublie les commandes terminées.
        #926 : démarre les commandes en file dès qu'une place se libère."""
        if self._shell_file:
            from . import remoteshell as rs
            while self._shell_file and self._shell_occupees() < rs.EN_COURS_MAX:
                p = self._shell_file.pop(0)
                try:
                    interp = rs.interpreteur()
                    permis = rs.mode_autorise(self.cfg.get("remote_shell"), self.cfg.get("remote_shell_max"))
                    if rs.rang(p.get("mode") or "lecture") > rs.rang(permis):      # réglage changé pendant l'attente
                        r = {"ok": False, "error": "mode « %s » plus autorisé sur ce poste (autorisé : %s)" % (p.get("mode"), permis)}
                    else:
                        r = self._shell_demarrer(p, p.get("mode") or "lecture", interp) if interp else {"ok": False, "error": "PowerShell introuvable"}
                except Exception as exc:  # noqa: BLE001
                    r = {"ok": False, "error": str(exc)[:200]}
                if not r.get("ok"):
                    self.queue.put({"task": "shell:%s" % p.get("id"), "at": _iso(self.clock()), "ok": False, "agent_id": self.agent_id,
                                    "data": {"id": p.get("id"), "titre": p.get("titre"), "mode": p.get("mode"), "statut": "erreur",
                                             "code": None, "motif": r.get("error"), "debut": None, "fin": None, "sortie": "", "tronque": False}})
        if not self._shell:
            return
        at = _iso(self.clock())
        pousse = False
        for tid, t in list(self._shell.items()):
            v = t.version
            if v == t.pousse_version or at == t.pousse_at:
                continue
            fini = t.termine                  # lu AVANT l'état : si vrai, l'état lu ensuite est complet ; sinon une fin
            data = t.etat()                   # survenue entre-temps change la version et sera poussée au tour suivant
            self.queue.put({"task": "shell:%s" % tid, "at": at, "ok": data["statut"] not in ("erreur", "refuse", "delai"),
                            "agent_id": self.agent_id, "data": data})
            t.pousse_version, t.pousse_at, pousse = v, at, True
            if fini:
                del self._shell[tid]
                if t.statut != "fini":
                    self.event("remote-shell-ended", "info", "commande à distance « %s » : %s%s" % (
                        t.titre, t.statut, (" (%s)" % t.motif) if t.motif else ""), {"id": tid, "statut": t.statut})
        if pousse:
            try:
                self.flush(force=True)
            except Exception:  # noqa: BLE001
                _log.debug("commandes à distance : envoi immédiat impossible", exc_info=True)

    def run_one_plugin(self, manifest, args=None):
        if args is not None:                                  # #913 : arguments imposés par la commande (épreuves, paramètres)
            try:
                manifest = dict(manifest, args=[str(x) for x in args])
            except Exception:  # noqa: BLE001
                pass
        live_path = None
        if manifest.get("id") == "poste-charge":              # #913 : suivi direct (--live) + arrêt (--stop)
            try:
                d = self._charge_dir()
                live_path = os.path.join(d, "poste-charge.live.ndjson")
                stop_path = os.path.join(d, "poste-charge.stop")
                for pth in (live_path, stop_path):
                    try:
                        os.remove(pth)
                    except OSError:
                        pass
                a = list(manifest.get("args") or [])
                if "--live" not in a:
                    a += ["--live", live_path]
                if "--stop" not in a:
                    a += ["--stop", stop_path]
                manifest = dict(manifest, args=a)
            except Exception:  # noqa: BLE001
                live_path = None
                _log.warning("poste-charge : préparation du suivi direct impossible", exc_info=True)
        env = {"SI_AGENT_ID": self.agent_id, "SI_AGENT_SITE": str(self.cfg.get("site") or "")}
        confine = self._confinement(manifest)
        _log.debug("sonde %s : lancement (%s, privilégiée=%s, utilisateur=%s)", manifest["id"], manifest.get("runner"),
                   bool(manifest.get("privileged")), (confine or {}).get("preexec_fn") and self._plugins_user_effective())
        _t0 = time.time()
        meas = plugins.run_plugin(manifest, self.cmd, now=self.clock(), env=env, confine=confine,
                                  python=plugin_python(sys.executable, IS_WINDOWS, run_as_root=_euid() == 0 and not ((confine or {}).get("run_as") or (0,))[0]))
        meas["agent_id"] = self.agent_id
        self.tracker.record("plugin:%s" % manifest["id"], time.time() - _t0, ok=bool(meas.get("ok")))  # #616
        self.queue.put(meas)
        if live_path:                                         # #913 : courbe de tension -> central
            try:
                self._charge_pousser_live(live_path)
            except Exception:  # noqa: BLE001
                _log.warning("poste-charge : poussée du suivi direct impossible", exc_info=True)
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
            if plugins.a_la_demande(m):                # #925 : test de charge & co : jamais sans commande
                continue
            if self._next_plugin.get(m["id"], 0) > now:
                continue
            fond = self._en_fond(m)
            if fond and not self._fond_libre(m["id"]):  # déjà en cours / trop de sondes longues : on repasse au tour suivant
                continue
            # Échéance fixée AVANT l'exécution : un plugin lent garde son rythme.
            _iv = float(m.get("interval_seconds", 3600))
            if self._bench_until > now:  # #616 : banc de charge, cadence forcée
                from . import introspect as _intro
                _iv = _intro.forced_interval(_iv, self._bench_factor)
            self._next_plugin[m["id"]] = now + _iv
            if fond:
                self._fond_lancer(m)
                continue
            produced.append(self.run_one_plugin(m))
        return produced

    # -- #925 : sondes longues en tâche de fond -----------------------------------------------------------------
    def _en_fond(self, m):
        """Sonde longue (délai > 2 min, ex. poste-windows : 10 min) exécutée dans un thread : la boucle continue de
        relever, de prendre les commandes et la configuration pendant qu'elle tourne. Avant, un relevé poste-windows
        bloquait l'agent jusqu'à 10 min (commandes « en attente », « configuration en attente »). Windows seulement
        par défaut : sous Linux le confinement passe par preexec_fn, non sûr en présence de threads
        (`plugins_background: true` l'active quand même)."""
        if not self._fond_autorise or m.get("id") == "poste-charge":
            return False
        try:
            return int(m.get("timeout_seconds") or 60) > FOND_SEUIL_S
        except (TypeError, ValueError):
            return False

    def _fond_libre(self, pid):
        for k, t in list(self._fond.items()):
            if not t.is_alive():
                del self._fond[k]
        return pid not in self._fond and len(self._fond) < FOND_MAX

    def sondes_en_fond(self):
        """Identifiants des sondes longues en cours (état de l'agent)."""
        return sorted(k for k, t in self._fond.items() if t.is_alive())

    def _fond_lancer(self, manifest, args=None):
        import threading
        pid = manifest["id"]
        if not self._fond_libre(pid):
            return {"ok": False, "error": "sonde %s déjà en cours" % pid if pid in self._fond
                    else "déjà %d sondes longues en cours : réessayer dans quelques minutes" % FOND_MAX}

        def work():
            try:
                self.run_one_plugin(manifest, args=args)   # mesure + événement d'échec mis en file depuis ce thread
            except Exception:  # noqa: BLE001
                _log.warning("sonde %s (fond) : exécution en échec", pid, exc_info=True)

        t = threading.Thread(target=work, name="si-agent-sonde-%s" % pid, daemon=True)
        self._fond[pid] = t
        t.start()
        _log.info("sonde %s lancée en tâche de fond", pid)
        return {"ok": True, "result": {"started": True, "en_fond": True,
                                       "note": "résultat dans la mesure plugin:%s à la fin de l'exécution" % pid}}

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

    # -- vue locale de transparence (#819) -----------------------------------
    def local_view_data(self):
        """JSON de la vue locale : identité, sondes, dernières mesures, journal, configuration (secrets masqués)."""
        tasks, _ = self.recorder.snapshot()
        last = {t["task"]: t for t in tasks}
        rows = localview.plugin_rows(self.store.list(), lambda m: plugins.is_enabled(m, self.cfg.get("plugins")),
                                     lambda m: bool(m.get("blocked")) or bool(control.plugin_blocked(self.state, m)),
                                     dict(self._next_plugin), last)
        info = {"agent_id": self.agent_id, "host": socket.gethostname(), "version": __import__("si_agent").__version__,
                "site": self.cfg.get("site"), "central_url": self.cfg.get("central_url"), "config_version": self.config_version,
                "started_at": self._started_at, "last_central_contact": self.last_central_contact, "pending": self._lv_pending,
                "blocked": self.is_blocked(), "block_reason": self.block_reason() if self.is_blocked() else None,
                "block_file": self.cfg.get("block_file"), "uninstall": uninstall_hint()}
        return localview.build_view(info, self.cfg, rows, self.recorder, now=time.time())

    def local_view_tick(self):
        lv = localview.merged(self.cfg.get("local_view"))
        srv = self._local_view
        if not lv["enabled"]:
            if srv:
                srv.stop(); self._local_view = None
                self.event("local-view-stopped", "info", "vue locale arrêtée")
            return
        key = (lv["port"], lv["bind"], tuple(lv["allow"]))
        if srv and self._lv_key != key:
            srv.stop(); srv = self._local_view = None
        if not srv:
            if self.clock() < self._lv_retry:
                return
            try:
                srv = localview.LocalViewServer(lv["port"], self.local_view_data, bind=lv["bind"], allow=lv["allow"])
                srv.start()
            except OSError as exc:
                self._lv_retry = self.clock() + 300
                self.event("local-view-failed", "warning", "vue locale impossible sur le port %d : %s" % (lv["port"], exc))
                return
            self._local_view, self._lv_key = srv, key
            shown = "127.0.0.1" if lv["bind"] in ("0.0.0.0", "::") else lv["bind"]
            self.event("local-view-started", "info", "vue locale (lecture seule) sur http://%s:%d/" % (shown, srv.port),
                       {"bind": lv["bind"], "port": srv.port, "allow": lv["allow"]})
        if self.clock() >= self._lv_next:
            self._lv_next = self.clock() + 10
            try:
                self._lv_pending = self.queue.pending_count()
            except Exception:  # noqa: BLE001
                self._lv_pending = None

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
               "last_report": self.clock(), "command": command_id, "delete_after": bool(delete_after), "sha256": None,
               "push": getattr(self, "_upload_push", None)}       # #751 : récepteur LAN du nœud au lieu du central
        self._upload_job = job
        threading.Thread(target=self._upload_worker, args=(job,), daemon=True, name="si-agent-upload").start()
        self.event("image-upload-started", "info", "transfert de %s vers %s (%.1f Go)" % (name, "le nœud sur le LAN" if job["push"] else "le central", total / 2**30), {"command": command_id, "file": path, "bytes": total})
        return {"ok": True, "result": {"file": path, "bytes": total, "message": "transfert lancé -- suivi par événements"}}

    def _upload_worker(self, job):
        """Fil à part : reprise (GET status), morceaux signés (PUT), clôture (POST complete)."""
        from . import uploadctl
        base = "%s/agents/%s/images/%s" % (protocol.API_PREFIX, self.agent_id, job["name"])
        cli = self.http
        if job.get("push"):                     # #751 : directement vers l'agent du nœud, sur le LAN (même protocole)
            from . import lanpush
            cli, base = lanpush.Client(job["push"]["url"], job["push"]["token"]), "/p2v/%s" % job["name"]
        try:
            st, body = cli.request("GET", base + "/status")
            offset = int((body or {}).get("size") or 0) if st == 200 else 0
            if offset > job["total"]:
                offset = 0
            with open(job["path"], "rb") as fh:
                def read(pos, n):
                    fh.seek(pos)
                    return fh.read(n)
                h = uploadctl.prefix_digest(read, offset)
                job["sent"] = offset
                from . import p2vctl
                t_start, sent0, mbps = time.time(), offset, float(getattr(self, "_upload_bwlimit", 0) or 0)
                for pos, n in uploadctl.plan_chunks(job["total"], offset):
                    data = read(pos, n)
                    h.update(data)
                    attempt = 0
                    while attempt < 5:
                        st, body = cli.send_raw("PUT", "%s?offset=%d" % (base, pos), data, timeout=300)
                        if st in (200, 201):
                            break
                        if st == 429:                     # #748 : fenêtre du relais pleine -- la cible lit encore, on attend sans compter d'échec
                            job["waiting"] = True
                            time.sleep(int((body or {}).get("retry_after") or 15) if isinstance(body, dict) else 15)
                            continue
                        attempt += 1
                        if st == 409 and isinstance(body, dict) and "size" in body:
                            raise RuntimeError("décalage de reprise : %s" % body.get("error"))
                        time.sleep(5 * (attempt + 1))
                    else:
                        raise RuntimeError("morceau à %d refusé (%s %s)" % (pos, st, (body or {}).get("error") if isinstance(body, dict) else ""))
                    job["sent"] = pos + n; job["waiting"] = False
                    pause = p2vctl.throttle_sleep(job["sent"] - sent0, time.time() - t_start, mbps)
                    if pause:
                        time.sleep(min(pause, 30))
            job["sha256"] = h.hexdigest()
            st, body = cli.request("POST", base + "/complete", {"size": job["total"], "sha256": job["sha256"]})
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

    def start_sbom(self, install=False, command_id=None):
        """#699 : inventaire syft en arrière-plan (un seul à la fois) ; compte rendu en état + évènement."""
        import threading
        from . import sbomctl
        if getattr(self, "_sbom_running", False):
            return False
        self._sbom_running = True

        def fetch(url):
            ctx = ssl.create_default_context(cafile=self.cfg.get("ca_file")) if self.cfg.get("ca_file") else ssl.create_default_context()
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "si-agent"}), timeout=300, context=ctx) as resp:
                return resp.read()

        def upload(gz, kind="host", name=None):
            path = protocol.API_PREFIX + "/agents/%s/sbom" % self.agent_id
            if kind != "host":                         # #711 : la requête fait partie du chemin signé
                path += "?" + urllib.parse.urlencode({"kind": kind, "name": name or ""})
            return self.http.send_raw("POST", path, gz, timeout=600, content_type="application/gzip")

        def work():
            now = self.clock()
            try:
                system = sbomctl.system_name()
                r = sbomctl.inventory(upload, fetch=fetch, install=install, system=system,
                                      tools_dir=os.path.join(os.path.dirname(self.cfg.get("queue_path") or "/var/lib/si-agent/x"), "tools"),
                                      installed=self._installed_software() if system != "linux" else None,
                                      images=system == "linux" and self.state.get("sbom_images", True))
            except Exception as exc:  # noqa: BLE001 -- jamais d'arrêt de l'agent pour un inventaire
                r = {"ok": False, "error": str(exc)[:300]}
            days = float(self.state.get("sbom_schedule_days") or 7)
            central = r.get("central") if isinstance(r.get("central"), dict) else {}
            self.state["sbom_last"] = {"at": _iso(now), "ok": r.get("ok"), "error": r.get("error"), "components": r.get("components"),
                                       "findings": central.get("findings"), "asset": central.get("asset"), "command": command_id}
            # échec : nouvel essai dans 6 h plutôt qu'à la prochaine période
            self.state["sbom_last_at"] = now if r.get("ok") else now - days * 86400 + 6 * 3600
            self._save_state()
            self.state["sbom_last"]["images"] = [{k: i.get(k) for k in ("name", "ok", "components", "findings", "error")} for i in r.get("images") or []]
            self._save_state()
            if r.get("ok"):
                imgs = r.get("images") or []
                self.event("sbom-sent", "info", "inventaire logiciel envoyé : %s composant(s), %s vulnérabilité(s) relevée(s)%s"
                           % (r.get("components"), central.get("findings", "?"), (" ; %d image(s) Docker" % len(imgs)) if imgs else ""),
                           {"components": r.get("components"), "by_type": r.get("by_type"), "images": len(imgs)})
            else:
                self.event("sbom-failed", "warning", "inventaire logiciel en échec : %s" % r.get("error"), {"error": r.get("error")})
            self._sbom_running = False

        threading.Thread(target=work, name="sbom", daemon=True).start()
        return True

    def p2v_action(self, params, command_id=None):
        """#748 : voir p2vctl."""
        from . import p2vctl, imagectl
        p = dict(params or {})
        action = str(p.get("action") or "")
        if action == "prepare_source":
            drives = [str(d) for d in (p.get("drives") or ["C:"])][:8]
            used = 0
            if IS_WINDOWS:
                for d in drives:
                    u = imagectl.used_bytes(getattr(self.cmd(["fsutil.exe", "volume", "diskfree", d], timeout=30), "stdout", "") or "")
                    used += u or 0
                cands = p2vctl.windows_drives()
                system = (os.environ.get("SystemDrive") or "C:") + "\\"
            else:
                import shutil as _sh
                used = _sh.disk_usage("/").used
                try:
                    cands = p2vctl.linux_mounts(open("/proc/mounts").read())
                except OSError:
                    cands = []
                system = "/"
            given = str(p.get("target") or "").strip() or None
            if given and not any(str(c["path"]).rstrip("\\/") == given.rstrip("\\/") for c in cands):
                try:
                    import shutil as _sh
                    cands.append({"path": given, "free": _sh.disk_usage(given).free})
                except OSError as exc:
                    return {"ok": False, "error": "cible %s inaccessible : %s" % (given, exc)}
            target, rows = p2vctl.choose_source_target(used, cands, system, given)
            if not target:
                return {"ok": False, "error": "aucun emplacement avec %d Go libres (image ~%d Go) : brancher un disque, un partage, ou libérer de la place" % (p2vctl.need_with_margin(used) // 2**30, used // 2**30),
                        "need_bytes": used, "candidates": rows}
            return {"ok": True, "message": "image ~%d Go -> %s" % (used // 2**30, target), "need_bytes": used, "target": target, "candidates": rows}
        if action == "prepare_target":
            job = str(p.get("job") or "")
            if not p2vctl.JOB_RE.match(job):
                return {"ok": False, "error": "job : minuscules, chiffres, tirets (32 max)"}
            need = int(p.get("need_bytes") or 0)
            storage = str(p.get("storage") or "local-lvm")
            try:
                cfg = p2vctl.parse_storage_cfg(open("/etc/pve/storage.cfg").read(), storage)
            except OSError as exc:
                return {"ok": False, "error": "pas un nœud Proxmox (storage.cfg illisible : %s)" % exc}
            if not cfg or cfg.get("type") != "lvmthin":
                return {"ok": False, "error": "stockage %s : LVM-thin attendu pour le volume temporaire (%s)" % (storage, (cfg or {}).get("type") or "inconnu")}
            vg, pool = cfg.get("vgname"), cfg.get("thinpool")
            free = p2vctl.thin_free(getattr(self.cmd(["lvs", "--noheadings", "--units", "b", "--nosuffix", "-o", "lv_size,data_percent", "%s/%s" % (vg, pool)], timeout=30), "stdout", "") or "")
            size_gb = p2vctl.lv_size_gb(need)
            # place pour le volume temporaire ET le disque importé (les deux coexistent pendant l'import)
            if free is not None and free < 2 * size_gb * 2**30:
                return {"ok": False, "error": "pool %s/%s : %d Go libres, il en faut ~%d (volume temporaire + disque importé)" % (vg, pool, free // 2**30, 2 * size_gb)}
            lv, mnt, steps = p2vctl.target_argv(vg, pool, job, size_gb)
            if os.path.ismount(mnt):
                return {"ok": True, "message": "volume %s déjà monté sur %s" % (lv, mnt), "import_dir": mnt, "job": job, "vg": vg}
            for argv in steps:
                r = self.cmd(argv, timeout=300)
                if getattr(r, "returncode", 1) != 0:
                    return {"ok": False, "error": "%s : %s" % (" ".join(argv[:2]), ((getattr(r, "stderr", "") or "")[-200:] or "échec"))}
            return {"ok": True, "message": "volume temporaire %s (%d Go) monté sur %s" % (lv, size_gb, mnt), "import_dir": mnt, "job": job, "vg": vg, "size_gb": size_gb, "pool_free": free}
        if action == "cleanup":
            job, vg = str(p.get("job") or ""), str(p.get("vg") or "pve")
            if not p2vctl.JOB_RE.match(job) or not re.match(r"^[A-Za-z0-9_.-]{1,64}$", vg):
                return {"ok": False, "error": "job / vg invalides"}
            errs = []
            for argv in p2vctl.cleanup_argv(vg, job):
                r = self.cmd(argv, timeout=300)
                if getattr(r, "returncode", 1) != 0:
                    errs.append("%s : %s" % (argv[0], (getattr(r, "stderr", "") or "")[-160:]))
            rx = getattr(self, "_p2v_rx", None)
            if rx:                                  # #751 : récepteur LAN fermé avec le volume
                rx.close(); self._p2v_rx = None
            return {"ok": not errs, "error": "; ".join(errs) or None, "message": "volume temporaire p2v-%s supprimé" % job}
        if action == "fetch":
            return self.start_p2v_fetch(p, command_id)
        if action == "receive":
            return self.start_p2v_receive(p, command_id)
        if action == "status":
            j = getattr(self, "_fetch_job", None)
            return {"ok": True, "fetch": {k: v for k, v in (j or {}).items() if k != "hash"} if j else None}
        return {"ok": False, "error": "action : prepare_source, prepare_target, fetch, status, cleanup"}

    @staticmethod
    def _push_target(params):
        """#751 : destination LAN d'un envoi d'image ({url, token}) ou None (central)."""
        url, tok = str(params.get("push_url") or ""), str(params.get("push_token") or "")
        if url and tok and re.match(r"^http://[0-9A-Za-z.:\[\]-]{1,80}$", url):
            return {"url": url, "token": tok}
        return None

    def start_p2v_receive(self, p, command_id=None):
        """#751 : récepteur temporaire sur l'IP LAN du nœud ; l'agent du poste y pousse son image directement (le hub ne
        voit passer que les commandes et les événements). Jeton à usage unique ; fermé après clôture ou inactivité."""
        import ipaddress
        import secrets
        import urllib.parse as _up
        from . import lanpush, p2vctl
        import_dir = str(p.get("import_dir") or "")
        if not import_dir.startswith(p2vctl.IMPORT_ROOT + "/") or ".." in import_dir or not os.path.isdir(import_dir):
            return {"ok": False, "error": "import_dir : dossier existant sous %s (prepare_target d'abord)" % p2vctl.IMPORT_ROOT}
        src_ip, lan_ip = str(p.get("source_ip") or "") or None, str(p.get("lan_ip") or "") or None
        try:
            for ip in (src_ip, lan_ip):
                if ip:
                    ipaddress.ip_address(ip)
            port = int(p.get("port") or 6461)
        except ValueError:
            return {"ok": False, "error": "source_ip / lan_ip / port invalides"}
        old = getattr(self, "_p2v_rx", None)
        if old:
            old.close()
        tok = secrets.token_urlsafe(24)

        def done(d):
            self.event("image-fetched", "info", "image %s reçue du poste sur le LAN (%.1f Go, sha256 %s)" % (d["name"], d["bytes"] / 2**30, d["sha256"][:12]),
                       dict(d, source="lan", command=command_id))
        try:
            self._p2v_rx = lanpush.Receiver(import_dir, tok, on_complete=done, allow_ip=src_ip, port=port)
        except OSError as exc:
            return {"ok": False, "error": "port %d indisponible : %s" % (port, exc)}
        ip = lan_ip or lanpush.local_ip_towards(src_ip or (_up.urlparse(self.cfg.get("central_url") or "").hostname or "192.0.2.1"))
        self.event("p2v-receive-open", "info", "récepteur LAN ouvert sur %s:%d -> %s%s" % (ip, self._p2v_rx.port, import_dir, (" (seule source admise : %s)" % src_ip) if src_ip else ""), {"command": command_id})
        return {"ok": True, "url": "http://%s:%d" % (ip, self._p2v_rx.port), "token": tok, "ip": ip, "port": self._p2v_rx.port,
                "message": "récepteur ouvert : le poste pousse son image directement sur le LAN"}

    def start_p2v_fetch(self, p, command_id=None):
        """#748 : lecture au fil de l'eau, par le relais du central, de l'image de l'agent source ; débit borné ;
        condensé SHA-256 vérifié contre celui annoncé par la source ; événement image-fetched (chemin local)."""
        import hashlib
        import threading
        from . import p2vctl
        src = str(p.get("source_agent") or "")
        import_dir = str(p.get("import_dir") or "")
        if not re.match(r"^[A-Za-z0-9._-]{1,64}$", src):
            return {"ok": False, "error": "source_agent invalide"}
        if not import_dir.startswith(p2vctl.IMPORT_ROOT + "/") or ".." in import_dir or not os.path.isdir(import_dir):
            return {"ok": False, "error": "import_dir : dossier existant sous %s (prepare_target d'abord)" % p2vctl.IMPORT_ROOT}
        j = getattr(self, "_fetch_job", None)
        if j and j.get("state") == "running":
            return {"ok": False, "error": "lecture déjà en cours (%s)" % j.get("name")}
        mbps, window = float(p.get("bwlimit_mbps") or 0), float(p.get("window_gb") or 4)
        job = {"state": "running", "source": src, "import_dir": import_dir, "name": None, "have": 0, "total": None, "started": self.clock(),
               "command": command_id, "error": None, "path": None}
        self._fetch_job = job

        def work():
            h, fh, t0, have0, idle = hashlib.sha256(), None, time.time(), 0, 0
            try:
                while True:
                    path = "%s/agents/%s/relay/%s?offset=%d&window_gb=%s" % (protocol.API_PREFIX, self.agent_id, src, job["have"], window)
                    st, hdr, data = self.http.get_raw_signed(path)
                    hdr = {k.lower(): v for k, v in hdr.items()}
                    name = hdr.get("x-relay-name") or None
                    if name and not job["name"]:
                        if not p2vctl.NAME_RE.match(name):
                            raise RuntimeError("nom d'image refusé : %r" % name)
                        job["name"] = name
                        part = os.path.join(import_dir, name + ".part")
                        if os.path.exists(part):            # reprise : on rattrape le condensé de ce qui est déjà là
                            with open(part, "rb") as r_:
                                for chunk in iter(lambda: r_.read(1 << 20), b""):
                                    h.update(chunk)
                            job["have"] = have0 = os.path.getsize(part)
                            continue
                        fh = open(part, "ab")
                    if st == 200 and data:
                        if fh is None:
                            fh = open(os.path.join(import_dir, job["name"] + ".part"), "ab")
                        fh.write(data); h.update(data); job["have"] += len(data); idle = 0
                        pause = p2vctl.throttle_sleep(job["have"] - have0, time.time() - t0, mbps)
                        if pause:
                            time.sleep(min(pause, 30))
                        continue
                    if st == 204:
                        if hdr.get("x-relay-complete") == "1" and job["name"] and job["have"] >= int(hdr.get("x-relay-total") or -1):
                            job["total"] = job["have"]
                            if fh:
                                fh.close(); fh = None
                            want = (hdr.get("x-relay-sha256") or "").lower()
                            if want and h.hexdigest() != want:
                                raise RuntimeError("condensé différent de celui de la source : image corrompue")
                            final = os.path.join(import_dir, job["name"])
                            os.replace(final + ".part", final)
                            job.update(state="finished", path=final, sha256=h.hexdigest())
                            return
                        idle += 1
                        if idle > 12 * 360:                 # 12 h sans rien de neuf
                            raise RuntimeError("source muette depuis 12 h")
                        time.sleep(10)
                        continue
                    raise RuntimeError("relais : HTTP %s" % st)
            except Exception as exc:  # noqa: BLE001
                job.update(state="failed", error=str(exc)[:300])
            finally:
                if fh:
                    fh.close()

        def report():
            last = 0
            while job["state"] == "running":
                time.sleep(20)
                if time.time() - last >= 300 and job["have"]:
                    last = time.time()
                    self.event("p2v-fetch-progress", "info", "lecture de %s : %.1f Go reçus" % (job["name"] or "?", job["have"] / 2**30), {"have": job["have"], "source": src})
            if job["state"] == "finished":
                self.event("image-fetched", "info", "image %s reçue de %s par le relais (%.1f Go, sha256 %s)" % (job["name"], src, job["have"] / 2**30, job["sha256"][:12]),
                           {"path": job["path"], "name": job["name"], "sha256": job["sha256"], "bytes": job["have"], "source": src, "command": command_id})
            else:
                self.event("image-fetch-failed", "warning", "lecture de l'image de %s en échec : %s (relancer fetch : reprise)" % (src, job["error"]), {"source": src, "have": job["have"]})

        threading.Thread(target=work, name="p2v-fetch", daemon=True).start()
        threading.Thread(target=report, name="p2v-fetch-report", daemon=True).start()
        return {"ok": True, "message": "lecture de l'image de %s lancée vers %s (débit %s)" % (src, import_dir, ("%g Mbit/s" % mbps) if mbps else "libre")}

    def xfer_action(self, params, command_id=None):
        """#750 : rapatriement d'un CT / d'une VM depuis un nœud Proxmox distant (pve-remote.json) -- export (vzdump --stdout
        par ssh, débit borné) puis restauration locale, vérification original / copie, destruction de l'original par tranches.
        Chaque action est détachée ; fin signalée par xfer-done / xfer-failed (details.command = id de la commande)."""
        import subprocess
        import tempfile
        import threading
        from . import xferctl
        p = dict(params or {})
        action = str(p.get("action") or "")
        if action == "status":
            j = getattr(self, "_xfer_job", None)
            return {"ok": True, "job": {k: v for k, v in (j or {}).items() if k != "proc"} if j else None,
                    "verified": self.state.get("xfer_verified", {})}
        if action in ("leftovers", "purge"):          # #765 : restes du rapatriement sur ce nœud
            return self._xfer_leftovers(action, p)
        need = {"export": ("vmid", "newid", "storage"), "verify": ("vmid", "newid"), "destroy": ("vmid", "copy")}.get(action)
        if not need:
            return {"ok": False, "error": "action : export, verify, destroy, status, leftovers, purge"}
        q, err = xferctl.check(p, need)
        if err:
            return {"ok": False, "error": err}
        try:
            with open(self.cfg.get("pve_remote") or xferctl.REMOTE_FILE, encoding="utf-8") as fh:
                h = xferctl.load_remotes(fh.read()).get(q["remote"])
        except OSError:
            h = None
        if not h:
            return {"ok": False, "error": "nœud distant %s absent de %s" % (q["remote"], self.cfg.get("pve_remote") or xferctl.REMOTE_FILE)}
        if h.get("key") and not os.path.exists(h["key"]):   # #768
            return {"ok": False, "error": "clé %s introuvable pour le service si-agent (ProtectHome masque /root et /home) : la placer dans /etc/si-agent/keys/ (chmod 600) et corriger pve-remote.json" % h["key"]}
        j = getattr(self, "_xfer_job", None)
        if j and j.get("state") == "running":
            return {"ok": False, "error": "rapatriement déjà en cours (%s %s)" % (j.get("action"), j.get("vmid"))}
        tool = xferctl.tool(q["kind"])

        def exists(vmid):
            try:
                return subprocess.run([tool, "status", str(vmid)], capture_output=True, text=True, timeout=60).returncode == 0
            except (OSError, subprocess.SubprocessError):
                return False

        key = "%s:%d" % (q["remote"], q["vmid"])
        if action == "export" and exists(q["newid"]):
            return {"ok": False, "error": "l'identifiant %d existe déjà sur ce nœud" % q["newid"]}
        if action == "destroy":
            if q["confirm"] != str(q["vmid"]):
                return {"ok": False, "error": "confirm doit répéter le vmid distant (%d)" % q["vmid"]}
            ver = self.state.get("xfer_verified", {}).get(key)
            if not ver or int(ver.get("copy") or 0) != q["copy"]:
                return {"ok": False, "error": "destruction refusée : pas de vérification réussie de %s contre la copie %d (action verify d'abord)" % (key, q["copy"])}
            if not exists(q["copy"]):
                return {"ok": False, "error": "la copie locale %d n'existe plus : destruction refusée" % q["copy"]}
        job = {"state": "running", "action": action, "remote": q["remote"], "vmid": q["vmid"], "command": command_id, "started": self.clock(),
               "bytes": 0, "progress": "", "error": None, "result": None}
        self._xfer_job = job

        def done(ok, msg, result=None):
            job.update(state="finished" if ok else "failed", result=result, error=None if ok else msg)
            self.event("xfer-done" if ok else "xfer-failed", "info" if ok else "warning", "%s %s %d : %s" % (action, q["remote"], q["vmid"], msg),
                       {"command": command_id, "action": action, "remote": q["remote"], "vmid": q["vmid"], "result": result})

        def export():
            stamp = time.strftime("%Y_%m_%d-%H_%M_%S")
            archive = os.path.join(q["dumpdir"], xferctl.archive_name(q["kind"], q["vmid"], stamp))
            try:
                with open(archive + ".part", "wb") as out:
                    proc = subprocess.Popen(xferctl.export_argv(h, q), stdout=out, stderr=subprocess.PIPE)
                    job["proc"] = proc; last = time.time()
                    while proc.poll() is None:
                        time.sleep(10)
                        job["bytes"] = os.path.getsize(archive + ".part")
                        if time.time() - last >= 300:
                            last = time.time()
                            self.event("xfer-progress", "info", "export de %s %d : %.1f Go reçus" % (q["remote"], q["vmid"], job["bytes"] / 2**30), {"command": command_id, "bytes": job["bytes"]})
                    errtxt = (proc.stderr.read() or b"").decode("utf-8", "replace")
                if proc.returncode != 0:
                    raise RuntimeError("vzdump distant : code %d -- %s" % (proc.returncode, errtxt.strip().splitlines()[-1:] or ""))
                os.replace(archive + ".part", archive)
                job["bytes"] = os.path.getsize(archive); job["progress"] = "restauration"
                r = subprocess.run(xferctl.restore_argv(q, archive), capture_output=True, text=True, timeout=24 * 3600)
                if r.returncode != 0:
                    raise RuntimeError("restauration : %s" % ((r.stderr or r.stdout).strip().splitlines()[-1:] or ["code %d" % r.returncode])[0])
                conf = subprocess.run([tool, "config", str(q["newid"])], capture_output=True, text=True, timeout=60).stdout
                if not q["keep_archive"]:
                    os.unlink(archive)
                done(True, "copié en %d (%.1f Go)" % (q["newid"], job["bytes"] / 2**30),
                     {"newid": q["newid"], "bytes": job["bytes"], "archive": archive if q["keep_archive"] else None, "config": conf[:2000]})
            except Exception as exc:  # noqa: BLE001
                done(False, str(exc)[:300])

        def verify():
            try:
                with tempfile.TemporaryDirectory() as d:
                    lo, re_ = os.path.join(d, "copie"), os.path.join(d, "orig")
                    with open(lo, "w") as fh:
                        r1 = subprocess.run(["bash", "-c", xferctl.list_script(q["kind"], q["newid"])], stdout=fh, stderr=subprocess.PIPE, text=True, timeout=6 * 3600)
                    with open(re_, "w") as fh:
                        r2 = subprocess.run(xferctl.ssh_argv(h) + [xferctl.list_script(q["kind"], q["vmid"])], stdout=fh, stderr=subprocess.PIPE, text=True, timeout=6 * 3600)
                    for r, who in ((r1, "copie %d" % q["newid"]), (r2, "original %d" % q["vmid"])):
                        if r.returncode != 0:
                            raise RuntimeError("liste de %s impossible : %s" % (who, (r.stderr or "").strip().splitlines()[-1:] or "code %d" % r.returncode))
                    with open(lo) as a, open(re_) as b:
                        res = xferctl.compare(xferctl.parse_list(b.read()), xferctl.parse_list(a.read()))
                res.update(newid=q["newid"])
                if res["identical"]:
                    self.state.setdefault("xfer_verified", {})[key] = {"copy": q["newid"], "at": _iso(self.clock())}
                    self._save_state()
                    done(True, "copie %d identique (%d fichiers ; %d exclus par vzdump)" % (q["newid"], res["copy_files"], res["vzdump_excluded"]), res)
                else:
                    done(False, "différences : %d absents de la copie, %d en trop, %d modifiés" % (res["missing"], res["extra"], res["changed"]), res)
            except Exception as exc:  # noqa: BLE001
                done(False, str(exc)[:300])

        def destroy():
            try:
                t0 = time.time()
                while not xferctl.in_window(q["window"], time.strftime("%H:%M")):
                    job["progress"] = "attente de la plage %s" % q["window"]
                    if time.time() - t0 > 24 * 3600:
                        raise RuntimeError("plage %s jamais atteinte en 24 h" % q["window"])
                    time.sleep(60)
                job["progress"] = "réduction par tranches"
                proc = subprocess.Popen(xferctl.ssh_argv(h) + [xferctl.destroy_script(q)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                job["proc"] = proc; last, lines = time.time(), []
                for line in proc.stdout:
                    lines = (lines + [line.strip()])[-20:]; job["progress"] = line.strip()[:200]
                    if time.time() - last >= 300:
                        last = time.time()
                        self.event("xfer-progress", "info", "destruction de %s %d : %s" % (q["remote"], q["vmid"], job["progress"]), {"command": command_id})
                proc.wait()
                if proc.returncode != 0 or "DESTROY-OK" not in lines:
                    raise RuntimeError("code %d -- %s" % (proc.returncode, " | ".join(lines[-3:])))
                self.state.get("xfer_verified", {}).pop(key, None); self._save_state()
                done(True, "original détruit (copie locale %d)" % q["copy"], {"log": lines})
            except Exception as exc:  # noqa: BLE001
                done(False, str(exc)[:300])

        threading.Thread(target={"export": export, "verify": verify, "destroy": destroy}[action], name="xfer-" + action, daemon=True).start()
        return {"ok": True, "message": "%s de %s %d lancé%s" % (action, q["remote"], q["vmid"], (" (plage %s)" % q["window"]) if q["window"] and action == "destroy" else "")}

    def _xfer_leftovers(self, action, p):
        """#765 : liste des restes (archives, .part, images en boucle) ou purge validée d'un élément."""
        import glob
        import subprocess
        from . import leftovers as lo

        def run(argv):
            try:
                r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
                return r.returncode, r.stdout or "", r.stderr or ""
            except (OSError, subprocess.SubprocessError) as e:
                return 1, "", str(e)

        def walk(d):
            out = []
            try:
                for e in os.scandir(d):
                    if e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        out.append((e.path, st.st_size, st.st_mtime))
            except OSError:
                pass
            return out

        def stat(path):
            try:
                st = os.stat(path)
                return st.st_size, st.st_mtime
            except OSError:
                return None

        def items():
            confs = {}
            for d in lo.CONF_GLOB_DIRS:
                for f in glob.glob(os.path.join(d, "*.conf")):
                    try:
                        with open(f, encoding="utf-8", errors="replace") as fh:
                            confs[os.path.basename(f)] = fh.read()
                    except OSError:
                        pass
            j = getattr(self, "_xfer_job", None) or {}
            busy = set()
            if j.get("state") == "running":
                busy.update(x for x in glob.glob(os.path.join(lo.DEFAULT_DIRS[0], "vzdump-*-%s-*" % j.get("vmid"))))
            try:
                with open("/proc/mounts", encoding="utf-8") as fh:
                    mounts = fh.read()
            except OSError:
                mounts = ""
            dirs = self.cfg.get("xfer_leftover_dirs") or lo.DEFAULT_DIRS
            return lo.scan(dirs, walk, run(["losetup", "-J", "-l"])[1], mounts, stat, confs, busy)

        its = items()
        if action == "leftovers":
            return {"ok": True, "items": its, "dirs": self.cfg.get("xfer_leftover_dirs") or lo.DEFAULT_DIRS}
        it, err = lo.check_purge(p, its)

        def audit(ok, msg):
            try:
                os.makedirs(os.path.dirname(lo.AUDIT_LOG), exist_ok=True)
                with open(lo.AUDIT_LOG, "a", encoding="utf-8") as fh:
                    fh.write(lo.audit_line(it, p, ok, msg) + "\n")
            except OSError:
                pass
        if err:
            audit(False, err)
            return {"ok": False, "error": err}
        for argv in lo.purge_steps(it):
            rc, _o, e = run(argv)
            if rc != 0:
                msg = "%s : %s" % (" ".join(argv), (e.strip().splitlines() or ["code %d" % rc])[-1])
                audit(False, msg)
                return {"ok": False, "error": msg}
        try:
            if not it.get("missing"):
                os.unlink(it["path"])
        except OSError as e:
            audit(False, str(e))
            return {"ok": False, "error": "effacement de %s : %s" % (it["path"], e)}
        msg = "%s supprimé (%.1f Go libérés)%s" % (it["path"], (it.get("size") or 0) / 2**30, " après démontage" if it.get("loop") else "")
        audit(True, msg)
        self.event("xfer-purge", "info", msg, {"path": it["path"], "size": it.get("size"), "actor": p.get("actor"), "reason": p.get("reason"), "force": bool(p.get("force"))})
        return {"ok": True, "message": msg, "freed": it.get("size") or 0}

    def start_ollama_pull(self, url, model, command_id=None):
        """#746 : téléchargement d'un modèle Ollama dans un fil détaché ; progression lue par l'action status."""
        import threading
        from . import ollamactl
        st = {"model": model, "running": True, "started": _iso(self.clock()), "status": "démarrage", "completed": None, "total": None}
        self._ollama_pull = st

        def work():
            ok, err = ollamactl.pull(url, model, progress=lambda p: st.update({k: v for k, v in p.items() if v is not None}))
            st.update({"running": False, "ended": _iso(self.clock()), "ok": ok, "error": err})
            if ok:
                self.event("ollama-pull-done", "info", "modèle %s téléchargé" % model, {"model": model, "command": command_id})
            else:
                self.event("ollama-pull-failed", "warning", "téléchargement de %s en échec : %s" % (model, err), {"model": model, "error": err})
            self._next_plugin.pop("ollama", None)

        threading.Thread(target=work, name="ollama-pull", daemon=True).start()
        return True

    def _installed_software(self):
        """#711 : logiciels installés (Windows / macOS) -- dernière mesure de la sonde software-inventory, sinon la
        sonde elle-même lancée en module (sans l'activer)."""
        try:
            rows = self.queue.latest(task="plugin:software-inventory", limit=1)
            if rows and isinstance(rows[0].get("data"), dict) and rows[0]["data"].get("installed"):
                return rows[0]["data"]["installed"]
            path = os.path.join(self.cfg.get("plugins_dir") or "", "software-inventory", "software_inventory.py")
            if os.path.exists(path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("si_software_inventory", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return (mod.collect() or {}).get("installed") or []
        except Exception as exc:  # noqa: BLE001
            _log.warning("logiciels installés pour l'inventaire : %s", exc)
        return []

    def maintenance(self):
        now = self.clock()
        try:  # #699 : relevé périodique de l'inventaire logiciel
            from . import sbomctl
            if sbomctl.due(self.state, now) and not getattr(self, "_sbom_running", False) and not self.is_blocked():
                self.start_sbom(install=bool(self.state.get("sbom_install")))
        except Exception as exc:  # noqa: BLE001
            _log.warning("inventaire logiciel périodique : %s", exc)
        self._mail_index_tick(now)
        if self.state.get("autologon_pending") and now - self._started_at > 120:
            self._autologon_cleanup()
        if now - self._last_purge > 3600:
            self._last_purge = now
            self.queue.purge_sent()

    def _mail_index_tick(self, now, log_path="/var/log/mail.log"):
        """#710 : index de l'historique du courrier tenu à jour toutes les 5 min (sonde mail-server active), en fond."""
        if now - getattr(self, "_mailidx_at", 0) < 300 or getattr(self, "_mailidx_running", False):
            return False
        self._mailidx_at = now
        m = self.store.get("mail-server")
        if not m or not plugins.is_enabled(m, self.cfg.get("plugins")) or not os.path.exists(log_path):
            return False
        import threading

        def work():
            self._mailidx_running = True
            try:
                from . import maillogidx
                maillogidx.update(log_path)
            except Exception as exc:  # noqa: BLE001
                _log.warning("index de l'historique du courrier : %s", exc)
            finally:
                self._mailidx_running = False
        threading.Thread(target=work, name="mail-index", daemon=True).start()
        return True

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
                self.run_power_schedule()
                self.follow_audit()
                self.follow_image()
                self.follow_update()
                self.follow_upload()
                self.run_deferred()
                self.run_plugins()
                self.collect_self()
                self.poll_commands()
                self.charge_tick()
                self.shell_tick()
                self.publish_tick()
                self.local_view_tick()
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
