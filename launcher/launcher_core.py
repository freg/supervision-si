"""Cœur du lanceur web -- séparé de launcher.cgi (le script CGI
lui-même) pour rester testable : les fonctions ci-dessous acceptent
en injection les fonctions RÉELLES de vérification (curl HTTP,
`docker compose ps`), remplaçables par de fausses versions en test,
sans jamais avoir besoin d'un vrai réseau ni d'un vrai Docker.

Cartographie construite et VÉRIFIÉE service par service (Dockerfiles
lus un par un, jamais une supposition sur les ports) -- voir
CHANGELOG.md pour le détail de cette vérification.
"""

# Chaque service -> port interne (nom DNS docker-compose = nom du
# service) si HTTP, ou None si le service ne parle PAS HTTP (base de
# données TCP-seule, cache, ou script d'arrière-plan sans interface
# réseau du tout). Pour ces derniers, seul `docker compose ps` peut
# dire s'ils tournent -- un curl n'aurait jamais de sens.
SERVICE_PORTS = {
    "tls-proxy": "gateway",  # cas particulier -- port dynamique (GATEWAY_PORT), résolu à l'exécution
    "keycloak": 8080,
    "keycloak-backup": None,  # script de sauvegarde périodique, aucune interface réseau
    "hub": 5173,
    "api": 5000,
    "frontend": 5173,
    "pipeline": None,  # pousse vers l'API périodiquement, n'écoute jamais lui-même
    "memcached": None,  # protocole binaire, pas HTTP
    "pixel-grid-postgres": None,  # PostgreSQL, TCP seulement
    "pixel-grid-api": 5000,
    "pixel-grid-bridge": None,  # relie pixel-grid-api à l'API, n'écoute jamais lui-même
    "tickets-postgres": None,
    "tickets-api": 5000,
    "tickets-portal": 5173,
    "dba-api": 5000,
    "dba-portal": 5173,
    "vault-api": 5000,
    "vault-portal": 5173,
    "vault-admin-api": 5000,
    "vault-admin-portal": 5173,
    "ipam-api": 5000,
    "optick-api": 5000,
    "zenoss-api": 5000,
    "tts-gu-api": 5000,
    "owncloud-api": 5000,
    "owncloud-search-api": 5000,
    "cacti-api": 5000,
    "elasticsearch": 9200,
    "geo-postgres": None,
    "geo-import-api": 5000,
    "prefs-api": 5000,
}


def is_known_service(service):
    return service in SERVICE_PORTS


def check_status(service, *, http_check, docker_state_check, gateway_port=None):
    """Détermine si `service` tourne -- HTTP réel si le service en
    parle, repli sur l'état du conteneur Docker sinon (jamais l'un ou
    l'autre au hasard, la table SERVICE_PORTS décide).

    `http_check(service, port) -> bool` et `docker_state_check(service) -> bool`
    sont INJECTÉS -- jamais appelés directement ici, pour rester
    testable sans réseau ni Docker réels (voir test_launcher_core.py).
    """
    if service not in SERVICE_PORTS:
        return "unknown"
    port = SERVICE_PORTS[service]
    if port == "gateway":
        port = gateway_port
    if port is None:
        alive = docker_state_check(service)
    else:
        alive = http_check(service, port)
    return "up" if alive else "down"


def dispatch_action(service, action, *, http_check, docker_state_check, docker_action, gateway_port=None):
    """Point d'entrée unique pour les commandes (start/stop/status/list)
    -- utilisé par launcher.cgi ET par les tests, jamais deux
    implémentations qui pourraient diverger.

    `docker_action(service, action) -> None` -- lance concrètement
    `docker compose start|stop <service>`, injecté pour la même
    raison que les vérifications ci-dessus.

    `action="list"` -- ignore `service` (peut être vide), renvoie la
    liste de tous les services connus. Utilisée par la page web au
    chargement, pour ne JAMAIS dupliquer SERVICE_PORTS une troisième
    fois côté JavaScript.
    """
    if action == "list":
        return {"services": sorted(SERVICE_PORTS.keys())}

    if not is_known_service(service):
        return {"error": f"service inconnu : {service!r}"}

    if action == "status":
        return {"service": service, "status": check_status(
            service, http_check=http_check, docker_state_check=docker_state_check, gateway_port=gateway_port
        )}

    if action in ("start", "stop"):
        docker_action(service, action)
        return {"service": service, "action": action, "status": "ok"}

    return {"error": f"action inconnue : {action!r} (attendu : start, stop, status)"}
