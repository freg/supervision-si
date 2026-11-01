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


# ---------------------------------------------------------------- #759 : points 3, 5, 6 de l'item 122
import re as _re

SPEED_RX = _re.compile(r"speed|linkrate|link_rate", _re.I)
POE_RX = _re.compile(r"poe", _re.I)
ERR_RX = _re.compile(r"err|crc|drop|discard", _re.I)
FW_RX = _re.compile(r"firm|^fw|fwversion|firmware", _re.I)
LIC_RX = _re.compile(r"licen|expir|subscription|pack", _re.I)


def find_keys(obj, rx, depth=2, prefix="", children=False, _inside=False):
    """Clés (jusqu'à `depth` niveaux) dont le nom correspond à `rx` -> {chemin: valeur}. Les champs exacts de l'OpenAPI
    Nebula ne sont pas tous documentés : on cherche par motif et on montre ce qui a été trouvé. `children` : sous une
    clé qui correspond (ex. « license »), tout le détail est retenu."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = "%s%s" % (prefix, k)
            hit = _inside or bool(rx.search(str(k)))
            if hit and not isinstance(v, (dict, list)):
                out[p] = v
            if depth > 0 and isinstance(v, dict):
                out.update(find_keys(v, rx, depth - 1, p + ".", children, children and hit))
    return out


def _mbps(v):
    """'1000M' / '1G' / 1000 / '100Mbps' / 'Auto (1000F)' -> Mbit/s ou None."""
    s = str(v or "").upper()
    m = _re.search(r"(\d+(?:\.\d+)?)\s*([GM]?)", s)
    if not m:
        return None
    n = float(m.group(1))
    return int(n * 1000) if m.group(2) == "G" or (n <= 10 and "G" in s) else int(n)


def ap_ports(links, ports_by_sw, names, prev, online):
    """links : liaisons de la carte VLAN (#548/#555 : liaison commutateur -> appareil, b_kind « AP ») ;
    ports_by_sw : {sw: [réglages bruts de port]} ; prev : {ap: "sw:port"} du passage précédent ; online : {ap: bool}.
    -> (tableau par borne, nouvelle correspondance, lignes d'anomalie)."""
    table, now_map, rows = [], {}, []
    by_port = {(sw, str(p.get("portNum"))): p for sw, ps in (ports_by_sw or {}).items() for p in ps or [] if isinstance(p, dict)}
    for l in links or []:
        if not l.get("device") or str(l.get("b_kind") or "").upper() != "AP" or not l.get("b"):
            continue
        ap, sw, port = l["b"], l["a"], str(l.get("a_port"))
        now_map[ap] = "%s:%s" % (sw, port)
        raw = by_port.get((sw, port)) or {}
        sp, poe, err = find_keys(raw, SPEED_RX), find_keys(raw, POE_RX), find_keys(raw, ERR_RX)
        speeds = [x for x in (_mbps(v) for v in sp.values()) if x]
        r = {"ap": ap, "name": names.get(ap, ap), "switch": names.get(sw, sw), "port": port, "speed": sp or None, "poe": poe or None, "errors": err or None,
             "speed_mbps": min(speeds) if speeds else None}
        table.append(r)
        if r["speed_mbps"] and r["speed_mbps"] < 1000:
            rows.append({"site_id": None, "id": "port-speed:%s" % ap, "severity": "moyenne", "element": r["name"], "kind": "anticipation",
                         "message": "%s : port %s de %s à %d Mbit/s (attendu 1 Gbit/s)" % (r["name"], port, r["switch"], r["speed_mbps"]),
                         "action": "câble ou connecteur abîmé, port en négociation forcée : vérifier le câblage et le réglage du port"})
        bad_poe = [k for k, v in poe.items() if _re.search(r"fault|overload|error|deny|denied|insufficient", str(v), _re.I)]
        if bad_poe:
            rows.append({"site_id": None, "id": "port-poe:%s" % ap, "severity": "haute", "element": r["name"], "kind": "anticipation",
                         "message": "%s : PoE en défaut sur le port %s de %s (%s)" % (r["name"], port, r["switch"], ", ".join("%s=%s" % (k, poe[k]) for k in bad_poe)),
                         "action": "budget PoE du commutateur, classe de la borne, câble"})
    for ap, where in (prev or {}).items():
        if ap not in now_map and online.get(ap):
            rows.append({"site_id": None, "id": "lldp-lost:%s" % ap, "severity": "moyenne", "element": names.get(ap, ap), "kind": "anticipation",
                         "message": "%s : plus vue en LLDP sur %s alors qu'elle est en ligne" % (names.get(ap, ap), where.replace(":", " port ")),
                         "action": "borne déplacée sur un commutateur non géré, LLDP désactivé, ou câble remplacé : vérifier"})
    return sorted(table, key=lambda r: r["name"]), now_map, rows


def firmware(devices):
    """Versions de micrologiciel par modèle -> (tableau, lignes « hétérogènes »)."""
    per = {}
    for d in devices or []:
        fw = find_keys(d, FW_RX)
        ver = next((str(v) for v in fw.values() if v not in (None, "")), None)
        per.setdefault(str(d.get("model") or d.get("type") or "?"), {}).setdefault(ver or "?", []).append(d.get("name") or d.get("devId"))
    table = [{"model": m, "versions": {v: sorted(n) for v, n in vs.items()}} for m, vs in sorted(per.items())]
    rows = [{"site_id": None, "id": "fw-mixed:%s" % t["model"], "severity": "moyenne", "element": t["model"], "kind": "anticipation",
             "message": "%s : %d versions de micrologiciel en service (%s)" % (t["model"], len([v for v in t["versions"] if v != "?"]), ", ".join(sorted(v for v in t["versions"] if v != "?"))),
             "action": "aligner les micrologiciels (planifier la mise à jour dans Nebula)"}
            for t in table if len([v for v in t["versions"] if v != "?"]) > 1]
    return table, rows


def _date(v):
    if isinstance(v, (int, float)):
        return float(v) / (1000 if v > 1e11 else 1)
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:19] if "T" in s else s[:10], fmt).timestamp()
        except ValueError:
            continue
    return None


def licenses(org_name, info, now):
    """Champs « licence / expiration » de la fiche d'organisation -> (tableau, lignes J-90 / J-30 / échue)."""
    found = find_keys(info or {}, LIC_RX, depth=3, children=True)
    table, rows = [], []
    for k, v in sorted(found.items()):
        ts = _date(v) if _re.search(r"expir|date|end|until", k, _re.I) else None
        days = int((ts - now) // 86400) if ts else None
        table.append({"org": org_name, "field": k, "value": v, "days_left": days})
        if days is not None and days <= 90:
            rows.append({"site_id": None, "id": "lic:%s:%s" % (org_name, k), "severity": "haute" if days <= 30 else "moyenne", "element": org_name, "kind": "anticipation",
                         "message": "%s : %s %s (%s)" % (org_name, k, "échue depuis %d jour(s)" % -days if days < 0 else "échoit dans %d jour(s)" % days, v),
                         "action": "renouveler la licence / l'abonnement Nebula avant l'échéance"})
    return table, rows


def band_signal(attached, names, weak_dbm, prev_weak, min_clients=5, share24=60, sticky_samples=3):
    """attached : {ap: [client brut]} ; prev_weak : {mac: nb de relevés consécutifs au signal faible}.
    -> (tableau par borne, nouveau prev_weak, lignes). Un client « collé » : signal faible sur `sticky_samples` relevés
    de suite ; part 2,4 GHz élevée sur une borne chargée : pilotage de bande à vérifier."""
    def sig(c):
        for k in ("signalStrength", "signal_strength", "signal", "rssi"):
            try:
                return int(float(str(c.get(k)).replace("dBm", "")))
            except (TypeError, ValueError):
                continue
        return None
    table, new_prev, rows = [], {}, []
    for ap, cl in sorted((attached or {}).items()):
        n = len(cl)
        b24 = sum(1 for c in cl if "2.4" in str(c.get("band") or "") or str(c.get("band") or "").startswith("2"))
        sticky = []
        for c in cl:
            mac = str(c.get("macAddress") or c.get("mac_address") or c.get("mac") or "")
            s = sig(c)
            if mac and s is not None and s < weak_dbm:
                new_prev[mac] = prev_weak.get(mac, 0) + 1
                if new_prev[mac] >= sticky_samples:
                    sticky.append({"mac": mac, "signal": s, "name": c.get("osHostname") or c.get("name") or c.get("hostname")})
        pct = round(100.0 * b24 / n) if n else 0
        table.append({"ap": ap, "name": names.get(ap, ap), "clients": n, "band24": b24, "share24": pct, "sticky": sticky})
        if n >= min_clients and pct >= share24:
            rows.append({"site_id": None, "id": "band24:%s" % ap, "severity": "moyenne", "element": names.get(ap, ap), "kind": "anticipation",
                         "message": "%s : %d %% des clients en 2,4 GHz (%d sur %d)" % (names.get(ap, ap), pct, b24, n),
                         "action": "activer / vérifier le pilotage de bande (band steering), SSID 5 GHz, puissance 2,4 GHz réduite"})
        if len(sticky) >= 3:
            rows.append({"site_id": None, "id": "sticky:%s" % ap, "severity": "moyenne", "element": names.get(ap, ap), "kind": "anticipation",
                         "message": "%s : %d client(s) restés sous %d dBm sur %d relevés de suite" % (names.get(ap, ap), len(sticky), weak_dbm, sticky_samples),
                         "action": "clients « collés » à une borne lointaine : itinérance assistée (802.11k/v), seuil de signal minimal, couverture"})
    return table, new_prev, rows
