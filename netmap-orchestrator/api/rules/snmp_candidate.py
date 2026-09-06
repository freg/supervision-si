"""
Règle "candidat SNMP" -- livraison #388. Un appareil dont
network-agent a capté du trafic sur le port 161 (SNMP standard)
répond probablement aux requêtes SNMP -- candidat naturel pour un
enregistrement comme cible dans `snmp-api`, permettant l'usage des
routes /query, /walk-interfaces, /traffic-rate (#384) sans deviner à
l'aveugle quels appareils du réseau parlent SNMP.

Port 161 UNIQUEMENT (SNMP standard) -- 162 (traps SNMP, appareil qui
ENVOIE des alertes, pas qui RÉPOND aux requêtes) volontairement exclu
ici, sémantique différente.
"""
SNMP_PORT = 161


def analyze(context, now_ts=None):
    """`now_ts` accepté mais inutilisé -- même signature que les
    autres règles pour un appel uniforme depuis engine.py."""
    findings = []
    for device in context["devices"]:
        services = context["services_by_device"].get(device["id"], [])
        has_snmp = any(s.get("port") == SNMP_PORT for s in services)
        if not has_snmp:
            continue
        ip = device.get("ip_address")
        if not ip:
            continue
        findings.append({
            "subject_type": "device",
            "subject_key": str(device["id"]),
            "severity": "info",
            "message": f"{ip} ({device.get('mac_address', '?')}) a du trafic observé sur le port SNMP (161) -- probablement interrogeable, candidat pour un enregistrement dans snmp-api.",
            "suggested_action": "snmp_register_target",
            "action_params": {"ip_address": ip, "device_id": device["id"]},
        })
    return findings
