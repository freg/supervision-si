"""
Règle "nouvel appareil détecté" -- livraison #388. Purement
INFORMATIF (severity="info", aucune action suggérée) -- signale
qu'un appareil vient d'apparaître dans les captures de network-agent,
pour une revue humaine ("est-ce attendu ?"), sans présumer que
c'est anormal.

Fenêtre VOLONTAIREMENT courte (15 minutes) -- au-delà, l'appareil
n'est plus vraiment "nouveau", la suggestion se fermerait
silencieusement au prochain passage (voir engine.py, une suggestion
non retrouvée VRAIE n'est jamais supprimée automatiquement, mais elle
cesse d'être RAFRAÎCHIE -- reste consultable comme trace historique).
"""
from datetime import datetime, timezone

MAX_AGE_SECONDS = 15 * 60


def _age_seconds(iso_ts, now_ts):
    try:
        dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return now_ts - dt.timestamp()
    except (ValueError, TypeError):
        return None


def analyze(context, now_ts=None):
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    findings = []
    for device in context["devices"]:
        age = _age_seconds(device.get("first_seen"), now_ts)
        if age is None or age > MAX_AGE_SECONDS or age < 0:
            continue
        ip = device.get("ip_address") or "IP inconnue"
        mac = device.get("mac_address", "?")
        hostname = device.get("hostname")
        label = f"{hostname} ({ip})" if hostname else ip
        findings.append({
            "subject_type": "device",
            "subject_key": str(device["id"]),
            "severity": "info",
            "message": f"Nouvel appareil détecté : {label} -- {mac}.",
            "suggested_action": None,
            "action_params": None,
        })
    return findings
