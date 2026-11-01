"""Topologie du site façon Nebula (livraison #555) -- logique pure, testée
dans nebula/tests/test_topology.py.

Un ARBRE : la passerelle en racine, sous elle le commutateur de cœur, puis
les commutateurs d'accès et les bornes, et sous chaque borne ou commutateur
ses CLIENTS (postes, téléphones…). Les liaisons viennent de la carte des
VLAN (#548/#555 : voisins LLDP reconnus parmi tous les appareils de
l'inventaire) ; les clients de l'OpenAPI (`/v2/nebula/{site}/clients`) sont
rattachés à l'appareil qui les sert par les champs que Zyxel publie
(`connectedTo`, `apName`, MAC de borne…) -- lecture tolérante, le nom exact
du champ n'étant pas documenté : tout champ dont la valeur désigne un
appareil connu fait l'affaire. Les clients sans rattachement sont listés à
part, jamais perdus.
"""
import re

GATEWAY_TYPES = ("GW", "GWH", "FIREWALL", "GATEWAY", "USG")
KIND_ORDER = {"gateway": 0, "switch": 1, "ap": 2, "other": 3}


def kind_of(dev_type):
    t = str(dev_type or "").upper()
    if t in GATEWAY_TYPES:
        return "gateway"
    if t in ("SW", "SWITCH"):
        return "switch"
    if t == "AP":
        return "ap"
    return "other"


def _norm_mac(s):
    return re.sub(r"[^0-9a-f]", "", str(s or "").lower())


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


# Champs candidats d'un client pour retrouver son appareil d'attache
_DEVICE_FIELDS = ("connectedTo", "connected_to", "apName", "ap_name", "deviceName", "device_name", "devName", "nebulaDeviceName",
                  "apMac", "ap_mac", "deviceMac", "device_mac", "devMac", "nebulaDeviceMac", "bssid", "switchMac", "swMac", "devId", "deviceId")
_PORT_FIELDS = ("port", "portNum", "switchPort", "sw_port", "portId")
_NAME_FIELDS = ("description", "osHostname", "os_hostname", "hostname", "name", "deviceType", "manufacturer")


def _client_name(c):
    """Nom lisible : hostname (osHostname est un objet {os, hostname} en
    réel), description si ce n'est pas la MAC répétée, fabricant, sinon MAC."""
    mac = c.get("macAddress") or c.get("mac_address") or c.get("mac") or "?"
    oh = c.get("osHostname") or c.get("os_hostname")
    if isinstance(oh, dict):
        oh = oh.get("hostname")
    for v in (oh, c.get("hostname"), c.get("name"), c.get("description")):
        if v and str(v).strip() not in ("", "-") and _norm_mac(v) != _norm_mac(mac):
            return str(v).strip()
    if c.get("manufacturer"):
        return "%s (%s)" % (c["manufacturer"], str(mac)[-8:])
    return str(mac)


def attach_clients(clients, devices):
    """clients : liste brute de l'OpenAPI ; devices : inventaire [{devId, name, mac, type}].
    Retourne (par_appareil {devId: [client]}, non_rattachés [client], champs_vus [str])."""
    by_name = {_norm(d.get("name")): d["devId"] for d in devices if d.get("devId") and d.get("name")}
    by_mac = {_norm_mac(d.get("mac")): d["devId"] for d in devices if d.get("devId") and d.get("mac")}
    by_id = {d["devId"]: d["devId"] for d in devices if d.get("devId")}
    attached, loose, fields = {}, [], set()
    for c in clients or []:
        if not isinstance(c, dict):
            continue
        fields.update(c.keys())
        dev = None
        for f in _DEVICE_FIELDS:
            v = c.get(f)
            if not v:
                continue
            sv = str(v)
            dev = by_id.get(sv) or by_name.get(_norm(sv)) or by_mac.get(_norm_mac(sv))
            if not dev and len(_norm_mac(sv)) == 12:  # BSSID d'une borne : même préfixe, dernier octet proche
                m = _norm_mac(sv)
                near = [(abs(int(dm, 16) - int(m, 16)), did) for dm, did in by_mac.items() if dm[:6] == m[:6] and len(dm) == 12]
                near = [t for t in near if t[0] <= 32]
                if near:
                    dev = min(near)[1]  # la borne la plus proche
            if dev:
                break
        rec = {
            "mac": c.get("macAddress") or c.get("mac_address") or c.get("mac"),
            "name": _client_name(c),
            "ip": c.get("ipv4Address") or c.get("ipv4") or c.get("ip"),
            "ssid": c.get("ssid") or c.get("ssidName") or c.get("ssid_name"),
            "vlan": c.get("vlan"),
            "status": _norm(c.get("status")) or "inconnu",
            "band": c.get("band"),
            "signal": c.get("signalStrength") or c.get("signal_strength") or c.get("rssi"),
            "last_seen": c.get("lastSeen") or c.get("last_seen"),
            "manufacturer": c.get("manufacturer"),
            "port": next((c.get(f) for f in _PORT_FIELDS if c.get(f) is not None), None),
            "os": (c.get("osHostname") or {}).get("os") if isinstance(c.get("osHostname"), dict) else c.get("os"),
        }
        if dev:
            attached.setdefault(dev, []).append(rec)
        else:
            loose.append(rec)
    return attached, loose, sorted(fields)


def build_tree(devices, links, clients=None, statuses=None):
    """devices : inventaire ; links : `links` de la carte des VLAN ; clients :
    liste brute OpenAPI ; statuses : {name: "online"|"offline"|...}.
    Retourne {"nodes": [...], "unmatched": [voisins LLDP inconnus], "loose_clients": [...],
    "client_fields": [...]}. Chaque nœud : id, name, model, kind, status, parent,
    uplink_port (côté enfant), parent_port (côté parent), depth, clients."""
    statuses = statuses or {}
    nodes = {}
    for d in devices or []:
        if not isinstance(d, dict) or not d.get("devId"):
            continue
        nodes[d["devId"]] = {"id": d["devId"], "name": d.get("name") or d["devId"], "model": d.get("model") or "", "mac": d.get("mac"),
                             "kind": kind_of(d.get("type")), "status": statuses.get(d.get("name")) or "inconnu",
                             "parent": None, "uplink_port": None, "parent_port": None, "depth": 0, "clients": [], "link": None}
    adj = {k: [] for k in nodes}
    unmatched = []
    for l in links or []:
        if l.get("external") or not l.get("b"):
            if l.get("external"):
                unmatched.append({"switch": nodes.get(l.get("a"), {}).get("name", l.get("a")), "port": l.get("a_port"), "sysname": l.get("sysname") or l.get("b_name"), "chassis": l.get("chassis")})
            continue
        if l["a"] in adj and l["b"] in adj:
            adj[l["a"]].append((l["b"], l.get("a_port"), l.get("b_port"), l))
            adj[l["b"]].append((l["a"], l.get("b_port"), l.get("a_port"), l))
    # racine : la passerelle, sinon le commutateur le plus connecté
    roots = [k for k, n in nodes.items() if n["kind"] == "gateway"]
    if not roots and nodes:
        roots = [max(nodes, key=lambda k: (len(adj[k]), nodes[k]["kind"] == "switch"))]
    seen = set(roots)
    queue = list(roots)
    while queue:
        cur = queue.pop(0)
        # voisins : commutateurs d'abord (le cœur avant les bornes), liaisons pleines avant les nues
        nbs = sorted(adj[cur], key=lambda t: (KIND_ORDER[nodes[t[0]]["kind"]], bool(t[3].get("bare")), nodes[t[0]]["name"]))
        for nb, my_port, their_port, link in nbs:
            if nb in seen:
                continue
            seen.add(nb)
            n = nodes[nb]
            side = "a" if link.get("a") == cur else "b"  # #565 : réglage du port côté PARENT (PVID, all, allowed)
            n["parent"], n["uplink_port"], n["parent_port"], n["depth"], n["link"] = cur, their_port, my_port, nodes[cur]["depth"] + 1, {
                "a_vlans": link.get("a_vlans"), "b_vlans": link.get("b_vlans"), "missing_on_a": link.get("missing_on_a") or [],
                "missing_on_b": link.get("missing_on_b") or [], "bare": bool(link.get("bare")),
                "parent_pvid": link.get(side + "_pvid"), "parent_all": bool(link.get(side + "_all")), "parent_allowed": link.get(side + "_allowed") or []}
            queue.append(nb)
    # appareils non reliés : sous la racine, marqués
    max_depth = max([n["depth"] for n in nodes.values()] + [0])
    for k, n in nodes.items():
        if k not in seen:
            n["parent"] = roots[0] if roots and k != roots[0] else None
            n["depth"] = 1 if roots and k != roots[0] else 0
            n["unlinked"] = True
    attached, loose, fields = attach_clients(clients, [{"devId": k, "name": n["name"], "mac": n["mac"]} for k, n in nodes.items()])
    for k, cl in attached.items():
        for c in cl:  # filaire ou Wi-Fi : selon l'appareil qui le sert (l'OpenAPI ne publie pas le SSID par client)
            c["wired"] = nodes[k]["kind"] != "ap"
        nodes[k]["clients"] = sorted(cl, key=lambda c: (c["status"] != "online", str(c["name"]).lower()))
    order = sorted(nodes.values(), key=lambda n: (n["depth"], KIND_ORDER[n["kind"]], n["name"].lower()))
    return {"nodes": order, "unmatched": unmatched, "loose_clients": loose, "client_fields": fields,
            "counts": {"devices": len(nodes), "clients": sum(len(n["clients"]) for n in nodes.values()) + len(loose), "unlinked": sum(1 for n in nodes.values() if n.get("unlinked"))}}
