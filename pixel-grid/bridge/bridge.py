"""
Pont pixel-grid -> Supervision SI.

Toutes les BRIDGE_INTERVAL_SECONDS, pour chaque type connu de
pixel-grid : récupère les événements de la fenêtre glissante récente
(BRIDGE_WINDOW_DAYS), les convertit en GeoJSON (résolution de la
localisation via la table de géolocalisation, repli sur la position
par défaut si non mappée), et pousse le résultat vers l'API de
supervision comme source `pixelgrid_<type>`.

Remplace intégralement la source à chaque cycle (cohérent avec le
principe déjà en place pour `pipeline/` : /ingest écrase, ne fusionne
pas).
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pixel-grid-bridge")

# Journal PARTAGÉ (livraison #351, backlog item 8) -- même motif que
# tous les services Flask de ce projet (voir shared/log_buffer.py,
# #145), mais SANS route /logs ici : ce script n'est pas un serveur
# HTTP (aucun Flask, juste une boucle de synchronisation périodique)
# -- memory-api lit directement la clé Memcached, jamais besoin d'un
# endpoint /logs pour ça. Handler attaché au logger RACINE, capture
# donc aussi les logs du module `requests` -- comportement identique
# à ce que font les autres services de ce projet.
try:
    from log_buffer import make_shared_log_handler
except ImportError:
    make_shared_log_handler = None

try:
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    _MemcacheClient = None

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


if make_shared_log_handler and _MemcacheClient:
    _log_handler = make_shared_log_handler(
        "pixel-grid-bridge", get_memcache_client,
        buffer_size=int(os.environ.get("LOG_BUFFER_SIZE", "200")),
        capture_level=os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper(),
    )
    logging.getLogger().addHandler(_log_handler)

PIXEL_GRID_API_URL = os.environ.get("PIXEL_GRID_API_URL", "http://pixel-grid-api:5000")
SUPERVISION_API_URL = os.environ.get("SUPERVISION_API_URL", "http://api:5000")
BRIDGE_INTERVAL_SECONDS = int(os.environ.get("BRIDGE_INTERVAL_SECONDS", "60"))
BRIDGE_WINDOW_DAYS = int(os.environ.get("BRIDGE_WINDOW_DAYS", "30"))
BRIDGE_MAX_POINTS_PER_TYPE = int(os.environ.get("BRIDGE_MAX_POINTS_PER_TYPE", "5000"))

DEFAULT_LOCATION_KEY = "__default__"


def fetch_types():
    try:
        r = requests.get(f"{PIXEL_GRID_API_URL}/types", timeout=10)
        r.raise_for_status()
        return [t["type"] for t in r.json().get("types", [])]
    except requests.RequestException as exc:
        logger.warning("Échec fetch_types : %s", exc)
        return []


def fetch_geolocations():
    """Renvoie ({localisation: (lat, lon)}, (default_lat, default_lon) ou None)."""
    try:
        r = requests.get(f"{PIXEL_GRID_API_URL}/geolocations", timeout=10)
        r.raise_for_status()
        mapping = {}
        default = None
        for g in r.json().get("geolocations", []):
            if g["latitude"] is None or g["longitude"] is None:
                continue
            if g.get("is_default"):
                default = (g["latitude"], g["longitude"])
            else:
                mapping[g["localisation"]] = (g["latitude"], g["longitude"])
        return mapping, default
    except requests.RequestException as exc:
        logger.warning("Échec fetch_geolocations : %s", exc)
        return {}, None


def fetch_events(event_type, start_iso, end_iso):
    try:
        r = requests.get(
            f"{PIXEL_GRID_API_URL}/events",
            params={"type": event_type, "start": start_iso, "end": end_iso, "limit": BRIDGE_MAX_POINTS_PER_TYPE},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("events", [])
    except requests.RequestException as exc:
        logger.warning("Échec fetch_events(%s) : %s", event_type, exc)
        return []


def build_geojson(events, geolocation_map, default_coords):
    features = []
    skipped_no_location = 0

    for event in events:
        data = event.get("data") or {}
        loc_path = data.get("localisation") if isinstance(data, dict) else None

        coords = geolocation_map.get(loc_path) if loc_path else None
        used_default = False
        if coords is None:
            coords = default_coords
            used_default = True

        if coords is None:
            skipped_no_location += 1
            continue

        lat, lon = coords
        properties = {
            "ts": event["ts"],
            "iso": event["iso"],
            "valeur": event["valeur"],
            "nom": event["nom"],
            "localisation_source": loc_path,
            "position_par_defaut": used_default,
        }
        if isinstance(data, dict):
            properties.update(data)

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": properties,
            }
        )

    return {"type": "FeatureCollection", "features": features}, skipped_no_location


def push_to_supervision(source_name, geojson):
    try:
        r = requests.post(f"{SUPERVISION_API_URL}/ingest/{source_name}", json=geojson, timeout=30)
        r.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("Échec push vers %s : %s", source_name, exc)
        return False


def run_cycle():
    types = fetch_types()
    if not types:
        logger.info("Aucun type pixel-grid trouvé pour l'instant.")
        return

    geolocation_map, default_coords = fetch_geolocations()
    if default_coords is None:
        logger.info(
            "Position par défaut non configurée (voir onglet Géolocalisation) — "
            "les événements sans localisation connue seront ignorés ce cycle."
        )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=BRIDGE_WINDOW_DAYS)
    start_iso, end_iso = start.isoformat(), end.isoformat()

    for event_type in types:
        events = fetch_events(event_type, start_iso, end_iso)
        geojson, skipped = build_geojson(events, geolocation_map, default_coords)
        source_name = f"pixelgrid_{event_type}"

        if push_to_supervision(source_name, geojson):
            logger.info(
                "%s : %d événement(s) -> %d feature(s) poussée(s) vers '%s' (%d ignoré(s), pas de localisation)",
                event_type, len(events), len(geojson["features"]), source_name, skipped,
            )


def main():
    logger.info(
        "Démarrage du pont pixel-grid -> Supervision SI — intervalle=%ss, fenêtre=%sj, max=%s pts/type",
        BRIDGE_INTERVAL_SECONDS, BRIDGE_WINDOW_DAYS, BRIDGE_MAX_POINTS_PER_TYPE,
    )
    while True:
        try:
            run_cycle()
        except Exception:  # noqa: BLE001 — un cycle raté ne doit pas arrêter le service
            logger.exception("Erreur pendant le cycle de synchronisation")
        time.sleep(BRIDGE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
