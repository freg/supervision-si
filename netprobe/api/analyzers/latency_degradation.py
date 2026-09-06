"""
Analyseur "dégradation de latence" -- livraison #307. Compare les
échantillons smokeping RÉCENTS à une fenêtre PLUS ANCIENNE pour la
même cible -- signale une hausse significative de latence ou de
perte de paquets, jamais un seuil ABSOLU (une cible normalement à
80ms n'est pas anormale en soi, mais une cible qui PASSE de 20ms à
80ms l'est).

Nécessite un MINIMUM d'échantillons dans les DEUX fenêtres pour
comparer -- jamais un constat sur une donnée trop clairsemée (une
seule mesure récente contre une seule ancienne serait du bruit, pas
un signal).
"""
import store

MIN_SAMPLES_PER_WINDOW = 5
RECENT_WINDOW_SIZE = 10
BASELINE_WINDOW_SIZE = 10
# Hausse relative de latence au-delà de laquelle un constat est
# généré -- 50% choisi comme seuil raisonnable pour une DÉGRADATION
# réelle plutôt qu'une fluctuation normale, jamais vérifié en
# conditions réelles (aucune donnée de production disponible ici).
LATENCY_INCREASE_THRESHOLD = 0.5
# Hausse ABSOLUE de perte de paquets (en points de pourcentage) --
# ex. 5 -> 20% de perte déclenche un constat, mais 0% -> 2% ne le
# déclenche pas (bruit normal).
PACKET_LOSS_INCREASE_THRESHOLD = 15


def analyze(db_path):
    """Renvoie une liste de {target_id, severity, message} -- jamais
    d'écriture directe en base ici, seulement le CONSTAT -- c'est
    à l'appelant (analyzer_engine.py) de décider comment/où
    l'enregistrer, séparation claire entre calcul et effet de bord."""
    findings = []
    for target in store.list_targets(db_path, active_only=True):
        samples = store.list_samples(db_path, target["id"], limit=RECENT_WINDOW_SIZE + BASELINE_WINDOW_SIZE)
        # `list_samples` renvoie du plus RÉCENT au plus ANCIEN (voir
        # store.py) -- les `RECENT_WINDOW_SIZE` premiers sont donc la
        # fenêtre récente, le reste la fenêtre de référence.
        recent = samples[:RECENT_WINDOW_SIZE]
        baseline = samples[RECENT_WINDOW_SIZE:RECENT_WINDOW_SIZE + BASELINE_WINDOW_SIZE]
        if len(recent) < MIN_SAMPLES_PER_WINDOW or len(baseline) < MIN_SAMPLES_PER_WINDOW:
            continue

        recent_latencies = [s["latency_ms"] for s in recent if s["latency_ms"] is not None]
        baseline_latencies = [s["latency_ms"] for s in baseline if s["latency_ms"] is not None]
        if recent_latencies and baseline_latencies:
            recent_avg = sum(recent_latencies) / len(recent_latencies)
            baseline_avg = sum(baseline_latencies) / len(baseline_latencies)
            if baseline_avg > 0 and (recent_avg - baseline_avg) / baseline_avg > LATENCY_INCREASE_THRESHOLD:
                findings.append({
                    "target_id": target["id"], "severity": "warning",
                    "message": f"Latence en hausse pour {target['ip_address']} : {baseline_avg:.1f}ms -> {recent_avg:.1f}ms (+{(recent_avg / baseline_avg - 1) * 100:.0f}%)",
                })

        recent_loss = [s["packet_loss_percent"] for s in recent if s["packet_loss_percent"] is not None]
        baseline_loss = [s["packet_loss_percent"] for s in baseline if s["packet_loss_percent"] is not None]
        if recent_loss and baseline_loss:
            recent_loss_avg = sum(recent_loss) / len(recent_loss)
            baseline_loss_avg = sum(baseline_loss) / len(baseline_loss)
            if (recent_loss_avg - baseline_loss_avg) > PACKET_LOSS_INCREASE_THRESHOLD:
                findings.append({
                    "target_id": target["id"], "severity": "critical" if recent_loss_avg > 50 else "warning",
                    "message": f"Perte de paquets en hausse pour {target['ip_address']} : {baseline_loss_avg:.0f}% -> {recent_loss_avg:.0f}%",
                })
    return findings
