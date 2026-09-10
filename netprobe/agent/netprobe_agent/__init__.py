"""netprobe-agent -- sonde distribuée et collecteur de site (backlog
items 45/47/48, livraison #405).

Bibliothèque STANDARD uniquement, volontairement : la cible est un
Raspberry Pi Zero W (ARMv6 monocœur, 512 Mo) sous Raspberry Pi OS Lite
-- aucune dépendance pip à compiler, aucun framework. Le même paquet sert
les deux rôles (`role` dans la configuration) :

- `probe`      : la sonde (Pi Zero W) -- exécute des tâches périodiques
                 (état du lien WiFi, scan des bornes visibles, ping, DNS,
                 HTTP, iperf3 si présent, santé du Pi) et pousse les
                 mesures vers le collecteur de site, avec file locale
                 SQLite quand celui-ci est injoignable.
- `collector`  : le collecteur (Pi 3B, Ethernet) -- reçoit les mesures
                 des sondes du site, les stocke, sert à chaque sonde sa
                 liste de tâches, et relaie vers `netprobe-api` central
                 (store-and-forward, le WAN/VPN étant précisément l'une
                 des couches à diagnostiquer).

Voir README.md du dossier `netprobe/agent/` pour l'architecture complète
et les choix tranchés (agent propre plutôt que sparrow-wifi, HMAC par
appareil, configuration TIRÉE par la sonde).
"""

__version__ = "0.1.0"
