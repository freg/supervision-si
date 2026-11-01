# -*- coding: utf-8 -*-
"""#751 : virtualisation directe sur le LAN, d'agent à agent. Le hub orchestre seulement ; l'image ne passe pas par lui.

  Récepteur (agent du nœud Proxmox) : serveur HTTP temporaire sur l'IP LAN du nœud, protégé par un jeton à usage unique
  (en-tête X-P2V-Token), éventuellement limité à l'IP de la source. Écrit dans le dossier d'import préparé (volume
  temporaire hors disque système), au fil de l'eau ; reprise par offset ; condensé SHA-256 vérifié à la clôture ;
  se ferme après la clôture ou après une longue inactivité.
  Émetteur (agent du poste) : même protocole que l'envoi au central (status / PUT ?offset= / complete) -> l'agent réutilise
  son fil d'envoi (reprise, débit borné) en changeant seulement de destinataire. Connexion SORTANTE du poste.

Routes : GET /p2v/<nom>/status -> {size} ; PUT /p2v/<nom>?offset=N -> {size} (409 + size si décalage) ;
POST /p2v/<nom>/complete {size, sha256} -> {path, sha256} (409 si taille ou condensé différents)."""
import hashlib
import hmac
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
MAX_CHUNK = 64 * 2**20
IDLE_TIMEOUT = 12 * 3600


def local_ip_towards(peer, port=80):
    """IP locale utilisée pour joindre `peer` (aucun paquet envoyé : connect UDP)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((peer, port))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


class Receiver:
    def __init__(self, import_dir, token, on_complete=None, allow_ip=None, bind="0.0.0.0", port=0, idle_timeout=IDLE_TIMEOUT):
        self.dir, self.token, self.on_complete, self.allow_ip = import_dir, token, on_complete, allow_ip or None
        self.idle_timeout, self.last = idle_timeout, time.time()
        self.done, self.lock, self.received, self.hashes = None, threading.Lock(), 0, {}
        rx = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def reply(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b)

            def guard(self):
                if rx.allow_ip and self.client_address[0] != rx.allow_ip:
                    self.reply(403, {"error": "adresse non autorisée"}); return None
                if not hmac.compare_digest(self.headers.get("X-P2V-Token", ""), rx.token):
                    self.reply(403, {"error": "jeton refusé"}); return None
                parts = self.path.split("?")[0].strip("/").split("/")
                if len(parts) < 2 or parts[0] != "p2v" or not NAME_RE.match(parts[1]):
                    self.reply(404, {"error": "chemin inconnu"}); return None
                rx.last = time.time()
                return parts

            def do_GET(self):
                p = self.guard()
                if p is None:
                    return
                self.reply(200, {"size": rx.size(p[1])})

            def do_PUT(self):
                p = self.guard()
                if p is None:
                    return
                n = int(self.headers.get("Content-Length") or 0)
                m = re.search(r"[?&]offset=(\d+)", self.path)
                if not m or n <= 0 or n > MAX_CHUNK:
                    self.reply(400, {"error": "offset et corps (≤ 64 Mio) requis"}); return
                with rx.lock:
                    cur = rx.size(p[1])
                    if int(m.group(1)) != cur or rx.done:
                        self.rfile.read(n); self.reply(409, {"error": "décalage (attendu %d)" % cur, "size": cur}); return
                    h = rx.hasher(p[1])
                    with open(os.path.join(rx.dir, p[1] + ".part"), "ab") as fh:
                        left = n
                        while left:
                            b = self.rfile.read(min(left, 1 << 20))
                            if not b:
                                break
                            fh.write(b); h.update(b); left -= len(b)
                    rx.hashes[p[1]] = (h, cur + n - left)
                    rx.received += n - left
                    self.reply(200, {"size": rx.size(p[1])})

            def do_POST(self):
                p = self.guard()
                if p is None:
                    return
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                except ValueError:
                    self.reply(400, {"error": "JSON attendu"}); return
                if len(p) < 3 or p[2] != "complete":
                    self.reply(404, {"error": "chemin inconnu"}); return
                with rx.lock:
                    part = os.path.join(rx.dir, p[1] + ".part")
                    size = os.path.getsize(part) if os.path.exists(part) else -1
                    if size != int(body.get("size") or -2):
                        self.reply(409, {"error": "taille reçue %d" % size, "size": max(size, 0)}); return
                    h = rx.hasher(p[1])
                    if h.hexdigest() != str(body.get("sha256") or "").lower():
                        self.reply(409, {"error": "condensé différent : image corrompue"}); return
                    final = os.path.join(rx.dir, p[1])
                    os.replace(part, final)
                    rx.done = {"path": final, "name": p[1], "sha256": h.hexdigest(), "bytes": size}
                self.reply(200, rx.done)
                if rx.on_complete:
                    threading.Thread(target=rx.on_complete, args=(dict(rx.done),), daemon=True).start()
                threading.Thread(target=rx.close, args=(5,), daemon=True).start()

        self.server = ThreadingHTTPServer((bind, port), H)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, name="p2v-receiver", daemon=True).start()
        threading.Thread(target=self._watch, name="p2v-receiver-idle", daemon=True).start()

    def hasher(self, name):
        """Condensé courant de <nom>.part, tenu à jour à chaque morceau ; recalculé depuis le fichier une seule fois
        (reprise après redémarrage du récepteur) -- la clôture ne relit pas des centaines de Go."""
        part = os.path.join(self.dir, name + ".part")
        size = os.path.getsize(part) if os.path.exists(part) else 0
        h, n = self.hashes.get(name, (None, -1))
        if h is None or n != size:
            h = hashlib.sha256()
            if size:
                with open(part, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
            self.hashes[name] = (h, size)
        return h

    def size(self, name):
        if self.done and self.done["name"] == name:
            return self.done["bytes"]
        part = os.path.join(self.dir, name + ".part")
        return os.path.getsize(part) if os.path.exists(part) else 0

    def _watch(self):
        while self.server:
            time.sleep(30)
            if self.server and time.time() - self.last > self.idle_timeout:
                self.close()

    def close(self, delay=0):
        if delay:
            time.sleep(delay)
        srv, self.server = self.server, None
        if srv:
            srv.shutdown(); srv.server_close()


class Client:
    """Même interface que le client du central utilisé par le fil d'envoi : request(method, path, body) et
    send_raw(method, path, data, timeout) -> (statut, corps JSON)."""

    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def _do(self, method, path, data=None, ctype=None, timeout=60):
        req = urllib.request.Request(self.url + path, data=data, method=method, headers={"X-P2V-Token": self.token})
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}
        except (urllib.error.URLError, OSError) as e:
            return 0, {"error": str(e)}

    def request(self, method, path, body=None):
        return self._do(method, path, json.dumps(body).encode() if body is not None else None, "application/json" if body is not None else None)

    def send_raw(self, method, path, data, timeout=300):
        return self._do(method, path, data, "application/octet-stream", timeout)
