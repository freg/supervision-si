"""
Orchestration de capture réseau via `tcpdump` (livraison #233,
backlog item 20 -- "exploration du réseau à base de tcpdump et
repérage PROGRESSIF des équipements"). Lance `tcpdump` en
sous-processus, écrivant le flux pcap sur sa sortie standard (`-w -`)
-- lu et analysé EN CONTINU par `pcap_parser.py` (Python pur, voir
sa docstring pour le choix d'écarter `dpkt`/`scapy`, non installables
dans cet environnement de développement).

**Détection du rôle passerelle/routeur** (volet demandé
explicitement, "identifier et évaluer leurs RÔLES -- NAT et
autres") -- heuristique RÉSEAU, pas devinée : sur un réseau local,
la résolution ARP ne peut résoudre qu'une IP DU MÊME SOUS-RÉSEAU --
pour toute IP destination HORS du sous-réseau local (CIDR configuré
pour le segment), le système d'exploitation résout automatiquement
l'adresse MAC de la PASSERELLE PAR DÉFAUT à la place (c'est
littéralement le mécanisme de routage IP sur Ethernet). Donc : une
MAC destination qui reçoit RÉGULIÈREMENT des paquets dont l'IP finale
sort du sous-réseau est très probablement une passerelle/un routeur
-- comptée comme `external_relay_count` par appareil (voir
`store.apply_role_hints`), jamais une affirmation, toujours une
hypothèse à seuil bas signalée comme telle.

**Simplification ASSUMÉE pour ce premier socle** : un "service" (port
TCP/UDP destination) est attribué à l'appareil identifié par
`dst_mac`, QUE ce trafic soit interne au segment OU relayé vers
l'extérieur. Un appareil déjà repéré comme passerelle probable
accumulera donc des services très divers, reflet du trafic RELAYÉ
plutôt que de services qu'il offre lui-même -- limite connue,
volontairement pas raffinée davantage dans cette première tranche
(nécessiterait de suivre des FLUX complets, pas seulement des
paquets isolés).
"""
import ipaddress
import logging
import subprocess
import time

import pcap_parser
import store

_log = logging.getLogger("network_agent_capture")

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"


def is_unicast_mac(mac):
    """Exclut broadcast/multicast -- jamais traités comme un
    "appareil" (voir docstring du module). Le bit de poids faible du
    PREMIER octet d'une MAC Ethernet indique multicast (norme IEEE
    802) -- `01:*`, `33:33:*` (multicast IPv6) en sont les cas les
    plus courants."""
    if mac is None or mac == BROADCAST_MAC:
        return False
    try:
        first_octet = int(mac.split(":")[0], 16)
    except (ValueError, IndexError):
        return False
    return (first_octet & 0x01) == 0


def ip_outside_cidr(ip_str, cidr_str):
    """`True` si `ip_str` est HORS de `cidr_str` -- `False` si `cidr`
    n'est pas configuré (segment sans CIDR connu -- jamais de
    détection de relais externe possible dans ce cas, pas une
    approximation risquée) ou si l'IP est malformée (paquet
    corrompu/atypique, jamais bloquant)."""
    if not cidr_str or not ip_str:
        return False
    try:
        return ipaddress.ip_address(ip_str) not in ipaddress.ip_network(cidr_str, strict=False)
    except ValueError:
        return False


def process_packet(conn, network_segment_id, segment_cidr, summary):
    """Cœur du traitement PROGRESSIF -- appelé une fois PAR PAQUET
    capturé. Ne lève JAMAIS (voir pcap_parser.summarize_packet, déjà
    défensif en amont) -- un paquet inattendu/mal formé est
    simplement ignoré pour cette mise à jour, jamais une exception
    qui interromprait la capture de tout le flux."""
    kind = summary["kind"]

    if kind == "arp":
        arp = summary["arp"]
        if arp and is_unicast_mac(arp["sender_mac"]) and arp["sender_ip"] not in (None, "0.0.0.0"):
            store.upsert_device(conn, network_segment_id, arp["sender_mac"], arp["sender_ip"],
                                 bytes_delta=summary["orig_len"], is_external_relay=False)
        return

    if kind not in ("tcp", "udp", "icmp", "ip_other"):
        return  # unknown/ipv6 -- hors de portée de ce premier socle, jamais devinés

    src_mac, dst_mac = summary["src_mac"], summary["dst_mac"]
    src_ip, dst_ip = summary["src_ip"], summary["dst_ip"]

    dst_is_external = ip_outside_cidr(dst_ip, segment_cidr)

    src_device_id = None
    if is_unicast_mac(src_mac):
        src_device_id = store.upsert_device(conn, network_segment_id, src_mac, src_ip,
                                             bytes_delta=summary["orig_len"], is_external_relay=False)

    dst_device_id = None
    if is_unicast_mac(dst_mac):
        dst_device_id = store.upsert_device(conn, network_segment_id, dst_mac, None,
                                             bytes_delta=0, is_external_relay=dst_is_external)

    if kind in ("tcp", "udp") and dst_device_id is not None and summary["dst_port"] is not None:
        store.upsert_device_service(conn, dst_device_id, kind, summary["dst_port"])

    # Échange entre appareils (livraison #250, "détection de la
    # communication => échange") -- seulement si les DEUX bouts sont
    # des appareils réels identifiés (jamais un échange enregistré
    # avec un seul côté connu -- pas de faux "appareil" implicite).
    if src_device_id is not None and dst_device_id is not None:
        store.upsert_device_link(conn, network_segment_id, src_device_id, dst_device_id,
                                  bytes_delta=summary["orig_len"])
        # Service utilisé DANS cet échange (livraison #251, "services
        # connectés par paire d'ip") -- seulement pour TCP/UDP avec un
        # port destination connu, même condition que
        # `upsert_device_service` juste au-dessus.
        if kind in ("tcp", "udp") and summary["dst_port"] is not None:
            store.upsert_device_link_service(conn, network_segment_id, src_device_id, dst_device_id,
                                              kind, summary["dst_port"], bytes_delta=summary["orig_len"])

    return src_device_id


def run_capture(interface, network_segment_id, segment_cidr, db_path,
                 packet_source=None, role_hint_every=200, max_packets=None):
    """Boucle PRINCIPALE -- lance `tcpdump` (ou utilise
    `packet_source` injecté, un itérable de résumés déjà prêts, pour
    les tests -- jamais un vrai `tcpdump` dans un test unitaire) et
    traite chaque paquet au fil de l'eau, avec un `commit()`
    périodique (pas à chaque paquet -- coût I/O disproportionné sur
    un flux à fort débit) et un recalcul périodique des indices de
    rôle (`role_hint_every` paquets). `max_packets` : borne le nombre
    de paquets traités avant de sortir (None = jusqu'à la fin du
    flux/processus tcpdump, comportement réel) -- injectable pour ne
    jamais boucler indéfiniment dans un test."""
    conn = store.get_connection(db_path)
    processed = 0
    proc = None
    try:
        if packet_source is not None:
            summaries = packet_source
        else:
            _log.debug("run_capture : démarrage de tcpdump sur l'interface %s", interface)
            proc = subprocess.Popen(
                ["tcpdump", "-i", interface, "-w", "-", "-U"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # Courte fenêtre pour détecter un échec RAPIDE (interface
            # inexistante, permission refusée malgré CAP_NET_RAW/
            # CAP_NET_ADMIN) -- même motif que
            # ssh-tunnels/api/tunnel_process.py (#210). **Trouvaille
            # réelle en testant sur un vrai déploiement** : sans cette
            # vérification, `proc.stdout` reste vide, et l'erreur
            # REMONTÉE À L'UTILISATEUR était le message générique de
            # `pcap_parser` ("flux vide -- aucun en-tête pcap") --
            # techniquement vrai, mais qui masquait la VRAIE raison
            # (toujours sur `stderr`, jamais lu jusqu'ici). Corrigé.
            time.sleep(0.5)
            if proc.poll() is not None:
                stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
                message = stderr_text or f"tcpdump s'est arrêté immédiatement (code {proc.returncode}), sans message sur stderr"
                _log.debug("run_capture : ÉCHEC RAPIDE de tcpdump -- %s", message)
                raise RuntimeError(f"tcpdump n'a pas pu démarrer sur l'interface '{interface}' : {message}")
            summaries = (pcap_parser.summarize_packet(p) for p in pcap_parser.iter_packets(proc.stdout))

        for summary in summaries:
            process_packet(conn, network_segment_id, segment_cidr, summary)
            processed += 1
            if processed % 20 == 0:
                conn.commit()  # périodique -- jamais un commit par paquet, coût disproportionné
            if processed % role_hint_every == 0:
                store.apply_role_hints(conn, network_segment_id)
                conn.commit()
            if max_packets is not None and processed >= max_packets:
                break
        conn.commit()
        store.apply_role_hints(conn, network_segment_id)
        conn.commit()
    except pcap_parser.PcapFormatError as exc:
        _log.debug("run_capture : flux pcap invalide après %d paquet(s) -- %s", processed, exc)
        raise
    finally:
        conn.close()
        if proc is not None:
            proc.terminate()
    _log.debug("run_capture : terminé -- %d paquet(s) traité(s)", processed)
    return processed
