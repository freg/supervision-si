#!/usr/bin/env bash
# Images pour la pile Swarm (livraison #509) : `docker stack deploy` ne
# construit rien ; on construit sur le manager avec compose (comme
# aujourd'hui) puis on pousse dans un registre privé joignable des nœuds
# par le VPN (service registry:2 épinglé au manager, volume ./deploy/registry).
#   deploy/build-push.sh [service…]    (défaut : tous)
# SI_REGISTRY (défaut <wg manager>:5000) et SI_TAG (défaut latest) viennent du .env.
# Sur chaque nœud : /etc/docker/daemon.json {"insecure-registries":["<wg manager>:5000"]}
# (réseau privé chiffré par WireGuard) puis systemctl restart docker.
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
load_env .env
REG=${SI_REGISTRY:-127.0.0.1:5000}; TAG=${SI_TAG:-latest}
docker ps --format '{{.Names}}' | grep -q '^si-registry$' || docker run -d --restart=always --name si-registry -p 5000:5000 -v "$ROOT/deploy/registry:/var/lib/registry" registry:2
services=${*:-$(python3 -c "import yaml;d=yaml.safe_load(open('docker-compose.yml'));print(' '.join(n for n,s in d['services'].items() if s.get('build')))")}
docker compose build $services
for s in $services; do
  img=$(docker compose config --images "$s" 2>/dev/null | head -1 || true)
  [ -n "$img" ] || img=$(docker compose images -q "$s" | head -1)
  docker tag "$img" "$REG/si/$s:$TAG" && docker push "$REG/si/$s:$TAG" && echo "poussé $REG/si/$s:$TAG"
done
