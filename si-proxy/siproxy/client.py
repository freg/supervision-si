# -*- coding: utf-8 -*-
"""Client Mac du bastion si-proxy (#452). Deux usages :

  shell  : ouvre un shell interactif sur le host de la VM du hub (sous freg).
             python3 -m siproxy.client shell --relay super:6450 --ca ca.crt \\
                 --token "$FREG_TOKEN" [--cert freg.crt --key freg.key]

  proxy  : lance un proxy HTTP local (127.0.0.1:PORT) ; règle ton navigateur
           dessus et navigue en https sur le hub et, par le hub, sur le LAN.
             python3 -m siproxy.client proxy --listen 127.0.0.1:6451 \\
                 --relay super:6450 --ca ca.crt --token "$FREG_TOKEN"

Chaque flux ouvre une connexion de données vers le relais (jeton + TLS) ;
le relais l'apparie à la connexion ouverte en retour par le shim host, qui
seul exécute le shell (freg) ou la connexion TCP vers la cible.
"""
import argparse
import asyncio
import os
import sys

from . import aio, proto


async def _open_stream(relay, ssl_ctx, token, kind, target=None, server_name=None):
    """Ouvre un canal de données et attend l'accusé du relais.
    Retourne (reader, writer) prêt au pontage brut, ou lève RuntimeError."""
    host, _, port = relay.rpartition(":")
    # server_name (#470) : nom vérifié dans le certificat quand on joint le relais
    # par un tunnel SSH local (127.0.0.1) -- le cert porte le nom du hub, pas 127.0.0.1
    reader, writer = await asyncio.open_connection(host, int(port), ssl=ssl_ctx, server_hostname=server_name or host)
    hello = {"role": "client", "type": proto.DATA, "token": token, "kind": kind}
    if target:
        hello["target"] = target
    writer.write(proto.encode_line(hello))
    await writer.drain()
    ack = await aio.read_hello(reader, timeout=25.0)
    if not ack or not ack.get("ok"):
        writer.close()
        raise RuntimeError((ack or {}).get("error") or "le relais n'a pas confirmé la session")
    return reader, writer


# ---------------------------------------------------------------------
# shell interactif
# ---------------------------------------------------------------------

async def run_shell(args):
    ctx = aio.client_context(ca_file=args.ca, insecure=args.insecure, certfile=args.cert, keyfile=args.key)
    reader, writer = await _open_stream(args.relay, ctx, args.token, proto.SHELL, server_name=args.server_name)
    sys.stderr.write("si-proxy : shell ouvert sur le host du hub (Ctrl-D pour quitter)\r\n")
    sys.stderr.flush()
    loop = asyncio.get_event_loop()
    stdin_fd = sys.stdin.fileno()
    raw = _RawTTY(stdin_fd)
    raw.enter()
    done = loop.create_future()

    def on_stdin():
        try:
            data = os.read(stdin_fd, 65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:
            if not done.done():
                done.set_result(True)
            return
        writer.write(data)

    os.set_blocking(stdin_fd, False)
    loop.add_reader(stdin_fd, on_stdin)

    async def server_to_stdout():
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                os.write(1, data)
        except (OSError, ConnectionError):
            pass
        if not done.done():
            done.set_result(True)

    pump = asyncio.ensure_future(server_to_stdout())
    try:
        await done
    finally:
        loop.remove_reader(stdin_fd)
        pump.cancel()
        raw.restore()
        try:
            writer.close()
        except OSError:
            pass
        sys.stderr.write("\r\nsi-proxy : shell fermé\r\n")


class _RawTTY(object):
    """Passe le terminal local en mode brut le temps du shell (restauré à la
    sortie). Sans effet si stdin n'est pas un terminal (pipe de test)."""
    def __init__(self, fd):
        self.fd, self.saved = fd, None

    def enter(self):
        try:
            import termios
            import tty
            self.saved = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
        except Exception:  # noqa: BLE001 -- pas un tty
            self.saved = None

    def restore(self):
        if self.saved is not None:
            try:
                import termios
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------
# proxy HTTP local (CONNECT + http absolu)
# ---------------------------------------------------------------------

async def run_proxy(args):
    ctx = aio.client_context(ca_file=args.ca, insecure=args.insecure, certfile=args.cert, keyfile=args.key)
    host, _, port = args.listen.rpartition(":")

    async def on_browser(b_reader, b_writer):
        try:
            head = await asyncio.wait_for(b_reader.readuntil(b"\r\n\r\n"), 30)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, asyncio.LimitOverrunError):
            b_writer.close()
            return
        method, target, _ver, is_connect = proto.parse_proxy_request(head)
        if is_connect:
            await _do_connect(target, b_reader, b_writer, ctx, args)
        elif method:
            await _do_http(target, head, b_reader, b_writer, ctx, args)
        else:
            b_writer.close()

    server = await asyncio.start_server(on_browser, host, int(port))
    sys.stderr.write("si-proxy : proxy local sur http://%s -- règle ton navigateur dessus\n" % args.listen)
    sys.stderr.flush()
    async with server:
        await server.serve_forever()

    _ = server  # noqa


async def _do_connect(target, b_reader, b_writer, ctx, args):
    try:
        up_reader, up_writer = await _open_stream(args.relay, ctx, args.token, proto.CONNECT, target=target, server_name=args.server_name)
    except RuntimeError as exc:
        b_writer.write(("HTTP/1.1 502 Bad Gateway\r\n\r\nsi-proxy : %s\r\n" % exc).encode())
        await b_writer.drain()
        b_writer.close()
        return
    b_writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
    await b_writer.drain()
    await aio.bridge(b_reader, b_writer, up_reader, up_writer)


async def _do_http(uri, head, b_reader, b_writer, ctx, args):
    hostport, path = proto.absolute_uri_target(uri)
    if not hostport:
        b_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        await b_writer.drain()
        b_writer.close()
        return
    try:
        up_reader, up_writer = await _open_stream(args.relay, ctx, args.token, proto.CONNECT, target=hostport, server_name=args.server_name)
    except RuntimeError as exc:
        b_writer.write(("HTTP/1.1 502 Bad Gateway\r\n\r\nsi-proxy : %s\r\n" % exc).encode())
        await b_writer.drain()
        b_writer.close()
        return
    # réécrit la requête en forme origine (chemin au lieu de l'URL absolue)
    rewritten = head.replace(uri.encode("latin-1"), path.encode("latin-1"), 1)
    up_writer.write(rewritten)
    await up_writer.drain()
    await aio.bridge(b_reader, b_writer, up_reader, up_writer)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Client du bastion si-proxy")
    sub = ap.add_subparsers(dest="mode", required=True)
    for name in ("shell", "proxy"):
        p = sub.add_parser(name)
        p.add_argument("--relay", required=True)
        p.add_argument("--token", default=os.environ.get("SI_PROXY_CLIENT_TOKEN"))
        p.add_argument("--ca")
        p.add_argument("--cert")
        p.add_argument("--key")
        p.add_argument("--insecure", action="store_true")
        p.add_argument("--server-name", default=None, help="nom attendu dans le certificat du relais (tunnel SSH : --relay 127.0.0.1:6450 --server-name super)")
        if name == "proxy":
            p.add_argument("--listen", default="127.0.0.1:6451")
    args = ap.parse_args(argv)
    if not args.token:
        raise SystemExit("jeton requis : --token (ou SI_PROXY_CLIENT_TOKEN)")
    coro = run_shell(args) if args.mode == "shell" else run_proxy(args)
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
