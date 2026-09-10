"""Collecteur de site (`role: collector`, Raspberry Pi 3B sur Ethernet).

Trois responsabilités, volontairement pas plus :
1. Recevoir les mesures des sondes du site (authentifiées, dédupliquées)
   et les garder localement -- consultables SUR PLACE même si le VPN vers
   le central est tombé (`GET /api/v1/status`, `/api/v1/latest`).
2. Servir à chaque sonde sa liste de tâches (`GET /api/v1/agents/<id>/tasks`)
   -- la "flotte" (sondes, secrets, tâches) vient du central quand il est
   joignable, et reste en cache local (`fleet.json`) sinon.
3. Relayer vers `netprobe-api` central par lots signés avec SON propre
   secret (store-and-forward, même file que la sonde).

Serveur HTTP de la bibliothèque standard (ThreadingHTTPServer) : pas de
Flask sur le Pi, pas de dépendance -- le trafic est celui de quelques
sondes, pas d'un site web. Toute la logique de traitement vit dans
`CollectorCore`, testable sans socket (tests/test_collector.py) ; le
handler HTTP n'est qu'une traduction.

Sécurité : les routes d'ÉCRITURE et la distribution des tâches sont
signées (protocol.py). Les routes de LECTURE locales (`/health`,
`/api/v1/status`, `/api/v1/latest`) sont ouvertes sur le LAN du site,
comme `launcher` côté central -- elles n'exposent aucun secret et
servent au technicien sur place. À ne jamais exposer au-delà du LAN.
"""
import json
import logging
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import protocol
from .localqueue import LocalQueue

_log = logging.getLogger("netprobe_collector")

DEFAULT_CONFIG_PATH = "/etc/netprobe-collector/collector.json"
DEFAULT_PORT = 6127

SEEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents_seen (
    agent_id TEXT PRIMARY KEY,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    last_ip TEXT,
    measurements INTEGER NOT NULL DEFAULT 0
);
"""


def load_config(path=DEFAULT_CONFIG_PATH):
    with open(path, "r") as fh:
        cfg = json.load(fh)
    for key in ("collector_id", "secret", "site"):
        if not cfg.get(key):
            raise ValueError("configuration : champ '%s' manquant dans %s" % (key, path))
    cfg.setdefault("listen", "0.0.0.0")
    cfg.setdefault("port", DEFAULT_PORT)
    cfg.setdefault("central_url", "")
    cfg.setdefault("fleet_path", "/etc/netprobe-collector/fleet.json")
    cfg.setdefault("queue_path", "/var/lib/netprobe-collector/queue.db")
    cfg.setdefault("db_path", "/var/lib/netprobe-collector/collector.db")
    cfg.setdefault("forward_seconds", 60)
    cfg.setdefault("fleet_sync_seconds", 300)
    cfg.setdefault("batch_size", 500)
    cfg.setdefault("central_ca_file", "")
    cfg.setdefault("central_insecure", False)
    cfg["central_url"] = (cfg["central_url"] or "").rstrip("/")
    return cfg


class Fleet:
    """Sondes connues du site : {agent_id: {"secret", "tasks", "tasks_version"}}.
    Chargée depuis fleet.json, remplacée par la version du central quand
    il répond, et REsauvegardée localement à chaque mise à jour."""

    def __init__(self, path):
        self.path = path
        self.agents = {}
        self.version = None
        self.lock = threading.Lock()
        self.load()

    def load(self):
        try:
            with open(self.path, "r") as fh:
                data = json.load(fh)
            with self.lock:
                self.agents = {k: v for k, v in (data.get("agents") or {}).items() if isinstance(v, dict) and v.get("secret")}
                self.version = data.get("version")
        except (OSError, ValueError):
            pass

    def save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with self.lock:
            payload = {"agents": self.agents, "version": self.version, "saved_at": time.time()}
        with open(tmp, "w") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def replace(self, agents, version):
        with self.lock:
            self.agents = {k: v for k, v in agents.items() if isinstance(v, dict) and v.get("secret")}
            self.version = version
        self.save()

    def get(self, agent_id):
        with self.lock:
            return self.agents.get(agent_id)


class CollectorCore:
    """Toute la logique -- aucun socket ici."""

    def __init__(self, cfg, fleet=None, queue=None, clock=time.time):
        self.cfg = cfg
        self.clock = clock
        self.fleet = fleet or Fleet(cfg["fleet_path"])
        self.queue = queue or LocalQueue(cfg["queue_path"])
        directory = os.path.dirname(cfg["db_path"])
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.db = sqlite3.connect(cfg["db_path"], timeout=10, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SEEN_SCHEMA)
        self.db_lock = threading.Lock()
        self.last_central_contact = None
        self.last_forward_error = None
        self.started_at = clock()

    # -- authentification ------------------------------------------------
    def _verify_agent(self, agent_id, method, path, headers, body):
        entry = self.fleet.get(agent_id)
        if not entry:
            return False, "sonde inconnue de ce collecteur : %s" % agent_id
        ok, why = protocol.verify(entry["secret"], method, path, headers, body)
        return ok, why

    def _touch_agent(self, agent_id, ip, count):
        now = self.clock()
        with self.db_lock, self.db:
            self.db.execute(
                "INSERT INTO agents_seen(agent_id, first_seen, last_seen, last_ip, measurements) VALUES (?,?,?,?,?) "
                "ON CONFLICT(agent_id) DO UPDATE SET last_seen = excluded.last_seen, last_ip = excluded.last_ip, "
                "measurements = agents_seen.measurements + excluded.measurements",
                (agent_id, now, now, ip, count))

    # -- routes ----------------------------------------------------------
    def handle_tasks(self, agent_id, headers, client_ip=None):
        path = "%s/agents/%s/tasks" % (protocol.API_PREFIX, agent_id)
        ok, why = self._verify_agent(agent_id, "GET", path, headers, b"")
        if not ok:
            return 401, {"error": why}
        entry = self.fleet.get(agent_id)
        self._touch_agent(agent_id, client_ip, 0)
        return 200, {"agent_id": agent_id, "tasks": entry.get("tasks") or [],
                     "version": entry.get("tasks_version") or self.fleet.version, "site": self.cfg["site"]}

    def handle_measurements(self, agent_id, headers, body_bytes, client_ip=None):
        path = "%s/agents/%s/measurements" % (protocol.API_PREFIX, agent_id)
        ok, why = self._verify_agent(agent_id, "POST", path, headers, body_bytes)
        if not ok:
            return 401, {"error": why}
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return 400, {"error": "corps JSON invalide"}
        items = body.get("measurements") if isinstance(body, dict) else None
        if not isinstance(items, list):
            return 400, {"error": "'measurements' (liste) attendu"}
        if len(items) > 5000:
            return 400, {"error": "lot trop volumineux (max 5000)"}
        accepted, duplicates, rejected = 0, 0, []
        for i, m in enumerate(items):
            valid, reason = protocol.validate_measurement(m)
            if not valid:
                rejected.append({"index": i, "error": reason})
                continue
            m = dict(m)
            # L'identité vient de la SIGNATURE, jamais du corps : une sonde ne
            # peut pas écrire au nom d'une autre.
            m["agent_id"] = agent_id
            if self.queue.put(m):
                accepted += 1
            else:
                duplicates += 1
        self._touch_agent(agent_id, client_ip, accepted)
        if rejected and not accepted and not duplicates:
            return 400, {"error": "aucune mesure valide", "rejected": rejected[:10]}
        return 200, {"accepted": accepted, "duplicates": duplicates, "rejected": rejected[:10]}

    def handle_status(self):
        with self.db_lock:
            rows = self.db.execute(
                "SELECT agent_id, first_seen, last_seen, last_ip, measurements FROM agents_seen ORDER BY agent_id").fetchall()
        now = self.clock()
        agents = [{"agent_id": r[0], "first_seen": r[1], "last_seen": r[2], "age_s": int(now - r[2]),
                   "last_ip": r[3], "measurements": r[4], "known": self.fleet.get(r[0]) is not None} for r in rows]
        return 200, {
            "collector_id": self.cfg["collector_id"], "site": self.cfg["site"],
            "uptime_s": int(now - self.started_at),
            "central_url": self.cfg["central_url"] or None,
            "last_central_contact": self.last_central_contact,
            "last_forward_error": self.last_forward_error,
            "fleet_version": self.fleet.version, "fleet_size": len(self.fleet.agents),
            "queue": self.queue.stats(), "agents": agents,
        }

    def handle_latest(self, task=None, limit=50):
        return 200, {"measurements": self.queue.latest(task=task, limit=max(1, min(int(limit), 500)))}

    # -- relais vers le central ------------------------------------------
    def forward(self, http):
        """`http(method, path, body) -> (status, dict|None)` signé avec le
        secret du COLLECTEUR. Renvoie le nombre de mesures relayées."""
        if not self.cfg["central_url"]:
            return 0
        sent = 0
        while True:
            batch = self.queue.pending(limit=self.cfg["batch_size"])
            if not batch:
                break
            ids = [m.pop("_id") for m in batch]
            status, body = http("POST", "/agents/measurements/bulk",
                                {"site": self.cfg["site"], "collector_id": self.cfg["collector_id"], "measurements": batch})
            if status in (200, 201):
                self.queue.mark_sent(ids)
                self.last_central_contact = self.clock()
                self.last_forward_error = None
                sent += len(ids)
                continue
            self.queue.mark_attempt(ids)
            self.last_forward_error = "HTTP %s%s" % (status, (" : " + str(body.get("error"))) if isinstance(body, dict) and body.get("error") else "")
            if status == 400:
                _log.error("lot rejeté par le central (400) : %s -- abandonné", (body or {}).get("error"))
                self.queue.mark_sent(ids)
                continue
            break
        return sent

    def sync_fleet(self, http):
        """Rapatrie la flotte du site depuis le central ; True si mise à jour."""
        if not self.cfg["central_url"]:
            return False
        status, body = http("GET", "/fleet?site=%s" % self.cfg["site"], None)
        if status == 200 and isinstance(body, dict) and isinstance(body.get("agents"), dict):
            self.last_central_contact = self.clock()
            if body.get("version") != self.fleet.version or body["agents"] != self.fleet.agents:
                self.fleet.replace(body["agents"], body.get("version"))
                _log.info("flotte mise à jour depuis le central : %d sonde(s), version %s", len(self.fleet.agents), self.fleet.version)
                return True
        elif status in (401, 403):
            _log.error("central : authentification du collecteur refusée (%s)", status)
        return False


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------

def make_handler(core):
    class Handler(BaseHTTPRequestHandler):
        server_version = "netprobe-collector/0.1"

        def log_message(self, fmt, *args):  # journal Python plutôt que stderr brut
            _log.debug("%s - %s", self.address_string(), fmt % args)

        def _send(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _route(self):
            path, _, query = self.path.partition("?")
            params = {}
            for part in query.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k] = v
            return path, params

        def do_GET(self):
            path, params = self._route()
            if path == "/health":
                return self._send(200, {"status": "ok", "collector_id": core.cfg["collector_id"], "site": core.cfg["site"]})
            if path == protocol.API_PREFIX + "/status":
                return self._send(*core.handle_status())
            if path == protocol.API_PREFIX + "/latest":
                return self._send(*core.handle_latest(task=params.get("task"), limit=params.get("limit", 50)))
            prefix = protocol.API_PREFIX + "/agents/"
            if path.startswith(prefix) and path.endswith("/tasks"):
                agent_id = path[len(prefix):-len("/tasks")]
                return self._send(*core.handle_tasks(agent_id, self.headers, self.client_address[0]))
            self._send(404, {"error": "route inconnue"})

        def do_POST(self):
            path, _ = self._route()
            length = int(self.headers.get("Content-Length") or 0)
            if length > 8 * 1024 * 1024:
                return self._send(413, {"error": "corps trop volumineux"})
            body = self.rfile.read(length) if length else b""
            prefix = protocol.API_PREFIX + "/agents/"
            if path.startswith(prefix) and path.endswith("/measurements"):
                agent_id = path[len(prefix):-len("/measurements")]
                return self._send(*core.handle_measurements(agent_id, self.headers, body, self.client_address[0]))
            self._send(404, {"error": "route inconnue"})

    return Handler


def serve(core, listen="0.0.0.0", port=DEFAULT_PORT):
    server = ThreadingHTTPServer((listen, port), make_handler(core))
    server.daemon_threads = True
    return server


def background_loop(core, http, stop_event, sleep=time.sleep):
    """Relais + synchronisation de flotte, en thread. Garde-fou : un seul
    thread par processus (pas de gunicorn ici, un seul processus)."""
    last_forward = 0
    last_sync = 0
    core.sync_fleet(http)
    while not stop_event.is_set():
        now = core.clock()
        try:
            if now - last_sync >= core.cfg["fleet_sync_seconds"]:
                last_sync = now
                core.sync_fleet(http)
            if now - last_forward >= core.cfg["forward_seconds"]:
                last_forward = now
                n = core.forward(http)
                if n:
                    _log.info("%d mesure(s) relayée(s) vers le central", n)
                core.queue.purge_sent()
        except Exception as exc:  # noqa: BLE001
            _log.exception("boucle de relais : %s", exc)
        sleep(1)


def main(argv=None):
    import argparse
    from .agent import HttpClient
    parser = argparse.ArgumentParser(description="netprobe-collector -- collecteur de site")
    parser.add_argument("--config", default=os.environ.get("NETPROBE_COLLECTOR_CONFIG", DEFAULT_CONFIG_PATH))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    core = CollectorCore(cfg)
    http = None
    if cfg["central_url"]:
        client = HttpClient(cfg["central_url"], cfg["collector_id"], cfg["secret"], timeout=30,
                            ca_file=cfg.get("central_ca_file") or None, insecure=bool(cfg.get("central_insecure")))
        http = client.request
    else:
        _log.warning("central_url vide : collecteur en mode LOCAL uniquement (aucun relais)")
        http = lambda *a, **k: (0, None)  # noqa: E731
    stop = threading.Event()
    t = threading.Thread(target=background_loop, args=(core, http, stop), daemon=True)
    t.start()
    server = serve(core, cfg["listen"], int(cfg["port"]))
    _log.info("collecteur %s (site %s) à l'écoute sur %s:%s", cfg["collector_id"], cfg["site"], cfg["listen"], cfg["port"])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
