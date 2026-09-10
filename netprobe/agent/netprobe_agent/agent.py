"""Sonde (`role: probe`) -- boucle principale.

Cycle :
1. `refresh_tasks()`  -- tire sa liste de tâches auprès du collecteur
   (toutes les `poll_config_seconds`), sinon garde la dernière connue,
   sinon `default_tasks` de sa configuration locale. La sonde n'est
   JAMAIS reflashée pour changer une cible : c'est le collecteur (et,
   derrière lui, le hub) qui décide.
2. `tick()`           -- exécute les tâches échues, écrit chaque mesure
   dans la file locale.
3. `flush()`          -- pousse les mesures en attente par lots signés ;
   marque `sent` uniquement sur accusé de réception.
4. purge périodique des mesures envoyées.

Tout est injectable (`http`, `cmd`, `files`, `clock`) : la boucle est
testée sans réseau ni Raspberry Pi (tests/test_agent.py).
"""
import json
import logging
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

from . import protocol, tasks
from .localqueue import LocalQueue

_log = logging.getLogger("netprobe_agent")

DEFAULT_CONFIG_PATH = "/etc/netprobe-agent/agent.json"
DEFAULT_QUEUE_PATH = "/var/lib/netprobe-agent/queue.db"

DEFAULT_TASKS = [
    {"type": "wifi_link", "every": 30},
    {"type": "sys", "every": 60},
    {"type": "wifi_scan", "every": 300},
]


def load_config(path=DEFAULT_CONFIG_PATH):
    with open(path, "r") as fh:
        cfg = json.load(fh)
    for key in ("agent_id", "secret", "collector_url"):
        if not cfg.get(key):
            raise ValueError("configuration : champ '%s' manquant dans %s" % (key, path))
    cfg.setdefault("role", "probe")
    cfg.setdefault("site", "default")
    cfg.setdefault("interface", "wlan0")
    cfg.setdefault("poll_config_seconds", 300)
    cfg.setdefault("flush_seconds", 30)
    cfg.setdefault("batch_size", 100)
    cfg.setdefault("queue_path", DEFAULT_QUEUE_PATH)
    cfg.setdefault("default_tasks", DEFAULT_TASKS)
    cfg["collector_url"] = cfg["collector_url"].rstrip("/")
    return cfg


class HttpClient:
    """Client HTTP minimal signé (urllib). `request(method, path, body)`
    renvoie (status, dict|None). Jamais d'exception vers l'appelant :
    une erreur réseau devient (0, None) et la file locale fait le reste."""

    def __init__(self, base_url, device_id, secret, timeout=15, ca_file=None, insecure=False):
        self.base_url, self.device_id, self.secret, self.timeout = base_url.rstrip("/"), device_id, secret, timeout
        # TLS vers le central (tls-proxy, certificat de la PKI du projet) :
        # `ca_file` = certificat de l'AC du projet embarqué dans l'image ;
        # `insecure` = ne pas vérifier (dépannage uniquement, journalisé).
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
            _log.warning("collecteur injoignable (%s %s) : %s", method, path, exc)
            return 0, None


class Agent:
    def __init__(self, cfg, http=None, cmd=tasks.run_cmd, files=tasks.read_file, clock=time.time, queue=None):
        self.cfg = cfg
        self.agent_id = cfg["agent_id"]
        self.http = http or HttpClient(cfg["collector_url"], cfg["agent_id"], cfg["secret"])
        self.cmd, self.files, self.clock = cmd, files, clock
        self.queue = queue or LocalQueue(cfg["queue_path"])
        self.tasks = [t for t in (cfg.get("default_tasks") or DEFAULT_TASKS) if tasks.validate_task_spec(t)]
        self.tasks_source = "local"
        self.tasks_version = None
        self._next_run = {}
        self._last_poll = 0
        self._last_flush = 0
        self._last_purge = 0
        self.last_collector_contact = None

    # -- configuration ---------------------------------------------------
    def refresh_tasks(self, force=False):
        now = self.clock()
        if not force and now - self._last_poll < self.cfg["poll_config_seconds"]:
            return False
        self._last_poll = now
        status, body = self.http.request("GET", "%s/agents/%s/tasks" % (protocol.API_PREFIX, self.agent_id))
        if status == 200 and isinstance(body, dict) and isinstance(body.get("tasks"), list):
            valid = [t for t in body["tasks"] if tasks.validate_task_spec(t)]
            self.last_collector_contact = now
            if body.get("version") != self.tasks_version or valid != self.tasks:
                self.tasks = valid
                self.tasks_version = body.get("version")
                self.tasks_source = "collector"
                _log.info("tâches mises à jour depuis le collecteur : %d tâche(s), version %s", len(valid), self.tasks_version)
            return True
        if status == 401 or status == 403:
            _log.error("collecteur : authentification refusée (%s) -- vérifier agent_id/secret", status)
        return False

    # -- exécution -------------------------------------------------------
    def due_tasks(self):
        now = self.clock()
        due = []
        for spec in self.tasks:
            name = tasks.task_name(spec)
            if self._next_run.get(name, 0) <= now:
                due.append(spec)
        return due

    def tick(self):
        """Exécute les tâches échues ; renvoie les mesures produites."""
        produced = []
        for spec in self.due_tasks():
            name = tasks.task_name(spec)
            # Prochaine échéance fixée AVANT l'exécution : une tâche lente
            # (scan, iperf3) ne décale pas son rythme à chaque passage.
            self._next_run[name] = self.clock() + float(spec.get("every", 60))
            m = tasks.run_task(spec, cmd=self.cmd, files=self.files, now=self.clock())
            m["agent_id"] = self.agent_id
            self.queue.put(m)
            produced.append(m)
        return produced

    # -- envoi -----------------------------------------------------------
    def flush(self, force=False):
        """Pousse les mesures en attente par lots ; renvoie le nombre
        d'envoyées. Un lot refusé (0/5xx) reste en file ; un lot accepté
        est marqué `sent` ; un lot rejeté pour forme (400) est marqué
        `sent` aussi -- le réémettre à l'infini ne le rendrait pas valide,
        et l'erreur est journalisée."""
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
                self.last_collector_contact = self.clock()
                sent += len(ids)
                continue
            self.queue.mark_attempt(ids)
            if status == 400:
                _log.error("lot rejeté par le collecteur (400) : %s -- abandonné", (body or {}).get("error"))
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
        return {
            "agent_id": self.agent_id,
            "site": self.cfg.get("site"),
            "tasks": [tasks.task_name(t) for t in self.tasks],
            "tasks_source": self.tasks_source,
            "tasks_version": self.tasks_version,
            "queue": self.queue.stats(),
            "last_collector_contact": self.last_collector_contact,
        }

    def run_forever(self, sleep=time.sleep):
        _log.info("sonde %s démarrée (site %s, collecteur %s)", self.agent_id, self.cfg.get("site"), self.cfg["collector_url"])
        self.refresh_tasks(force=True)
        self.flush(force=True)
        while True:
            try:
                self.refresh_tasks()
                self.tick()
                self.flush()
                self.maintenance()
            except Exception as exc:  # noqa: BLE001 -- la boucle ne meurt jamais
                _log.exception("erreur dans la boucle : %s", exc)
            sleep(1)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="netprobe-agent -- sonde distribuée")
    parser.add_argument("--config", default=os.environ.get("NETPROBE_AGENT_CONFIG", DEFAULT_CONFIG_PATH))
    parser.add_argument("--once", action="store_true", help="un seul passage (tâches + envoi) puis sortie")
    parser.add_argument("--status", action="store_true", help="affiche l'état local et sort")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    agent = Agent(cfg)
    if args.status:
        print(json.dumps(agent.status(), indent=2, ensure_ascii=False))
        return 0
    if args.once:
        agent.refresh_tasks(force=True)
        for spec in agent.tasks:
            agent._next_run[tasks.task_name(spec)] = 0
        for m in agent.tick():
            print(json.dumps(m, ensure_ascii=False))
        print("envoyées :", agent.flush(force=True))
        return 0
    agent.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
