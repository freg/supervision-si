"""
Règle "aucun service découvert" -- livraison #388. Un appareil connu
depuis un moment (first_seen ancien) mais dont aucun port/service n'a
encore été identifié par network-agent (capture PASSIVE uniquement)
est un candidat naturel pour un scan ACTIF (nmap, via netprobe) --
l'orchestrateur ne lance rien lui-même ici, il SUGGÈRE l'étape
suivante avec le contexte nécessaire pour l'exécuter (voir
`suggested_action`/`action_params`).

Seuil de "depuis un moment" VOLONTAIREMENT généreux (30 minutes) --
un appareil qui vient d'apparaître peut simplement n'avoir pas encore
émis de trafic vers un port que network-agent aurait capté ; inutile
de suggérer un scan actif sur un signal encore trop frais pour être
significatif.
"""
from datetime import datetime, timezone

MIN_AGE_SECONDS = 30 * 60


def _age_seconds(iso_ts, now_ts):
    try:
        dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return now_ts - dt.timestamp()
    except (ValueError, TypeError):
        return None


def analyze(context, now_ts=None):
    """`context` : {"devices": [...], "services_by_device": {device_id: [...]}}
    (voir engine.py pour la construction). `now_ts` injectable pour
    les tests -- jamais dépendant de l'horloge réelle dans un test."""
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    findings = []
    for device in context["devices"]:
        services = context["services_by_device"].get(device["id"], [])
        if services:
            continue  # au moins un service deja connu -- rien a suggerer ici
        age = _age_seconds(device.get("first_seen"), now_ts)
        if age is None or age < MIN_AGE_SECONDS:
            continue
        ip = device.get("ip_address")
        if not ip:
            continue  # jamais de scan suggere sans IP a viser
        findings.append({
            "subject_type": "device",
            "subject_key": str(device["id"]),
            "severity": "info",
            "message": f"{ip} ({device.get('mac_address', '?')}) connu depuis plus de 30 min, aucun service détecté -- un scan actif pourrait révéler ce qu'il expose réellement.",
            "suggested_action": "netprobe_nmap_scan",
            "action_params": {"ip_address": ip, "device_id": device["id"]},
        })
    return findings
