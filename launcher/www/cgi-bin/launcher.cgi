#!/usr/bin/env python3
"""CGI réel -- exécuté par le serveur HTTP CGI (voir launcher/serve.py)
à chaque requête sur /cgi-bin/launcher.cgi. Volontairement MINCE :
toute la logique (cartographie des services, décision HTTP vs Docker,
dispatch des actions) vit dans launcher_core.py, testée séparément
sans avoir besoin d'un vrai serveur CGI ni d'un vrai Docker. Ce
fichier ne fait que le pont avec le PROTOCOLE CGI lui-même (variables
d'environnement, en-têtes de sortie).

Restreint au réseau local -- même raisonnement de sécurité que
vault-admin-api (LAN uniquement) : ce CGI peut arrêter/démarrer
N'IMPORTE QUEL service du stack, jamais exposé publiquement.
"""
import ipaddress
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launcher_core as lc

DEFAULT_ALLOWED_CIDRS = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"
# Répertoire du projet MONTÉ en lecture seule (voir docker-compose.yml,
# service "launcher") -- volontairement PAS "/app" (qui accueille les
# fichiers du serveur web lui-même, voir Dockerfile), pour ne jamais
# risquer de collision entre les deux montages.
COMPOSE_DIR = "/compose-project"


def is_ip_allowed(ip_str):
    """Même garde-fou que vault-admin-api (voir vault/admin-api/app.py)
    -- redondant en apparence, mais chaque service LAN-only reste
    responsable de son propre contrôle, jamais une confiance implicite
    envers un service voisin."""
    allowed_cidrs = os.environ.get("LAUNCHER_ALLOWED_CIDRS", DEFAULT_ALLOWED_CIDRS)
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for cidr in allowed_cidrs.split(","):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            if ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def real_http_check(service, port, timeout=2):
    """N'IMPORTE QUEL code de statut HTTP compte comme "vivant" (même
    404/500) -- seule une erreur de CONNEXION (rien n'écoute sur ce
    port) compte comme "arrêté". Le but est juste de savoir si le
    processus répond, pas de vérifier qu'il répond correctement."""
    url = f"http://{service}:{port}/"
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # a répondu, même en erreur -- bien vivant
    except Exception:
        return False


def real_docker_state_check(service):
    """Repli pour les services sans interface HTTP -- voir
    launcher_core.py, SERVICE_PORTS. Seul moyen de savoir s'ils
    tournent."""
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "-a", "--format", "json", service],
            capture_output=True, text=True, cwd=COMPOSE_DIR, timeout=10,
        )
    except Exception:
        return False
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("State") == "running":
            return True
    return False


def real_docker_action(service, action):
    subprocess.run(["docker", "compose", action, service], cwd=COMPOSE_DIR, timeout=30, check=False)


def main():
    remote_addr = os.environ.get("REMOTE_ADDR", "")
    query = urllib.parse.parse_qs(os.environ.get("QUERY_STRING", ""))
    service = query.get("service", [""])[0]
    action = query.get("action", [""])[0]
    gateway_port = os.environ.get("LAUNCHER_GATEWAY_PORT", "")

    print("Content-Type: application/json")
    print()

    if not is_ip_allowed(remote_addr):
        print(json.dumps({"error": "accès refusé (hors réseau local)"}))
        return

    result = lc.dispatch_action(
        service, action,
        http_check=real_http_check,
        docker_state_check=real_docker_state_check,
        docker_action=real_docker_action,
        gateway_port=int(gateway_port) if gateway_port.isdigit() else None,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
