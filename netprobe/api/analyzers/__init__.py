"""
Registre des analyseurs disponibles -- livraison #307. Un
analyseur = un module exposant `analyze(db_path) -> list de
{target_id, severity, message}`. Ajouter un nouvel analyseur :
créer le module dans ce dossier, l'importer et l'ajouter à ANALYZERS
ci-dessous -- jamais de découverte automatique par scan de fichiers
(plus explicite, jamais un module oublié dans un coin qui tourne
sans qu'on le sache).
"""
from . import latency_degradation
from . import new_open_ports

ANALYZERS = {
    "latency_degradation": latency_degradation,
    "new_open_ports": new_open_ports,
}
