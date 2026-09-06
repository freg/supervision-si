"""
Analyseur "nouveaux ports ouverts" -- livraison #307. Compare le
DERNIER scan nmap d'une cible au PRÉCÉDENT -- signale tout port
apparu OUVERT qui ne l'était pas avant. Pertinence sécurité directe :
un nouveau service qui démarre sur une cible surveillée mérite un
constat, que ce soit légitime (déploiement volontaire) ou pas.

Nécessite AU MOINS deux scans pour la même cible pour comparer --
jamais de constat sur un premier scan (rien à comparer).
"""
import store


def analyze(db_path):
    """Renvoie une liste de {target_id, severity, message} -- même
    contrat que latency_degradation.analyze(), voir ce module pour
    le raisonnement sur la séparation calcul/effet de bord."""
    findings = []
    for target in store.list_targets(db_path, active_only=True):
        scans = store.list_nmap_scans(db_path, target["id"], limit=2)
        # `list_nmap_scans` renvoie du plus RÉCENT au plus ANCIEN.
        if len(scans) < 2:
            continue
        latest, previous = scans[0], scans[1]
        if not latest["success"] or not previous["success"]:
            continue  # jamais de comparaison sur un scan en echec -- port manquant y signifierait juste "scan rate", pas "port ferme"

        latest_ports = {p["port"] for p in latest["open_ports"]}
        previous_ports = {p["port"] for p in previous["open_ports"]}
        new_ports = latest_ports - previous_ports
        if new_ports:
            port_list = ", ".join(str(p) for p in sorted(new_ports))
            findings.append({
                "target_id": target["id"], "severity": "warning",
                "message": f"Nouveau(x) port(s) ouvert(s) sur {target['ip_address']} : {port_list}",
            })
    return findings
