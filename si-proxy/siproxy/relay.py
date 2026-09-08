# -*- coding: utf-8 -*-
"""Relais du bastion si-proxy (#452) : aiguilleur TLS, dans le conteneur du
hub. Il n'exécute RIEN -- il apparie, par identifiant de session, la
connexion de données du client Mac et celle ouverte en retour par le shim
host, puis pompe les octets entre les deux.

Le host de la VM APPELLE le relais en sortant (canal de contrôle) : le
conteneur n'a donc pas besoin d'accès au host, et le host n'ouvre aucun
port entrant. Réservé à freg : jeton client dédié + (recommandé) TLS mutuel
avec liste blanche de CN.

    python3 -m siproxy.relay --cert s.crt --key s.key --port 6450 \\
        --host-token "$HOST_TOKEN" --client-token "$FREG_TOKEN" \\
        [--ca ca.crt --require-client-cert --allow-cn freg]
"""
import argparse
import asyncio
import itertools
import logging
import os

from . import aio, proto

_log = logging.getLogger("siproxy.relay")


class Relay(object):
    def __init__(self, host_token, client_token, allow_cn=None, require_cn=False, pair_timeout=20.0):
        self.host_token = host_token
        self.client_token = client_token
        self.allow_cn = list(allow_cn or [])
        self.require_cn = require_cn
        self.pair_timeout = pair_timeout
        self._host_control = None          # (reader, writer) du canal de contrôle host
        self._waiting = {}                 # sid -> asyncio.Future -> (host_reader, host_writer)
        self._ids = itertools.count(1)

    # -- authentification -------------------------------------------------
    def _authorized(self, hello, writer, role):
        token = self.host_token if role == "host" else self.client_token
        ok, why = proto.valid_hello(hello, token, roles=(role,))
        if not ok:
            return False, why
        if role == "client" and self.require_cn:
            cn = aio.peer_cn(writer)
            if cn not in self.allow_cn:
                return False, "certificat client non autorisé (CN=%r)" % cn
        return True, None

    # -- connexions -------------------------------------------------------
    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        hello = await aio.read_hello(reader)
        role = (hello or {}).get("role")
        typ = (hello or {}).get("type")
        ok, why = self._authorized(hello or {}, writer, role) if role in ("host", "client") else (False, "role inconnu")
        if not ok:
            _log.warning("connexion refusée de %s : %s", peer, why)
            await self._bye(writer, why)
            return
        try:
            if role == "host" and typ == proto.CONTROL:
                await self._host_control_loop(reader, writer)
            elif role == "host" and typ == proto.DATA:
                await self._host_data(hello, reader, writer)
            elif role == "client" and typ == proto.DATA:
                await self._client_data(hello, reader, writer)
            else:
                await self._bye(writer, "combinaison role/type non permise")
        finally:
            try:
                writer.close()
            except OSError:
                pass

    async def _bye(self, writer, why):
        try:
            writer.write(proto.encode_line({"error": why}))
            await writer.drain()
            writer.close()
        except OSError:
            pass

    async def _host_control_loop(self, reader, writer):
        if self._host_control is not None:
            old = self._host_control[1]
            self._host_control = None
            try:
                old.close()
            except OSError:
                pass
            _log.info("nouveau canal de contrôle host : l'ancien est remplacé")
        self._host_control = (reader, writer)
        _log.info("shim host enregistré")
        writer.write(proto.encode_line({"ok": True, "role": "host"}))
        await writer.drain()
        try:
            while True:
                line = await reader.readuntil(b"\n")
                if not line:
                    break  # acks/heartbeats éventuels ignorés
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            if self._host_control and self._host_control[1] is writer:
                self._host_control = None
                _log.info("canal de contrôle host fermé")

    async def _client_data(self, hello, reader, writer):
        if self._host_control is None:
            await self._bye(writer, "aucun shim host connecté")
            return
        sid = next(self._ids)
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._waiting[sid] = fut
        order = {"cmd": "open", "session": sid, "kind": hello.get("kind"), "target": hello.get("target")}
        _log.info("session %d : %s %s", sid, hello.get("kind"), hello.get("target") or "")
        try:
            self._host_control[1].write(proto.encode_line(order))
            await self._host_control[1].drain()
        except OSError:
            self._waiting.pop(sid, None)
            await self._bye(writer, "shim host injoignable")
            return
        try:
            host_reader, host_writer, finished = await asyncio.wait_for(fut, self.pair_timeout)
        except asyncio.TimeoutError:
            self._waiting.pop(sid, None)
            await self._bye(writer, "le shim host n'a pas ouvert la session à temps")
            return
        # confirmation au client puis pontage brut ; on signale la fin au
        # handler du canal host pour qu'il ne rende la main (et ne ferme sa
        # connexion) qu'une fois le pont terminé.
        writer.write(proto.encode_line({"ok": True, "session": sid}))
        await writer.drain()
        try:
            await aio.bridge(reader, writer, host_reader, host_writer)
        finally:
            if not finished.done():
                finished.set_result(True)
        _log.info("session %d terminée", sid)

    async def _host_data(self, hello, reader, writer):
        sid = hello.get("session")
        fut = self._waiting.pop(sid, None)
        if fut is None or fut.done():
            await self._bye(writer, "session inconnue ou déjà appariée")
            return
        loop = asyncio.get_event_loop()
        finished = loop.create_future()
        fut.set_result((reader, writer, finished))
        # le pontage est piloté par _client_data ; on maintient cette
        # connexion ouverte jusqu'à la fin du pont (sinon le handler la
        # fermerait et couperait le flux).
        try:
            await asyncio.wait_for(finished, timeout=None)
        except asyncio.CancelledError:
            pass


async def _amain():
    ap = argparse.ArgumentParser(description="Relais du bastion si-proxy")
    ap.add_argument("--cert", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=6450)
    ap.add_argument("--host-token", default=os.environ.get("SI_PROXY_HOST_TOKEN"))
    ap.add_argument("--client-token", default=os.environ.get("SI_PROXY_CLIENT_TOKEN"))
    ap.add_argument("--ca")
    ap.add_argument("--require-client-cert", action="store_true")
    ap.add_argument("--allow-cn", action="append", default=None)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not args.host_token or not args.client_token:
        raise SystemExit("jetons requis : --host-token et --client-token (ou SI_PROXY_HOST_TOKEN / SI_PROXY_CLIENT_TOKEN)")
    ctx = aio.server_context(args.cert, args.key, ca_file=args.ca, require_client_cert=args.require_client_cert)
    relay = Relay(args.host_token, args.client_token, allow_cn=args.allow_cn or ["freg"], require_cn=args.require_client_cert)
    server = await asyncio.start_server(relay.handle, args.bind, args.port, ssl=ctx)
    _log.info("relais si-proxy à l'écoute sur %s:%d (TLS mutuel=%s)", args.bind, args.port, args.require_client_cert)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_amain())
