#!/usr/bin/env bash
# Régénère tout ce qui est propre à CE host (livraison #458) : HOST_IP et
# les URL qui la contenaient dans .env, certificat serveur (CA conservée),
# realm Keycloak, conf nginx, cert du relais si-proxy, EXPOSURE.json ;
# imprime ce qui reste à faire à la main (agents, shim, DNS, Keycloak).
#   ./scripts/regenerate-host.sh [--host-ip IP] [--hub-name NOM] [--rotate-tokens] [--skip Keycloak] [--dry-run]
# Sans --host-ip : détection (shared/detect-host-ip.sh). Jamais de rotation
# des sels/phrases de chiffrement (*_SALT, *_PASSPHRASE).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/full_backup.py" regenerate "$@"
