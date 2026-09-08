# -*- coding: utf-8 -*-
"""Helpers asyncio partagés (lecture du HELLO, pompe d'octets, contexte TLS)
du bastion si-proxy (#452)."""
import asyncio
import ssl

from . import proto


async def read_hello(reader, timeout=15.0):
    """Lit la première ligne (HELLO) d'une connexion -> objet ou None."""
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\n"), timeout)
    except (asyncio.IncompleteReadError, asyncio.TimeoutError, asyncio.LimitOverrunError):
        return None
    return proto.decode_line(raw.rstrip(b"\n"))


async def pipe(reader, writer, chunk=65536, counter=None):
    """Copie reader -> writer jusqu'à EOF, puis ferme l'écriture de writer.
    Ne lève jamais : une erreur réseau termine simplement la pompe. Si
    `counter` (liste [n]) est fourni, y accumule le nombre d'octets copiés
    (pour l'audit -- métadonnée de volume, jamais le contenu)."""
    try:
        while True:
            data = await reader.read(chunk)
            if not data:
                break
            writer.write(data)
            await writer.drain()
            if counter is not None:
                counter[0] += len(data)
    except (ConnectionError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        try:
            if writer.can_write_eof():
                writer.write_eof()
        except (OSError, RuntimeError):
            pass


async def bridge(a_reader, a_writer, b_reader, b_writer):
    """Relie deux flux dans les deux sens. Dès qu'UN sens se termine (EOF ou
    erreur), on ferme les DEUX connexions : en TLS on ne peut pas demi-fermer
    (`write_eof` indisponible), donc fermer franchement évite qu'un pair reste
    suspendu et que les connexions s'accumulent (sémantique d'un proxy)."""
    ca, cb = [0], [0]
    t1 = asyncio.ensure_future(pipe(a_reader, b_writer, counter=ca))
    t2 = asyncio.ensure_future(pipe(b_reader, a_writer, counter=cb))
    await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
    for w in (a_writer, b_writer):
        try:
            w.close()
        except OSError:
            pass
    for t in (t1, t2):
        t.cancel()
    for t in (t1, t2):
        try:
            await t
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    return ca[0], cb[0]


def server_context(certfile, keyfile, ca_file=None, require_client_cert=False):
    """Contexte TLS serveur ; si `require_client_cert`, exige et vérifie le
    certificat client contre `ca_file` (TLS mutuel)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if require_client_cert:
        if not ca_file:
            raise ValueError("TLS mutuel demandé sans CA de vérification (ca_file)")
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(ca_file)
    return ctx


def client_context(ca_file=None, insecure=False, certfile=None, keyfile=None):
    """Contexte TLS client : vérifie le serveur via `ca_file` (ou système),
    présente un certificat client si fourni (TLS mutuel)."""
    ctx = ssl.create_default_context(cafile=ca_file) if not insecure else ssl._create_unverified_context()  # noqa: SLF001
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if certfile and keyfile:
        ctx.load_cert_chain(certfile, keyfile)
    return ctx


def peer_cn(writer):
    """CN du certificat client présenté (TLS mutuel), ou None."""
    ssl_obj = writer.get_extra_info("ssl_object")
    if ssl_obj is None:
        return None
    cert = ssl_obj.getpeercert()
    if not cert:
        return None
    for rdn in cert.get("subject", ()):
        for k, v in rdn:
            if k == "commonName":
                return v
    return None
