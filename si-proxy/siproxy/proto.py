# -*- coding: utf-8 -*-
"""Bastion si-proxy (livraison #452) -- primitives PURES et helpers de
tunnel partagés par le relais, le shim host et le client Mac.

Le bastion est réservé à freg (pour l'instant) : accès depuis le Mac à un
shell sur le host de la VM du hub, à la navigation HTTPS sur le hub et, par
le hub, sur le LAN. Rien n'est exécuté par le relais -- il ne fait
qu'aiguiller des octets entre deux connexions TLS d'une même session ; le
shim host, sur la VM, est le seul à ouvrir un PTY (sous freg) ou une socket
TCP vers une cible.

Protocole : chaque connexion s'ouvre par UNE ligne JSON (utf-8, terminée par
\\n) -- le HELLO -- puis, selon le rôle :
  - canal de contrôle (host)  : le relais envoie des lignes JSON `open` ;
  - canal de données (host/client) : octets bruts aiguillés tels quels.
Aucun secret n'est journalisé (voir `redact`).
"""
import ipaddress
import json
import re

MAX_LINE = 64 * 1024
CONTROL, DATA = "control", "data"
SHELL, CONNECT = "shell", "connect"


def encode_line(obj):
    """Objet -> une ligne JSON terminée par \\n (compacte, utf-8)."""
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def decode_line(raw):
    """Ligne (sans le \\n final) -> objet, ou None si illisible."""
    try:
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


def valid_hello(obj, expected_token, roles=("host", "client")):
    """(ok, raison). Un HELLO valide : role connu, jeton exact, type
    cohérent, et pour un canal de données un `kind` valable avec une cible
    bien formée pour `connect`."""
    if not isinstance(obj, dict):
        return False, "hello absent"
    if obj.get("role") not in roles:
        return False, "role inconnu"
    if not expected_token or obj.get("token") != expected_token:
        return False, "jeton refusé"
    typ = obj.get("type")
    if typ not in (CONTROL, DATA):
        return False, "type inconnu"
    # kind / target ne concernent QUE le canal de données du client : c'est
    # lui qui demande un shell ou une connexion. Le canal de données du host
    # (ouvert en retour) ne porte qu'un `session`.
    if typ == DATA and obj.get("role") == "client":
        kind = obj.get("kind")
        if kind not in (SHELL, CONNECT):
            return False, "kind inconnu"
        if kind == CONNECT:
            host, port, err = split_target(obj.get("target"))
            if err:
                return False, err
    return True, None


def split_target(target):
    """« host:port » -> (host, port, None) ou (None, None, raison). IPv6
    accepté entre crochets : « [::1]:443 »."""
    if not target or not isinstance(target, str):
        return None, None, "cible manquante"
    m = re.match(r"^\[([0-9a-fA-F:]+)\]:(\d+)$", target) or re.match(r"^([^:/\s]+):(\d+)$", target)
    if not m:
        return None, None, "cible mal formée (attendu host:port)"
    host, port = m.group(1), int(m.group(2))
    if not (0 < port < 65536):
        return None, None, "port hors bornes"
    return host, port, None


# Cibles interdites même pour freg : boucle locale du host (le shim tourne
# sur la VM ; 127.0.0.1 y désignerait la VM elle-même, pas une intention de
# navigation), et adresses de métadonnées cloud / lien-local.
_DENY_NETS = [ipaddress.ip_network(n) for n in ("127.0.0.0/8", "::1/128", "169.254.0.0/16", "fe80::/10")]


def target_allowed(host, extra_deny=None):
    """(ok, raison). Par défaut tout est permis (le bastion sert justement à
    joindre le hub et le LAN), sauf la boucle locale du host et le
    lien-local ; `extra_deny` ajoute des réseaux/hôtes refusés par config."""
    for pat in extra_deny or []:
        if _match_deny(host, pat):
            return False, "cible refusée par configuration (%s)" % pat
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True, None  # nom d'hôte : résolu côté host, non filtré ici
    for net in _DENY_NETS:
        if ip.version == net.version and ip in net:
            return False, "cible interdite (boucle locale / lien-local du host)"
    return True, None


def _match_deny(host, pat):
    pat = (pat or "").strip()
    if not pat:
        return False
    if pat == host:
        return True
    try:
        net = ipaddress.ip_network(pat, strict=False)
        ip = ipaddress.ip_address(host)
        return ip.version == net.version and ip in net
    except ValueError:
        return False


def parse_proxy_request(head):
    """Première ligne d'une requête HTTP reçue par le proxy local du client.
    Retourne (method, target, http_version, is_connect) ; target est
    « host:port » pour CONNECT, l'URL absolue sinon. (None,...) si illisible."""
    try:
        line = head.split(b"\r\n", 1)[0].decode("latin-1")
    except (IndexError, UnicodeDecodeError):
        return None, None, None, False
    parts = line.split(" ")
    if len(parts) < 3:
        return None, None, None, False
    method, target, version = parts[0], parts[1], parts[2]
    return method, target, version, method.upper() == "CONNECT"


def absolute_uri_target(uri):
    """« http://host:port/chemin » -> (« host:port », chemin) pour un proxy
    HTTP en clair (le navigateur passe l'URL absolue). None si non http."""
    m = re.match(r"^http://([^/]+)(/.*)?$", uri, re.I)
    if not m:
        return None, None
    hostport, path = m.group(1), m.group(2) or "/"
    if ":" not in hostport:
        hostport += ":80"
    return hostport, path


def redact(obj):
    """Copie d'un objet de contrôle sans le jeton, pour les traces."""
    if not isinstance(obj, dict):
        return obj
    return {k: ("***" if k in ("token", "secret") else v) for k, v in obj.items()}
