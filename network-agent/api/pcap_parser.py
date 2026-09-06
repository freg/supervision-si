"""
Analyseur de flux pcap en Python PUR (livraison #233, backlog item
20 -- agent d'exploration réseau, "à base de tcpdump"). Ni `dpkt` ni
`scapy` ne sont installables dans cet environnement de développement
(même famille de restriction que `pysnmp`/`sshpass`/`npm` rencontrée
plus tôt dans ce projet) -- plutôt que de dépendre d'un paquet dont
même la présence côté déploiement final n'est pas garantie, ce
module réimplémente le strict nécessaire : le format pcap lui-même
(RFC officieuse mais stable depuis les années 1990, largement
documentée) et les en-têtes Ethernet/IPv4/ARP/TCP/UDP, qui sont de
simples structures binaires de taille fixe -- aucune bibliothèque
n'est réellement nécessaire pour ce sous-ensemble précis.

**Portée volontairement limitée** : IPv4 seulement (pas IPv6 --
détecté et ignoré proprement, jamais une erreur), pas de
réassemblage de fragments IP, pas de suivi de flux TCP (SYN/FIN) --
seulement l'EXTRACTION d'un résumé par paquet (MACs, IPs, ports,
protocole, taille), suffisant pour construire progressivement un
inventaire d'appareils/services vus sur le réseau (le but de ce
module), pas une resynthèse complète du trafic.

Format pcap (in-line, jamais deviné -- structure fixe documentée
depuis la création du format par tcpdump/libpcap) :
- En-tête global (24 octets) : magic_number(4) détermine le boutisme,
  version_major(2), version_minor(2), thiszone(4), sigfigs(4),
  snaplen(4), network(4, type de lien -- 1 = Ethernet, le seul
  supporté ici).
- Par paquet : en-tête (16 octets) ts_sec(4), ts_usec(4),
  incl_len(4, octets RÉELLEMENT capturés), orig_len(4, taille
  ORIGINALE sur le fil -- peut différer si `snaplen` a tronqué le
  paquet) puis `incl_len` octets de données.
"""
import struct

PCAP_MAGIC_LE = 0xA1B2C3D4  # boutisme natif de la machine qui a capturé
PCAP_MAGIC_BE = 0xD4C3B2A1  # boutisme inversé -- capture faite sur une machine à l'endianness opposée
LINKTYPE_ETHERNET = 1

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP = 0x0806
ETHERTYPE_IPV6 = 0x86DD

IPPROTO_TCP = 6
IPPROTO_UDP = 17
IPPROTO_ICMP = 1


class PcapFormatError(Exception):
    pass


def _read_exact(stream, n):
    """`stream.read(n)` peut renvoyer MOINS de `n` octets même si
    plus de données arrivent ensuite (comportement standard d'un
    pipe/socket, PAS un fichier régulier) -- boucle jusqu'à obtenir
    exactement `n` octets, ou `None` si le flux est terminé AVANT le
    premier octet lu (fin normale), ou lève si terminé EN COURS DE
    LECTURE (flux tronqué, anormal)."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            if not chunks:
                return None  # fin propre, rien lu du tout
            raise PcapFormatError(f"flux tronqué -- {remaining} octet(s) manquant(s) sur {n} attendus")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def parse_global_header(stream):
    """Renvoie `byte_order` ('<' ou '>', format `struct`) après avoir
    validé le nombre magique -- lève si ni l'un ni l'autre (flux qui
    n'est pas du pcap valide, jamais une erreur silencieuse plus
    loin)."""
    raw = _read_exact(stream, 24)
    if raw is None:
        raise PcapFormatError("flux vide -- aucun en-tête global pcap")
    magic = struct.unpack("<I", raw[:4])[0]
    if magic == PCAP_MAGIC_LE:
        byte_order = "<"
    elif magic == PCAP_MAGIC_BE:
        byte_order = ">"
    else:
        raise PcapFormatError(f"nombre magique pcap invalide (0x{magic:08x}) -- flux non reconnu")
    network = struct.unpack(byte_order + "I", raw[20:24])[0]
    if network != LINKTYPE_ETHERNET:
        raise PcapFormatError(f"type de lien {network} non supporté -- seul Ethernet (1) l'est ici")
    return byte_order


def iter_packets(stream):
    """Générateur -- lit l'en-tête global PUIS chaque paquet un par
    un, jusqu'à la fin du flux. Chaque élément produit :
    {ts_sec, ts_usec, orig_len, data} -- `data` : les octets
    RÉELLEMENT capturés (peut être < orig_len si snaplen a tronqué)."""
    byte_order = parse_global_header(stream)
    while True:
        header = _read_exact(stream, 16)
        if header is None:
            return  # fin propre du flux
        ts_sec, ts_usec, incl_len, orig_len = struct.unpack(byte_order + "IIII", header)
        data = _read_exact(stream, incl_len)
        if data is None:
            raise PcapFormatError("flux tronqué -- en-tête de paquet sans les données annoncées")
        yield {"ts_sec": ts_sec, "ts_usec": ts_usec, "orig_len": orig_len, "data": data}


def _format_mac(raw6):
    return ":".join(f"{b:02x}" for b in raw6)


def _format_ipv4(raw4):
    return ".".join(str(b) for b in raw4)


def parse_ethernet_frame(data):
    """Renvoie (dst_mac, src_mac, ethertype, payload) ou None si
    `data` est trop court pour être une trame Ethernet valide (jamais
    une exception sur un paquet malformé/tronqué -- un seul paquet
    suspect ne doit jamais interrompre l'analyse de tout le flux)."""
    if len(data) < 14:
        return None
    dst_mac = _format_mac(data[0:6])
    src_mac = _format_mac(data[6:12])
    ethertype = struct.unpack(">H", data[12:14])[0]
    return dst_mac, src_mac, ethertype, data[14:]


def parse_ipv4_packet(payload):
    """Renvoie un dict {src_ip, dst_ip, protocol, header_len,
    total_length, ttl, transport_payload} ou None si `payload` trop
    court/pas de l'IPv4 valide. N'exige PAS que `total_length`
    corresponde exactement à la longueur réelle (un paquet tronqué
    par snaplen aura moins de données que ce que l'en-tête annonce --
    normal, jamais une erreur)."""
    if len(payload) < 20:
        return None
    version_ihl = payload[0]
    version = version_ihl >> 4
    if version != 4:
        return None  # IPv6 ou autre -- hors de portée de ce parseur, ignoré proprement
    header_len = (version_ihl & 0x0F) * 4
    if header_len < 20 or len(payload) < header_len:
        return None
    total_length, = struct.unpack(">H", payload[2:4])
    ttl = payload[8]
    protocol = payload[9]
    src_ip = _format_ipv4(payload[12:16])
    dst_ip = _format_ipv4(payload[16:20])
    return {
        "src_ip": src_ip, "dst_ip": dst_ip, "protocol": protocol,
        "header_len": header_len, "total_length": total_length, "ttl": ttl,
        "transport_payload": payload[header_len:],
    }


def parse_tcp_ports(transport_payload):
    """Renvoie (src_port, dst_port) ou None si trop court."""
    if len(transport_payload) < 4:
        return None
    return struct.unpack(">HH", transport_payload[:4])


def parse_udp_ports(transport_payload):
    """Même forme que parse_tcp_ports -- les 4 premiers octets de TCP
    et UDP sont structurellement identiques (src_port, dst_port)."""
    if len(transport_payload) < 4:
        return None
    return struct.unpack(">HH", transport_payload[:4])


def parse_arp_packet(payload):
    """Renvoie {operation, sender_mac, sender_ip, target_mac,
    target_ip} pour une requête/réponse ARP Ethernet+IPv4 (le cas de
    très loin le plus courant) -- None pour tout autre type de
    matériel/protocole ARP (rare, jamais deviné). `operation` : 1 =
    request, 2 = reply."""
    if len(payload) < 28:
        return None
    hw_type, proto_type, hw_len, proto_len, operation = struct.unpack(">HHBBH", payload[0:8])
    if hw_type != 1 or proto_type != ETHERTYPE_IPV4 or hw_len != 6 or proto_len != 4:
        return None
    sender_mac = _format_mac(payload[8:14])
    sender_ip = _format_ipv4(payload[14:18])
    target_mac = _format_mac(payload[18:24])
    target_ip = _format_ipv4(payload[24:28])
    return {
        "operation": operation, "sender_mac": sender_mac, "sender_ip": sender_ip,
        "target_mac": target_mac, "target_ip": target_ip,
    }


def summarize_packet(raw_packet):
    """Point d'entrée principal -- prend UN élément produit par
    `iter_packets` et en extrait un résumé structuré et STABLE
    (mêmes clés toujours présentes, valeurs `None` si non
    applicables) pour l'inventaire progressif (voir `capture.py`).
    Ne lève JAMAIS -- un paquet malformé/tronqué produit un résumé
    partiel (`kind: "unknown"` ou champs `None`), jamais une
    exception qui interromprait la capture de tout le flux."""
    summary = {
        "ts_sec": raw_packet["ts_sec"], "orig_len": raw_packet["orig_len"],
        "kind": "unknown", "src_mac": None, "dst_mac": None,
        "src_ip": None, "dst_ip": None, "protocol": None,
        "src_port": None, "dst_port": None, "arp": None,
    }
    eth = parse_ethernet_frame(raw_packet["data"])
    if eth is None:
        return summary
    dst_mac, src_mac, ethertype, payload = eth
    summary["src_mac"] = src_mac
    summary["dst_mac"] = dst_mac

    if ethertype == ETHERTYPE_ARP:
        arp = parse_arp_packet(payload)
        if arp is not None:
            summary["kind"] = "arp"
            summary["arp"] = arp
        return summary

    if ethertype == ETHERTYPE_IPV6:
        summary["kind"] = "ipv6"  # hors de portée -- signalé comme tel, jamais confondu avec IPv4
        return summary

    if ethertype != ETHERTYPE_IPV4:
        return summary  # kind reste "unknown" -- ethertype non reconnu par ce parseur

    ip = parse_ipv4_packet(payload)
    if ip is None:
        return summary
    summary["src_ip"] = ip["src_ip"]
    summary["dst_ip"] = ip["dst_ip"]
    summary["protocol"] = ip["protocol"]

    if ip["protocol"] == IPPROTO_TCP:
        summary["kind"] = "tcp"
        ports = parse_tcp_ports(ip["transport_payload"])
        if ports:
            summary["src_port"], summary["dst_port"] = ports
    elif ip["protocol"] == IPPROTO_UDP:
        summary["kind"] = "udp"
        ports = parse_udp_ports(ip["transport_payload"])
        if ports:
            summary["src_port"], summary["dst_port"] = ports
    elif ip["protocol"] == IPPROTO_ICMP:
        summary["kind"] = "icmp"
    else:
        summary["kind"] = "ip_other"

    return summary
