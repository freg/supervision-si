# -*- coding: utf-8 -*-
"""#712 : passerelle USG FLEX vue par l'OpenAPI Nebula -- exposition (NAT) et cohérence des zones invité.

Vérifié dans la documentation officielle de l'OpenAPI (zyxelnetworks.github.io/NebulaOpenAPI) : AUCUNE route ne
publie les règles de sécurité (security policies) ni les zones du pare-feu ; seules sont lisibles les interfaces
(`guestZone` par interface LAN, déjà exploité par la carte des VLAN) et le NAT (`gw/{devId}/nat-settings` :
`oneToOne` et `virtualServer`). On en déduit ce qui est déductible :

  nat_sensitive_port   haute / basse  service d'administration ou de base publié sur Internet (basse si l'origine est restreinte)
  nat_whole_host       haute          NAT 1:1 sans restriction de port ni d'origine : tout l'hôte exposé
  nat_to_guest         moyenne        service publié depuis un VLAN en zone invité
  nat_unknown_target   basse          cible d'une publication hors de tout sous-réseau connu
  ssid_guest_not_isolated moyenne     SSID « invité » sur un VLAN hors zone invité (isolation à la seule charge des règles)
  guest_zone_mixed     basse          VLAN en zone invité portant un SSID non invité

Pur : `parse_nat`, `anomalies` (même forme que vlanmap : kind, element, message, details)."""
import ipaddress

SENSITIVE = {22: "SSH", 23: "Telnet", 135: "RPC Windows", 139: "NetBIOS", 445: "SMB (partages Windows)", 1433: "SQL Server",
             1521: "Oracle", 2375: "Docker (API sans chiffrement)", 2376: "Docker (API)", 3306: "MySQL / MariaDB", 3389: "Bureau à distance (RDP)",
             5432: "PostgreSQL", 5900: "VNC", 5985: "WinRM", 5986: "WinRM", 6379: "Redis", 8006: "Proxmox (administration)",
             8007: "Proxmox Backup Server", 9200: "Elasticsearch", 10000: "Webmin", 11211: "Memcached", 27017: "MongoDB", 161: "SNMP"}
PROTO = {0: "tout", 1: "TCP", 2: "UDP", 3: "TCP/UDP", "0": "tout", "1": "TCP", "2": "UDP", "3": "TCP/UDP"}
ANY = {"", "any", "all", "*", "0.0.0.0/0", "0.0.0.0", "::/0"}


def _first(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _list(v):
    if v in (None, ""):
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


def _ports(values):
    """["22", "8000-8010", "any"] -> (ensemble de ports, tous ?, ports explicites) ; plages bornées à 2000 ports.
    « Explicites » : ports seuls et petites plages (4 au plus) -- un 8006 au milieu de 8000-8010 n'est pas Proxmox."""
    ports, every, explicit = set(), False, set()
    for v in values:
        v = v.lower()
        if v in ANY:
            every = True
            continue
        if "-" in v or ":" in v:
            a, b = (v.replace(":", "-").split("-", 1) + [""])[:2]
            if a.isdigit() and b.isdigit() and int(b) >= int(a):
                if int(b) - int(a) > 2000:
                    every = True
                else:
                    ports.update(range(int(a), int(b) + 1))
                    if int(b) - int(a) < 4:
                        explicit.update(range(int(a), int(b) + 1))
        elif v.isdigit():
            ports.add(int(v)); explicit.add(int(v))
    return ports, every or not values, explicit


def parse_nat(nat):
    """Réponse nat-settings -> [{kind, enabled, name, interface, public_ip, private_ip, ports, all_ports, protocol, remote, any_remote}]."""
    out = []
    nat = nat or {}
    for r in nat.get("oneToOne") or nat.get("one_to_one") or []:
        base = {"kind": "1:1", "enabled": bool(r.get("enabled", True)), "name": _first(r, ("name", "description"), ""),
                "interface": r.get("interface"), "public_ip": _first(r, ("publicIPv4", "publicIp", "publicIP")),
                "private_ip": _first(r, ("privateIPv4", "privateIp", "privateIP", "lanIp"))}
        inbound = r.get("inbound") or []
        if not inbound:
            out.append(dict(base, ports=[], all_ports=True, explicit_ports=[], protocol="tout", remote=[], any_remote=True))
        for ib in inbound:
            ports, every, explicit = _ports(_list(ib.get("port") or ib.get("ports")))
            remote = _list(ib.get("remote") or ib.get("allowedRemote") or ib.get("remoteIp"))
            out.append(dict(base, enabled=base["enabled"] and bool(ib.get("enabled", True)), ports=sorted(ports), all_ports=every, explicit_ports=sorted(explicit),
                            protocol=PROTO.get(ib.get("protocol"), str(ib.get("protocol"))), remote=remote,
                            any_remote=not remote or any(x.lower() in ANY for x in remote)))
    for r in nat.get("virtualServer") or nat.get("virtual_server") or []:
        ports, every, explicit = _ports(_list(_first(r, ("publicPorts", "publicPort", "externalPorts", "externalPort", "ports"))))
        remote = _list(_first(r, ("remote", "allowedRemote", "allowedRemoteIPs", "remoteIp", "sourceIp")))
        out.append({"kind": "redirection", "enabled": bool(r.get("enabled", True)), "name": _first(r, ("description", "name"), ""),
                    "interface": r.get("interface"), "public_ip": _first(r, ("publicIPv4", "publicIp", "publicIP")),
                    "private_ip": _first(r, ("privateIPv4", "privateIp", "privateIP", "lanIp", "serverIp")),
                    "private_ports": _list(_first(r, ("privatePorts", "privatePort", "internalPorts", "internalPort"))),
                    "ports": sorted(ports), "all_ports": every, "explicit_ports": sorted(explicit), "protocol": PROTO.get(r.get("protocol"), str(r.get("protocol"))),
                    "remote": remote, "any_remote": not remote or any(x.lower() in ANY for x in remote)})
    return out


def _net(s):
    try:
        return ipaddress.ip_network(str(s), strict=False)
    except ValueError:
        return None


def _vlan_of(ip, vlans):
    try:
        a = ipaddress.ip_address(str(ip))
    except ValueError:
        return None
    for v in vlans:
        n = _net(v.get("subnet")) if v.get("subnet") else None
        if n is not None and a in n:
            return v
    return None


def anomalies(nat_rules, vmap):
    """-> [{kind, element, message, details}] (identifiant posé par l'appelant, comme vlanmap)."""
    found = []

    def add(kind, element, message, **details):
        found.append({"kind": kind, "element": element, "message": message, "details": details})
    vlans = (vmap or {}).get("vlans") or []
    for r in nat_rules or []:
        if not r.get("enabled"):
            continue
        label = "%s %s%s" % (r["kind"], r.get("name") or "", (" → %s" % r["private_ip"]) if r.get("private_ip") else "")
        origin = "toute origine" if r["any_remote"] else "origine restreinte à %s" % ", ".join(r["remote"][:4])
        if r["kind"] == "1:1" and r["all_ports"] and r["any_remote"]:
            add("nat_whole_host", label.strip(), "NAT 1:1 %s → %s : tous les ports de l'hôte publiés sur Internet, %s."
                % (r.get("public_ip") or "?", r.get("private_ip") or "?", origin), public_ip=r.get("public_ip"), private_ip=r.get("private_ip"))
        else:
            hits = sorted(p for p in r.get("explicit_ports", r["ports"]) if p in SENSITIVE)
            if hits:
                what = ", ".join("%d (%s)" % (p, SENSITIVE[p]) for p in hits[:5])
                add("nat_sensitive_port" if r["any_remote"] else "nat_sensitive_port_restricted", label.strip(),
                    "Publication %s vers %s : port(s) sensible(s) %s ouverts sur Internet, %s."
                    % (r.get("name") or r["kind"], r.get("private_ip") or "?", what, origin),
                    ports=hits, private_ip=r.get("private_ip"), remote=r["remote"], services=[SENSITIVE[p] for p in hits])
        if r.get("private_ip"):
            v = _vlan_of(r["private_ip"], vlans)
            if v and v.get("guest"):
                add("nat_to_guest", label.strip(), "Publication %s vers %s, dans le VLAN %s en zone invité : un service publié depuis le réseau des invités."
                    % (r.get("name") or r["kind"], r["private_ip"], v.get("vid")), vlan=v.get("vid"), private_ip=r["private_ip"])
            elif v is None and any(x.get("subnet") for x in vlans):
                add("nat_unknown_target", label.strip(), "Publication %s vers %s : adresse hors de tout sous-réseau connu de la passerelle (cible obsolète ?)."
                    % (r.get("name") or r["kind"], r["private_ip"]), private_ip=r["private_ip"])
    for v in vlans:
        guest_ssids = [s["name"] for s in v.get("ssids") or [] if s.get("guest")]
        other_ssids = [s["name"] for s in v.get("ssids") or [] if not s.get("guest")]
        if guest_ssids and v.get("gateway_interface") and not v.get("guest"):
            add("ssid_guest_not_isolated", "VLAN %s" % v.get("vid"), "SSID invité %s sur le VLAN %s, dont l'interface %s n'est pas en zone invité : "
                "l'isolation du réseau interne ne tient qu'aux règles de sécurité de la passerelle (non lisibles par l'API)."
                % (", ".join(guest_ssids), v.get("vid"), v.get("gateway_interface")), vlan=v.get("vid"), ssids=guest_ssids, interface=v.get("gateway_interface"))
        if v.get("guest") and other_ssids:
            add("guest_zone_mixed", "VLAN %s" % v.get("vid"), "VLAN %s en zone invité mais SSID non invité %s : ses clients sont isolés comme des invités."
                % (v.get("vid"), ", ".join(other_ssids)), vlan=v.get("vid"), ssids=other_ssids)
    return found
