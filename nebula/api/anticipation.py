# -*- coding: utf-8 -*-
"""Anticipation Wi-Fi (livraison #758, BACKLOG 122 tranche 1) -- logique PURE, testée (nebula/tests/test_anticipation.py).

À partir des relevés d'occupation (#747, 35 jours) et des transitions d'état Nebula :
  1. prévision : profil habituel par borne × jour de semaine × heure (médiane, p90) ; alerte AVANT le pic habituel
     (horizon de quelques heures) et affluence inhabituelle (seuil dynamique = habituel + marge) ;
  2. battements d'état : borne passée plusieurs fois hors ligne / en alerte en 24 h (précurseur PoE, câble,
     commutateur) ; disponibilité par borne sur 7 et 30 jours ;
  4. étendues DHCP par SSID : clients connectés rapportés à la taille de l'étendue déclarée (alerte à 80 / 95 %).
Les constats sont des lignes d'anomalie (site_id, id, severity, element, message, action, kind="anticipation") suivies
par alerting.track comme celles de l'occupation."""
from datetime import datetime, timedelta

DEFAULTS = {"enabled": True, "horizon_hours": 2, "min_weeks": 2, "unusual_margin_pct": 50, "unusual_min": 5,
            "flap_count": 3, "dhcp_pools": {}, "dhcp_warn_pct": 80, "dhcp_crit_pct": 95}
DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _int(v, lo, hi, d):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return d


def normalize(cfg):
    cfg = cfg if isinstance(cfg, dict) else {}
    pools = {}
    for k, v in (cfg.get("dhcp_pools") or {}).items():
        size = _int(v, 0, 1 << 20, 0)
        if str(k).strip() and size:
            pools[str(k).strip()[:64]] = size
    return {"enabled": bool(cfg.get("enabled", True)), "horizon_hours": _int(cfg.get("horizon_hours"), 1, 12, 2),
            "min_weeks": _int(cfg.get("min_weeks"), 1, 5, 2), "unusual_margin_pct": _int(cfg.get("unusual_margin_pct"), 10, 500, 50),
            "unusual_min": _int(cfg.get("unusual_min"), 1, 500, 5), "flap_count": _int(cfg.get("flap_count"), 2, 50, 3),
            "dhcp_pools": pools, "dhcp_warn_pct": _int(cfg.get("dhcp_warn_pct"), 10, 100, 80), "dhcp_crit_pct": _int(cfg.get("dhcp_crit_pct"), 10, 100, 95)}


def _pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def profile(samples, tz=None):
    """samples : [(dev_id, at, clients)] -> {dev_id: {(jour 0-6, heure): [max des relevés de chaque semaine]}}.
    On garde le MAXIMUM de chaque créneau d'une semaine donnée (un pic court compte), puis on compare les semaines."""
    per = {}
    for dev, at, n in samples:
        dt = datetime.fromtimestamp(int(at), tz)
        key = (dt.weekday(), dt.hour)
        week = dt.isocalendar()[:2]
        slot = per.setdefault(dev, {}).setdefault(key, {})
        slot[week] = max(slot.get(week, 0), int(n or 0))
    return {dev: {k: sorted(v.values()) for k, v in slots.items()} for dev, slots in per.items()}


def expected(prof, dev, dt, min_weeks=2):
    vals = (prof.get(dev) or {}).get((dt.weekday(), dt.hour)) or []
    if len(vals) < min_weeks:
        return None
    return {"p50": _pct(vals, 0.5), "p90": _pct(vals, 0.9), "weeks": len(vals)}


def forecast(prof, names, site_id, site_name, now_dt, occ, ant):
    """Pic habituel attendu dans les `horizon_hours` prochaines heures (heure pleine suivante incluse)."""
    rows = []
    base = now_dt.replace(minute=0, second=0, microsecond=0)
    for dev in sorted(prof):
        for h in range(1, ant["horizon_hours"] + 1):
            t = base + timedelta(hours=h)
            e = expected(prof, dev, t, ant["min_weeks"])
            if not e or e["p90"] < occ["ap_warn"]:
                continue
            crit = e["p90"] >= occ["ap_crit"]
            rows.append({"site_id": site_id, "site": site_name, "id": "prev:%s" % dev, "severity": "haute" if crit else "moyenne",
                         "element": names.get(dev, dev), "kind": "anticipation", "expected": e, "at_hour": t.strftime("%H:%M"),
                         "message": "%s : pic habituel attendu vers %s — %d clients (médiane %d, %d semaine(s) observée(s) le %s à cette heure ; seuil %d)"
                                    % (names.get(dev, dev), t.strftime("%Hh"), e["p90"], e["p50"], e["weeks"], DAYS_FR[t.weekday()], occ["ap_crit"] if crit else occ["ap_warn"]),
                         "action": "avant le pic : orienter vers les bornes voisines, vérifier la bande 5 GHz et la puissance, prévenir l'accueil"})
            break
    return rows


def unusual(prof, aps, names, site_id, site_name, now_dt, ant):
    """Affluence inhabituelle : relevé courant > habituel (p90 du créneau) + marge (%), et au moins `unusual_min` de plus."""
    rows = []
    for ap in aps or []:
        e = expected(prof, ap["dev_id"], now_dt, ant["min_weeks"])
        if not e:
            continue
        limit = e["p90"] * (1 + ant["unusual_margin_pct"] / 100.0)
        if ap["clients"] > limit and ap["clients"] - e["p90"] >= ant["unusual_min"]:
            rows.append({"site_id": site_id, "site": site_name, "id": "unusual:%s" % ap["dev_id"], "severity": "moyenne",
                         "element": names.get(ap["dev_id"], ap.get("name") or ap["dev_id"]), "kind": "anticipation",
                         "message": "%s : affluence inhabituelle — %d clients, habituellement %d au plus le %s à cette heure"
                                    % (names.get(ap["dev_id"], ap.get("name") or ap["dev_id"]), ap["clients"], e["p90"], DAYS_FR[now_dt.weekday()]),
                         "action": "événement imprévu ? vérifier la charge de la borne et des voisines"})
    return rows


def flapping(transitions, names, site_id, site_name, now, ant, window_h=24):
    """transitions : [(dev_id, from_status, to_status, at)] -> bornes passées ≥ flap_count fois hors ligne / en alerte."""
    count = {}
    for dev, _f, to, at in transitions:
        if at >= now - window_h * 3600 and to != "online":
            count[dev] = count.get(dev, 0) + 1
    return [{"site_id": site_id, "site": site_name, "id": "flap:%s" % dev, "severity": "haute" if n >= 2 * ant["flap_count"] else "moyenne",
             "element": names.get(dev, dev), "kind": "anticipation", "flaps": n,
             "message": "%s : %d passages hors ligne / en alerte en %d h" % (names.get(dev, dev), n, window_h),
             "action": "précurseur de panne : alimentation PoE (budget du commutateur), câble, port, liaison montante"}
            for dev, n in sorted(count.items()) if n >= ant["flap_count"]]


def availability(transitions, current, now, days):
    """Part du temps « online » sur `days` jours, par appareil. transitions triées ou non : [(dev, from, to, at)] ;
    current : {dev: statut actuel}. Avant la première transition de la fenêtre, l'état est son `from`."""
    start, per = now - days * 86400, {}
    for dev, f, to, at in sorted(transitions, key=lambda t: t[3]):
        per.setdefault(dev, []).append((at, f, to))
    out = {}
    for dev in set(per) | set(current):
        evs = [e for e in per.get(dev, []) if e[0] >= start]
        before = [e for e in per.get(dev, []) if e[0] < start]
        state = before[-1][2] if before else (evs[0][1] if evs else current.get(dev))
        t, up = start, 0.0
        for at, _f, to in evs:
            if state == "online":
                up += at - t
            t, state = at, to
        if state == "online":
            up += now - t
        out[dev] = round(100.0 * up / (now - start), 2) if state is not None or evs else None
    return out


def dhcp(snaps, ant):
    """Clients connectés par SSID (tous sites) rapportés aux étendues déclarées -> (tableau, lignes d'anomalie).
    Borne basse : un bail court encore des appareils partis, l'usage réel de l'étendue peut être plus élevé."""
    used = {}
    for snap in (snaps or {}).values():
        for ap in snap.get("aps") or []:
            for ssid, n in (ap.get("by_ssid") or {}).items():
                used[ssid] = used.get(ssid, 0) + n
    table, rows = [], []
    for ssid, size in sorted(ant["dhcp_pools"].items()):
        n = used.get(ssid, 0)
        pct = round(100.0 * n / size, 1)
        table.append({"ssid": ssid, "pool": size, "clients": n, "pct": pct})
        if pct >= ant["dhcp_warn_pct"]:
            rows.append({"site_id": "*", "site": "Wi-Fi", "id": "dhcp:%s" % ssid, "severity": "haute" if pct >= ant["dhcp_crit_pct"] else "moyenne",
                         "element": "SSID %s" % ssid, "kind": "anticipation",
                         "message": "SSID %s : %d clients connectés pour une étendue DHCP de %d adresses (%s %%)" % (ssid, n, size, pct),
                         "action": "agrandir l'étendue ou raccourcir la durée des baux avant l'épuisement (nouveaux clients sans adresse)"})
    return table, rows
