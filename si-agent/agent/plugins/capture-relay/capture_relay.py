#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin si-agent « capture-relay » (livraison #436, backlog 63 point (e)) :
relais d'exploration réseau depuis un hôte -- une capture tcpdump BORNÉE
(SI_CAPTURE_SECONDS, 60 s ; SI_CAPTURE_MAX_BYTES, 1,5 Mo ; SI_CAPTURE_SNAPLEN,
96 octets : en-têtes seulement, jamais le contenu des paquets) sur
l'interface de la route par défaut (ou SI_CAPTURE_INTERFACE), rendue en
JSON : {interface, cidr, seconds, packets, truncated, pcap_base64}. Le
central (si-agent-api) la relaie à network-agent-api qui la traite comme
sa propre capture, dans le site de l'agent, segment = nom d'hôte.

Livré DÉSACTIVÉ (trafic réel observé) ; privilégié (root pour tcpdump).
Sortie d'erreur explicite si tcpdump manque ou si l'interface est
introuvable -- jamais une exception brute.
"""
import base64
import json
import os
import shutil
import subprocess
import sys


def sh(argv, timeout=10):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        class R:  # noqa: D401
            returncode, stdout, stderr = -1, "", str(exc)
        return R()


def default_interface():
    r = sh(["ip", "-j", "route", "show", "default"])
    try:
        routes = json.loads(r.stdout or "[]")
        if routes:
            return routes[0].get("dev")
    except ValueError:
        pass
    r = sh(["ip", "-j", "-4", "addr", "show", "scope", "global"])
    try:
        for it in json.loads(r.stdout or "[]"):
            if it.get("ifname") != "lo":
                return it.get("ifname")
    except ValueError:
        pass
    return None


def interface_cidr(iface):
    r = sh(["ip", "-j", "-4", "addr", "show", "dev", iface])
    try:
        for it in json.loads(r.stdout or "[]"):
            for a in it.get("addr_info") or []:
                if a.get("family") == "inet" and a.get("scope") == "global":
                    import ipaddress
                    return str(ipaddress.ip_network("%s/%s" % (a["local"], a["prefixlen"]), strict=False))
    except (ValueError, KeyError):
        pass
    return None


def main():
    # réglages : arguments du manifeste (`args`: ["--seconds", "30", "--interface", "eth1"]),
    # sinon variables d'environnement, sinon défauts
    opts = {}
    argv = sys.argv[1:]
    for i in range(0, len(argv) - 1, 2):
        if argv[i].startswith("--"):
            opts[argv[i][2:].replace("-", "_")] = argv[i + 1]
    seconds = int(opts.get("seconds") or os.environ.get("SI_CAPTURE_SECONDS", "60"))
    max_bytes = int(opts.get("max_bytes") or os.environ.get("SI_CAPTURE_MAX_BYTES", str(1500 * 1024)))
    snaplen = int(opts.get("snaplen") or os.environ.get("SI_CAPTURE_SNAPLEN", "96"))
    iface = opts.get("interface") or os.environ.get("SI_CAPTURE_INTERFACE") or default_interface()
    out = {"interface": iface, "cidr": None, "seconds": seconds, "snaplen": snaplen, "packets": None, "truncated": False, "pcap_base64": None, "error": None}
    if not shutil.which("tcpdump"):
        out["error"] = "tcpdump absent (apt install tcpdump)"
        print(json.dumps(out)); return 2
    if not iface:
        out["error"] = "aucune interface avec une route par défaut (SI_CAPTURE_INTERFACE pour forcer)"
        print(json.dumps(out)); return 2
    out["cidr"] = interface_cidr(iface)
    # -G/-W : tcpdump s'arrête seul après `seconds` ; -s snaplen ; -w - : pcap sur stdout
    argv = ["tcpdump", "-i", iface, "-s", str(snaplen), "-w", "-", "-U", "-nn", "-q", "-G", str(seconds), "-W", "1"]
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        out["error"] = "tcpdump : %s" % exc
        print(json.dumps(out)); return 2
    chunks, size = [], 0
    try:
        while True:
            data = proc.stdout.read(65536)
            if not data:
                break
            size += len(data)
            if size > max_bytes:
                chunks.append(data[: max(0, max_bytes - (size - len(data)))])
                out["truncated"] = True
                proc.terminate()
                break
            chunks.append(data)
        try:
            proc.wait(timeout=seconds + 15)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        err = (proc.stderr.read() or b"").decode("utf-8", "replace")
    pcap = b"".join(chunks)
    if len(pcap) < 24:
        out["error"] = "capture vide : %s" % (err.strip().splitlines()[-1] if err.strip() else "aucun paquet")
        print(json.dumps(out)); return 1
    # nombre de paquets : compté sans dépendance, format pcap classique
    import struct
    magic = pcap[:4]
    bo = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
    pos, n = 24, 0
    while pos + 16 <= len(pcap):
        incl = struct.unpack(bo + "IIII", pcap[pos:pos + 16])[2]
        pos += 16 + incl
        if pos <= len(pcap):
            n += 1
    out["packets"] = n
    out["bytes"] = len(pcap)
    out["pcap_base64"] = base64.b64encode(pcap).decode("ascii")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
