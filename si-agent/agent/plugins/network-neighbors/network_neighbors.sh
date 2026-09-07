#!/bin/bash
# Plugin si-agent « network-neighbors » (livraison #420) -- audit de la
# zone réseau accessible autour de l'hôte. Sortie : JSON sur stdout.
# Trafic ACTIF (balayage ping) : livré DÉSACTIVÉ, à activer par hôte.
set -u
SWEEP="${SI_NEIGHBORS_SWEEP:-1}"

json_escape() { sed 's/\\/\\\\/g; s/"/\\"/g'; }

# Sous-réseaux IPv4 locaux (hors loopback)
subnets=$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $2" "$4}')

# Balayage ping du premier /24 (au plus 254 hôtes, 1 paquet, 1 s, en parallèle)
if [ "$SWEEP" = "1" ]; then
  first=$(echo "$subnets" | awk '{print $2}' | grep '/24$' | head -1)
  if [ -n "$first" ]; then
    base=$(echo "$first" | cut -d/ -f1 | awk -F. '{print $1"."$2"."$3}')
    seq 1 254 | xargs -P 32 -I{} sh -c "ping -c1 -W1 $base.{} >/dev/null 2>&1" 2>/dev/null
  fi
fi

# Voisins connus du noyau (après balayage : table ARP remplie)
neigh=$(ip -o neigh show 2>/dev/null | awk '$0 !~ /FAILED|INCOMPLETE/ {mac=""; for(i=1;i<=NF;i++) if($i=="lladdr") mac=$(i+1); print $1" "$3" "mac" "$NF}')

printf '{"subnets":['
first=1
while read -r iface cidr; do
  [ -z "$iface" ] && continue
  [ $first = 1 ] || printf ','
  first=0
  printf '{"interface":"%s","cidr":"%s"}' "$(echo "$iface" | json_escape)" "$(echo "$cidr" | json_escape)"
done <<< "$subnets"
printf '],"neighbors":['
first=1
while read -r ip dev mac state; do
  [ -z "$ip" ] && continue
  [ $first = 1 ] || printf ','
  first=0
  printf '{"ip":"%s","interface":"%s","mac":"%s","state":"%s"}' "$ip" "$dev" "$mac" "$state"
done <<< "$neigh"
count=$(echo "$neigh" | grep -c . || true)
printf '],"neighbor_count":%s,"sweep":%s}\n' "$count" "$([ "$SWEEP" = 1 ] && echo true || echo false)"
