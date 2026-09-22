# -*- coding: utf-8 -*-
"""Carte des VLAN d'un site Nebula (livraison #548) -- logique PURE, testée
(nebula/tests/test_vlanmap.py). Reconstitue, à partir de l'OpenAPI :

- par VLAN : SSID qui y déposent leurs clients, sous-réseau de la passerelle,
  ports de chaque commutateur (PVID = non étiqueté, trunk = étiqueté),
  adresses MAC apprises, clients ;
- les LIAISONS entre commutateurs (LLDP) avec, de chaque côté, les VLAN
  portés -- et les VLAN manquants d'un côté (la cause des incidents de
  septembre 2026 : listes de VLAN incomplètes sur les uplinks) ;
- des anomalies en phrases.

Le tout tolérant aux champs absents : un appel qui échoue laisse un trou,
jamais une exception."""
import re


def parse_vlan_list(values):
    """`allowedVLAN` : ["1", "10", "20-25", "all"] ou "1,10,20-25" -> ensemble
    d'entiers ; "all" -> {"all"}."""
    if values is None:
        return set()
    if isinstance(values, (int, float)):
        return {int(values)}
    if isinstance(values, str):
        values = [v for v in re.split(r"[,\s]+", values) if v]
    out = set()
    for v in values:
        if isinstance(v, (int, float)):
            out.add(int(v)); continue
        t = str(v).strip().lower()
        if not t:
            continue
        if t == "all":
            out.add("all"); continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", t)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < b - a < 4096:
                out.update(range(a, b + 1))
            continue
        if t.isdigit():
            out.add(int(t))
    return out


def switch_vlans(port_settings):
    """[{portNum, enabled, trunk, portVid, allowedVLAN}] -> {vid: {"untagged": [ports], "tagged": [ports]}}
    et {port: {"pvid", "trunk", "allowed"}}."""
    by_vlan, by_port = {}, {}
    for p in port_settings or []:
        if not isinstance(p, dict):
            continue
        port = p.get("portNum")
        pvid = p.get("portVid")
        trunk = bool(p.get("trunk"))
        allowed = parse_vlan_list(p.get("allowedVLAN")) if trunk else set()
        by_port[port] = {"pvid": pvid, "trunk": trunk, "allowed": sorted(x for x in allowed if x != "all"), "all": "all" in allowed, "enabled": p.get("enabled", True)}
        if isinstance(pvid, int) and pvid > 0:
            by_vlan.setdefault(pvid, {"untagged": [], "tagged": []})["untagged"].append(port)
        for v in allowed:
            if v == "all" or v == pvid:
                continue
            by_vlan.setdefault(v, {"untagged": [], "tagged": []})["tagged"].append(port)
    return by_vlan, by_port


def port_carries(port_info, vid):
    """Un port porte-t-il le VLAN vid (étiqueté, non étiqueté ou « all ») ?"""
    if not port_info:
        return False
    return port_info.get("pvid") == vid or port_info.get("all") or vid in (port_info.get("allowed") or [])


def _norm_name(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _near_mac(mac, table):
    """MAC à ±8 (dernier octet) d'une MAC connue -> devId, sinon None."""
    if not mac or len(mac) != 12:
        return None
    try:
        base = int(mac, 16)
    except ValueError:
        return None
    for m, dev in table.items():
        try:
            if m[:6] == mac[:6] and abs(int(m, 16) - base) <= 8:
                return dev
        except ValueError:
            continue
    return None


def _name_in(sysname, table):
    """Nom LLDP contenu dans un nom d'inventaire ou l'inverse (>= 4 caractères)."""
    if not sysname or len(sysname) < 4:
        return None
    for name, dev in table.items():
        if name and (sysname in name or name in sysname):
            return dev
    return None


def _norm_mac(s):
    return re.sub(r"[^0-9a-f]", "", str(s or "").lower())


def links_from_lldp(switches, lldp_by_sw, ports_by_sw, others=None):
    """switches : {devId: {"name", "mac"}} ; lldp_by_sw : {devId: [{lldpRemLocalPortNum, lldpRemPortId, lldpRemSysName, lldpRemChassisId}]}.
    Retourne les liaisons entre DEUX commutateurs du site (dédoublonnées) avec
    les VLAN portés de chaque côté et les manquants."""
    by_name = {_norm_name(v.get("name")): k for k, v in switches.items() if v.get("name")}
    by_mac = {_norm_mac(v.get("mac")): k for k, v in switches.items() if v.get("mac")}
    # #555 : les autres appareils de l'inventaire (bornes, passerelle) sont
    # aussi reconnus -- par nom (insensible à la casse) ou par MAC (une borne
    # annonce en LLDP sa MAC de base, parfois à quelques unités de celle de
    # l'inventaire : tolérance ±8 sur le dernier octet).
    other_name = {_norm_name(v.get("name")): k for k, v in (others or {}).items() if v.get("name")}
    other_mac = {_norm_mac(v.get("mac")): k for k, v in (others or {}).items() if v.get("mac")}
    links, seen = [], set()
    for dev, neighbors in (lldp_by_sw or {}).items():
        for n in neighbors or []:
            if not isinstance(n, dict):
                continue
            other = by_name.get(_norm_name(n.get("lldpRemSysName"))) or by_mac.get(_norm_mac(n.get("lldpRemChassisId")))
            local_port = _port_num(n.get("lldpRemLocalPortNum"))
            remote_port = _port_num(n.get("lldpRemPortId")) or _port_num(n.get("lldpRemPortDesc"))
            if (not other or other == dev) and others:
                sysname = _norm_name(n.get("lldpRemSysName"))
                chassis = _norm_mac(n.get("lldpRemChassisId"))
                dev2 = other_name.get(sysname) or other_mac.get(chassis) or _near_mac(chassis, other_mac) or _name_in(sysname, other_name)
                if dev2:
                    pa = (ports_by_sw.get(dev) or {}).get(local_port) or {}
                    va = _carried(pa)
                    key = (dev, local_port, dev2)
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append({"a": dev, "a_port": local_port, "b": dev2, "b_port": remote_port, "external": False, "device": True,
                                  "b_kind": str((others.get(dev2) or {}).get("type") or "").upper(),
                                  "a_vlans": sorted(va) if va != "all" else "all", "b_vlans": None, "missing_on_a": [], "missing_on_b": []})
                    continue
            if not other or other == dev:
                links.append({"a": dev, "a_port": local_port, "b": None, "b_name": n.get("lldpRemSysName") or n.get("lldpRemChassisId"), "b_port": remote_port, "external": True,
                              "chassis": n.get("lldpRemChassisId"), "sysname": n.get("lldpRemSysName")})
                continue
            key = tuple(sorted([(dev, local_port), (other, remote_port)]))
            if key in seen:
                continue
            seen.add(key)
            pa = (ports_by_sw.get(dev) or {}).get(local_port) or {}
            pb = (ports_by_sw.get(other) or {}).get(remote_port) or {}
            va = _carried(pa); vb = _carried(pb)
            links.append({"a": dev, "a_port": local_port, "b": other, "b_port": remote_port, "external": False,
                          "a_vlans": sorted(va) if va != "all" else "all", "b_vlans": sorted(vb) if vb != "all" else "all",
                          "missing_on_a": sorted(vb - va) if isinstance(va, set) and isinstance(vb, set) else [],
                          "missing_on_b": sorted(va - vb) if isinstance(va, set) and isinstance(vb, set) else []})
    return links


def _carried(p):
    if not p:
        return set()
    if p.get("all"):
        return "all"
    out = set(p.get("allowed") or [])
    if isinstance(p.get("pvid"), int) and p["pvid"] > 0:
        out.add(p["pvid"])
    return out


def _port_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"(\d+)\s*$", str(v))
    return int(m.group(1)) if m else str(v)


def gateway_networks(interface_settings):
    """{"wan": [...], "lan": [{interface, ipv4Address, ipv4Netmask, guestZone, vlan?}], "vlan"?: [...]} -> {vid: {subnet, name, guest}}
    Le VLAN d'une interface se lit dans `vlan` / `vlanId` / `vid` s'il existe,
    sinon dans son nom (« vlan10 », « lan2 » sans VLAN). Tolère une liste
    plate et des sections `vlan` / `lan` / `bridge`."""
    out = {}
    if isinstance(interface_settings, list):
        ifaces = interface_settings
    else:
        ifaces = []
        for key in ("lan", "vlan", "bridge", "lan2", "dmz"):
            v = (interface_settings or {}).get(key)
            if isinstance(v, list):
                ifaces.extend(v)
    for iface in ifaces:
        if not isinstance(iface, dict):
            continue
        vid = None
        for k in ("vlan", "vlanId", "vlan_id", "vid"):
            if isinstance(iface.get(k), int):
                vid = iface[k]; break
            if isinstance(iface.get(k), str) and iface[k].isdigit():
                vid = int(iface[k]); break
        if vid is None:
            m = re.search(r"vlan\s*(\d+)", str(iface.get("interface") or iface.get("name") or iface.get("id") or ""), re.I)
            vid = int(m.group(1)) if m else None
        if vid is None:
            continue
        out[vid] = {"subnet": _cidr(iface.get("ipv4Address") or iface.get("ip"), iface.get("ipv4Netmask") or iface.get("netmask")), "name": iface.get("interface") or iface.get("name") or iface.get("id"), "guest": bool(iface.get("guestZone"))}
    return out


def _cidr(ip, mask):
    if not ip:
        return None
    if not mask:
        return str(ip)
    try:
        bits = sum(bin(int(x)).count("1") for x in str(mask).split("."))
        return "%s/%d" % (ip, bits)
    except ValueError:
        return "%s/%s" % (ip, mask)


def build_vlan_map(devices, port_settings_by_sw, lldp_by_sw=None, gw_interfaces=None, wlans=None, ip_status_by_sw=None, mac_tables_by_sw=None, sw_clients=None):
    """devices : inventaire du site [{devId, name, model, type, mac}]. Les autres
    paramètres sont les réponses brutes de l'OpenAPI par commutateur."""
    switches = {d["devId"]: {"name": d.get("name") or d["devId"], "model": d.get("model"), "mac": d.get("mac")}
                for d in devices or [] if isinstance(d, dict) and d.get("devId") and str(d.get("type") or "").upper() in ("SW", "SWITCH")}
    ports_by_sw, vlans = {}, {}
    for dev, ps in (port_settings_by_sw or {}).items():
        by_vlan, by_port = switch_vlans(ps)
        ports_by_sw[dev] = by_port
        for vid, pp in by_vlan.items():
            v = vlans.setdefault(vid, {"vid": vid, "ssids": [], "subnet": None, "gateway_interface": None, "guest": False, "switches": {}, "mac_count": 0, "clients": 0, "management": []})
            v["switches"][switches.get(dev, {}).get("name", dev)] = pp
    for w in wlans or []:
        if isinstance(w, dict) and isinstance(w.get("vlan"), int):
            v = vlans.setdefault(w["vlan"], {"vid": w["vlan"], "ssids": [], "subnet": None, "gateway_interface": None, "guest": False, "switches": {}, "mac_count": 0, "clients": 0, "management": []})
            v["ssids"].append({"name": w.get("name"), "enabled": w.get("enabled", True), "guest": bool(w.get("guestNetwork"))})
    for vid, net in gateway_networks(gw_interfaces).items():
        v = vlans.setdefault(vid, {"vid": vid, "ssids": [], "subnet": None, "gateway_interface": None, "guest": False, "switches": {}, "mac_count": 0, "clients": 0, "management": []})
        v["subnet"], v["gateway_interface"], v["guest"] = net["subnet"], net["name"], net["guest"]
    for dev, rows in (ip_status_by_sw or {}).items():
        for r in rows or []:
            if isinstance(r, dict) and isinstance(r.get("vlan"), int) and r["vlan"] in vlans:
                vlans[r["vlan"]]["management"].append(switches.get(dev, {}).get("name", dev))
    for dev, rows in (mac_tables_by_sw or {}).items():
        for r in rows or []:
            if isinstance(r, dict) and isinstance(r.get("vlan"), int):
                vlans.setdefault(r["vlan"], {"vid": r["vlan"], "ssids": [], "subnet": None, "gateway_interface": None, "guest": False, "switches": {}, "mac_count": 0, "clients": 0, "management": []})["mac_count"] += 1
    prefixes = {}
    for c in (sw_clients or {}).get("data", sw_clients) if isinstance(sw_clients, (dict, list)) else []:
        if isinstance(c, dict) and isinstance(c.get("vlan"), int) and c["vlan"] in vlans:
            vlans[c["vlan"]]["clients"] += 1
            ip = str(c.get("ipv4Address") or "")
            m = re.match(r"^(\d+\.\d+\.\d+)\.\d+$", ip)
            if m:
                prefixes.setdefault(c["vlan"], {}).setdefault(m.group(1), 0)
                prefixes[c["vlan"]][m.group(1)] += 1
    # Sous-réseau déduit des clients quand la passerelle ne donne pas
    # d'adresse (l'OpenAPI renvoie des adresses vides sur l'USG FLEX en réel) :
    # le /24 le plus fréquent, marqué comme déduit.
    for vid, counts in prefixes.items():
        if vlans[vid]["subnet"] is None and counts:
            best = max(counts.items(), key=lambda kv: kv[1])
            vlans[vid]["subnet"] = "%s.0/24" % best[0]
            vlans[vid]["subnet_inferred"] = True
    others = {d["devId"]: {"name": d.get("name") or d["devId"], "model": d.get("model"), "mac": d.get("mac"), "type": d.get("type")}
              for d in devices or [] if isinstance(d, dict) and d.get("devId") and d["devId"] not in switches}
    links = links_from_lldp(switches, lldp_by_sw, ports_by_sw, others)
    anomalies = []
    for l in links:
        if l.get("external") or l.get("device"):
            continue
        a, b = switches.get(l["a"], {}).get("name", l["a"]), switches.get(l["b"], {}).get("name", l["b"])
        if l["missing_on_a"]:
            anomalies.append("Liaison %s port %s ↔ %s port %s : VLAN %s portés côté %s mais absents côté %s." % (a, l["a_port"], b, l["b_port"], ", ".join(map(str, l["missing_on_a"])), b, a))
        if l["missing_on_b"]:
            anomalies.append("Liaison %s port %s ↔ %s port %s : VLAN %s portés côté %s mais absents côté %s." % (a, l["a_port"], b, l["b_port"], ", ".join(map(str, l["missing_on_b"])), a, b))
    for vid, v in sorted(vlans.items()):
        if v["ssids"] and not v["switches"]:
            anomalies.append("VLAN %d : utilisé par le SSID %s mais présent sur aucun port de commutateur." % (vid, ", ".join(s["name"] or "?" for s in v["ssids"])))
        if v["switches"] and v["gateway_interface"] is None and vid != 1:
            anomalies.append("VLAN %d : présent sur les commutateurs sans interface de passerelle connue (routage ailleurs, ou VLAN de couche 2 seule)." % vid)
        if v["ssids"] or v["subnet"]:
            for name in switches.values():
                pass
    for l in links:
        if l.get("external") or l.get("device"):
            continue
        pa = (ports_by_sw.get(l["a"]) or {}).get(l["a_port"]); pb = (ports_by_sw.get(l["b"]) or {}).get(l["b_port"])
        a, b = switches.get(l["a"], {}).get("name", l["a"]), switches.get(l["b"], {}).get("name", l["b"])
        # Liaison sans aucun VLAN des deux côtés : membre d'un agrégat (LACP,
        # les VLAN sont sur l'agrégat) ou lien de secours -- signalé, pas une
        # anomalie par VLAN (constaté en réel : deux liens par commutateur d'accès).
        if _carried(pa) in (set(), "all") and _carried(pb) in (set(), "all") and not (_carried(pa) == "all" or _carried(pb) == "all"):
            l["bare"] = True
            anomalies.append("Liaison %s port %s ↔ %s port %s : aucun VLAN déclaré de part et d'autre (membre d'un agrégat LACP, ou lien inutilisé)." % (a, l["a_port"], b, l["b_port"]))
            continue
        for vid, v in vlans.items():
            if v["ssids"] and not port_carries(pa, vid) and not port_carries(pb, vid):
                anomalies.append("VLAN %d (SSID %s) n'est pas porté par la liaison %s port %s ↔ %s port %s." % (vid, ", ".join(s["name"] or "?" for s in v["ssids"]), a, l["a_port"], b, l["b_port"]))
    for l in links:
        l["a_name"] = switches.get(l["a"], {}).get("name", l["a"])
        if l.get("b"):
            l["b_name"] = switches.get(l["b"], {}).get("name") or others.get(l["b"], {}).get("name") or l["b"]
    return {"vlans": [vlans[k] for k in sorted(vlans)], "links": links, "switches": [dict(v, devId=k) for k, v in switches.items()], "anomalies": sorted(set(anomalies))}


def to_csv_rows(vmap):
    """Export plat : une ligne par (VLAN, commutateur) + une par VLAN sans port."""
    rows = [["vlan", "sous_reseau", "interface_passerelle", "ssid", "commutateur", "ports_non_etiquetes", "ports_etiquetes", "mac_apprises", "clients", "gestion"]]
    for v in vmap.get("vlans") or []:
        ssids = " | ".join(s.get("name") or "?" for s in v["ssids"])
        if not v["switches"]:
            rows.append([v["vid"], v["subnet"] or "", v["gateway_interface"] or "", ssids, "", "", "", v["mac_count"], v["clients"], " | ".join(v["management"])])
        for sw, pp in sorted(v["switches"].items()):
            rows.append([v["vid"], v["subnet"] or "", v["gateway_interface"] or "", ssids, sw, " ".join(map(str, pp["untagged"])), " ".join(map(str, pp["tagged"])), v["mac_count"], v["clients"], " | ".join(v["management"])])
    return rows
