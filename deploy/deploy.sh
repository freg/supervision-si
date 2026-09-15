#!/usr/bin/env bash
# Déploiement de la pile Swarm (livraison #509) : cohortes vérifiées, stack
# générée depuis docker-compose.yml, variables du .env substituées, déploiement.
#   deploy/deploy.sh [nom de pile, défaut si]
load_env() {  # lit .env clé par clé (le fichier n'est pas sourçable : valeurs avec espaces non citées)
  local k v
  while IFS= read -r line; do
    k=${line%%=*}; v=${line#*=}
    [[ $k =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    v=${v%\"}; v=${v#\"}; v=${v%\'}; v=${v#\'}
    export "$k=$v"
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${1:-.env}" 2>/dev/null || true)
}
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
python3 deploy/cohorts.py check
python3 deploy/cohorts.py stack
load_env .env
docker stack deploy --compose-file deploy/generated/stack.yml --with-registry-auth --prune "${1:-si}"
echo "network-agent-api (network_mode: host) : sur son nœud, docker compose up -d network-agent-api"
