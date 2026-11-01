#!/usr/bin/env python3
"""Rapport d'audit Wi-Fi continu (livraison #657) depuis le journal du central local (data/history.jsonl) : par sonde,
courbes RSSI / occupation du canal / débit négocié / latence-pertes du chemin, synthèse par heure, constats, bornes vues.
Usage : python3 report-wifi-day.py data/history.jsonl rapport.html [--md rapport.md] [--since 2026-10-04T07:00] [--until ...]
Bibliothèque standard seule ; SVG inline. Les fonctions de calcul sont pures (testées)."""
import sys, json, argparse, statistics, html, collections, datetime

def load(path, since=None, until=None):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try: r = json.loads(line)
            except ValueError: continue
            at = r.get("at") or ""
            if since and at < since: continue
            if until and at > until: continue
            rows.append(r)
    return rows

def series(rows, task, path):
    """[(at, valeur)] d'un champ de mesure (chemin a.b.c) pour une tâche, mesures ok seulement."""
    out = []
    for r in rows:
        if r.get("task") != task or not r.get("ok"): continue
        v = r.get("data") or {}
        for k in path.split("."):
            v = v.get(k) if isinstance(v, dict) else None
            if v is None: break
        if isinstance(v, (int, float)): out.append((r.get("at"), float(v)))
    return out

def hourly(points):
    """{heure 'YYYY-MM-DDTHH': {n, min, avg, max}}"""
    g = collections.defaultdict(list)
    for at, v in points: g[(at or "")[:13]].append(v)
    return {h: dict(n=len(v), min=min(v), avg=round(statistics.fmean(v), 1), max=max(v)) for h, v in sorted(g.items())}

def findings(rows):
    """Constats (alerts/findings des sondes) comptés par libellé et par sonde, avec première/dernière occurrence."""
    out = {}
    for r in rows:
        d = r.get("data") or {}
        for a in (d.get("alerts") or d.get("findings") or []):
            key = (r.get("agent_id"), r.get("task"), a.get("kind") or a.get("code") or a.get("message") or str(a)[:60])
            e = out.setdefault(key, dict(agent=r.get("agent_id"), task=r.get("task"), label=a.get("message") or a.get("kind") or str(a)[:80], n=0, first=r.get("at"), last=r.get("at")))
            e["n"] += 1; e["last"] = r.get("at")
    return sorted(out.values(), key=lambda x: -x["n"])

def aps_seen(rows):
    """Bornes vues (voisinage wifi-probe v3) : bssid -> {ssid, chan/freq, n, rssi max, stations max}."""
    out = {}
    for r in rows:
        if r.get("task") != "plugin:wifi-probe" or not r.get("ok"): continue
        for ap in ((r.get("data") or {}).get("neighbors") or (r.get("data") or {}).get("scan") or []):
            b = ap.get("bssid");
            if not b: continue
            e = out.setdefault(b, dict(bssid=b, ssid=ap.get("ssid"), freq=ap.get("freq"), n=0, rssi_max=-999, stations_max=0))
            e["n"] += 1; e["rssi_max"] = max(e["rssi_max"], ap.get("signal_dbm") or ap.get("rssi") or -999)
            e["stations_max"] = max(e["stations_max"], (ap.get("bss_load") or {}).get("stations") or ap.get("stations") or 0)
    return sorted(out.values(), key=lambda x: -x["n"])

def svg_line(points, width=760, height=120, lo=None, hi=None, unit=""):
    if not points: return "<p class='muted'>aucune mesure</p>"
    vals = [v for _, v in points]; lo = min(vals) if lo is None else lo; hi = max(vals) if hi is None else hi
    if hi == lo: hi = lo + 1
    n = len(points); xs = [10 + i * (width - 20) / max(1, n - 1) for i in range(n)]; ys = [height - 15 - (v - lo) * (height - 30) / (hi - lo) for v in vals]
    pts = " ".join("%.1f,%.1f" % (x, y) for x, y in zip(xs, ys))
    return ("<svg viewBox='0 0 %d %d' width='100%%' height='%d' role='img'><polyline fill='none' stroke='currentColor' stroke-width='1.5' points='%s'/>"
            "<text x='4' y='12' font-size='10'>%s%s</text><text x='4' y='%d' font-size='10'>%s%s</text><text x='%d' y='%d' font-size='10' text-anchor='end'>%s → %s</text></svg>"
            % (width, height, height, pts, hi, unit, height - 3, lo, unit, width - 4, height - 3, html.escape((points[0][0] or "")[11:16]), html.escape((points[-1][0] or "")[11:16])))

METRICS = [("plugin:wifi-probe", "link.signal_dbm", "RSSI (dBm)", "dBm"), ("plugin:wifi-probe", "channel.busy_pct", "Occupation du canal (%)", "%"),
           ("plugin:wifi-probe", "link.tx_mbit", "Débit négocié émission (Mbit/s)", ""), ("plugin:wifi-probe", "path.rtt_avg_ms", "Latence vers la passerelle (ms)", "ms"),
           ("plugin:wifi-probe", "path.loss_pct", "Pertes vers la passerelle (%)", "%"), ("plugin:path-probe", "summary.http_ms", "HTTP réel (ms)", "ms")]

def build(rows):
    agents = sorted({r.get("agent_id") for r in rows if r.get("agent_id")}); parts = []; md = []
    span = (min((r.get("at") or "~" for r in rows), default=""), max((r.get("at") or "" for r in rows), default=""))
    parts.append("<h1>Audit Wi-Fi continu</h1><p class='muted'>%d mesure(s), %d sonde(s), du %s au %s</p>" % (len(rows), len(agents), html.escape(span[0]), html.escape(span[1])))
    md.append("# Audit Wi-Fi continu\n\n%d mesure(s), %d sonde(s), du %s au %s\n" % (len(rows), len(agents), span[0], span[1]))
    fs = findings(rows)
    parts.append("<h2>Constats</h2>" + ("<table><tr><th>Sonde</th><th>Constat</th><th>Occurrences</th><th>Première</th><th>Dernière</th></tr>" + "".join("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (html.escape(str(f["agent"])), html.escape(str(f["label"])), f["n"], html.escape(str(f["first"])[11:16]), html.escape(str(f["last"])[11:16])) for f in fs) + "</table>" if fs else "<p>aucun constat remonté par les sondes</p>"))
    md.append("## Constats\n\n" + ("\n".join("- %s : %s (%d fois, %s → %s)" % (f["agent"], f["label"], f["n"], str(f["first"])[11:16], str(f["last"])[11:16]) for f in fs) if fs else "aucun") + "\n")
    for a in agents:
        rs = [r for r in rows if r.get("agent_id") == a]; parts.append("<h2>Sonde %s</h2>" % html.escape(a)); md.append("## Sonde %s\n" % a)
        for task, path, title, unit in METRICS:
            pts = series(rs, task, path)
            if not pts: continue
            h = hourly(pts); vals = [v for _, v in pts]
            parts.append("<h3>%s</h3>%s<p class='muted'>%d points · min %s · moy %s · max %s</p>" % (title, svg_line(pts, unit=unit), len(pts), min(vals), round(statistics.fmean(vals), 1), max(vals)))
            parts.append("<details><summary>par heure</summary><table><tr><th>Heure</th><th>n</th><th>min</th><th>moy</th><th>max</th></tr>" + "".join("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (html.escape(k[11:13] + "h"), v["n"], v["min"], v["avg"], v["max"]) for k, v in h.items()) + "</table></details>")
            md.append("### %s\n\n| Heure | n | min | moy | max |\n|---|---|---|---|---|\n" % title + "\n".join("| %sh | %d | %s | %s | %s |" % (k[11:13], v["n"], v["min"], v["avg"], v["max"]) for k, v in h.items()) + "\n")
    aps = aps_seen(rows)
    if aps:
        parts.append("<h2>Bornes vues</h2><table><tr><th>BSSID</th><th>SSID</th><th>Fréquence</th><th>Vue (fois)</th><th>RSSI max</th><th>Stations max</th></tr>" + "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (html.escape(x["bssid"]), html.escape(str(x["ssid"])), x["freq"], x["n"], x["rssi_max"], x["stations_max"]) for x in aps[:60]) + "</table>")
        md.append("## Bornes vues\n\n" + "\n".join("- %s %s %s : vue %d fois, RSSI max %s, stations max %s" % (x["bssid"], x["ssid"], x["freq"], x["n"], x["rssi_max"], x["stations_max"]) for x in aps[:60]) + "\n")
    page = ("<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Audit Wi-Fi continu</title><style>body{font-family:system-ui,sans-serif;max-width:900px;margin:20px auto;padding:0 12px;color:#1b1f23}"
            "table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #d0d4d9;padding:3px 7px;text-align:left}.muted{color:#6a737d}svg{display:block;margin:4px 0}@media(prefers-color-scheme:dark){body{background:#101418;color:#e6e9ec}td,th{border-color:#3a414a}}</style></head><body>"
            + "".join(parts) + "</body></html>")
    return page, "\n".join(md)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("history"); ap.add_argument("out_html"); ap.add_argument("--md"); ap.add_argument("--since"); ap.add_argument("--until"); a = ap.parse_args()
    rows = load(a.history, a.since, a.until); page, md = build(rows)
    open(a.out_html, "w", encoding="utf-8").write(page)
    if a.md: open(a.md, "w", encoding="utf-8").write(md)
    print("%d mesure(s) -> %s%s" % (len(rows), a.out_html, (" + " + a.md) if a.md else ""))
