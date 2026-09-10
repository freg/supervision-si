# -*- coding: utf-8 -*-
"""Relais du bastion si-proxy (#452, audit/contrôle/ban #453) : aiguilleur
TLS, dans le conteneur du hub. Il n'exécute RIEN -- il apparie, par
identifiant de session, la connexion de données du client Mac et celle
ouverte en retour par le shim host, puis pompe les octets entre les deux.

Le host de la VM APPELLE le relais en sortant (canal de contrôle) : le
conteneur n'a donc pas besoin d'accès au host, et le host n'ouvre aucun
port entrant. Réservé à freg : jeton client dédié + (recommandé) TLS mutuel
avec liste blanche de CN.

#453 : journal d'audit (audit.py), garde-fou anti-force-brute (guard.py) et
interface de contrôle HTTP (control.py, port séparé, jeton d'admin).

    python3 -m siproxy.relay --cert s.crt --key s.key --port 6450 \\
        --host-token "$HOST_TOKEN" --client-token "$FREG_TOKEN" \\
        [--ca ca.crt --require-client-cert --allow-cn freg] \\
        [--audit-log /data/si-proxy-audit.jsonl] \\
        [--control-port 6452 --admin-token "$ADMIN_TOKEN"]
"""
import argparse
import asyncio
import itertools
import logging
import os

from . import aio, audit as audit_mod, control as control_mod, guard as guard_mod, proto

_log = logging.getLogger("siproxy.relay")


class Relay(object):
    def __init__(self, host_token, client_token, allow_cn=None, require_cn=False, pair_timeout=20.0,
                 audit=None, guard=None):
        self.host_token = host_token
        self.client_token = client_token
        self.allow_cn = list(allow_cn or [])
        self.require_cn = require_cn
        self.pair_timeout = pair_timeout
        self.audit = audit or audit_mod.Audit()
        self.guard = guard or guard_mod.Guard()
        self.enabled = True
        self._host_control = None          # (reader, writer) du canal de contrôle host
        self._waiting = {}                 # sid -> Future -> (host_reader, host_writer, finished)
        self._active = {}                  # sid -> {client_writer, host_writer, finished} (pour kill)
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

    # -- état pour l'interface de contrôle --------------------------------
    def status(self):
        return {"enabled": self.enabled, "host_connected": self._host_control is not None,
                "sessions": self.audit.active(), "counters": self.audit.counters(),
                "banned": self.guard.banned(), "mtls": self.require_cn, "allow_cn": self.allow_cn}

    def kill_session(self, sid):
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            return False
        entry = self._active.get(sid)
        if not entry:
            return False
        for w in (entry.get("client_writer"), entry.get("host_writer")):
            try:
                if w:
                    w.close()
            except OSError:
                pass
        fin = entry.get("finished")
        if fin is not None and not fin.done():
            fin.set_result(True)
        _log.warning("session %s tuée via l'interface de contrôle", sid)
        return True

    # -- connexions -------------------------------------------------------
    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        peer_ip = peer[0] if peer else None
        if self.guard.is_banned(peer_ip):
            _log.warning("connexion rejetée (IP bannie) : %s", peer_ip)
            try:
                writer.close()
            except OSError:
                pass
            return
        hello = await aio.read_hello(reader)
        role = (hello or {}).get("role")
        typ = (hello or {}).get("type")
        ok, why = self._authorized(hello or {}, writer, role) if role in ("host", "client") else (False, "role inconnu")
        if not ok:
            banned = self.guard.record_failure(peer_ip)
            self.audit.refused(audit_mod.client_label(aio.peer_cn(writer), role or "?"), why,
                               kind=(hello or {}).get("kind"), target=(hello or {}).get("target"), peer=peer_ip)
            _log.warning("connexion refusée de %s : %s%s", peer_ip, why, " -- IP BANNIE" if banned else "")
            await self._bye(writer, why)
            return
        self.guard.record_success(peer_ip)
        try:
            if role == "host" and typ == proto.CONTROL:
                await self._host_control_loop(reader, writer)
            elif role == "host" and typ == proto.DATA:
                await self._host_data(hello, reader, writer)
            elif role == "client" and typ == proto.DATA:
                await self._client_data(hello, reader, writer, peer_ip)
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

    async def _client_data(self, hello, reader, writer, peer_ip=None):
        if not self.enabled:
            self.audit.refused(audit_mod.client_label(aio.peer_cn(writer)), "bastion désactivé",
                               kind=hello.get("kind"), target=hello.get("target"), peer=peer_ip)
            await self._bye(writer, "bastion désactivé")
            return
        if self._host_control is None:
            await self._bye(writer, "aucun shim host connecté")
            return
        sid = next(self._ids)
        client = audit_mod.client_label(aio.peer_cn(writer))
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._waiting[sid] = fut
        order = {"cmd": "open", "session": sid, "kind": hello.get("kind"), "target": hello.get("target")}
        _log.info("session %d : %s %s (client %s, %s)", sid, hello.get("kind"), hello.get("target") or "", client, peer_ip)
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
        writer.write(proto.encode_line({"ok": True, "session": sid}))
        await writer.drain()
        self.audit.start(sid, client, hello.get("kind"), hello.get("target"), peer=peer_ip)
        self._active[sid] = {"client_writer": writer, "host_writer": host_writer, "finished": finished}
        up = down = 0
        outcome, error = "closed", None
        try:
            up, down = await aio.bridge(reader, writer, host_reader, host_writer)
        except Exception as exc:  # noqa: BLE001
            outcome, error = "error", str(exc)[:200]
        finally:
            if not finished.done():
                finished.set_result(True)
            self._active.pop(sid, None)
            self.audit.finish(sid, bytes_up=up, bytes_down=down, outcome=outcome, error=error)
        _log.info("session %d terminée (%d↑ %d↓ octets)", sid, up, down)

    async def _host_data(self, hello, reader, writer):
        sid = hello.get("session")
        fut = self._waiting.pop(sid, None)
        if fut is None or fut.done():
            await self._bye(writer, "session inconnue ou déjà appariée")
            return
        loop = asyncio.get_event_loop()
        finished = loop.create_future()
        fut.set_result((reader, writer, finished))
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
    ap.add_argument("--audit-log", default=os.environ.get("SI_PROXY_AUDIT_LOG"))
    ap.add_argument("--control-port", type=int, default=int(os.environ.get("SI_PROXY_CONTROL_PORT", "0") or 0))
    ap.add_argument("--admin-token", default=os.environ.get("SI_PROXY_ADMIN_TOKEN"))
    ap.add_argument("--ban-threshold", type=int, default=int(os.environ.get("SI_PROXY_BAN_THRESHOLD", "5")))
    ap.add_argument("--ban-window", type=int, default=int(os.environ.get("SI_PROXY_BAN_WINDOW", "300")))
    ap.add_argument("--ban-minutes", type=int, default=int(os.environ.get("SI_PROXY_BAN_MINUTES", "15")))
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not args.host_token or not args.client_token:
        raise SystemExit("jetons requis : --host-token et --client-token (ou SI_PROXY_HOST_TOKEN / SI_PROXY_CLIENT_TOKEN)")
    ctx = aio.server_context(args.cert, args.key, ca_file=args.ca, require_client_cert=args.require_client_cert)
    audit = audit_mod.Audit(path=args.audit_log)
    guard = guard_mod.Guard(threshold=args.ban_threshold, window_s=args.ban_window, ban_s=args.ban_minutes * 60)
    relay = Relay(args.host_token, args.client_token, allow_cn=args.allow_cn or ["freg"],
                  require_cn=args.require_client_cert, audit=audit, guard=guard)
    server = await asyncio.start_server(relay.handle, args.bind, args.port, ssl=ctx)
    _log.info("relais si-proxy à l'écoute sur %s:%d (TLS mutuel=%s, audit=%s)",
              args.bind, args.port, args.require_client_cert, args.audit_log or "off")
    servers = [server]
    if args.control_port and args.admin_token:
        cctx = aio.server_context(args.cert, args.key)  # TLS serveur seul ; auth par jeton d'admin
        servers.append(await control_mod.serve(relay, args.admin_token, args.bind, args.control_port, cctx))
    elif args.control_port:
        _log.warning("interface de contrôle non démarrée : --admin-token manquant")
    async with server:
        await asyncio.gather(*[s.serve_forever() for s in servers])


if __name__ == "__main__":
    asyncio.run(_amain())
