#!/usr/bin/env bash
# Swarm sur le VPN (livraison #509). Sur le manager :
#   deploy/swarm-init.sh manager <adresse wg du manager>
# puis sur chaque worker, avec le jeton affiché :
#   deploy/swarm-init.sh worker <adresse wg du manager> <jeton> <adresse wg locale>
# Enfin, sur le manager, les labels depuis nodes.json :
#   deploy/swarm-init.sh labels
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
case "${1:-}" in
  manager)
    docker swarm init --advertise-addr "$2" --listen-addr "$2:2377" --data-path-addr "$2"
    docker network create --driver overlay --attachable --opt encrypted "${SUPERVISION_SI_NETWORK_NAME:-supervision-si-net}" || true
    echo "Jeton worker :"; docker swarm join-token -q worker ;;
  worker)
    docker swarm join --token "$3" --advertise-addr "$4" --data-path-addr "$4" "$2:2377" ;;
  labels)
    NODES=${2:-$HERE/nodes.json}
    for n in $(jq -r '.nodes[].name' "$NODES"); do
      zone=$(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .zone' "$NODES")
      edge=$(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .edge // false' "$NODES")
      args="--label-add si.zone=$zone --label-add si.edge=$edge"
      for c in $(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .cohorts[]' "$NODES"); do args="$args --label-add si.cohort.$c=true"; done
      docker node update $args "$n" && echo "$n : $args"
    done ;;
  *) sed -n 2,8p "$0" ;;
esac
