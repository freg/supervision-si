# -*- coding: utf-8 -*-
"""Occupation des bornes Wi-Fi (livraison #747) -- logique PURE, testée (nebula/tests/test_occupancy.py).

- relevé : clients connectés par borne (bande, SSID, signal faible), à partir des clients de l'OpenAPI rattachés
  aux bornes par topology.attach_clients ;
- seuils : clients par borne (avertissement / critique), part de clients au signal faible, total du site ;
  alertes Nebula : borne hors ligne ou « alerting » depuis au moins N minutes ;
- les dépassements sont rendus sous forme de lignes d'anomalie (site_id, id, severity, element, message, action,
  kind) pour réutiliser le suivi d'alerting.track (délai, rappel, retour à la normale) ;
- récapitulatif : par borne, moyenne / maximum (avec l'heure) / p95 des relevés de la période, bornes les plus
  chargées, bornes restées vides, pic du site."""
from datetime import datetime

import topology

DEFAULTS = {"enabled": False, "sample_minutes": 10, "ap_warn": 25, "ap_crit": 40, "site_warn": 0,
            "weak_dbm": -75, "weak_pct": 40, "weak_min_clients": 5,
            "status_alerts": True, "status_delay_minutes": 5,
            "recap": {"enabled": False, "time": "18:00", "weekdays": [1, 2, 3, 4, 5], "hours": 24}}
CONNECTED = ("online", "connected", "connecté", "en ligne", "active")


def _int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def normalize(cfg, time_ok, weekdays_of):
    """Réglages partiels -> complets. time_ok / weekdays_of : validateurs partagés avec alerting."""
    cfg = cfg if isinstance(cfg, dict) else {}
    out = {"enabled": bool(cfg.get("enabled", DEFAULTS["enabled"])),
           "sample_minutes": _int(cfg.get("sample_minutes", 10), 5, 120, 10),
           "ap_warn": _int(cfg.get("ap_warn", 25), 1, 500, 25),
           "ap_crit": _int(cfg.get("ap_crit", 40), 1, 500, 40),
           "site_warn": _int(cfg.get("site_warn", 0), 0, 100000, 0),
           "weak_dbm": _int(cfg.get("weak_dbm", -75), -95, -40, -75),
           "weak_pct": _int(cfg.get("weak_pct", 40), 0, 100, 40),
           "weak_min_clients": _int(cfg.get("weak_min_clients", 5), 1, 500, 5),
           "status_alerts": bool(cfg.get("status_alerts", True)),
           "status_delay_minutes": _int(cfg.get("status_delay_minutes", 5), 0, 1440, 5)}
    if out["ap_crit"] < out["ap_warn"]:
        out["ap_crit"] = out["ap_warn"]
    r = cfg.get("recap") if isinstance(cfg.get("recap"), dict) else {}
    d = DEFAULTS["recap"]
    t = str(r.get("time") or d["time"]).strip()
    out["recap"] = {"enabled": bool(r.get("enabled", d["enabled"])), "time": t if time_ok(t) else d["time"],
                    "weekdays": weekdays_of(r.get("weekdays", d["weekdays"]), d["weekdays"]),
                    "hours": _int(r.get("hours", d["hours"]), 1, 168, 24)}
    return out


def _signal(v):
    try:
        return int(float(str(v).replace("dBm", "").strip()))
    except (TypeError, ValueError):
        return None


def snapshot(clients, devices, weak_dbm=-75):
    """-> {"aps": [{dev_id, name, clients, by_band, by_ssid, weak}], "total", "unattached"} (bornes seulement,
    clients connectés seulement ; une borne sans client figure avec 0)."""
    aps = [d for d in devices or [] if topology.kind_of(d.get("type")) == "ap" and d.get("devId")]
    attached, loose, _f = topology.attach_clients(clients, devices or [])
    rows = []
    for d in aps:
        cl = [c for c in attached.get(d["devId"], []) if (c.get("status") or "") in CONNECTED or not c.get("status") or c.get("status") == "inconnu"]
        bands, ssids, weak = {}, {}, 0
        for c in cl:
            bands[str(c.get("band") or "?")] = bands.get(str(c.get("band") or "?"), 0) + 1
            ssids[str(c.get("ssid") or "?")] = ssids.get(str(c.get("ssid") or "?"), 0) + 1
            s = _signal(c.get("signal"))
            if s is not None and s < weak_dbm:
                weak += 1
        rows.append({"dev_id": d["devId"], "name": d.get("name") or d["devId"], "clients": len(cl), "by_band": bands,
                     "by_ssid": ssids, "weak": weak})
    rows.sort(key=lambda r: (-r["clients"], r["name"]))
    return {"aps": rows, "total": sum(r["clients"] for r in rows),
            "unattached": len([c for c in loose if (c.get("status") or "") in CONNECTED])}


def breaches(site_id, site_name, snap, statuses, names, cfg, now):
    """Dépassements -> lignes d'anomalie (gravités d'alerting : haute / moyenne).
    statuses : {devId: {"status", "since"}} (relevé minute du sondeur) ; names : {devId: nom}."""
    out = []

    def row(key, sev, element, message, action, kind):
        out.append({"site_id": site_id, "site": site_name, "id": key, "severity": sev, "element": element,
                    "message": "%s : %s" % (element, message) if element and element != site_name else message, "action": action, "kind": kind})
    for ap in snap.get("aps") or []:
        n = ap["clients"]
        if n >= cfg["ap_crit"]:
            row("occ-crit:%s" % ap["dev_id"], "haute", ap["name"], "%d clients sur la borne (seuil critique %d)" % (n, cfg["ap_crit"]),
                "répartir la charge : borne voisine, bande 5/6 GHz, puissance", "occupation")
        elif n >= cfg["ap_warn"]:
            row("occ-warn:%s" % ap["dev_id"], "moyenne", ap["name"], "%d clients sur la borne (seuil %d)" % (n, cfg["ap_warn"]),
                "surveiller ; envisager une borne de plus dans la zone", "occupation")
        if n >= cfg["weak_min_clients"] and cfg["weak_pct"] and 100 * ap["weak"] >= cfg["weak_pct"] * n:
            row("occ-weak:%s" % ap["dev_id"], "moyenne", ap["name"],
                "%d client(s) sur %d sous %d dBm (%d %%)" % (ap["weak"], n, cfg["weak_dbm"], round(100 * ap["weak"] / n)),
                "couverture insuffisante ou clients collés à une borne lointaine", "occupation")
    if cfg["site_warn"] and snap.get("total", 0) >= cfg["site_warn"]:
        row("occ-site", "moyenne", site_name, "%d clients Wi-Fi sur le site (seuil %d)" % (snap["total"], cfg["site_warn"]),
            "vérifier la capacité globale (licences, bornes, DHCP)", "occupation")
    if cfg["status_alerts"]:
        for dev, st in (statuses or {}).items():
            s = (st or {}).get("status")
            if s and s != "online" and now - int((st or {}).get("since") or now) >= cfg["status_delay_minutes"] * 60:
                since = datetime.fromtimestamp(int(st["since"])).strftime("%d/%m %H:%M") if st.get("since") else "?"
                row("neb-status:%s" % dev, "haute" if s == "offline" else "moyenne", names.get(dev, dev),
                    "Nebula : %s depuis %s" % ({"offline": "hors ligne", "alerting": "en alerte"}.get(s, s), since),
                    "vérifier l'alimentation PoE, la liaison montante, l'état dans Nebula", "nebula")
    return out


def recap(samples, since_ts, names=None):
    """samples : [(dev_id, at, clients, site_id)] ; -> {aps: [{dev_id, name, avg, max, max_at, p95, n}], site_peak, idle}."""
    names = names or {}
    per, site = {}, {}
    for dev, at, n, sid in samples or []:
        if at < since_ts:
            continue
        per.setdefault(dev, []).append((at, n))
        site[(sid, at)] = site.get((sid, at), 0) + n
    rows = []
    for dev, pts in per.items():
        vals = sorted(n for _a, n in pts)
        mx = max(pts, key=lambda p: (p[1], p[0]))
        rows.append({"dev_id": dev, "name": names.get(dev, dev), "avg": round(sum(vals) / len(vals), 1), "max": mx[1],
                     "max_at": mx[0], "p95": vals[min(len(vals) - 1, int(round(0.95 * (len(vals) - 1))))], "n": len(vals)})
    rows.sort(key=lambda r: (-r["max"], -r["avg"], r["name"]))
    peak = max(site.items(), key=lambda kv: kv[1]) if site else None
    return {"aps": rows, "site_peak": {"clients": peak[1], "at": peak[0][1]} if peak else None,
            "idle": [r["name"] for r in rows if r["max"] == 0]}


def recap_text(rec, title, hours):
    lines = [title, "=" * len(title), ""]
    if not rec["aps"]:
        return "\n".join(lines + ["Aucun relevé sur la période."])
    if rec["site_peak"]:
        lines.append("Pic du site : %d clients le %s" % (rec["site_peak"]["clients"], datetime.fromtimestamp(rec["site_peak"]["at"]).strftime("%d/%m à %H:%M")))
    lines += ["Période : %d h, %d borne(s)" % (hours, len(rec["aps"])), "", "%-28s %6s %6s %6s  %s" % ("Borne", "moy.", "p95", "max", "heure du max")]
    for r in rec["aps"]:
        lines.append("%-28s %6s %6s %6s  %s" % (r["name"][:28], r["avg"], r["p95"], r["max"], datetime.fromtimestamp(r["max_at"]).strftime("%d/%m %H:%M")))
    if rec["idle"]:
        lines += ["", "Bornes sans aucun client sur la période : " + ", ".join(rec["idle"])]
    return "\n".join(lines)
