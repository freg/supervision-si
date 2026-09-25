#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « trace réseau du poste » (livraison #618, famille explorer) --
capture BORNÉE du trafic du poste puis analyse SUR PLACE (trace_analyzer) :
hôtes joints (SNI / Host / DNS), protocoles, connexions sans réponse, RST,
retransmissions, DNS en échec, codes HTTP en clair, RTT par serveur,
latences DNS / TLS / premier octet. Seul le résumé part au central ; la
capture est effacée. Complète web-audit : web-audit rejoue une URL choisie,
web-trace observe ce que les applications font réellement.

Windows 10/11 : `pktmon` (natif, administrateur -- l'agent tourne en SYSTEM)
  pktmon start --capture --comp nics --pkt-size 0 -f <etl>  … pktmon stop
  pktmon etl2pcap <etl> -o <pcapng>  (pktmon ≥ 2004 ; sinon erreur explicite)
Linux / macOS : tcpdump -w (root ; sonde privilégiée).

Usage : web_trace.py [--seconds 30] [--filter ""] ; --seconds borné 5–300.
Sortie : JSON de trace_analyzer.analyze + {seconds, tool, error}.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import trace_analyzer  # noqa: E402


def clamp_seconds(v, default=30):
    try:
        return max(5, min(300, int(v)))
    except (TypeError, ValueError):
        return default


def capture_plan(platform, seconds, tmpdir):
    """-> ([argv de démarrage], chemin du fichier brut). Pure."""
    if platform == "win32":
        etl = os.path.join(tmpdir, "si-agent-trace.etl")
        return [["pktmon", "start", "--capture", "--comp", "nics", "--pkt-size", "0", "-f", etl]], etl
    pcap = os.path.join(tmpdir, "si-agent-trace.pcap")
    return [["tcpdump", "-i", "any" if platform.startswith("linux") else "en0", "-s", "256", "-w", pcap, "-U", "-nn", "-q", "-G", str(seconds), "-W", "1"]], pcap


def _run(argv, timeout):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def local_ips():
    ips = set()
    try:
        import socket
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:  # noqa: BLE001
        pass
    return sorted(ips - {"127.0.0.1"})


def capture(seconds, platform=sys.platform):
    """-> (bytes de capture | None, outil, erreur)."""
    tmpdir = tempfile.mkdtemp(prefix="si-agent-trace-")
    plan, raw = capture_plan(platform, seconds, tmpdir)
    tool = plan[0][0]
    if not shutil.which(tool):
        return None, tool, "%s absent%s" % (tool, " (Windows 10 2004+ requis)" if tool == "pktmon" else " (apt install tcpdump)")
    try:
        if platform == "win32":
            r = _run(plan[0], 30)
            if r is None or r.returncode != 0:
                return None, tool, "pktmon start : %s" % ((r.stderr or r.stdout).strip()[:200] if r else "délai / absent")
            time.sleep(seconds)
            _run(["pktmon", "stop"], 30)
            out = raw[:-4] + ".pcapng"
            r = _run(["pktmon", "etl2pcap", raw, "-o", out], 120)
            if r is None or r.returncode != 0 or not os.path.exists(out):
                return None, tool, "pktmon etl2pcap : %s" % ((r.stderr or r.stdout).strip()[:200] if r else "échec")
            with open(out, "rb") as fh:
                return fh.read(), tool, None
        r = _run(plan[0], seconds + 30)
        if not os.path.exists(raw):
            return None, tool, "tcpdump : %s" % ((r.stderr or "").strip()[:200] if r else "délai")
        with open(raw, "rb") as fh:
            return fh.read(), tool, None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", default="30")
    ap.add_argument("--slow-rtt", type=float, default=200)
    ap.add_argument("--slow-dns", type=float, default=300)
    args = ap.parse_args(argv)
    seconds = clamp_seconds(args.seconds)
    data, tool, err = capture(seconds)
    if err:
        print(json.dumps({"error": err, "tool": tool, "seconds": seconds, "summary": {"state": "unknown"}, "findings": [], "hosts": []}))
        return 0
    try:
        res = trace_analyzer.analyze(data, local_ips=local_ips(), slow_rtt_ms=args.slow_rtt, slow_dns_ms=args.slow_dns)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "analyse échouée : %s" % exc, "tool": tool, "seconds": seconds}))
        return 0
    res.update({"seconds": seconds, "tool": tool, "capture_bytes": len(data)})
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
