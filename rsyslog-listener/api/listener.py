"""
Écoute UDP syslog (livraison #177, backlog BACKLOG.md #3, étape
4/4 -- DERNIÈRE de l'initiative "logs de toutes sortes"). Socket UDP
simple, tournant dans un thread DAEMON démarré UNE SEULE FOIS (voir
app.py) -- ce service a délibérément UN SEUL worker Gunicorn (voir
Dockerfile), même raisonnement que ssh-tunnels-api (#159) : un port
UDP ne peut être BOUND que par un seul processus à la fois (sans
SO_REUSEPORT, jamais utilisé ici -- inutile pour ce volume de trafic
de diagnostic, et ça éviterait juste un conflit de bind sans rien
apporter côté fiabilité).

Le parsing (syslog_parser.py) reste SÉPARÉ et testable sans réseau --
ce module ne fait QUE la mécanique socket + écriture dans le tampon
partagé (log_buffer.py, #145), même mécanisme que les autres sources
(push/url/file) : le hub affiche cette source automatiquement, sans
AUCUNE modification frontend.
"""
import logging
import socket
import time

from syslog_parser import parse_syslog_message

# Traces DEBUG (livraison #224, audit rétroactif) -- VOLONTAIREMENT
# LIMITÉES au démarrage du socket et au ré-enregistrement périodique
# (déjà throttlé à _REGISTER_THROTTLE_SECONDS) -- JAMAIS par paquet
# reçu, qui pourrait représenter un flux à fort volume et noierait le
# tampon partagé de bruit sans valeur ajoutée réelle.
_log = logging.getLogger("rsyslog_listener")

MAX_DATAGRAM_SIZE = 8192  # RFC 5424 recommande >= 2048 -- large marge

# Enregistrement de la source (registre partagé, log_buffer.py) --
# throttlé, PAS à chaque paquet reçu : register_shared_log_source fait
# un aller-retour Memcached même quand la source est déjà connue
# (vérifié dans son code -- gets() puis comparaison, jamais un
# court-circuit AVANT la lecture). Un flux syslog à fort volume
# multiplierait inutilement les appels Memcached pour un gain nul la
# plupart du temps. Ré-enregistré périodiquement (pas juste une fois)
# en filet de sécurité si Memcached LUI-MÊME redémarre entre-temps
# (rare, mais le registre serait alors vide sans que ce processus ne
# redémarre pour autant).
_REGISTER_THROTTLE_SECONDS = 300


def run_listener(host, port, source_name, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, log_fn=None, socket_factory=None, max_iterations=None):
    """Boucle BLOQUANTE -- à lancer dans un thread daemon dédié (voir
    app.py). `socket_factory` et `max_iterations` injectables pour
    les tests (jamais un vrai socket réseau ni une boucle infinie
    dans un test unitaire) -- `max_iterations` borne le nombre de
    paquets traités avant de sortir, None = boucle indéfiniment
    (comportement réel)."""
    sock = (socket_factory or _default_socket)(host, port)
    _log.debug("run_listener : socket prêt, écoute démarrée sur %s:%s (source=%s)", host, port, source_name)
    last_registered = 0.0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        try:
            data, _addr = sock.recvfrom(MAX_DATAGRAM_SIZE)
        except OSError as exc:
            if log_fn:
                log_fn("Écoute syslog UDP : erreur socket : %s", exc)
            continue

        text = data.decode("utf-8", errors="replace")
        entry_data = parse_syslog_message(text, source_name)
        if entry_data is None:
            continue

        full_entry = {
            "service": source_name,
            "timestamp": time.time(),
            "level": entry_data["level"],
            "logger": entry_data["logger"],
            "message": entry_data["message"],
        }
        append_fn(source_name, memcache_client_factory, full_entry, buffer_size=buffer_size)

        now = time.time()
        if now - last_registered >= _REGISTER_THROTTLE_SECONDS:
            _log.debug("run_listener : ré-enregistrement périodique de la source '%s' (throttlé à %ss)", source_name, _REGISTER_THROTTLE_SECONDS)
            register_fn(memcache_client_factory, registry_key, source_name)
            last_registered = now


def _default_socket(host, port):
    _log.debug("_default_socket : tentative de bind sur %s:%s", host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
    except OSError as exc:
        _log.debug("_default_socket : ÉCHEC du bind sur %s:%s -- %s", host, port, exc)
        raise
    _log.debug("_default_socket : bind réussi sur %s:%s", host, port)
    return sock
