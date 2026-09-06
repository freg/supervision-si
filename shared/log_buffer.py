"""
Tampon de logs PARTAGÉ via Memcached -- livraison #145. Corrige un
problème réel découvert en investigant une panne du 01/09 : chaque
backend (les 15 APIs + prefs-api) tourne avec 2 workers Gunicorn --
des PROCESSUS séparés, mémoire NON partagée -- or le tampon de logs
(/logs, /hub-log, /push-log, livraisons #139-#142) était jusqu'ici un
simple `deque` EN MÉMOIRE PAR PROCESSUS : une entrée capturée par un
worker restait invisible si la lecture suivante (un simple sondage du
gestionnaire de logs) atterrissait sur l'autre worker.

Corrigé en stockant le tampon dans Memcached -- déjà présent dans le
projet (service `memcached`, déjà utilisé par 8 des 15 backends pour
du cache de requêtes, voir get_memcache_client() dans api/app.py) --
partagé par TOUS les workers d'un même service, ET persistant à
travers un redémarrage individuel d'un conteneur (perdu seulement si
Memcached LUI-MÊME redémarre -- rare, et un tampon de diagnostic
remis à zéro dans ce cas reste acceptable, jamais une donnée métier).

Choix assumé : les 2 workers restent à 2 (pas réduits à 1) -- ce
correctif règle la cause du problème (l'absence de mémoire partagée)
directement, sans sacrifier la concurrence que le second worker
apporte par ailleurs.

Lecture-modification-écriture avec CAS (compare-and-swap,
gets()/cas()) -- JAMAIS un read-modify-write naïf, qui perdrait des
entrées sous écriture concurrente des deux workers (le scénario même
qu'on corrige). Quelques tentatives en cas de collision ; au-delà,
l'entrée EST perdue plutôt que de bloquer la requête HTTP en cours qui
a déclenché ce warning/cette erreur -- acceptable pour un outil de
diagnostic (même philosophie que le tampon en mémoire d'origine :
volatile, borné, jamais un historique garanti), jamais pour une
donnée métier de ce projet.

Copié dans chaque backend au build (COPY shared/log_buffer.py .,
même motif que shared/version_endpoint.py) -- importé avec le même
garde défensif (module absent hors conteneur Docker réel, ex. tests
directs de app.py dans un environnement de développement).

Couvre aussi /push-log (sources externes poussées, livraison #142) --
même faille jumelle (dictionnaire Python en mémoire de processus),
corrigée en même temps plutôt que laissée derrière : append_shared_log_entry
(écriture DIRECTE, pour un appelant qui n'a pas d'enregistrement
logging.LogRecord -- le cas de POST /push-log) et
register_shared_log_source/read_shared_log_source_registry (Memcached
n'offre PAS de "lister les clés" -- un registre séparé, sous sa
propre clé, tient la liste des sources déjà vues, mise à jour avec le
même motif CAS).
"""
import json
import logging as _logging


def _append_with_cas(buffer_key, entry, memcache_client_factory, buffer_size, max_retries):
    """Cœur PARTAGÉ de l'écriture -- lecture-modification-écriture
    avec CAS (compare-and-swap), utilisé aussi bien par le
    logging.Handler (make_shared_log_handler) que par l'écriture
    DIRECTE (append_shared_log_entry, pour /push-log qui n'a pas de
    logging.LogRecord). JAMAIS un read-modify-write naïf -- perdrait
    des entrées sous écriture concurrente des deux workers, le
    scénario même qu'on corrige. Quelques tentatives en cas de
    collision ; au-delà, l'entrée EST perdue plutôt que de bloquer la
    requête HTTP en cours -- acceptable pour un outil de diagnostic,
    jamais pour une donnée métier de ce projet."""
    try:
        client = memcache_client_factory()
        for _ in range(max_retries):
            result = client.gets(buffer_key)
            if result is None or result[0] is None:
                current, cas_token = [], None
            else:
                raw, cas_token = result
                try:
                    current = json.loads(raw)
                    if not isinstance(current, list):
                        current = []
                except Exception:
                    current = []
            current.append(entry)
            current = current[-buffer_size:]
            new_raw = json.dumps(current).encode("utf-8")
            if cas_token is None:
                # Clé absente -- add() est ATOMIQUE (échoue si un
                # AUTRE worker l'a créée entre-temps) -- dans ce cas
                # on retente (gets() la trouvera).
                if client.add(buffer_key, new_raw, expire=0):
                    return
            else:
                # cas() échoue si la valeur a changé depuis le gets()
                # -- un autre worker a écrit entre-temps -- on
                # retente avec l'état à jour.
                if client.cas(buffer_key, new_raw, cas_token, expire=0):
                    return
    except Exception:
        pass  # le logging ne doit jamais faire planter l'appli lui-même


def make_shared_log_handler(service_name, memcache_client_factory, buffer_size=200, capture_level="WARNING", max_retries=3):
    """Construit un logging.Handler qui écrit dans Memcached au lieu
    d'un tampon en mémoire de processus. `memcache_client_factory` :
    fonction SANS ARGUMENT renvoyant un client pymemcache -- RECRÉÉ À
    CHAQUE APPEL par l'appelant (même motif déjà établi côté chaque
    backend, voir get_memcache_client() dans api/app.py) -- jamais une
    connexion persistante gardée ici, pour éviter de garder une
    connexion morte si Memcached redémarre.

    **Correctif #215 -- trouvaille réelle en répondant à la demande
    "rien ne doit être silencieux"** : jusqu'ici, AUCUN service de ce
    projet ne configurait explicitement le NIVEAU du logger racine
    Python -- il restait à sa valeur par défaut (`WARNING`). Or le
    niveau du LOGGER filtre AVANT même que l'enregistrement
    n'atteigne un handler quelconque -- un appel `logging.debug(...)`
    ou même `logging.info(...)` ÉTAIT DONC SILENCIEUSEMENT REJETÉ,
    quelle que soit la valeur de `capture_level`/`LOG_CAPTURE_LEVEL`
    ci-dessous (le filtre du HANDLER n'entre en jeu qu'APRÈS,
    beaucoup trop tard). Corrigé : le logger racine est désormais
    explicitement mis à `DEBUG` (le niveau le plus permissif) --
    PLUS AUCUN enregistrement n'est perdu avant le handler. Le tri
    "que garder réellement" reste entièrement le rôle de
    `capture_level` ci-dessous (par défaut toujours `WARNING`, donc
    le tampon partagé reste silencieux par défaut comme avant) --
    élever `LOG_CAPTURE_LEVEL=DEBUG` pour UN service précis suffit
    désormais à voir immédiatement toute sa trace fine, sans plus
    jamais se heurter à ce filtre invisible en amont."""
    buffer_key = f"logbuf:{service_name}"
    _logging.getLogger().setLevel(_logging.DEBUG)

    class SharedRingBufferLogHandler(_logging.Handler):
        def emit(self, record):
            entry = {
                "service": service_name,
                "timestamp": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            _append_with_cas(buffer_key, entry, memcache_client_factory, buffer_size, max_retries)

    handler = SharedRingBufferLogHandler()
    handler.setLevel(getattr(_logging, capture_level, _logging.WARNING))
    return handler


def append_shared_log_entry(service_name, memcache_client_factory, entry, buffer_size=200, max_retries=3):
    """Écriture DIRECTE (pas via le module logging) -- pour un
    appelant qui construit lui-même son entrée (ex. POST /push-log,
    qui reçoit déjà service/level/message/logger depuis le corps de
    la requête, jamais un logging.LogRecord). Même cœur CAS que
    make_shared_log_handler -- une seule logique à maintenir."""
    buffer_key = f"logbuf:{service_name}"
    _append_with_cas(buffer_key, entry, memcache_client_factory, buffer_size, max_retries)


def register_shared_log_source(memcache_client_factory, registry_key, source_name, max_retries=3):
    """Ajoute `source_name` à un REGISTRE partagé (liste de noms
    connus) si elle n'y est pas déjà. Nécessaire car Memcached
    n'offre PAS de "lister les clés existantes" -- sans registre
    séparé, impossible de savoir quelles sources /push-log ont déjà
    poussé au moins une fois. Même motif CAS que _append_with_cas
    (évite qu'une course entre deux workers découvrant la MÊME
    nouvelle source ne se marchent dessus)."""
    try:
        client = memcache_client_factory()
        for _ in range(max_retries):
            result = client.gets(registry_key)
            if result is None or result[0] is None:
                current, cas_token = [], None
            else:
                raw, cas_token = result
                try:
                    current = json.loads(raw)
                    if not isinstance(current, list):
                        current = []
                except Exception:
                    current = []
            if source_name in current:
                return  # déjà connue -- rien à faire
            current.append(source_name)
            new_raw = json.dumps(current).encode("utf-8")
            if cas_token is None:
                if client.add(registry_key, new_raw, expire=0):
                    return
            else:
                if client.cas(registry_key, new_raw, cas_token, expire=0):
                    return
    except Exception:
        pass


def read_shared_log_source_registry(memcache_client_factory, registry_key):
    """Lit le registre des sources connues -- toujours une liste
    triée, jamais une exception qui remonterait."""
    try:
        client = memcache_client_factory()
        raw = client.get(registry_key)
        if raw is None:
            return []
        sources = json.loads(raw)
        if not isinstance(sources, list):
            return []
        return sorted(sources)
    except Exception:
        return []


def read_shared_log_buffer(service_name, memcache_client_factory, limit=None, buffer_size=200):
    """Lit le tampon partagé -- toujours une liste, jamais une
    exception qui remonterait (Memcached injoignable, clé absente,
    JSON corrompu -- tous traités comme "tampon vide", jamais une
    500 sur /logs à cause d'un souci Memcached)."""
    try:
        client = memcache_client_factory()
        raw = client.get(f"logbuf:{service_name}")
        if raw is None:
            return []
        entries = json.loads(raw)
        if not isinstance(entries, list):
            return []
    except Exception:
        return []
    effective_limit = buffer_size if limit is None else max(1, min(limit, buffer_size))
    return entries[-effective_limit:]
