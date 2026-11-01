# -*- coding: utf-8 -*-
"""Inventaire des équipements réseau (#506) -- SQLite dans /data.

Une fiche par équipement, rapprochée entre les sources par MAC
(normalisée) d'abord, IP ensuite, nom enfin. Les champs « identifiés »
(vendor, model, kind, generation…) sont TOUJOURS recalculés par
`identify.merge` à partir des preuves stockées (colonnes sys_*, entity,
zenoss, oui, role_hint, ports, manual) -- jamais édités directement :
une nouvelle preuve ré-identifie, un choix manuel a le dernier mot.

Aucun secret ici : la communauté SNMP vit dans snmp-api (cible
enregistrée, `snmp_target_id`) ou dans le coffre des accès
(`snmp_credential` = nom d'un accès de genre « snmp »), jamais dans
cette base.
"""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    ip TEXT,
    mac TEXT,
    hostname TEXT,
    site TEXT,
    -- preuves
    oui_vendor TEXT, oui_category TEXT,
    sys_descr TEXT, sys_object_id TEXT, sys_name TEXT, sys_location TEXT, sys_contact TEXT,
    entity_json TEXT,
    zenoss_json TEXT, zenoss_class TEXT,
    role_hint TEXT, ports_json TEXT,
    manual_json TEXT,
    -- identification calculée
    vendor TEXT, model TEXT, os TEXT, os_version TEXT, serial TEXT, kind TEXT, generation TEXT, generation_reason TEXT,
    confidence REAL, sources_json TEXT, notes_json TEXT,
    -- supervision
    profile_id TEXT, snmp_target_id INTEGER, snmp_credential TEXT, snmp_port INTEGER,
    last_identified_at TEXT, last_identify_error TEXT,
    last_poll_json TEXT, last_poll_at TEXT, last_poll_error TEXT,
    network_agent_device_id INTEGER,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_equipment_mac ON equipment(mac);
CREATE INDEX IF NOT EXISTS idx_equipment_ip ON equipment(ip);

CREATE TABLE IF NOT EXISTS neighbors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    protocol TEXT NOT NULL,          -- lldp | cdp
    local_port TEXT,
    remote_name TEXT, remote_port TEXT, remote_chassis TEXT, remote_descr TEXT, remote_address TEXT, remote_platform TEXT,
    remote_equipment_id INTEGER,
    seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_neighbors_eq ON neighbors(equipment_id);

CREATE TABLE IF NOT EXISTS fdb (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    mac TEXT NOT NULL,
    port TEXT,
    vlan TEXT,
    seen_at TEXT NOT NULL,
    UNIQUE(equipment_id, mac, vlan)
);
CREATE INDEX IF NOT EXISTS idx_fdb_mac ON fdb(mac);

CREATE TABLE IF NOT EXISTS identifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    at TEXT NOT NULL,
    source TEXT NOT NULL,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    source TEXT NOT NULL,
    file_name TEXT,
    counts_json TEXT
);
"""

JSON_COLS = ("entity_json", "zenoss_json", "ports_json", "manual_json", "sources_json", "notes_json", "last_poll_json")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def connect(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(db_path):
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for col in JSON_COLS:
        if col in d:
            raw = d.pop(col)
            key = col[:-5]
            try:
                d[key] = json.loads(raw) if raw else None
            except (TypeError, ValueError):
                d[key] = None
    for k in ("ports", "sources", "notes"):
        if d.get(k) is None:
            d[k] = []
    return d


def find(conn, mac=None, ip=None, name=None):
    """Rapprochement : MAC, puis IP, puis nom (insensible à la casse)."""
    if mac:
        r = conn.execute("SELECT * FROM equipment WHERE mac = ?", (mac,)).fetchone()
        if r:
            return r
    if ip:
        r = conn.execute("SELECT * FROM equipment WHERE ip = ? ORDER BY id LIMIT 1", (ip,)).fetchone()
        if r:
            return r
    if name:
        r = conn.execute("SELECT * FROM equipment WHERE lower(name) = lower(?) OR lower(hostname) = lower(?) ORDER BY id LIMIT 1", (name, name)).fetchone()
        if r:
            return r
    return None


def upsert(conn, fields, mac=None, ip=None, name=None):
    """Crée ou met à jour (les valeurs None de `fields` ne remplacent
    jamais une valeur existante). Retourne (id, created)."""
    row = find(conn, mac=mac, ip=ip, name=name)
    now = now_iso()
    clean = {}
    for k, v in fields.items():
        if k.endswith("_json") and not isinstance(v, (str, type(None))):
            v = json.dumps(v, ensure_ascii=False)
        clean[k] = v
    if row is None:
        clean.setdefault("mac", mac)
        clean.setdefault("ip", ip)
        clean.setdefault("name", name)
        clean["created_at"] = now
        clean["updated_at"] = now
        cols = ", ".join(clean.keys())
        marks = ", ".join("?" for _ in clean)
        cur = conn.execute("INSERT INTO equipment (%s) VALUES (%s)" % (cols, marks), list(clean.values()))
        return cur.lastrowid, True
    sets, vals = [], []
    for k, v in clean.items():
        if v is None:
            continue
        sets.append("%s = ?" % k)
        vals.append(v)
    if mac and not row["mac"]:
        sets.append("mac = ?"); vals.append(mac)
    if ip and not row["ip"]:
        sets.append("ip = ?"); vals.append(ip)
    if name and not row["name"]:
        sets.append("name = ?"); vals.append(name)
    sets.append("updated_at = ?"); vals.append(now)
    vals.append(row["id"])
    conn.execute("UPDATE equipment SET %s WHERE id = ?" % ", ".join(sets), vals)
    return row["id"], False


def get(conn, equipment_id):
    return row_to_dict(conn.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,)).fetchone())


def list_equipment(conn, kind=None, vendor=None, generation=None, q=None, site=None, limit=2000):
    clauses, params = [], []
    if kind:
        clauses.append("kind = ?"); params.append(kind)
    if vendor:
        clauses.append("lower(vendor) LIKE ?"); params.append("%" + vendor.lower() + "%")
    if generation:
        clauses.append("generation = ?"); params.append(generation)
    if site:
        clauses.append("site = ?"); params.append(site)
    if q:
        like = "%" + q.lower() + "%"
        clauses.append("(lower(coalesce(name,'')) LIKE ? OR lower(coalesce(ip,'')) LIKE ? OR lower(coalesce(mac,'')) LIKE ? OR lower(coalesce(model,'')) LIKE ? OR lower(coalesce(hostname,'')) LIKE ? OR lower(coalesce(sys_name,'')) LIKE ?)")
        params.extend([like] * 6)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute("SELECT * FROM equipment%s ORDER BY CASE kind WHEN 'routeur' THEN 0 WHEN 'pare-feu' THEN 1 WHEN 'switch' THEN 2 WHEN 'équipement réseau' THEN 3 WHEN 'point d''accès' THEN 4 ELSE 9 END, coalesce(vendor,'~'), coalesce(name, ip, mac) LIMIT ?" % where,
                        params + [int(limit)]).fetchall()
    return [row_to_dict(r) for r in rows]


def set_identification(conn, equipment_id, ident, source, extra=None):
    """Écrit le résultat de identify.merge + journalise."""
    fields = {
        "vendor": ident.get("vendor"), "model": ident.get("model"), "os": ident.get("os"), "os_version": ident.get("os_version"),
        "serial": ident.get("serial"), "kind": ident.get("kind"), "generation": ident.get("generation"),
        "generation_reason": ident.get("generation_reason"), "confidence": ident.get("confidence"),
        "sources_json": json.dumps(ident.get("sources") or [], ensure_ascii=False),
        "notes_json": json.dumps(ident.get("notes") or [], ensure_ascii=False),
        "updated_at": now_iso(),
    }
    if extra:
        fields.update(extra)
    sets = ", ".join("%s = ?" % k for k in fields)
    conn.execute("UPDATE equipment SET %s WHERE id = ?" % sets, list(fields.values()) + [equipment_id])
    conn.execute("INSERT INTO identifications (equipment_id, at, source, result_json) VALUES (?, ?, ?, ?)",
                 (equipment_id, now_iso(), source, json.dumps(ident, ensure_ascii=False)))


def replace_neighbors(conn, equipment_id, protocol, rows):
    conn.execute("DELETE FROM neighbors WHERE equipment_id = ? AND protocol = ?", (equipment_id, protocol))
    now = now_iso()
    for n in rows:
        remote_id = None
        if n.get("remote_chassis"):
            r = conn.execute("SELECT id FROM equipment WHERE mac = ?", (n["remote_chassis"],)).fetchone()
            remote_id = r["id"] if r else None
        if remote_id is None and n.get("remote_name"):
            r = conn.execute("SELECT id FROM equipment WHERE lower(name) = lower(?) OR lower(sys_name) = lower(?) OR lower(hostname) = lower(?) LIMIT 1",
                             (n["remote_name"], n["remote_name"], n["remote_name"])).fetchone()
            remote_id = r["id"] if r else None
        if remote_id is None and n.get("remote_address"):
            r = conn.execute("SELECT id FROM equipment WHERE ip = ? LIMIT 1", (n["remote_address"],)).fetchone()
            remote_id = r["id"] if r else None
        conn.execute("INSERT INTO neighbors (equipment_id, protocol, local_port, remote_name, remote_port, remote_chassis, remote_descr, remote_address, remote_platform, remote_equipment_id, seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (equipment_id, protocol, n.get("local_port"), n.get("remote_name"), n.get("remote_port"), n.get("remote_chassis"),
                      n.get("remote_descr"), n.get("remote_address"), n.get("remote_platform"), remote_id, now))


def replace_fdb(conn, equipment_id, entries):
    conn.execute("DELETE FROM fdb WHERE equipment_id = ?", (equipment_id,))
    now = now_iso()
    for e in entries:
        conn.execute("INSERT OR REPLACE INTO fdb (equipment_id, mac, port, vlan, seen_at) VALUES (?, ?, ?, ?, ?)",
                     (equipment_id, e["mac"], e.get("port"), e.get("vlan"), now))


def neighbors_of(conn, equipment_id=None):
    if equipment_id:
        rows = conn.execute("SELECT * FROM neighbors WHERE equipment_id = ? ORDER BY protocol, local_port", (equipment_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM neighbors ORDER BY equipment_id, protocol, local_port").fetchall()
    return [dict(r) for r in rows]


def fdb_of(conn, equipment_id):
    return [dict(r) for r in conn.execute("SELECT * FROM fdb WHERE equipment_id = ? ORDER BY port, mac", (equipment_id,)).fetchall()]


def where_is_mac(conn, mac):
    """Sur quel(s) switch(s)/port(s) cette MAC est apprise -- en excluant
    les ports d'uplink (ceux qui voient beaucoup de MAC)."""
    rows = conn.execute("SELECT f.equipment_id, f.port, f.vlan, e.name, e.ip, (SELECT COUNT(*) FROM fdb g WHERE g.equipment_id = f.equipment_id AND g.port = f.port) AS port_macs FROM fdb f JOIN equipment e ON e.id = f.equipment_id WHERE f.mac = ? ORDER BY port_macs ASC", (mac,)).fetchall()
    return [dict(r) for r in rows]


def topology(conn):
    """Liens entre équipements connus : voisins LLDP/CDP rapprochés, et
    ports de switch n'apprenant qu'UNE MAC connue (lien d'accès)."""
    links = []
    # un lien par paire d'équipements : LLDP prime sur CDP quand les deux
    # voient le même voisin (même port), et un lien vu des deux côtés
    # n'est compté qu'une fois
    pairs = {}
    for n in conn.execute("SELECT * FROM neighbors WHERE remote_equipment_id IS NOT NULL ORDER BY CASE protocol WHEN 'lldp' THEN 0 ELSE 1 END").fetchall():
        key = tuple(sorted((n["equipment_id"], n["remote_equipment_id"])))
        if key in pairs:
            continue
        pairs[key] = True
        links.append({"from": n["equipment_id"], "to": n["remote_equipment_id"], "protocol": n["protocol"],
                      "local_port": n["local_port"], "remote_port": n["remote_port"]})
    rows = conn.execute("""SELECT f.equipment_id AS sw, f.port, e.id AS dev FROM fdb f JOIN equipment e ON e.mac = f.mac
                           WHERE e.id != f.equipment_id AND (SELECT COUNT(*) FROM fdb g WHERE g.equipment_id = f.equipment_id AND g.port = f.port) <= 2""").fetchall()
    seen = set((l["from"], l["to"]) for l in links) | set((l["to"], l["from"]) for l in links)
    for r in rows:
        key = (r["sw"], r["dev"])
        if key in seen:
            continue
        seen.add(key); seen.add((r["dev"], r["sw"]))
        links.append({"from": r["sw"], "to": r["dev"], "protocol": "fdb", "local_port": r["port"], "remote_port": None})
    return links


def record_import(conn, source, file_name, counts):
    conn.execute("INSERT INTO imports (at, source, file_name, counts_json) VALUES (?, ?, ?, ?)",
                 (now_iso(), source, file_name, json.dumps(counts, ensure_ascii=False)))


def status(conn):
    out = {"equipment": conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0], "by_kind": {}, "by_vendor": {}, "by_generation": {},
           "neighbors": conn.execute("SELECT COUNT(*) FROM neighbors").fetchone()[0], "fdb": conn.execute("SELECT COUNT(*) FROM fdb").fetchone()[0],
           "identified": conn.execute("SELECT COUNT(*) FROM equipment WHERE last_identified_at IS NOT NULL").fetchone()[0]}
    for r in conn.execute("SELECT coalesce(kind,'inconnu') k, COUNT(*) n FROM equipment GROUP BY k"):
        out["by_kind"][r["k"]] = r["n"]
    for r in conn.execute("SELECT coalesce(vendor,'?') v, COUNT(*) n FROM equipment GROUP BY v ORDER BY n DESC LIMIT 30"):
        out["by_vendor"][r["v"]] = r["n"]
    for r in conn.execute("SELECT coalesce(generation,'?') g, COUNT(*) n FROM equipment GROUP BY g"):
        out["by_generation"][r["g"]] = r["n"]
    last = conn.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 5").fetchall()
    out["imports"] = [dict(r) | {"counts": json.loads(r["counts_json"] or "{}")} for r in last]
    for i in out["imports"]:
        i.pop("counts_json", None)
    return out


def delete(conn, equipment_id):
    cur = conn.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
    return cur.rowcount > 0
