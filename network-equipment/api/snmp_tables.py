# -*- coding: utf-8 -*-
"""Décodage des tables SNMP relevées par snmp-api `/walk` (#506) --
logique PURE sur des lignes {oid, value} (texte prettyPrint de pysnmp) :
ENTITY-MIB (châssis), LLDP-MIB et CISCO-CDP-MIB (voisins), BRIDGE-MIB /
Q-BRIDGE-MIB (table des adresses MAC), colonnes génériques.

Formats d'entrée tolérés pour les octets binaires : « 0x4c5e0c112233 »
(prettyPrint d'un OctetString non imprimable), « 4c:5e:0c:11:22:33 »,
ou six entiers décimaux dans l'OID (index d'une table FDB).
"""
import re

ENTITY_PREFIX = "1.3.6.1.2.1.47.1.1.1.1"
LLDP_REM_PREFIX = "1.0.8802.1.1.2.1.4.1.1"
CDP_PREFIX = "1.3.6.1.4.1.9.9.23.1.2.1.1"
FDB_PREFIX = "1.3.6.1.2.1.17.4.3.1.2"
FDB_Q_PREFIX = "1.3.6.1.2.1.17.7.1.2.2.1.2"
BASEPORT_IFINDEX_PREFIX = "1.3.6.1.2.1.17.1.4.1.2"
IFNAME_PREFIX = "1.3.6.1.2.1.31.1.1.1.1"
IFDESCR_PREFIX = "1.3.6.1.2.1.2.2.1.2"

ENT_CLASS_CHASSIS = 3


def _suffix(oid, prefix):
    o = str(oid or "").lstrip(".")
    p = prefix.lstrip(".")
    if o == p:
        return ""
    if o.startswith(p + "."):
        return o[len(p) + 1:]
    return None


def by_column(rows, prefix):
    """{colonne: {index: valeur}} pour une table dont l'OID est
    prefix.<col>.<index…>."""
    out = {}
    for r in rows or []:
        s = _suffix(r.get("oid"), prefix)
        if not s:
            continue
        col, _, idx = s.partition(".")
        out.setdefault(col, {})[idx] = r.get("value")
    return out


def column(rows, prefix):
    """{index: valeur} pour une colonne scalaire prefix.<index>."""
    out = {}
    for r in rows or []:
        s = _suffix(r.get("oid"), prefix)
        if s:
            out[s] = r.get("value")
    return out


def hex_to_mac(value):
    """« 0x4c5e0c112233 » / « 4c:5e:0c:11:22:33 » / « 4c 5e 0c 11 22 33 » -> « 4C:5E:0C:11:22:33 » ; None sinon."""
    v = str(value or "").strip()
    if v.lower().startswith("0x"):
        v = v[2:]
    hexs = re.sub(r"[^0-9A-Fa-f]", "", v)
    if len(hexs) != 12 or re.search(r"[^0-9A-Fa-f: -]", str(value or "").strip().lstrip("0x").lstrip("0X")):
        return None
    return ":".join(hexs[i:i + 2].upper() for i in range(0, 12, 2))


def dotted_from_index(index_text):
    """« 76.94.12.17.34.51 » (6 octets décimaux) -> « 4C:5E:0C:11:22:33 »."""
    parts = str(index_text or "").split(".")
    if len(parts) != 6 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return None
    return ":".join("%02X" % int(p) for p in parts)


def hex_to_ipv4(value):
    """« 0xc0000201 » -> « 192.0.2.1 » (CDP cdpCacheAddress) ; texte déjà pointé rendu tel quel."""
    v = str(value or "").strip()
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", v):
        return v
    if v.lower().startswith("0x"):
        v = v[2:]
    hexs = re.sub(r"[^0-9A-Fa-f]", "", v)
    if len(hexs) == 8:
        return ".".join(str(int(hexs[i:i + 2], 16)) for i in range(0, 8, 2))
    return None


def _clean(text):
    if text is None:
        return None
    t = str(text).strip()
    if t.lower().startswith("0x"):
        # texte binaire : tenter le décodage ASCII imprimable
        try:
            raw = bytes.fromhex(t[2:])
            dec = raw.decode("utf-8", errors="replace")
            if dec.isprintable():
                return dec
        except ValueError:
            pass
    return t or None


def parse_entity(rows):
    """Châssis d'après ENTITY-MIB : l'entrée de classe chassis(3) sinon
    l'index 1 -> {model, serial, mfg, sw, hw, fw, descr, name}."""
    cols = by_column(rows, ENTITY_PREFIX)
    if not cols:
        return {}
    classes = cols.get("5", {})
    chassis = None
    for idx, cls in classes.items():
        try:
            if int(cls) == ENT_CLASS_CHASSIS:
                chassis = idx
                break
        except (TypeError, ValueError):
            continue
    if chassis is None:
        # premier index qui porte un modèle ou une série
        for idx in sorted(set(cols.get("13", {})) | set(cols.get("11", {})), key=lambda x: [int(p) if p.isdigit() else p for p in x.split(".")]):
            if _clean(cols.get("13", {}).get(idx)) or _clean(cols.get("11", {}).get(idx)):
                chassis = idx
                break
    if chassis is None:
        chassis = "1"
    get = lambda c: _clean(cols.get(c, {}).get(chassis))  # noqa: E731
    out = {"index": chassis, "descr": get("2"), "name": get("7"), "hw": get("8"), "fw": get("9"), "sw": get("10"),
           "serial": get("11"), "mfg": get("12"), "model": get("13")}
    return {k: v for k, v in out.items() if v}


def parse_lldp(rows, port_names=None):
    """Voisins LLDP : index <timemark>.<localport>.<remindex>."""
    cols = by_column(rows, LLDP_REM_PREFIX)
    keys = set()
    for c in ("5", "7", "8", "9", "10"):
        keys |= set(cols.get(c, {}).keys())
    out = []
    for k in sorted(keys):
        parts = k.split(".")
        local = parts[1] if len(parts) >= 2 else None
        chassis_raw = cols.get("5", {}).get(k)
        n = {"local_port": (port_names or {}).get(local, local), "local_port_index": local,
             "remote_chassis": hex_to_mac(chassis_raw) or _clean(chassis_raw),
             "remote_port": hex_to_mac(cols.get("7", {}).get(k)) or _clean(cols.get("7", {}).get(k)),
             "remote_port_descr": _clean(cols.get("8", {}).get(k)),
             "remote_name": _clean(cols.get("9", {}).get(k)), "remote_descr": _clean(cols.get("10", {}).get(k))}
        out.append(n)
    return out


def parse_cdp(rows, port_names=None):
    """Voisins CDP : index <ifIndex>.<cdpIndex>."""
    cols = by_column(rows, CDP_PREFIX)
    keys = set()
    for c in ("4", "6", "7", "8"):
        keys |= set(cols.get(c, {}).keys())
    out = []
    for k in sorted(keys):
        local = k.split(".")[0]
        out.append({"local_port": (port_names or {}).get(local, local), "local_port_index": local,
                    "remote_address": hex_to_ipv4(cols.get("4", {}).get(k)),
                    "remote_name": _clean(cols.get("6", {}).get(k)), "remote_port": _clean(cols.get("7", {}).get(k)),
                    "remote_platform": _clean(cols.get("8", {}).get(k)), "remote_descr": _clean(cols.get("8", {}).get(k))})
    return out


def parse_fdb(rows, baseport_ifindex=None, port_names=None, q_rows=None):
    """Table des MAC apprises : BRIDGE-MIB (index = 6 octets, valeur = port
    de pont) et/ou Q-BRIDGE-MIB (index = vlan.6 octets). Le port est
    traduit en nom d'interface quand la correspondance est fournie."""
    def port_label(bridge_port):
        p = str(bridge_port or "").strip()
        ifidx = (baseport_ifindex or {}).get(p)
        if ifidx and port_names and ifidx in port_names:
            return port_names[ifidx]
        if port_names and p in port_names and not baseport_ifindex:
            return port_names[p]
        return p or None

    out = {}
    for r in column(rows, FDB_PREFIX).items():
        mac = dotted_from_index(r[0])
        if mac:
            out[(mac, None)] = {"mac": mac, "port": port_label(r[1]), "bridge_port": str(r[1]), "vlan": None}
    for idx, port in column(q_rows, FDB_Q_PREFIX).items():
        vlan, _, rest = idx.partition(".")
        mac = dotted_from_index(rest)
        if mac:
            out[(mac, vlan)] = {"mac": mac, "port": port_label(port), "bridge_port": str(port), "vlan": vlan}
    return list(out.values())


def parse_scalar_column(rows, prefix, spec=None, decode=None):
    """Colonne d'un profil -> [{index, value}] (valeur décodée par
    `decode(spec, raw)` si fourni)."""
    out = []
    for idx, raw in column(rows, prefix).items():
        out.append({"index": idx, "value": decode(spec or {}, raw) if decode else raw})
    return out
