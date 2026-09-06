"""
tcpdump partagé, sans stockage (volet 3 de la demande #295) --
livraison #305. Appelle le VRAI binaire `tcpdump` système via
sous-processus, même motif que `ping_probe.py`/`nmap_probe.py`.

**⚠️ NON VÉRIFIÉ contre un vrai `tcpdump`** -- binaire absent de cet
environnement de développement (`/bin/sh: tcpdump: not found`), même
limitation déjà documentée pour les deux autres sondes. Le format
texte par ligne de tcpdump VARIE significativement selon le
protocole (TCP/UDP/ICMP/ARP n'ont pas la même structure de ligne) --
plutôt que de parser chaque format précisément (fragile, jamais
vérifiable ici), extraction par MOTIFS robustes aux variations :
adresses IP par expression régulière, mots-clés de protocole
recherchés comme mots entiers. Résultat un résumé agrégé, jamais
une reconstruction ligne-par-ligne fidèle.

**SANS STOCKAGE, VOLONTAIREMENT** -- contrairement à smokeping/nmap
(échantillons/scans conservés en base), une capture tcpdump n'est
JAMAIS écrite sur disque ni en base ici. Raison double : (1) demandé
explicitement ("tcpdump sans stockage utilisable par d'autres
modules") -- le résultat structuré est transmis à l'appelant, pas
gardé ; (2) une capture réseau peut contenir des données sensibles
(contenu de paquets, même si ce module ne s'intéresse qu'aux
en-têtes) -- la persister élargirait sans raison la surface de ce
qui doit être protégé.

**BORNÉ PAR DÉFAUT** -- nombre de paquets ou durée, jamais une
capture illimitée : une capture non bornée sur une interface chargée
pourrait consommer beaucoup de ressources pour un usage "partagé".
"""
import re
import subprocess

DEFAULT_PACKET_COUNT = 200
DEFAULT_TIMEOUT_SECONDS = 30

# Mots de protocole recherchés comme MOTS ENTIERS (\b...\b) --
# évite de confondre "tcp" dans un nom d'hôte avec le mot-clé de
# protocole lui-même. Insensible à la casse -- tcpdump peut afficher
# en majuscules (ICMP) ou minuscules (tcp) selon le contexte.
_PROTOCOL_RE = re.compile(r"\b(tcp|udp|icmp6?|arp)\b", re.IGNORECASE)
_IP_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")


def capture(interface=None, packet_count=DEFAULT_PACKET_COUNT, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    """Lance `tcpdump -n -q -c <packet_count> [-i <interface>]` --
    renvoie {"success", "packet_count", "protocol_counts": {...},
    "top_ips": [{"ip", "count"}], "error"}. JAMAIS d'exception
    remontée à l'appelant -- une interface invalide ou un tcpdump
    absent sont des résultats à signaler, pas des pannes de ce
    module (même raisonnement que ping_probe.py/nmap_probe.py)."""
    cmd = ["tcpdump", "-n", "-q", "-c", str(packet_count)]
    if interface:
        cmd += ["-i", interface]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    except FileNotFoundError:
        return {"success": False, "packet_count": 0, "protocol_counts": {}, "top_ips": [], "error": "binaire 'tcpdump' introuvable sur ce système"}
    except subprocess.TimeoutExpired as exc:
        # tcpdump attend `packet_count` paquets -- sur une interface
        # calme, ce délai est NORMAL (pas assez de trafic), jamais
        # une erreur en soi. La sortie PARTIELLE déjà capturée
        # (exc.stdout) reste exploitable -- jamais jetée.
        # Piège réel trouvé en testant : `TimeoutExpired.stdout` reste
        # en BYTES même avec `text=True` sur le subprocess.run() qui a
        # levé l'exception -- text=True ne s'applique qu'au retour
        # NORMAL, jamais à la capture partielle d'un timeout. Décodage
        # explicite requis, sinon échec sur le `.splitlines()` /
        # regex (qui attendent du `str`) juste en dessous.
        partial_output = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return _summarize(partial_output, timed_out=True)
    except Exception as exc:  # noqa: BLE001 -- défensif, jamais remonté brut
        return {"success": False, "packet_count": 0, "protocol_counts": {}, "top_ips": [], "error": str(exc)}

    # tcpdump sans privilège suffisant échoue au démarrage (returncode
    # != 0) AVANT de capturer quoi que ce soit -- distingué d'un
    # timeout normal ci-dessus (qui, lui, a déjà capturé un peu).
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        return {"success": False, "packet_count": 0, "protocol_counts": {}, "top_ips": [], "error": (detail[-1] if detail else f"tcpdump a échoué (code {proc.returncode})")}

    return _summarize(proc.stdout, timed_out=False)


def _summarize(output, timed_out):
    lines = [l for l in output.splitlines() if l.strip()]
    protocol_counts = {}
    ip_counts = {}
    for line in lines:
        proto_match = _PROTOCOL_RE.search(line)
        if proto_match:
            proto = proto_match.group(1).lower()
            protocol_counts[proto] = protocol_counts.get(proto, 0) + 1
        for ip in _IP_RE.findall(line):
            ip_counts[ip] = ip_counts.get(ip, 0) + 1

    top_ips = sorted(ip_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "success": True,
        "packet_count": len(lines),
        "protocol_counts": protocol_counts,
        "top_ips": [{"ip": ip, "count": count} for ip, count in top_ips],
        "error": "délai atteint avant le nombre de paquets demandé (trafic faible, résultat partiel)" if timed_out else None,
    }
