# -*- coding: utf-8 -*-
"""Activité par client (livraison #1002, identification des cibles tranche 2) -- logique PURE + stockage SQLite, testée
(tests/test_activite.py).

L'OpenAPI Nebula ne donne PAS l'usage des applications par client (constaté dans la doc publique le 10/11/2026 : aucune
route « applications ») ; ce qu'elle donne et qu'on garde : volumes montants / descendants par client Wi-Fi (v2
ap-clients, octets sur la période) à chaque relève horaire, et la présence (sessions de l'historique des clients : heures,
jours, bornes, SSID, VLAN, filaire / Wi-Fi). Le profil qui en sort -- rythme, régularité, nuits, week-ends, volumes,
mobilité -- sert à catégoriser (tranche 3) comme on le fait à vue : une machine sans écran parle peu et tout le temps,
une tablette par rafales aux heures d'atelier."""
import math
import time

RETENTION_DAYS = 60
SCHEMA = """
CREATE TABLE IF NOT EXISTS nebula_client_activite (
    site_id TEXT NOT NULL, mac TEXT NOT NULL, at INTEGER NOT NULL, up REAL, down REAL, fenetre_s INTEGER NOT NULL,
    PRIMARY KEY (site_id, mac, at));
CREATE INDEX IF NOT EXISTS idx_nca_at ON nebula_client_activite(at);
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _g(c, *keys):
    for k in keys:
        if c.get(k) not in (None, ""):
            return c.get(k)
    return None


def _mac(s):
    import re
    h = re.sub(r"[^0-9a-f]", "", str(s or "").lower())
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else None


def ingest(conn, site_id, ap_clients, fenetre_s, now=None):
    """Volumes d'une relève (v2 ap-clients, octets sur `fenetre_s`) -> lignes horaires ; purge au-delà de RETENTION_DAYS."""
    conn.executescript(SCHEMA)
    now = int(now or time.time())
    heure = now - now % 3600
    n = 0
    for c in ap_clients or []:
        mac = _mac(_g(c, "mac_address", "macAddress", "mac"))
        up, down = _num(_g(c, "upload", "tx", "uplink")), _num(_g(c, "download", "rx", "downlink"))
        if not mac or (up is None and down is None):
            continue
        conn.execute("INSERT OR REPLACE INTO nebula_client_activite (site_id, mac, at, up, down, fenetre_s) VALUES (?, ?, ?, ?, ?, ?)",
                     (site_id, mac, heure, up, down, int(fenetre_s)))
        n += 1
    conn.execute("DELETE FROM nebula_client_activite WHERE at < ?", (now - RETENTION_DAYS * 86400,))
    conn.commit()
    return n


def _heures_presence(sessions, depuis, now):
    """Sessions -> ensemble des créneaux horaires (début d'heure, epoch) où le client était présent."""
    out = set()
    for s in sessions:
        a, b = max(int(s["start"]), depuis), min(int(s["end"]), now)
        if b < a:
            continue
        h = a - a % 3600
        while h <= b and len(out) < 24 * 400:
            out.add(h)
            h += 3600
    return out


def profil(conn, site_id, mac, jours=14, now=None):
    """-> profil d'activité sur `jours` : présence (jours, heures / jour, histogramme 24 h, nuit, week-end, continu),
    raccordement (filaire / Wi-Fi, bornes, SSID, VLAN), volumes Wi-Fi (moyenne par heure, pointe, régularité, sens)."""
    conn.executescript(SCHEMA)
    now = int(now or time.time())
    depuis = now - int(jours) * 86400
    try:
        sess = [dict(zip(("start", "end", "device", "port", "ssid", "vlan"), r)) for r in conn.execute(
            "SELECT start, end, device, port, ssid, vlan FROM nebula_client_sessions WHERE site_id = ? AND mac = ? AND end >= ?",
            (site_id, mac, depuis))]
    except Exception:  # noqa: BLE001 -- pas encore d'historique
        sess = []
    creneaux = _heures_presence(sess, depuis, now)
    histo = [0] * 24
    jours_vus, nuit, weekend = set(), 0, 0
    for h in creneaux:
        t = time.localtime(h)
        histo[t.tm_hour] += 1
        jours_vus.add(time.strftime("%Y-%m-%d", t))
        nuit += 1 if t.tm_hour < 6 else 0
        weekend += 1 if t.tm_wday >= 5 else 0
    nh = len(creneaux)
    vol = [dict(zip(("at", "up", "down", "fenetre_s"), r)) for r in conn.execute(
        "SELECT at, up, down, fenetre_s FROM nebula_client_activite WHERE site_id = ? AND mac = ? AND at >= ? ORDER BY at", (site_id, mac, depuis))]
    par_h = [((v["up"] or 0) + (v["down"] or 0)) / max(1.0, v["fenetre_s"] / 3600.0) for v in vol]
    moy = sum(par_h) / len(par_h) if par_h else None
    cv = (math.sqrt(sum((x - moy) ** 2 for x in par_h) / len(par_h)) / moy) if par_h and moy else None
    up = sum(v["up"] or 0 for v in vol)
    down = sum(v["down"] or 0 for v in vol)
    return {
        "mac": mac, "jours": int(jours), "jours_vus": len(jours_vus), "heures_presence": nh,
        "heures_par_jour": round(nh / len(jours_vus), 1) if jours_vus else 0,
        "histogramme": histo, "part_nuit": round(nuit / nh, 2) if nh else None, "part_weekend": round(weekend / nh, 2) if nh else None,
        "continu": bool(jours_vus) and nh / len(jours_vus) >= 20,
        "filaire": any(s.get("port") and not s.get("ssid") for s in sess), "wifi": any(s.get("ssid") for s in sess),
        "bornes": sorted({s["device"] for s in sess if s.get("device")}), "ssids": sorted({s["ssid"] for s in sess if s.get("ssid")}),
        "vlans": sorted({str(s["vlan"]) for s in sess if s.get("vlan")}),
        "volumes": {"mesures": len(vol), "moyenne_heure": round(moy) if moy is not None else None, "pointe_heure": round(max(par_h)) if par_h else None,
                    "regularite_cv": round(cv, 2) if cv is not None else None,
                    "part_descendant": round(down / (up + down), 2) if up + down else None},
        "serie": [{"at": v["at"], "octets_heure": round(x)} for v, x in zip(vol, par_h)][-24 * int(jours):],
    }


def profils_site(conn, site_id, jours=14, now=None, macs=None):
    """Profils de tous les clients vus sur la fenêtre (population du site, pour la singularité -- tranche 3)."""
    now = int(now or time.time())
    try:
        tous = [r[0] for r in conn.execute("SELECT mac FROM nebula_client_seen WHERE site_id = ? AND last_seen >= ?", (site_id, now - int(jours) * 86400))]
    except Exception:  # noqa: BLE001
        tous = []
    return {m: profil(conn, site_id, m, jours, now) for m in (macs if macs is not None else tous)}
