#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent relais des parcours applicatifs (livraison #441) -- tourne sur le
poste de la personne qui parcourt l'application (Python 3 seul, aucune
dépendance). L'extension Firefox lui parle en local (127.0.0.1:6320) ; lui
seul connaît le jeton et l'URL du central (retro-api derrière la passerelle
TLS du hub) : l'extension n'embarque aucun secret, et le navigateur n'a pas
besoin de faire confiance à la CA interne.

    python3 relay.py --central https://VM:6443/api/retro --token SECRET [--ca ca.crt | --insecure] [--port 6320]
    python3 relay.py --config relay.json          # {central_url, token, ca_file, insecure, port, queue_path}

Routes locales (JSON, CORS ouvert : seul le poste local peut joindre 127.0.0.1) :
  GET  /status                         état, parcours en cours, file locale
  GET  /apps                           applications connues du central (transmis)
  POST /journeys      {app, name, tester, base_url}   crée un parcours au central, le mémorise comme courant
  POST /events        {journey_id?, events: [...]}    met en file, expédie par lots (rejoue après une coupure)
  POST /journeys/<id>/end                               termine (après avoir vidé la file)
  POST /mark          {label}                           repère posé depuis le relais (ou l'extension)
La file locale est un SQLite (`queue_path`) : rien n'est perdu si le central
est injoignable, les lots sont renvoyés dans l'ordre avec leur `seq`.
"""
import argparse
import json
import os
import socket
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.1.0"


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Central(object):
    """Client HTTP minimal vers retro-api (jeton X-Relay-Token)."""

    def __init__(self, base_url, token, ca_file=None, insecure=False, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        if insecure:
            self.ctx = ssl._create_unverified_context()
        else:
            self.ctx = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "X-Relay-Token": self.token, "User-Agent": "retro-relay/" + VERSION})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
            except ValueError:
                return exc.code, {"error": "HTTP %s" % exc.code}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 0, {"error": str(exc)}


class Queue(object):
    """File locale SQLite : événements en attente, par parcours, avec leur seq."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS pending (id INTEGER PRIMARY KEY AUTOINCREMENT, journey_id TEXT NOT NULL, seq INTEGER NOT NULL, at TEXT, kind TEXT, data TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS seqs (journey_id TEXT PRIMARY KEY, last_seq INTEGER NOT NULL)")

    def _conn(self):
        return sqlite3.connect(self.path, timeout=10)

    def put(self, journey_id, events):
        with self.lock, self._conn() as c:
            r = c.execute("SELECT last_seq FROM seqs WHERE journey_id = ?", (journey_id,)).fetchone()
            seq = r[0] if r else 0
            for ev in events:
                if not isinstance(ev, dict) or not ev.get("kind"):
                    continue
                seq += 1
                c.execute("INSERT INTO pending (journey_id, seq, at, kind, data) VALUES (?, ?, ?, ?, ?)",
                          (journey_id, seq, ev.get("at") or now_iso(), str(ev["kind"])[:40], json.dumps(ev.get("data") or {}, ensure_ascii=False)))
            c.execute("INSERT INTO seqs (journey_id, last_seq) VALUES (?, ?) ON CONFLICT(journey_id) DO UPDATE SET last_seq = excluded.last_seq", (journey_id, seq))
            return seq

    def next_batch(self, limit=200):
        with self.lock, self._conn() as c:
            r = c.execute("SELECT journey_id FROM pending ORDER BY id LIMIT 1").fetchone()
            if not r:
                return None, []
            jid = r[0]
            rows = c.execute("SELECT id, seq, at, kind, data FROM pending WHERE journey_id = ? ORDER BY id LIMIT ?", (jid, limit)).fetchall()
            return jid, [{"_id": i, "seq": s, "at": a, "kind": k, "data": json.loads(d or "{}")} for i, s, a, k, d in rows]

    def ack(self, ids):
        if not ids:
            return
        with self.lock, self._conn() as c:
            c.executemany("DELETE FROM pending WHERE id = ?", [(i,) for i in ids])

    def pending_count(self):
        with self.lock, self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM pending").fetchone()[0]


class Relay(object):
    def __init__(self, central, queue, flush_seconds=2.0):
        self.central, self.queue, self.flush_seconds = central, queue, flush_seconds
        self.current = None          # {id, app, name, started_at}
        self.last_error = None
        self.sent = 0
        self.started_at = now_iso()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="relay-flush", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set(); self._wake.set()

    def kick(self):
        self._wake.set()

    def flush_once(self):
        """Un lot : True si quelque chose est parti, False sinon (rien ou échec)."""
        jid, batch = self.queue.next_batch()
        if not batch:
            return False
        status, resp = self.central.request("POST", "/journeys/%s/events" % jid, {"events": [{k: v for k, v in e.items() if k != "_id"} for e in batch]})
        if status == 200:
            self.queue.ack([e["_id"] for e in batch])
            self.sent += len(batch)
            self.last_error = None
            return True
        if status in (404, 409):   # parcours inconnu ou terminé : on jette, sinon la file se bloque
            self.queue.ack([e["_id"] for e in batch])
            self.last_error = "central : %s (lot abandonné)" % resp.get("error")
            return True
        self.last_error = "central : %s" % (resp.get("error") or status)
        return False

    def flush_all(self, max_batches=100):
        n = 0
        while n < max_batches and self.flush_once():
            n += 1
        return n

    def _loop(self):
        while not self._stop.is_set():
            self._wake.wait(self.flush_seconds)
            self._wake.clear()
            try:
                self.flush_all()
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)

    # -- actions ------------------------------------------------------------
    def create_journey(self, body):
        status, resp = self.central.request("POST", "/journeys", {"app": body.get("app"), "name": body.get("name"), "tester": body.get("tester"),
                                                                  "base_url": body.get("base_url")})
        if status != 201:
            return status or 502, {"error": resp.get("error") or "création refusée par le central"}
        self.current = {"id": resp["id"], "app": resp.get("app"), "name": resp.get("name"), "base_url": body.get("base_url"), "started_at": resp.get("started_at")}
        return 201, resp

    def add_events(self, body):
        jid = body.get("journey_id") or (self.current or {}).get("id")
        if not jid:
            return 409, {"error": "aucun parcours en cours : créer un parcours d'abord (POST /journeys)"}
        events = body.get("events")
        if not isinstance(events, list):
            return 400, {"error": "'events' : liste attendue"}
        last = self.queue.put(jid, events)
        self.kick()
        return 200, {"queued": len(events), "last_seq": last, "pending": self.queue.pending_count()}

    def mark(self, body):
        return self.add_events({"events": [{"kind": "mark", "at": now_iso(), "data": {"label": body.get("label") or "repère"}}]})

    def end_journey(self, jid, body):
        self.flush_all()
        status, resp = self.central.request("POST", "/journeys/%s/end" % jid, {"notes": body.get("notes")})
        if self.current and self.current.get("id") == jid:
            self.current = None
        return (status or 502), resp

    def status(self):
        return {"relay_version": VERSION, "central_url": self.central.base_url, "started_at": self.started_at, "current": self.current,
                "pending": self.queue.pending_count(), "sent": self.sent, "last_error": self.last_error}


def make_handler(relay):
    class H(BaseHTTPRequestHandler):
        server_version = "retro-relay/" + VERSION

        def log_message(self, fmt, *args):
            sys.stderr.write("%s relay: %s\n" % (now_iso(), fmt % args))

        def _send(self, code, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self._send(204, {})

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 8 * 1024 * 1024:
                return None
            raw = self.rfile.read(n) if n else b""
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return None

        def do_GET(self):
            if self.path == "/status":
                return self._send(200, relay.status())
            if self.path == "/apps":
                status, resp = relay.central.request("GET", "/apps")
                return self._send(status or 502, resp)
            return self._send(404, {"error": "inconnu"})

        def do_POST(self):
            body = self._body()
            if body is None:
                return self._send(400, {"error": "corps JSON attendu (8 Mo max.)"})
            if self.path == "/journeys":
                return self._send(*relay.create_journey(body))
            if self.path == "/events":
                return self._send(*relay.add_events(body))
            if self.path == "/mark":
                return self._send(*relay.mark(body))
            if self.path.startswith("/journeys/") and self.path.endswith("/end"):
                return self._send(*relay.end_journey(self.path.split("/")[2], body))
            return self._send(404, {"error": "inconnu"})
    return H


def serve(relay, host="127.0.0.1", port=6320):
    srv = ThreadingHTTPServer((host, port), make_handler(relay))
    relay.start()
    return srv


def main(argv=None):
    p = argparse.ArgumentParser(description="agent relais des parcours applicatifs (supervision-si)")
    p.add_argument("--config", help="fichier JSON {central_url, token, ca_file, insecure, port, queue_path}")
    p.add_argument("--central"); p.add_argument("--token"); p.add_argument("--ca"); p.add_argument("--insecure", action="store_true")
    p.add_argument("--port", type=int); p.add_argument("--queue")
    a = p.parse_args(argv)
    cfg = {}
    if a.config:
        with open(a.config, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    central_url = a.central or cfg.get("central_url")
    token = a.token or cfg.get("token") or os.environ.get("RETRO_RELAY_TOKEN")
    if not central_url or not token:
        p.error("--central et --token (ou un fichier --config) sont requis")
    port = a.port or int(cfg.get("port") or 6320)
    queue_path = a.queue or cfg.get("queue_path") or os.path.join(os.path.expanduser("~"), ".retro-relay", "queue.db")
    central = Central(central_url, token, ca_file=a.ca or cfg.get("ca_file"), insecure=bool(a.insecure or cfg.get("insecure")))
    relay = Relay(central, Queue(queue_path))
    srv = serve(relay, port=port)
    status, resp = central.request("GET", "/apps")
    print("relais des parcours %s sur http://127.0.0.1:%d -- central %s : %s" % (VERSION, port, central_url,
          ("%d application(s), jeton %s" % (len(resp.get("apps") or []), "configuré" if resp.get("relay_token_configured") else "ABSENT côté central")) if status == 200 else "injoignable (%s)" % resp.get("error")))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        relay.stop(); srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
