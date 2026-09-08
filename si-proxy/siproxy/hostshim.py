# -*- coding: utf-8 -*-
"""Shim host du bastion si-proxy (#452) : tourne sur le host de la VM du hub
(systemd), APPELLE le relais en sortant (aucun port entrant sur le host) et,
sur ordre du relais, ouvre pour chaque session :
  - `shell`   : un PTY exécutant un shell de connexion SOUS freg (non-root ;
                sudo reste à la main de freg dans ce shell) ;
  - `connect` : une socket TCP vers la cible (le hub lui-même ou un hôte du
                LAN) -- c'est ce qui permet au navigateur du Mac, via le
                proxy local, de joindre le hub et le LAN à travers le hub.

Le shim est le SEUL composant qui exécute quelque chose ; le relais n'est
qu'un aiguilleur. Réservé à freg (jeton + TLS).

    sudo python3 -m siproxy.hostshim --relay super:6450 --ca ca.crt \\
        --token "$HOST_TOKEN" --shell-user freg [--cert h.crt --key h.key] \\
        [--deny 10.0.0.0/8 ...]
"""
import argparse
import asyncio
import fcntl
import logging
import os
import pty
import struct
import termios

from . import aio, proto

_log = logging.getLogger("siproxy.hostshim")


class HostShim(object):
    def __init__(self, relay_host, relay_port, token, ssl_ctx, shell_user="freg", deny=None, shell="/bin/bash"):
        self.relay_host, self.relay_port = relay_host, relay_port
        self.token, self.ssl_ctx = token, ssl_ctx
        self.shell_user, self.deny, self.shell = shell_user, list(deny or []), shell

    async def run_forever(self, retry=5.0):
        while True:
            try:
                await self._control_session()
            except (ConnectionError, OSError, asyncio.IncompleteReadError) as exc:
                _log.warning("canal de contrôle perdu (%s) ; nouvelle tentative dans %.0fs", exc, retry)
            await asyncio.sleep(retry)

    async def _connect_relay(self, hello):
        reader, writer = await asyncio.open_connection(self.relay_host, self.relay_port, ssl=self.ssl_ctx,
                                                        server_hostname=self.relay_host)
        writer.write(proto.encode_line(hello))
        await writer.drain()
        return reader, writer

    async def _control_session(self):
        reader, writer = await self._connect_relay({"role": "host", "type": proto.CONTROL, "token": self.token})
        ack = await aio.read_hello(reader)
        if not ack or not ack.get("ok"):
            _log.error("enregistrement refusé par le relais : %s", (ack or {}).get("error"))
            writer.close()
            return
        _log.info("shim host enregistré auprès du relais %s:%d", self.relay_host, self.relay_port)
        while True:
            line = await reader.readuntil(b"\n")
            order = proto.decode_line(line.rstrip(b"\n"))
            if not order or order.get("cmd") != "open":
                continue
            asyncio.ensure_future(self._serve_session(order))

    async def _serve_session(self, order):
        sid, kind, target = order.get("session"), order.get("kind"), order.get("target")
        try:
            reader, writer = await self._connect_relay({"role": "host", "type": proto.DATA, "token": self.token, "session": sid})
        except OSError as exc:
            _log.warning("session %s : ouverture du canal de données impossible (%s)", sid, exc)
            return
        try:
            if kind == proto.SHELL:
                await self._serve_shell(reader, writer)
            elif kind == proto.CONNECT:
                await self._serve_connect(target, reader, writer)
        finally:
            try:
                writer.close()
            except OSError:
                pass

    # -- connect : TCP vers le hub / le LAN -------------------------------
    async def _serve_connect(self, target, reader, writer):
        host, port, err = proto.split_target(target)
        if err:
            return
        ok, why = proto.target_allowed(host, self.deny)
        if not ok:
            _log.warning("connect refusé vers %s : %s", target, why)
            return
        try:
            up_reader, up_writer = await asyncio.wait_for(asyncio.open_connection(host, port), 15)
        except (OSError, asyncio.TimeoutError) as exc:
            _log.info("connect %s échoué : %s", target, exc)
            return
        _log.info("connect établi vers %s", target)
        await aio.bridge(reader, writer, up_reader, up_writer)

    # -- shell : PTY sous freg --------------------------------------------
    async def _serve_shell(self, reader, writer):
        master_fd, slave_fd = pty.openpty()
        _set_winsize(master_fd, 32, 120)
        env = _shell_env(self.shell_user)
        try:
            drop = _make_drop(self.shell_user)
            proc = await asyncio.create_subprocess_exec(
                self.shell, "-l", stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                start_new_session=True, preexec_fn=drop, env=env)
        except (OSError, PermissionError, RuntimeError) as exc:
            os.close(master_fd)
            os.close(slave_fd)
            _log.error("shell non lancé : %s", exc)
            try:
                writer.write(("si-proxy : shell indisponible (%s)\r\n" % exc).encode())
                await writer.drain()
            except OSError:
                pass
            return
        os.close(slave_fd)
        _log.info("shell ouvert (utilisateur %s, pid %s)", self.shell_user, proc.pid)
        await self._pump_pty(master_fd, reader, writer, proc)

    async def _pump_pty(self, master_fd, reader, writer, proc):
        loop = asyncio.get_event_loop()
        os.set_blocking(master_fd, False)
        closed = loop.create_future()

        def on_readable():
            try:
                data = os.read(master_fd, 65536)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                data = b""
            if not data:
                if not closed.done():
                    closed.set_result(True)
                return
            writer.write(data)

        loop.add_reader(master_fd, on_readable)

        async def client_to_pty():
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    os.write(master_fd, data)
            except (OSError, ConnectionError):
                pass
            if not closed.done():
                closed.set_result(True)

        pump = asyncio.ensure_future(client_to_pty())
        try:
            await closed
        finally:
            loop.remove_reader(master_fd)
            pump.cancel()
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), 5)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass


def _set_winsize(fd, rows, cols):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def _make_drop(user):
    """preexec_fn : passe le processus sous `user` (si on est root) ; sinon
    ne change rien (fonctionne alors sous l'utilisateur courant)."""
    if os.geteuid() != 0:
        return None  # pas root : le shell tournera sous l'utilisateur courant
    import pwd
    try:
        p = pwd.getpwnam(user)
    except KeyError:
        raise RuntimeError("utilisateur du shell introuvable : %r" % user)

    def drop():
        os.setgid(p.pw_gid)
        try:
            os.initgroups(user, p.pw_gid)
        except (OSError, PermissionError):
            pass
        os.setuid(p.pw_uid)
        os.chdir(p.pw_dir if os.path.isdir(p.pw_dir) else "/")
    return drop


def _shell_env(user):
    env = {"TERM": os.environ.get("TERM", "xterm-256color"), "LANG": os.environ.get("LANG", "C.UTF-8"),
           "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
    try:
        import pwd
        p = pwd.getpwnam(user)
        env.update({"USER": user, "LOGNAME": user, "HOME": p.pw_dir, "SHELL": p.pw_shell or "/bin/bash"})
    except (KeyError, ImportError):
        pass
    return env


async def _amain():
    ap = argparse.ArgumentParser(description="Shim host du bastion si-proxy")
    ap.add_argument("--relay", required=True, help="host:port du relais (ex. super:6450 ou localhost:6450)")
    ap.add_argument("--token", default=os.environ.get("SI_PROXY_HOST_TOKEN"))
    ap.add_argument("--ca")
    ap.add_argument("--cert")
    ap.add_argument("--key")
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--shell-user", default="freg")
    ap.add_argument("--shell", default="/bin/bash")
    ap.add_argument("--deny", action="append", default=None, help="réseau/hôte refusé (répétable)")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not args.token:
        raise SystemExit("jeton requis : --token (ou SI_PROXY_HOST_TOKEN)")
    host, _, port = args.relay.rpartition(":")
    ctx = aio.client_context(ca_file=args.ca, insecure=args.insecure, certfile=args.cert, keyfile=args.key)
    shim = HostShim(host, int(port), args.token, ctx, shell_user=args.shell_user, deny=args.deny, shell=args.shell)
    _log.info("shim host : relais %s, shell sous %s", args.relay, args.shell_user)
    await shim.run_forever()


if __name__ == "__main__":
    asyncio.run(_amain())
