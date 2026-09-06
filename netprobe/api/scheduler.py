"""
Ordonnanceur smokeping (livraison #297) -- une PASSE testable en
isolation (`run_smokeping_tick`), enveloppée dans une boucle de fond
par `start_background_loop` (appelée depuis app.py). Même motif déjà
établi dans ce projet (voir vigilance/README.md, "Thread de fond, un
passage toutes les X secondes") -- pas réinventé, réutilisé.

Respecte le système de contrôle (#295) à CHAQUE cible individuellement
: désactivée -> jamais sondée ; hors fenêtre horaire -> jamais sondée
CETTE fois-ci (revérifié au prochain tick) ; fréquence -> une cible
n'est sondée que si `frequency_seconds` s'est bien écoulé depuis son
dernier échantillon, jamais plus souvent même si le tick est plus
rapide que la fréquence configurée.
"""
import logging
import threading
import time
from datetime import datetime, timezone

import ping_probe
import store
import analyzer_engine

_log = logging.getLogger("netprobe_scheduler")

# Fréquence du TICK lui-même -- indépendante de frequency_seconds par
# cible (qui peut être plus longue). Un tick plus fin que la
# fréquence la plus courte configurée permet de rester réactif sans
# sur-solliciter les cibles dont la fréquence est plus longue (la
# vérification "assez de temps écoulé ?" ci-dessous s'en charge).
DEFAULT_TICK_SECONDS = 15


def _last_sample_ts(db_path, target_id):
    """Horodatage (epoch) du dernier échantillon pour cette cible, ou
    None si aucun -- une cible jamais sondée est toujours due."""
    samples = store.list_samples(db_path, target_id, limit=1)
    if not samples:
        return None
    sampled_at = samples[0]["sampled_at"]
    try:
        dt = datetime.strptime(sampled_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def run_smokeping_tick(db_path, now_ts=None, now_hour=None):
    """Une passe -- pour CHAQUE cible active, sonde si (1) smokeping
    est activé pour elle (config effective, précise ou globale),
    (2) l'heure actuelle tombe dans sa fenêtre horaire éventuelle,
    (3) assez de temps s'est écoulé depuis son dernier échantillon.
    `now_ts`/`now_hour` injectables pour les tests -- jamais dépendant
    de l'horloge réelle dans le test, résultat reproductible.
    Renvoie {"checked", "sampled", "skipped"} pour observabilité."""
    if now_ts is None:
        now_ts = time.time()
    if now_hour is None:
        now_hour = datetime.now(timezone.utc).hour

    checked = 0
    sampled = 0
    skipped = 0
    for target in store.list_targets(db_path, active_only=True):
        checked += 1
        config = store.get_effective_config(db_path, "smokeping", target_id=target["id"])
        if not config.get("enabled"):
            skipped += 1
            continue
        if not store.is_within_schedule(config, now_hour):
            skipped += 1
            continue
        frequency = config.get("frequency_seconds")
        if frequency is None:
            # Pas de fréquence définie -- jamais sondé automatiquement
            # (cohérent avec la convention "désactivé par défaut" du
            # système de contrôle, #295).
            skipped += 1
            continue
        last_ts = _last_sample_ts(db_path, target["id"])
        if last_ts is not None and (now_ts - last_ts) < frequency:
            skipped += 1
            continue

        result = ping_probe.ping_once(target["ip_address"])
        store.record_sample(
            db_path, target["id"],
            success=result["success"], latency_ms=result["latency_ms"],
            packet_loss_percent=result["packet_loss_percent"], error=result["error"],
        )
        sampled += 1
        _log.debug("run_smokeping_tick : cible %s (%s) -- %s", target["id"], target["ip_address"], "OK" if result["success"] else f"échec ({result['error']})")

    return {"checked": checked, "sampled": sampled, "skipped": skipped}


def _last_analyzer_run_ts(db_path):
    """Horodatage (epoch) du DERNIER constat toutes analyseurs
    confondus -- réutilise l'état déjà persisté (analysis_results)
    plutôt qu'une variable de suivi séparée qui ne survivrait pas à
    un redémarrage. Approximation acceptable : si le tout dernier
    tick n'a produit AUCUN constat, cette fonction regarde un peu
    plus loin en arrière que le tick réel -- sans conséquence, un
    analyseur qui tourne un peu plus souvent que sa fréquence
    minimale n'est jamais un problème (contrairement à moins
    souvent)."""
    results = store.list_analysis_results(db_path, limit=1)
    if not results:
        return None
    try:
        dt = datetime.strptime(results[0]["detected_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def run_analyzer_tick(db_path, now_ts=None, now_hour=None):
    """Exécute TOUS les analyseurs si le système de contrôle
    l'autorise -- réutilise le même "analyzer" déjà présent dans
    PROBE_TYPES (#295), configuration GLOBALE uniquement (jamais par
    cible : un analyseur regarde l'ensemble des cibles lui-même).
    Renvoie {\"ran\": bool, \"results\": {...} | None}."""
    if now_ts is None:
        now_ts = time.time()
    if now_hour is None:
        now_hour = datetime.now(timezone.utc).hour

    config = store.get_effective_config(db_path, "analyzer", target_id=None)
    if not config.get("enabled"):
        return {"ran": False, "results": None}
    if not store.is_within_schedule(config, now_hour):
        return {"ran": False, "results": None}
    frequency = config.get("frequency_seconds")
    if frequency is None:
        return {"ran": False, "results": None}
    last_ts = _last_analyzer_run_ts(db_path)
    if last_ts is not None and (now_ts - last_ts) < frequency:
        return {"ran": False, "results": None}

    results = analyzer_engine.run_all_analyzers(db_path)
    _log.debug("run_analyzer_tick : terminé -- %s", results)
    return {"ran": True, "results": results}


def start_background_loop(db_path, tick_seconds=DEFAULT_TICK_SECONDS, stop_event=None):
    """Boucle de fond -- appelée depuis app.py dans un thread daemon.
    `stop_event` (threading.Event) permet un arrêt propre en test,
    jamais un thread qui tourne indéfiniment dans un harnais de
    test."""
    while stop_event is None or not stop_event.is_set():
        try:
            result = run_smokeping_tick(db_path)
            if result["sampled"] > 0:
                _log.debug("start_background_loop : tick smokeping terminé -- %s", result)
        except Exception as exc:  # noqa: BLE001 -- un tick en échec ne doit jamais arrêter la boucle
            _log.debug("start_background_loop : tick smokeping en échec, on continue -- %s", exc)
        try:
            analyzer_result = run_analyzer_tick(db_path)
            if analyzer_result["ran"]:
                _log.debug("start_background_loop : tick analyseurs terminé -- %s", analyzer_result)
        except Exception as exc:  # noqa: BLE001 -- même raisonnement, jamais bloquant pour le reste de la boucle
            _log.debug("start_background_loop : tick analyseurs en échec, on continue -- %s", exc)
        if stop_event is not None:
            stop_event.wait(tick_seconds)
        else:
            time.sleep(tick_seconds)


def start_background_thread(db_path, tick_seconds=DEFAULT_TICK_SECONDS):
    """Démarre la boucle dans un thread daemon -- jamais bloquant au
    démarrage de l'application (voir app.py)."""
    thread = threading.Thread(target=start_background_loop, args=(db_path, tick_seconds), daemon=True)
    thread.start()
    return thread
