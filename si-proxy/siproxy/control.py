# -*- coding: utf-8 -*-
"""Interface de contrôle du bastion si-proxy (livraison #453) : un petit
serveur HTTP (TLS, jeton d'administration) exposé par le relais, que la
tuile du hub consomme. Lecture seule pour l'état, actions pour la maîtrise :

  GET  /status                 -> état (host connecté ?, bastion actif ?,
                                  sessions en cours, compteurs, IP bannies)
  GET  /audit?limit=N          -> N derniers événements du journal
  POST /sessions/<id>/kill     -> ferme une session en cours
  POST /disable | /enable      -> refuse / réautorise les nouvelles sessions
  POST /unban/<ip>             -> lève un bannissement

Toutes les requêtes exigent l'en-tête `X-Si-Proxy-Admin: <jeton>`. Aucune
donnée de charge ni jeton n'est exposée -- uniquement des métadonnées.
"""
import asyncio
import json
import logging

from . import aio, proto

_log = logging.getLogger("siproxy.control")


class Control(object):
    def __init__(self, relay, admin_token):
        self.relay = relay
        self.admin_token = admin_token

    async def handle(self, reader, writer):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, asyncio.LimitOverrunError):
            writer.close()
            return
        method, path, headers = proto.parse_http_request(head)
        try:
            if not self.admin_token or headers.get("x-si-proxy-admin") != self.admin_token:
                return await self._json(writer, 403, {"error": "jeton d'administration requis"})
            await self._route(method, path, writer)
        finally:
            try:
                writer.close()
            except OSError:
                pass

    async def _route(self, method, path, writer):
        p = path.split("?", 1)
        route, query = p[0], (p[1] if len(p) > 1 else "")
        if method == "GET" and route == "/status":
            return await self._json(writer, 200, self.relay.status())
        if method == "GET" and route == "/audit":
            limit = 100
            for kv in query.split("&"):
                if kv.startswith("limit="):
                    try:
                        limit = max(1, min(1000, int(kv[6:])))
                    except ValueError:
                        pass
            return await self._json(writer, 200, {"audit": self.relay.audit.recent(limit)})
        if method == "POST" and route == "/disable":
            self.relay.enabled = False
            _log.warning("bastion DÉSACTIVÉ via l'interface de contrôle")
            return await self._json(writer, 200, {"enabled": False})
        if method == "POST" and route == "/enable":
            self.relay.enabled = True
            _log.info("bastion réactivé via l'interface de contrôle")
            return await self._json(writer, 200, {"enabled": True})
        if method == "POST" and route.startswith("/sessions/") and route.endswith("/kill"):
            sid = route[len("/sessions/"):-len("/kill")]
            killed = self.relay.kill_session(sid)
            return await self._json(writer, 200 if killed else 404, {"killed": killed, "session": sid})
        if method == "POST" and route.startswith("/unban/"):
            ip = route[len("/unban/"):]
            return await self._json(writer, 200, {"unbanned": self.relay.guard.unban(ip), "ip": ip})
        return await self._json(writer, 404, {"error": "route inconnue"})

    async def _json(self, writer, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        reason = {200: "OK", 403: "Forbidden", 404: "Not Found"}.get(status, "OK")
        writer.write(("HTTP/1.1 %d %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"
                      % (status, reason, len(payload))).encode("latin-1") + payload)
        try:
            await writer.drain()
        except OSError:
            pass


async def serve(relay, admin_token, bind, port, ssl_ctx):
    ctrl = Control(relay, admin_token)
    server = await asyncio.start_server(ctrl.handle, bind, port, ssl=ssl_ctx)
    _log.info("interface de contrôle si-proxy sur %s:%d", bind, port)
    return server
