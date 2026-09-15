#!/usr/bin/env bash
# Déploiement de la pile Swarm (livraison #509) : cohortes vérifiées, stack
# générée depuis docker-compose.yml, variables du .env substituées, déploiement.
#   deploy/deploy.sh [nom de pile, défaut si]
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
python3 deploy/cohorts.py check
python3 deploy/cohorts.py stack
set -a; [ -f .env ] && . ./.env; set +a
docker stack deploy --compose-file deploy/generated/stack.yml --with-registry-auth --prune "${1:-si}"
echo "network-agent-api (network_mode: host) : sur son nœud, docker compose up -d network-agent-api"
