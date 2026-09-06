"""
Résolution DNS inverse des appareils découverts (livraison #250,
demandé explicitement par la personne : "afficher la résolution
dns" + "récupérer le dns et le domain par défaut depuis l'hôte OU le
faire paramétrer").

**Deux mécanismes** :
1. **Résolveur SYSTÈME** (`socket.gethostbyaddr`, bibliothèque
   standard) -- utilisé par défaut, respecte `/etc/resolv.conf` du
   conteneur ("depuis l'hôte", au mieux -- voir la limite ci-dessous).
2. **Serveur DNS SPÉCIFIQUE** (`NETWORK_AGENT_DNS_SERVER`, si
   configuré -- "le faire paramétrer") -- `socket.gethostbyaddr` ne
   permet PAS de choisir un serveur précis par appel ; `dnspython`
   (bibliothèque tierce qui ferait ça proprement) N'EST PAS
   installable dans cet environnement de développement (vérifié :
   `pip install dnspython` échoue, aucun miroir PyPI accessible ici)
   -- MÊME contrainte que `pcap_parser.py` (#233) pour `dpkt`/`scapy`.
   Ce module réimplémente donc, comme pour le pcap, le strict
   nécessaire du protocole DNS -- UNE SEULE requête PTR par UDP,
   rien d'autre (pas de TCP fallback, pas de DNSSEC, pas de cache) --
   suffisant pour ce besoin précis, jamais présenté comme un client
   DNS complet.

**Limite honnêtement signalée** : `network-agent-api` tourne en
`network_mode: host` (#238-239) -- son `/etc/resolv.conf` reste
celui géré PAR LE CONTENEUR (Docker ne le fait pas correspondre
automatiquement à celui de l'hôte même en network_mode: host), donc
le résolveur système "depuis l'hôte" est un BEST-EFFORT, pas une
garantie -- d'où l'intérêt réel de `NETWORK_AGENT_DNS_SERVER` en
solution de repli fiable, l'option "paramétrable" explicitement
proposée par la personne.
"""
import logging
import socket
import struct

_log = logging.getLogger("network_agent_dns")

_DNS_TYPE_PTR = 12
_DNS_CLASS_IN = 1


def resolve_hostname(ip, dns_server=None, timeout=2.0):
    """Point d'entrée principal -- renvoie le nom d'hôte résolu (sans
    le domaine par défaut retiré, voir `strip_default_domain`) ou
    `None` (jamais une exception, une résolution DNS ratée est
    routinière -- pas de PTR pour cette IP, timeout, serveur
    injoignable -- jamais un incident à faire remonter)."""
    if dns_server:
        return _resolve_via_server(ip, dns_server, timeout)
    return _resolve_via_system(ip, timeout)


def _resolve_via_system(ip, timeout):
    try:
        socket.setdefaulttimeout(timeout)
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, socket.timeout, OSError) as exc:
        _log.debug("resolve_hostname : résolution système échouée pour %s -- %s", ip, exc)
        return None
    finally:
        socket.setdefaulttimeout(None)


def _reverse_arpa_name(ip):
    """"192.168.0.10" -> "10.0.168.192.in-addr.arpa" -- format
    standard des requêtes PTR IPv4 (octets inversés). `None` si `ip`
    n'est pas une adresse IPv4 valide (IPv6 hors de portée ici, même
    limite que `pcap_parser.py` -- voir sa docstring)."""
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return None
    return ".".join(reversed(parts)) + ".in-addr.arpa"


def _encode_dns_name(name):
    """Encode un nom de domaine au format DNS (chaque étiquette
    précédée de sa longueur, terminé par un octet nul) -- ex.
    "10.0.168.192.in-addr.arpa" -> b'\\x0210\\x010\\x03168\\x03192\\x07in-addr\\x04arpa\\x00"."""
    encoded = b""
    for label in name.split("."):
        label_bytes = label.encode("ascii")
        encoded += bytes([len(label_bytes)]) + label_bytes
    return encoded + b"\x00"


def _build_ptr_query(ip, query_id):
    arpa_name = _reverse_arpa_name(ip)
    if arpa_name is None:
        return None
    header = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0)  # 0x0100 = recursion désirée
    question = _encode_dns_name(arpa_name) + struct.pack(">HH", _DNS_TYPE_PTR, _DNS_CLASS_IN)
    return header + question


def _decode_dns_name(packet, offset):
    """Décode un nom DNS à partir de `offset` dans `packet` --
    GÈRE LA COMPRESSION (pointeur `0xC0` -- un nom peut référencer un
    autre emplacement du paquet plutôt que de se répéter, standard
    DNS RFC 1035 §4.1.4). Renvoie (nom_decode, offset_apres_le_nom)
    -- `offset_apres_le_nom` est celui APRÈS le nom tel qu'écrit à
    l'emplacement de départ, JAMAIS celui suivant un pointeur suivi
    (un pointeur ne fait toujours que 2 octets à l'endroit d'origine,
    peu importe la longueur de ce vers quoi il pointe)."""
    labels = []
    original_offset = None
    pos = offset
    guard = 0  # jamais une boucle infinie sur un paquet malformé avec des pointeurs circulaires
    while guard < 128:
        guard += 1
        if pos >= len(packet):
            return None, offset
        length = packet[pos]
        if length == 0:
            pos += 1
            break
        if (length & 0xC0) == 0xC0:  # pointeur de compression -- 2 octets, 14 bits d'offset
            if pos + 1 >= len(packet):
                return None, offset
            pointer = ((length & 0x3F) << 8) | packet[pos + 1]
            if original_offset is None:
                original_offset = pos + 2
            pos = pointer
            continue
        pos += 1
        if pos + length > len(packet):
            return None, offset
        labels.append(packet[pos:pos + length].decode("ascii", errors="replace"))
        pos += length
    end_offset = original_offset if original_offset is not None else pos
    return ".".join(labels), end_offset


def _parse_ptr_response(packet, expected_query_id):
    """Renvoie le nom d'hôte du PREMIER enregistrement PTR trouvé
    dans la réponse, ou `None` (réponse vide, ID de requête différent
    -- réponse tardive d'une requête antérieure, jamais associée par
    erreur -- ou format inattendu)."""
    if len(packet) < 12:
        return None
    resp_id, flags, qdcount, ancount = struct.unpack(">HHHH", packet[:8])
    if resp_id != expected_query_id or ancount == 0:
        return None

    pos = 12
    for _ in range(qdcount):  # sauter la section question, jamais utile pour la réponse elle-même
        _, pos = _decode_dns_name(packet, pos)
        pos += 4  # QTYPE + QCLASS

    for _ in range(ancount):
        _, pos = _decode_dns_name(packet, pos)
        if pos + 10 > len(packet):
            return None
        rtype, rclass, ttl, rdlength = struct.unpack(">HHIH", packet[pos:pos + 10])
        pos += 10
        if rtype == _DNS_TYPE_PTR:
            hostname, _ = _decode_dns_name(packet, pos)
            return hostname
        pos += rdlength
    return None


def _resolve_via_server(ip, dns_server, timeout):
    query_id = 0x1234  # fixe -- une seule requête à la fois par appel, jamais de correspondance ambiguë
    query = _build_ptr_query(ip, query_id)
    if query is None:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(query, (dns_server, 53))
            response, _ = sock.recvfrom(512)  # 512 octets -- taille max UDP DNS classique (RFC 1035), largement suffisant pour un PTR
    except (socket.timeout, OSError) as exc:
        _log.debug("resolve_hostname : requête vers %s échouée pour %s -- %s", dns_server, ip, exc)
        return None
    hostname = _parse_ptr_response(response, query_id)
    if hostname and hostname.endswith("."):
        hostname = hostname[:-1]
    return hostname


def strip_default_domain(hostname, default_domain):
    """Retire le SUFFIXE `default_domain` d'un nom résolu, pour un
    affichage plus court -- "pc1.corp.local" + "corp.local" ->
    "pc1". Renvoie `hostname` INCHANGÉ si `default_domain` est vide
    ou ne correspond pas (jamais une troncature hasardeuse)."""
    if not hostname or not default_domain:
        return hostname
    suffix = "." + default_domain.lower().strip(".")
    if hostname.lower().endswith(suffix):
        return hostname[:-len(suffix)]
    return hostname
