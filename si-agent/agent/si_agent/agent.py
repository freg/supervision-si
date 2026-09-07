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

Mesures produites : `host` (collecte complète), `risks` (constats),
`inventory` (outils disponibles, plugins installés) et `plugin:<id>`.
"""
import json
import logging
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

from . import host, plugins, protocol, risks
from .localqueue import LocalQueue

_log = logging.getLogger("si_agent")

DEFAULT_CONFIG_PATH = "/etc/si-agent/agent.json"
DEFAULTS = {
    "site": "default",
    "host_interval_seconds": 60,
    "inventory_interval_seconds": 3600,
    "poll_config_seconds": 300,
    "commands_poll_seconds": 60,
    "flush_seconds": 30,
    "batch_size": 100,
    "queue_path": "/var/lib/si-agent/queue.db",
    "plugins_dir": "/var/lib/si-agent/plugins",
    "risk_thresholds": {},
    "plugins": {},
    "ca_file": None,
    "insecure": False,
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
        if base_url.lower().startswith("https"):
            if insecure:
                self.ssl_context = ssl._create_unverified_context()  # noqa: SLF001
                _log.warning("TLS non vérifié vers %s (insecure=true) -- dépannage uniquement", base_url)
            else:
                self.ssl_context = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()

    def request(self, method, path, body=None):
        body_bytes = protocol.canonical_json(body) if body is not None else b""
        headers = protocol.auth_headers(self.device_id, self.secret, method, path, body_bytes)
        req = urllib.request.Request(self.base_url + path, data=body_bytes if body is not None else None,
                                     method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw.decode("utf-8")) if raw else {}
                except ValueError:
                    return resp.status, None
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read().decode("utf-8"))
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
        self.config_version = None
        self._prev_cpu = None
        self._next_host = 0
        self._next_inventory = 0
        self._next_plugin = {}
        self._last_poll = 0
        self._last_commands = 0
        self._last_flush = 0
        self._last_purge = 0
        self.last_central_contact = None
        self.last_host_data = None
        self.last_risks = []

    # -- configuration depuis le central ----------------------------------
    def refresh_config(self, force=False):
        now = self.clock()
        if not force and now - self._last_poll < self.cfg["poll_config_seconds"]:
            return False
        self._last_poll = now
        status, body = self.http.request("GET", "%s/agents/%s/config" % (protocol.API_PREFIX, self.agent_id))
        if status in (401, 403):
            _log.error("central : authentification refusée (%s) -- vérifier agent_id/secret", status)
            return False
        if status != 200 or not isinstance(body, dict):
            return False
        self.last_central_contact = now
        if body.get("version") == self.config_version:
            return True
        self.config_version = body.get("version")
        for key in ("host_interval_seconds", "inventory_interval_seconds"):
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
            if existing and existing.get("sha256") == plugins.sha256_text(script) and str(existing.get("version")) == str(manifest.get("version")):
                if bool(existing.get("enabled")) != bool(manifest.get("enabled")):
                    self.store.set_enabled(manifest["id"], manifest.get("enabled"))
                continue
            ok, why = self.store.install(manifest, script, source="central", secret=self.cfg["secret"])
            if ok:
                installed += 1
                self._next_plugin.pop(manifest["id"], None)
            else:
                _log.error("plugin %s refusé : %s", manifest.get("id"), why)
        for pid in body.get("remove_plugins") or []:
            if self.store.remove(str(pid)):
                self._next_plugin.pop(pid, None)
        _log.info("configuration version %s appliquée (%d plugin(s) installé(s))", self.config_version, installed)
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
        self.last_central_contact = now
        done = []
        for c in body.get("commands") or []:
            result = self.execute_command(c)
            self.http.request("POST", "%s/agents/%s/commands/%s/ack" % (protocol.API_PREFIX, self.agent_id, c.get("id")), result)
            done.append((c, result))
        return done

    def execute_command(self, c):
        ctype = (c or {}).get("type")
        params = (c or {}).get("params") or {}
        try:
            if ctype == "collect_now":
                m = self.collect_host(force=True)
                return {"ok": True, "result": {"measurements": len(m)}}
            if ctype == "run_plugin":
                m = self.store.get(str(params.get("id", "")))
                if m is None:
                    return {"ok": False, "error": "plugin inconnu"}
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

    def collect_inventory(self, force=False):
        now = self.clock()
        if not force and now < self._next_inventory:
            return None
        self._next_inventory = now + float(self.cfg["inventory_interval_seconds"])
        tools = host.collect_tools(self.which)
        installed = [{k: v for k, v in m.items() if k != "path"} for m in self.store.list()]
        for m in installed:
            m["effective_enabled"] = plugins.is_enabled(m, self.cfg.get("plugins"))
        m = {"agent_id": self.agent_id, "task": "inventory", "at": _iso(now), "ok": True,
             "data": {"tools": tools, "plugins": installed, "agent_version": __import__("si_agent").__version__,
                      "config_version": self.config_version}, "error": None}
        self.queue.put(m)
        return m

    def run_one_plugin(self, manifest):
        env = {"SI_AGENT_ID": self.agent_id, "SI_AGENT_SITE": str(self.cfg.get("site") or "")}
        meas = plugins.run_plugin(manifest, self.cmd, now=self.clock(), env=env)
        meas["agent_id"] = self.agent_id
        self.queue.put(meas)
        return meas

    def run_plugins(self):
        now = self.clock()
        produced = []
        for m in self.store.list():
            if not plugins.is_enabled(m, self.cfg.get("plugins")):
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
        }

    def run_once(self):
        self.refresh_config(force=True)
        out = self.collect_host(force=True)
        inv = self.collect_inventory(force=True)
        if inv:
            out.append(inv)
        out.extend(self.run_plugins())
        return out

    def run_forever(self, sleep=time.sleep):
        _log.info("si-agent %s démarré (site %s, central %s)", self.agent_id, self.cfg.get("site"), self.cfg["central_url"])
        self.refresh_config(force=True)
        self.flush(force=True)
        while True:
            try:
                self.refresh_config()
                self.collect_host()
                self.collect_inventory()
                self.run_plugins()
                self.poll_commands()
                self.flush()
                self.maintenance()
            except Exception as exc:  # noqa: BLE001 -- la boucle ne meurt jamais
                _log.exception("erreur dans la boucle : %s", exc)
            sleep(1)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="si-agent -- agent hôte de supervision-si")
    parser.add_argument("--config", default=os.environ.get("SI_AGENT_CONFIG", DEFAULT_CONFIG_PATH))
    parser.add_argument("--once", action="store_true", help="un passage complet (collecte, inventaire, plugins, envoi) puis sortie")
    parser.add_argument("--collect", action="store_true", help="affiche la collecte hôte et les risques en JSON, sans envoi ni configuration")
    parser.add_argument("--status", action="store_true", help="affiche l'état local et sort")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.collect:
        data, _ = host.collect_all()
        print(json.dumps({"host": data, "risks": risks.evaluate(data), "summary": risks.summarize(risks.evaluate(data))},
                         indent=2, ensure_ascii=False))
        return 0
    cfg = load_config(args.config)
    agent = Agent(cfg)
    if args.status:
        print(json.dumps(agent.status(), indent=2, ensure_ascii=False))
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
