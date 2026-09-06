"""
Pipeline d'agrégation — squelette minimal.
Responsabilité unique : calculer les données d'une source et les pousser
vers l'API via HTTP. Ne connaît rien de Memcached ni du stockage fichier :
c'est le rôle de l'API, pas le sien (source unique d'écriture côté API).

Ce fichier simule une première source ("supervision_demo") avec un point
GeoJSON factice, à remplacer par la vraie logique d'agrégation
(scripts convertis depuis les notebooks Jupyter de prototypage).
"""
import os
import time
import logging

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pipeline")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:5000")
PUSH_INTERVAL_SECONDS = int(os.environ.get("PUSH_INTERVAL_SECONDS", "30"))
SOURCE_NAME = os.environ.get("SOURCE_NAME", "supervision_demo")


def aggregate_source_data() -> dict:
    """
    Placeholder de la logique d'agrégation réelle.
    À remplacer par le script converti depuis le prototypage Jupyter :
    lecture de la source, transformation en GeoJSON, contrôle de qualité.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]},
                "properties": {
                    "label": "Site de démonstration",
                    "status": "ok",
                    "generated_at": time.time(),
                },
            }
        ],
    }


def push_to_api(payload: dict) -> bool:
    url = f"{API_BASE_URL}/ingest/{SOURCE_NAME}"
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        # Le pipeline ne doit jamais crasher parce que l'API est indisponible
        # ponctuellement : on log et on retente au prochain cycle.
        logger.warning("Échec du push vers %s : %s", url, exc)
        return False
    # Livraison #287 -- ".json()" isolé du bloc ci-dessus : sert
    # UNIQUEMENT au message de log, un corps non-JSON (2xx quand même)
    # ne doit jamais faire remonter un push HTTP réellement réussi
    # comme un échec.
    try:
        logger.info("Push réussi vers %s : %s", url, response.json())
    except ValueError:
        logger.info("Push réussi vers %s (réponse non-JSON, ignorée)", url)
    return True


def run_forever():
    logger.info(
        "Démarrage du pipeline — source=%s, intervalle=%ss, cible=%s",
        SOURCE_NAME, PUSH_INTERVAL_SECONDS, API_BASE_URL,
    )
    while True:
        payload = aggregate_source_data()
        push_to_api(payload)
        time.sleep(PUSH_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
