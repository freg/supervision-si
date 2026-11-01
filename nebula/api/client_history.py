# -*- coding: utf-8 -*-
"""Historique des clients du réseau Nebula (livraison #872).

Nebula ne garde que 24 h d'historique des clients : une passerelle LoRa muette depuis des jours y est introuvable.
Relève HORAIRE (et à la demande) des clients du site (v2 clients + clients des bornes + clients des commutateurs,
période 2 h pour recouvrir deux relèves), conservée ici :
- nebula_client_seen     : une ligne par (site, MAC) -- première / dernière vue, dernière IP, nom, fabricant,
                           dernier raccordement (équipement, port, SSID, VLAN), nombre de relèves où il était présent ;
- nebula_client_sessions : périodes de présence (début, fin) à raccordement constant (IP, équipement, port, SSID, VLAN) ;
                           une session est prolongée tant que le client est revu à moins de GAP_S de sa fin.
Peu de lignes (une session par changement), index par site / MAC / date, rétention RETENTION_DAYS : la leçon des
15 Go de la base des agents. Logique pure + SQLite ; les appels Nebula sont dans app.py.
"""
import re
import time

GAP_S = 3 * 3600          # trou toléré entre deux vues pour rester dans la même session (relève horaire + aléas)
RETENTION_DAYS = 400
SORTS = {"last_seen": "last_seen", "first_seen": "first_seen", "mac": "mac", "ip": "ip", "name": "name",
         "manufacturer": "manufacturer", "device": "device", "seen_count": "seen_count"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS nebula_client_seen (
    site_id TEXT NOT NULL, mac TEXT NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
    ip TEXT, name TEXT, manufacturer TEXT, os TEXT, device TEXT, device_id TEXT, port TEXT, ssid TEXT, vlan TEXT,
    sources TEXT, seen_count INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL,
    PRIMARY KEY (site_id, mac));
CREATE INDEX IF NOT EXISTS idx_ncs_last ON nebula_client_seen(site_id, last_seen);
CREATE TABLE IF NOT EXISTS nebula_client_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, mac TEXT NOT NULL, start INTEGER NOT NULL,
    end INTEGER NOT NULL, ip TEXT, device TEXT, port TEXT, ssid TEXT, vlan TEXT);
CREATE INDEX IF NOT EXISTS idx_ncsess_mac ON nebula_client_sessions(site_id, mac, end);
CREATE INDEX IF NOT EXISTS idx_ncsess_end ON nebula_client_sessions(end);
CREATE TABLE IF NOT EXISTS nebula_client_polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, site_id TEXT, clients INTEGER, sources TEXT,
    error TEXT, duration_ms INTEGER, trigger TEXT);
"""


def mac_norm(s):
    h = re.sub(r"[^0-9a-f]", "", str(s or "").lower())
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else None


def ts(v, default=None):
    """last_seen Nebula : ms, s ou ISO -> secondes."""
    if v in (None, ""):
        return default
    try:
        f = float(v)
        return int(f / 1000.0) if f > 1e11 else int(f)
    except (TypeError, ValueError):
        pass
    try:
        return int(time.mktime(time.strptime(str(v)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")) - time.timezone)
    except ValueError:
        return default


def _first(c, *keys):
    for k in keys:
        v = c.get(k)
        if v not in (None, "", []):
            return v if not isinstance(v, (int, float)) else str(v)
    return None


def merge(clients=None, ap_clients=None, sw_clients=None, device_names=None, now=None):
    """Trois listes Nebula -> {mac: fiche} ; le raccordement le plus précis gagne (commutateur : port ; borne : SSID)."""
    now = int(now or time.time())
    names = device_names or {}
    out = {}

    def fiche(c, source):
        m = mac_norm(c.get("mac_address") or c.get("macAddress") or c.get("mac"))
        if not m:
            return None
        f = out.setdefault(m, {"mac": m, "sources": set(), "last_seen": None})
        f["sources"].add(source)
        seen = ts(c.get("last_seen") or c.get("lastSeen"))
        if seen and seen <= now + 300 and (f["last_seen"] is None or seen > f["last_seen"]):
            f["last_seen"] = seen
        for k, keys in (("ip", ("ipv4", "ipv4Address", "ipv4_address", "ip")),
                        ("name", ("os_hostname", "osHostname", "description", "name", "hostname")),
                        ("manufacturer", ("manufacturer", "vendor")), ("os", ("os", "osType", "os_type"))):
            v = _first(c, *keys)
            if v and not f.get(k):
                f[k] = str(v)[:120]
        return f

    for c in clients or []:
        fiche(c, "clients")
    for c in ap_clients or []:
        f = fiche(c, "bornes")
        if f:
            dev = _first(c, "connected_device_id", "devId", "apId")
            f.update({k: v for k, v in (("device_id", dev), ("ssid", _first(c, "ssid", "ssidName")), ("vlan", _first(c, "vlan", "vlanId"))) if v})
            if dev:
                f["device"] = names.get(dev) or _first(c, "connected_device_name", "apName") or dev
    for c in sw_clients or []:
        f = fiche(c, "commutateurs")
        if f:
            dev = _first(c, "connected_device_id", "devId", "switchId")
            port = _first(c, "connected_port", "port", "portNum")
            if dev and port:   # port de commutateur : raccordement le plus précis (remplace la borne d'un client Wi-Fi vu des deux côtés seulement s'il n'a pas de SSID)
                if not f.get("ssid"):
                    f.update({"device_id": dev, "device": names.get(dev) or _first(c, "connected_device_name", "switchName") or dev, "port": str(port)})
                if _first(c, "vlan", "vlanId") and not f.get("vlan"):
                    f["vlan"] = _first(c, "vlan", "vlanId")
    for f in out.values():
        f["last_seen"] = f["last_seen"] or now
        f["sources"] = ",".join(sorted(f["sources"]))
    return out


def ingest(conn, site_id, fiches, now=None):
    """Fusionne une relève dans les deux tables -> nombre de clients. Transactions courtes (lot de 200)."""
    now = int(now or time.time())
    conn.executescript(SCHEMA)
    for i, f in enumerate(fiches.values(), 1):
        seen = min(f["last_seen"], now)
        row = conn.execute("SELECT first_seen, last_seen FROM nebula_client_seen WHERE site_id = ? AND mac = ?", (site_id, f["mac"])).fetchone()
        cols = ("ip", "name", "manufacturer", "os", "device", "device_id", "port", "ssid", "vlan", "sources")
        vals = [f.get(k) for k in cols]
        if row is None:
            conn.execute("INSERT INTO nebula_client_seen (site_id, mac, first_seen, last_seen, %s, seen_count, updated_at) VALUES (?, ?, ?, ?, %s, 1, ?)"
                         % (", ".join(cols), ", ".join("?" * len(cols))), [site_id, f["mac"], seen, seen] + vals + [now])
        else:
            # une valeur absente de cette relève ne remplace pas une valeur connue
            sets = ", ".join("%s = COALESCE(?, %s)" % (k, k) for k in cols)
            conn.execute("UPDATE nebula_client_seen SET last_seen = MAX(last_seen, ?), first_seen = MIN(first_seen, ?), %s, "
                         "seen_count = seen_count + 1, updated_at = ? WHERE site_id = ? AND mac = ?" % sets,
                         [seen, seen] + vals + [now, site_id, f["mac"]])
        key = [f.get(k) for k in ("ip", "device", "port", "ssid", "vlan")]
        s = conn.execute("SELECT id, end, ip, device, port, ssid, vlan FROM nebula_client_sessions WHERE site_id = ? AND mac = ? "
                         "ORDER BY end DESC LIMIT 1", (site_id, f["mac"])).fetchone()
        same = s is not None and all(a is None or a == b for a, b in zip(key, list(s)[2:]))
        if same and seen - s[1] <= GAP_S:
            conn.execute("UPDATE nebula_client_sessions SET end = MAX(end, ?), ip = COALESCE(ip, ?), device = COALESCE(device, ?), "
                         "port = COALESCE(port, ?), ssid = COALESCE(ssid, ?), vlan = COALESCE(vlan, ?) WHERE id = ?", [seen] + key + [s[0]])
        elif s is None or seen > s[1]:
            conn.execute("INSERT INTO nebula_client_sessions (site_id, mac, start, end, ip, device, port, ssid, vlan) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         [site_id, f["mac"], seen, seen] + key)
        if i % 200 == 0:
            conn.commit()
    conn.commit()
    return len(fiches)


def purge(conn, now=None, days=RETENTION_DAYS):
    now = int(now or time.time())
    conn.executescript(SCHEMA)
    lim = now - days * 86400
    n = conn.execute("DELETE FROM nebula_client_sessions WHERE end < ?", (lim,)).rowcount
    n += conn.execute("DELETE FROM nebula_client_seen WHERE last_seen < ?", (lim,)).rowcount
    conn.execute("DELETE FROM nebula_client_polls WHERE at < ?", (lim,))
    conn.commit()
    return n


def query(conn, site_id=None, q=None, manufacturer=None, since=None, until=None, absent_since=None, device=None,
          sort="last_seen", order="desc", limit=200, offset=0):
    """Recherche filtrée et triée. q : MAC (avec ou sans séparateurs), IP, nom, fabricant, équipement (début de mot
    d'abord : un résultat qui COMMENCE par q passe avant ceux qui le contiennent). since / until : vu dans l'intervalle
    (présence) ; absent_since : plus vu depuis cette date (les disparus, ex. passerelle muette depuis le 13/10)."""
    conn.executescript(SCHEMA)
    where, args = [], []
    if site_id:
        where.append("site_id = ?"); args.append(site_id)
    if manufacturer:
        where.append("LOWER(COALESCE(manufacturer, '')) LIKE ?"); args.append("%" + manufacturer.lower() + "%")
    if device:
        where.append("LOWER(COALESCE(device, '')) LIKE ?"); args.append("%" + device.lower() + "%")
    if since or until:   # présent dans l'intervalle : au moins une session qui le recoupe
        where.append("EXISTS (SELECT 1 FROM nebula_client_sessions s WHERE s.site_id = nebula_client_seen.site_id "
                     "AND s.mac = nebula_client_seen.mac AND s.end >= ? AND s.start <= ?)")
        args += [int(since or 0), int(until or 4102444800)]
    if absent_since:
        where.append("last_seen < ?"); args.append(int(absent_since))
    rank = None
    if q:
        s = q.strip().lower()
        hexq = re.sub(r"[^0-9a-f]", "", s)
        cond = ["LOWER(COALESCE(ip, '')) LIKE ?", "LOWER(COALESCE(name, '')) LIKE ?", "LOWER(COALESCE(manufacturer, '')) LIKE ?",
                "LOWER(COALESCE(device, '')) LIKE ?", "LOWER(COALESCE(ssid, '')) LIKE ?"]
        args_q = ["%" + s + "%"] * 5
        if len(hexq) >= 4:
            cond.append("REPLACE(mac, ':', '') LIKE ?"); args_q.append("%" + hexq + "%")
        else:
            cond.append("mac LIKE ?"); args_q.append("%" + s + "%")
        where.append("(" + " OR ".join(cond) + ")"); args += args_q
        rank = ("CASE WHEN LOWER(COALESCE(name, '')) LIKE ? OR LOWER(COALESCE(ip, '')) LIKE ? OR LOWER(COALESCE(manufacturer, '')) LIKE ? "
                "OR REPLACE(mac, ':', '') LIKE ? THEN 0 ELSE 1 END")
        rank_args = [s + "%", s + "%", s + "%", (hexq or s) + "%"]
    col = SORTS.get(sort, "last_seen")
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute("SELECT COUNT(*) FROM nebula_client_seen" + w, args).fetchone()[0]
    sql = ("SELECT site_id, mac, first_seen, last_seen, ip, name, manufacturer, os, device, port, ssid, vlan, sources, seen_count "
           "FROM nebula_client_seen%s ORDER BY %s%s COLLATE NOCASE %s, mac LIMIT ? OFFSET ?" % (w, (rank + ", ") if rank else "", col, direction))
    params = (rank_args if q else []) + args + [max(1, min(int(limit or 200), 2000)), max(0, int(offset or 0))]
    rows = [dict(zip(("site_id", "mac", "first_seen", "last_seen", "ip", "name", "manufacturer", "os", "device", "port", "ssid", "vlan",
                      "sources", "seen_count"), r)) for r in conn.execute(sql, params).fetchall()]
    return {"total": total, "rows": rows}


def sessions(conn, site_id, mac, limit=500):
    conn.executescript(SCHEMA)
    m = mac_norm(mac) or mac
    cur = conn.execute("SELECT start, end, ip, device, port, ssid, vlan FROM nebula_client_sessions WHERE site_id = ? AND mac = ? "
                       "ORDER BY end DESC LIMIT ?", (site_id, m, int(limit)))
    return [dict(zip(("start", "end", "ip", "device", "port", "ssid", "vlan"), r)) for r in cur.fetchall()]


def manufacturers(conn, site_id=None):
    conn.executescript(SCHEMA)
    sql = "SELECT manufacturer, COUNT(*) FROM nebula_client_seen WHERE manufacturer IS NOT NULL" + (" AND site_id = ?" if site_id else "") + \
          " GROUP BY manufacturer ORDER BY 2 DESC LIMIT 200"
    return [{"manufacturer": r[0], "n": r[1]} for r in conn.execute(sql, (site_id,) if site_id else ())]
