"""
Sondeur des sources de logs URL (livraison #147, backlog "logs de
toutes sortes", BACKLOG.md #3, étape 2/4) -- tâche de fond, DANS le
processus prefs-api (pas un conteneur séparé). Tourne dans CHAQUE
worker Gunicorn (2 workers, voir docker-compose.yml) -- double
sondage possible de la MÊME URL si les deux workers sont dus au même
moment, CHOIX ASSUMÉ plutôt qu'une complexité de coordination
inter-workers : chaque sondage écrit dans le MÊME tampon Memcached
PARTAGÉ (shared/log_buffer.py, livraison #145), donc jamais une
incohérence de LECTURE -- juste, au pire, une entrée occasionnellement
dupliquée si les deux workers tombent pile au même instant.
Acceptable pour un outil de diagnostic (même philosophie assumée
partout ailleurs dans ce mécanisme de logs).

Suivi "dernier sondage" PAR PROCESSUS (dict en mémoire, jamais
partagé) -- volontairement : coordonner CE suivi entre workers
ajouterait de la complexité pour un gain minime (au pire, l'intervalle
RÉEL observé est légèrement plus court que configuré si les deux
workers sont désynchronisés, jamais un problème de fond).

Format "plain" -- déduction de niveau par MOTS-CLÉS (français ET
anglais, voir _detect_level), choix ASSUMÉ faute de réponse tranchée
de la personne (question posée explicitement, jamais confirmée) :
ERROR/ERREUR/CRITICAL/CRITIQUE -> ERROR, WARN/ATTENTION/AVERTISSEMENT
-> WARNING, sinon INFO. Documenté ici pour être facilement révisable
si la personne préfère finalement "tout INFO, jamais deviner".
"""
import json
import threading
import time
import urllib.error
import urllib.request

CHECK_INTERVAL_SECONDS = 10  # fréquence de VÉRIFICATION ("une source est-elle due"), pas l'intervalle de sondage lui-même (propre à chaque source, config.interval_seconds)
FETCH_TIMEOUT_SECONDS = 10

_last_polled = {}  # nom de source -> horodatage Unix du dernier sondage tenté (réussi ou pas)


def _detect_level(line):
    """Déduction de niveau par mots-clés pour le format "plain" --
    insensible à la casse, français ET anglais (contexte du projet :
    les systèmes visés écrivent vraisemblablement dans l'une ou
    l'autre langue, jamais garanti). "ERREUR" (français) ne contient
    PAS la sous-chaîne "ERROR" (anglais) -- découvert en test, une
    détection anglais-seul aurait raté toute ligne française."""
    upper = line.upper()
    if "CRITICAL" in upper or "CRITIQUE" in upper or "ERROR" in upper or "ERREUR" in upper:
        return "ERROR"
    if "WARN" in upper or "ATTENTION" in upper or "AVERTISSEMENT" in upper:
        return "WARNING"
    return "INFO"


def parse_response(body_text, fmt, source_name):
    """Transforme le corps de réponse en liste d'entrées
    {level, logger, message} -- jamais une exception qui remonterait,
    une ligne malformée est simplement ignorée plutôt que de faire
    échouer tout le lot. Fonction PURE, testable directement."""
    entries = []
    for line in body_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if fmt == "jsonl":
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if not isinstance(obj, dict):
                continue
            message = str(obj.get("message", "")).strip()
            if not message:
                continue
            level = str(obj.get("level", "INFO")).strip().upper() or "INFO"
            logger_name = str(obj.get("logger", source_name)).strip() or source_name
            entries.append({"level": level, "logger": logger_name, "message": message})
        else:  # "plain"
            entries.append({"level": _detect_level(line), "logger": source_name, "message": line})
    return entries


def poll_source(source, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, log_fn=None, fetch_fn=None):
    """Sonde UNE source URL, écrit ses entrées dans le tampon partagé.
    Jamais une exception qui remonterait -- une source en échec
    (réseau, timeout, réponse invalide) est journalisée (si `log_fn`
    fourni, typiquement app.logger.warning -- visible dans /logs
    grâce au tampon partagé #145) et simplement retentée au prochain
    cycle. `fetch_fn` injectable pour les tests (jamais un vrai appel
    réseau dans un test unitaire)."""
    name = source["name"]
    config = source.get("config") or {}
    url = config.get("url", "")
    fmt = config.get("format", "plain")

    fetch = fetch_fn or _default_fetch
    try:
        body_text = fetch(url)
    except Exception as exc:  # noqa: BLE001
        if log_fn:
            log_fn("Source de logs '%s' (URL) injoignable : %s", name, exc)
        return

    entries = parse_response(body_text, fmt, name)
    for entry in entries:
        full_entry = {
            "service": name,
            "timestamp": time.time(),
            "level": entry["level"],
            "logger": entry["logger"],
            "message": entry["message"],
        }
        append_fn(name, memcache_client_factory, full_entry, buffer_size=buffer_size)
    if entries:
        register_fn(memcache_client_factory, registry_key, name)


def _default_fetch(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8", errors="replace")


def poll_all_due_sources(sources, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, log_fn=None, now=None, fetch_fn=None, base_dir=None, poll_file_fn=None):
    """Sonde toutes les sources (URL ET fichier, livraison #176)
    ACTIVÉES dont l'intervalle est écoulé. `sources` : liste de dicts
    (voir row_to_log_source côté prefs-api/app.py) -- pas besoin que
    l'appelant pré-filtre par type, DISPATCHÉ ici. Fonction PURE côté
    logique de sélection (testable directement, sans thread ni sleep
    réel) -- `now` injectable pour les tests.

    `poll_file_fn` (livraison #176) : injecté plutôt qu'importé en
    dur ici -- garde ce module autonome (le sondeur URL, #147,
    fonctionne SANS aucune dépendance au module fichier) et testable
    sans dépendre de file_source_poller.py. `base_dir` : répertoire
    racine autorisé pour les sources fichier (voir
    file_source_poller._resolve_safe_path) -- une source "file" est
    silencieusement IGNORÉE si `poll_file_fn`/`base_dir` absents
    (jamais une exception), ex. le module fichier pas disponible."""
    current = now if now is not None else time.time()
    for source in sources:
        source_type = source.get("type")
        if source_type not in ("url", "file") or not source.get("enabled"):
            continue
        name = source["name"]
        interval = (source.get("config") or {}).get("interval_seconds", 60)
        last = _last_polled.get(name, 0)
        if current - last < interval:
            continue
        _last_polled[name] = current
        if source_type == "url":
            poll_source(source, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, log_fn, fetch_fn)
        elif source_type == "file" and poll_file_fn and base_dir:
            poll_file_fn(source, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, base_dir, log_fn)


def start_background_poller(get_sources_fn, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size=200, log_fn=None, check_interval=None, base_dir=None, poll_file_fn=None):
    """Démarre la boucle de fond DANS UN THREAD DAEMON -- ne bloque
    jamais l'arrêt du processus (`daemon=True`). `get_sources_fn` :
    fonction SANS ARGUMENT renvoyant la liste actuelle des sources
    (relit la base à CHAQUE cycle -- une source ajoutée/modifiée/
    désactivée est prise en compte au cycle suivant, jamais besoin de
    redémarrer le service). `base_dir`/`poll_file_fn` (livraison
    #176) : voir poll_all_due_sources ci-dessus."""

    def _loop():
        interval = check_interval or CHECK_INTERVAL_SECONDS
        while True:
            try:
                sources = get_sources_fn()
                poll_all_due_sources(sources, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, log_fn, base_dir=base_dir, poll_file_fn=poll_file_fn)
            except Exception:
                pass  # jamais laisser une exception arrêter la boucle de fond
            time.sleep(interval)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
