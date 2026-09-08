"""si-agent -- agent hôte de supervision-si (livraison #420, backlog 63).

Surveille l'hôte (CPU, charge, mémoire, disques, services, ports,
journaux, comptes) et sert de moteur de plugins / sondes (Python ou
shell) poussés et signés par le central. Paquet DISTINCT de
`netprobe_agent` (la sonde WiFi/réseau) -- décision de la personne --
mais même protocole d'authentification et même file locale, copiés depuis
la source canonique (voir sync-shared.sh).
"""
__version__ = "0.2.0"
