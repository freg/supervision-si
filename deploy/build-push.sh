#!/usr/bin/env bash
# Images pour la pile Swarm (livraison #509) : `docker stack deploy` ne
# construit rien ; on construit sur le manager avec compose (comme
# aujourd'hui) puis on pousse dans un registre privé joignable des nœuds
# par le VPN (service registry:2 épinglé au manager, volume ./deploy/registry).
#   deploy/build-push.sh [service…]    (défaut : tous)
# SI_REGISTRY (défaut <wg manager>:5000) et SI_TAG (défaut latest) viennent du .env.
# Sur chaque nœud : /etc/docker/daemon.json {"insecure-registries":["<wg manager>:5000"]}
# (réseau privé chiffré par WireGuard) puis systemctl restart docker.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
set -a; [ -f .env ] && . ./.env; set +a
REG=${SI_REGISTRY:-127.0.0.1:5000}; TAG=${SI_TAG:-latest}
docker ps --format '{{.Names}}' | grep -q '^si-registry$' || docker run -d --restart=always --name si-registry -p 5000:5000 -v "$ROOT/deploy/registry:/var/lib/registry" registry:2
services=${*:-$(python3 -c "import yaml;d=yaml.safe_load(open('docker-compose.yml'));print(' '.join(n for n,s in d['services'].items() if s.get('build')))")}
docker compose build $services
for s in $services; do
  img=$(docker compose config --images "$s" 2>/dev/null | head -1 || true)
  [ -n "$img" ] || img=$(docker compose images -q "$s" | head -1)
  docker tag "$img" "$REG/si/$s:$TAG" && docker push "$REG/si/$s:$TAG" && echo "poussé $REG/si/$s:$TAG"
done
