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
import socket
import ssl
import time
import urllib.error
import urllib.request

from . import control, host, netview, plugins, protocol, review, risks
from .localqueue import LocalQueue

_log = logging.getLogger("si_agent")

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
    "queue_path": "/var/lib/si-agent/queue.db",
    "plugins_dir": "/var/lib/si-agent/plugins",
    "risk_thresholds": {},
    "plugins": {},
    "ca_file": None,
    "ca_fingerprint": None,
    "insecure": False,
    # #422
    "state_path": "/var/lib/si-agent/state.json",
    "block_file": "/etc/si-agent/BLOCKED",
    "require_signed_responses": True,
    "plugins_user": "nobody",
    "plugin_max_memory_mb": 512,
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

    def __init__(self, base_url, device_id, secret, timeout=15, ca_file=None, insecure=False):
        self.base_url, self.device_id, self.secret, self.timeout = base_url.rstrip("/"), device_id, secret, timeout
        self.ssl_context = None
        self.insecure = bool(insecure)
        # Dernière réponse brute (corps, en-têtes) -- l'agent y vérifie la
        # signature du central (#422) sans que le contrat (status, body)
        # change pour les appelants.
        self.last_raw = b""
        self.last_headers = {}
        if base_url.lower().startswith("https"):
            if insecure:
                self.ssl_context = ssl._create_unverified_context()  # noqa: SLF001
                _log.warning("TLS non vérifié vers %s (insecure=true) -- dépannage uniquement", base_url)
            else:
                self.ssl_context = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
        elif not base_url.lower().startswith("http://127.") and not base_url.lower().startswith("http://localhost"):
            _log.warning("central en HTTP clair (%s) -- réservé au test ; utiliser https + ca_file", base_url)

    def request(self, method, path, body=None):
        body_bytes = protocol.canonical_json(body) if body is not None else b""
        headers = protocol.auth_headers(self.device_id, self.secret, method, path, body_bytes)
        req = urllib.request.Request(self.base_url + path, data=body_bytes if body is not None else None,
                                     method=method, headers=headers)
        started = time.monotonic()
        self.last_raw, self.last_headers = b"", {}
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
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
            _log.warning("central injoignable (%s %s) : %s", method, path, exc)
            return 0, None


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class Agent(object):
    def __init__(self, cfg, http=None, cmd=host.run_cmd, files=host.read_file, clock=time.time, queue=None,
                 store=None, usage=None, which=None, exists=None):
        self.cfg = cfg
        self.agent_id = cfg["agent_id"]
        self.http = http or HttpClient(cfg["central_url"], cfg["agent_id"], cfg["secret"],
                                       ca_file=cfg.get("ca_file"), insecure=bool(cfg.get("insecure")))
        self.cmd, self.files, self.clock = cmd, files, clock
        self.usage = usage or __import__("shutil").disk_usage
        self.which = which or __import__("shutil").which
        self.exists = exists or os.path.exists
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
        self._next_plugin = {}
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

    def execute_command(self, c):
        ctype = (c or {}).get("type")
        params = (c or {}).get("params") or {}
        try:
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
            self.event("command-unknown", "warning", "commande inconnue reçue : %s" % ctype, {"command": c.get("id")})
            return {"ok": False, "error": "commande inconnue : %s" % ctype}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # -- collecte ----------------------------------------------------------
    def collect_host(self, force=False):
        now = self.clock()
        if not force and now < self._next_host:
            return []
        self._next_host = now + float(self.cfg["host_interval_seconds"])
        data, self._prev_cpu = host.collect_all(files=self.files, cmd=self.cmd, usage=self.usage, which=self.which,
                                                previous_cpu=self._prev_cpu, include_tools=False, exists=self.exists)
        # #428 : activité (processus, sessions, connexions, services actifs)
        data["activity"] = review.collect_activity(cmd=self.cmd, files=self.files)
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
        data = netview.collect(cmd=self.cmd, files=self.files)
        self.last_netview = data
        m = {"agent_id": self.agent_id, "task": "netview", "at": _iso(now), "ok": not data.get("partial"), "data": data,
             "error": ("collecte partielle : " + ", ".join(data["partial"])) if data.get("partial") else None}
        self.queue.put(m)
        return m

    def collect_inventory(self, force=False):
        now = self.clock()
        if not force and now < self._next_inventory:
            return None
        self._next_inventory = now + float(self.cfg["inventory_interval_seconds"])
        tools = host.collect_tools(self.which)
        hardware = review.collect_hardware(cmd=self.cmd, files=self.files)  # #428
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
                      "log_level": self.cfg.get("log_level")}, "error": None}
        self.queue.put(m)
        return m

    def _plugins_user_effective(self):
        """Utilisateur d'exécution des sondes non privilégiées : `plugins_user`
        s'il existe et si l'agent est root ; sinon l'utilisateur courant."""
        user = self.cfg.get("plugins_user")
        if not user or os.geteuid() != 0 or not self._lookup_user(user):
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
        run_as = control.resolve_run_user(manifest, self.cfg.get("plugins_user"), os.geteuid(), self._lookup_user)
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
        meas = plugins.run_plugin(manifest, self.cmd, now=self.clock(), env=env, confine=confine)
        meas["agent_id"] = self.agent_id
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
            self._next_plugin[m["id"]] = now + float(m.get("interval_seconds", 3600))
            produced.append(self.run_one_plugin(m))
        return produced

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

    def maintenance(self):
        now = self.clock()
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
        out.extend(self.run_plugins())
        return out

    def run_forever(self, sleep=time.sleep):
        _log.info("si-agent %s démarré (site %s, central %s)", self.agent_id, self.cfg.get("site"), self.cfg["central_url"])
        self.event("agent-started", "info", "agent démarré (v%s)" % __import__("si_agent").__version__,
                   {"version": __import__("si_agent").__version__, "blocked": self.is_blocked(), "plugins_user": self._plugins_user_effective()})
        self.refresh_config(force=True)
        self.flush(force=True)
        last_local_block = self.local_block_file()
        while True:
            try:
                lb = self.local_block_file()
                if lb != last_local_block:
                    last_local_block = lb
                    self.event("blocked" if lb else "unblocked", "warning" if lb else "info",
                               "fichier BLOCKED local %s" % ("présent : blocage général" if lb else "retiré"))
                self.refresh_config()
                self.collect_host()
                self.collect_netview()
                self.collect_inventory()
                self.run_plugins()
                self.poll_commands()
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
        data, _ = host.collect_all()
        data["activity"] = review.collect_activity()
        print(json.dumps({"host": data, "risks": risks.evaluate(data), "summary": risks.summarize(risks.evaluate(data)),
                          "netview": netview.collect(), "hardware": review.collect_hardware()},
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
    agent.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
