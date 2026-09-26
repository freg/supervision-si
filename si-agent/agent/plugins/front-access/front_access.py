#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « accès publics du frontal » (livraison #622, item 99) -- lit le
journal d'accès Apache du frontal public (format combined, plus la durée
`%D` en µs quand le vhost la journalise : front-reverse-proxy.sh #622) sur
les N dernières minutes et remonte un résumé : requêtes, codes (2xx, 3xx,
401 = jeton exigé par A0, 403 = périmètre / refus, 404, 5xx = hub
injoignable), clients (IP publique, volume, erreurs, dernier accès,
navigateur), chemins les plus demandés, requêtes lentes, erreurs 5xx, et
constats : hub-unreachable (5xx en série), auth-refused-burst (401/403
répétés depuis une même IP = balayage), slow-backend, scan-404. Jamais le
journal lui-même : le résumé seulement (IP publiques, pas de contenu).

Usage : front_access.py [--log /var/log/apache2/hub-*-access.log] [--minutes 60]
        [--slow 3] [--top 15]   (globs acceptés ; l'agent tourne en root sur le frontal)
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

LINE_RE = re.compile(r'^(?P<ip>\S+) \S+ (?P<user>\S+) \[(?P<ts>[^\]]+)\] "(?P<req>[^"]*)" (?P<status>\d{3}) (?P<bytes>\S+)(?: "(?P<ref>[^"]*)" "(?P<ua>[^"]*)")?(?: (?P<us>\d+))?\s*$')
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_ts(s):
    """'25/Sep/2026:14:03:12 +0200' -> epoch."""
    m = re.match(r"(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})", s or "")
    if not m:
        return None
    d, mon, y, hh, mm, ss, sign, oh, om = m.groups()
    tz = timezone((1 if sign == "+" else -1) * timedelta(hours=int(oh), minutes=int(om)))
    try:
        return datetime(int(y), MONTHS.get(mon, 1), int(d), int(hh), int(mm), int(ss), tzinfo=tz).timestamp()
    except ValueError:
        return None


def parse_line(line):
    m = LINE_RE.match(line.strip())
    if not m:
        return None
    req = m.group("req").split(" ")
    method, path = (req[0], req[1]) if len(req) >= 2 else ("?", m.group("req")[:200])
    us = m.group("us")
    return {"ip": m.group("ip"), "user": None if m.group("user") == "-" else m.group("user"), "t": parse_ts(m.group("ts")),
            "method": method, "path": path[:300], "status": int(m.group("status")), "bytes": 0 if m.group("bytes") == "-" else int(m.group("bytes")),
            "ua": (m.group("ua") or "")[:120], "ms": round(int(us) / 1000, 1) if us else None}


def ua_family(ua):
    u = (ua or "").lower()
    for key, label in (("curl", "curl"), ("python", "python"), ("wget", "wget"), ("go-http", "go"), ("bot", "robot"), ("spider", "robot"), ("crawl", "robot"),
                       ("edg/", "Edge"), ("firefox", "Firefox"), ("chrome", "Chrome"), ("safari", "Safari"), ("okhttp", "mobile app"), ("si-agent", "si-agent")):
        if key in u:
            return label
    return "autre" if u else "—"


def summarize(entries, now=None, slow_s=3.0, top=15, window_minutes=60):
    now = now or time.time()
    since = now - window_minutes * 60
    rows = [e for e in entries if e and (e["t"] is None or e["t"] >= since)]
    st = Counter(); clients = defaultdict(lambda: {"count": 0, "errors": 0, "auth": 0, "bytes": 0, "last": 0, "ua": Counter(), "paths": Counter()})
    paths = Counter(); slow = []; err5 = []; api_401 = 0
    for e in rows:
        s = e["status"]
        cls = "5xx" if s >= 500 else "404" if s == 404 else "403" if s == 403 else "401" if s == 401 else "4xx" if s >= 400 else "3xx" if s >= 300 else "2xx"
        st[cls] += 1
        c = clients[e["ip"]]
        c["count"] += 1; c["bytes"] += e["bytes"]; c["last"] = max(c["last"], e["t"] or 0); c["ua"][ua_family(e["ua"])] += 1
        c["paths"][e["path"].split("?")[0][:80]] += 1
        if s >= 500:
            c["errors"] += 1; err5.append(e)
        if s in (401, 403):
            c["auth"] += 1
            if e["path"].startswith("/api/"):
                api_401 += 1
        paths[e["path"].split("?")[0][:80]] += 1
        if e["ms"] is not None and e["ms"] >= slow_s * 1000:
            slow.append(e)
    findings = []
    if st["5xx"] >= 5 or (rows and st["5xx"] / len(rows) > 0.2):
        findings.append({"code": "hub-unreachable", "severity": "critical", "detail": "%d réponse(s) 5xx sur %d (hub ou Keycloak injoignable depuis le frontal)" % (st["5xx"], len(rows))})
    for ip, c in clients.items():
        if c["auth"] >= 20 and c["auth"] >= 0.8 * c["count"]:
            findings.append({"code": "auth-refused-burst", "severity": "warning", "detail": "%s : %d refus 401/403 sur %d requêtes (balayage ou client sans jeton)" % (ip, c["auth"], c["count"])})
    scan = [ip for ip, c in clients.items() if c["count"] >= 30 and sum(1 for e in rows if e["ip"] == ip and e["status"] == 404) >= 0.7 * c["count"]]
    for ip in scan:
        findings.append({"code": "scan-404", "severity": "info", "detail": "%s : majorité de 404 (exploration automatique)" % ip})
    if len(slow) >= 5:
        findings.append({"code": "slow-backend", "severity": "warning", "detail": "%d requête(s) au-delà de %.0f s" % (len(slow), slow_s)})
    ms_vals = [e["ms"] for e in rows if e["ms"] is not None]
    out_clients = sorted(({"ip": ip, "count": c["count"], "errors": c["errors"], "auth_refused": c["auth"], "bytes": c["bytes"],
                           "last": datetime.fromtimestamp(c["last"]).isoformat(timespec="seconds") if c["last"] else None,
                           "ua": c["ua"].most_common(1)[0][0] if c["ua"] else "—", "top_path": c["paths"].most_common(1)[0][0] if c["paths"] else None}
                          for ip, c in clients.items()), key=lambda x: -x["count"])[:top]
    state = "critical" if any(f["severity"] == "critical" for f in findings) else "warning" if any(f["severity"] == "warning" for f in findings) else "ok"
    return {"window_minutes": window_minutes, "total": len(rows), "status": dict(st), "clients": out_clients, "distinct_clients": len(clients),
            "top_paths": [{"path": p, "count": n} for p, n in paths.most_common(top)],
            "slow": [{"ip": e["ip"], "path": e["path"][:120], "status": e["status"], "ms": e["ms"]} for e in sorted(slow, key=lambda e: -(e["ms"] or 0))[:top]],
            "errors_5xx": [{"ip": e["ip"], "path": e["path"][:120], "status": e["status"], "at": datetime.fromtimestamp(e["t"]).isoformat(timespec="seconds") if e["t"] else None} for e in err5[-top:]],
            "latency": {"avg_ms": round(sum(ms_vals) / len(ms_vals), 1) if ms_vals else None, "max_ms": max(ms_vals) if ms_vals else None, "measured": len(ms_vals)},
            "api_auth_refused": api_401, "findings": findings, "summary": {"state": state, "total": len(rows), "errors_5xx": st["5xx"], "clients": len(clients)}}


def read_tail(path, max_bytes=8_000_000):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            return fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="/var/log/apache2/hub-*-access.log")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--slow", type=float, default=3.0)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args(argv)
    files = sorted(set(f for pat in args.log.split(",") for f in glob.glob(pat.strip())))
    if not files:
        print(json.dumps({"error": "aucun journal : %s" % args.log, "summary": {"state": "unknown"}, "findings": []})); return 0
    entries = []
    for f in files:
        entries.extend(parse_line(l) for l in read_tail(f))
    out = summarize(entries, slow_s=args.slow, top=args.top, window_minutes=max(1, min(1440, args.minutes)))
    out["files"] = files
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
