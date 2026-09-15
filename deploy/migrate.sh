#!/usr/bin/env bash
# Migration d'une cohorte vers un autre nœud (livraison #509), depuis le manager :
#   deploy/migrate.sh <cohorte> <nœud cible> [nœud source]
# 1. arrêt des services de la cohorte (replicas 0) ; 2. copie des dossiers de
# données (bind mounts) du nœud source vers la cible par rsync sur le VPN
# (même chemin absolu du dépôt sur les deux nœuds) ; 3. déplacement du label
# si.cohort.<c> ; 4. redéploiement. Sauvegarde totale conseillée avant.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
c=$1; target=$2; source=${3:-$(docker node ls --format '{{.Hostname}}' | while read -r n; do docker node inspect "$n" --format '{{index .Spec.Labels "si.cohort.'"$c"'"}}' | grep -q true && echo "$n"; done | head -1)}
[ -n "$source" ] || { echo "nœud source introuvable pour $c"; exit 1; }
services=$(python3 -c "import json;print(' '.join(next(x for x in json.load(open('deploy/cohorts.json'))['cohorts'] if x['name']=='$c')['services']))")
dirs=$(python3 - <<PY
import yaml
d=yaml.safe_load(open('docker-compose.yml'))['services']
out=set()
for s in "$services".split():
    for v in d.get(s,{}).get('volumes') or []:
        src=v.split(':')[0] if isinstance(v,str) else v.get('source','')
        if src.startswith('./') or src.startswith('\${'): out.add(src)
print(' '.join(sorted(out)))
PY
)
echo "cohorte $c : $source -> $target ; services : $services ; données : $dirs"
read -r -p "Continuer ? (oui) " ok; [ "$ok" = "oui" ] || exit 1
for s in $services; do docker service scale "si_$s=0" 2>/dev/null || true; done
src_wg=$(docker node inspect "$source" --format '{{.Status.Addr}}'); dst_wg=$(docker node inspect "$target" --format '{{.Status.Addr}}')
for d in $dirs; do
  dd=$(echo "$d" | sed "s#^\./##")
  ssh "$src_wg" "cd '$ROOT' && tar czf - '$dd'" | ssh "$dst_wg" "mkdir -p '$ROOT' && cd '$ROOT' && tar xzf -"
done
docker node update --label-rm "si.cohort.$c" "$source"
docker node update --label-add "si.cohort.$c=true" "$target"
deploy/deploy.sh
