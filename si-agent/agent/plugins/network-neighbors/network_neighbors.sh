#!/bin/bash
# Plugin si-agent « network-neighbors » (livraison #420) -- audit de la
# zone réseau accessible autour de l'hôte. Sortie : JSON sur stdout.
# Trafic ACTIF (balayage ping) : livré DÉSACTIVÉ, à activer par hôte.
# Linux (iproute2) ET macOS (ifconfig/arp/ndp) -- premier Mac réel : le
# script d'origine n'utilisait que `ip`, absent de macOS (résultat vide).
set -u
SWEEP="${SI_NEIGHBORS_SWEEP:-1}"
OS="$(uname -s)"

json_escape() { sed 's/\\/\\\\/g; s/"/\\"/g'; }

# --- ping : timeout par OS (-W = secondes sous Linux iputils, millisecondes sous macOS)
if [ "$OS" = "Darwin" ]; then PING_WAIT="-W1000"; else PING_WAIT="-W1"; fi

if [ "$OS" = "Darwin" ]; then
  # Sous-réseaux IPv4 locaux : ifconfig, netmask hexa -> longueur de préfixe
  subnets=$(ifconfig -a 2>/dev/null | awk '
    /^[a-zA-Z0-9_]+:/ { iface = substr($1, 1, length($1)-1); next }
    iface != "lo0" && $1 == "inet" && $3 == "netmask" {
      hex = substr($4, 3); bits = 0
      for (i = 1; i <= length(hex); i++) {
        c = substr(hex, i, 1)
        if (c >= "0" && c <= "9") v = c + 0
        else v = index("abcdef", c) + 9
        bits += substr("0112122312232334", v + 1, 1) + 0
      }
      print iface, $2 "/" bits
    }')
  # Voisins ARP (IPv4) : `arp -an` ; IPv6 : `ndp -an` (absent sur tous les
  # Mac -> ignoré silencieusement). Entrées incomplètes (mac nul) écartées.
  neigh=$( { arp -an 2>/dev/null; ndp -an 2>/dev/null; } | awk '
    function padmac(m,   parts, i, out) {
      n = split(m, parts, ":"); out = ""
      for (i = 1; i <= n; i++) out = out (i > 1 ? ":" : "") sprintf("%02x", ("0x" parts[i]) + 0)
      return out
    }
    $1 == "?" {
      ip = $2; gsub(/[()]/, "", ip)
      if ($3 != "at") next
      mac = $4
      if (mac == "(incomplete)" || mac == "0:0:0:0:0:0" || mac == "0:0:0:0:0:0%*") next
      iface = ""; for (i = 5; i <= NF; i++) if ($i == "on") iface = $(i + 1)
      print ip, iface, padmac(mac), "REACHABLE"
    }')
else
  # Sous-réseaux IPv4 locaux (hors loopback)
  subnets=$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $2" "$4}')

  # Voisins connus du noyau (après balayage : table ARP remplie)
  neigh=$(ip -o neigh show 2>/dev/null | awk '$0 !~ /FAILED|INCOMPLETE/ {mac=""; for(i=1;i<=NF;i++) if($i=="lladdr") mac=$(i+1); print $1" "$3" "mac" "$NF}')
fi

# Balayage ping du premier /24 (au plus 254 hôtes, 1 paquet, ~1 s, en parallèle)
if [ "$SWEEP" = "1" ]; then
  first=$(echo "$subnets" | awk '{print $2}' | grep '/24$' | head -1)
  if [ -n "$first" ]; then
    base=$(echo "$first" | cut -d/ -f1 | awk -F. '{print $1"."$2"."$3}')
    seq 1 254 | xargs -P 32 -I{} sh -c "ping -c1 $PING_WAIT $base.{} >/dev/null 2>&1" 2>/dev/null
    # relecture des voisins après le balayage (table ARP remplie)
    if [ "$OS" = "Darwin" ]; then
      neigh=$( { arp -an 2>/dev/null; ndp -an 2>/dev/null; } | awk '
        function padmac(m,   parts, i, out) {
          n = split(m, parts, ":"); out = ""
          for (i = 1; i <= n; i++) out = out (i > 1 ? ":" : "") sprintf("%02x", ("0x" parts[i]) + 0)
          return out
        }
        $1 == "?" {
          ip = $2; gsub(/[()]/, "", ip)
          if ($3 != "at") next
          mac = $4
          if (mac == "(incomplete)" || mac == "0:0:0:0:0:0") next
          iface = ""; for (i = 5; i <= NF; i++) if ($i == "on") iface = $(i + 1)
          print ip, iface, padmac(mac), "REACHABLE"
        }')
    else
      neigh=$(ip -o neigh show 2>/dev/null | awk '$0 !~ /FAILED|INCOMPLETE/ {mac=""; for(i=1;i<=NF;i++) if($i=="lladdr") mac=$(i+1); print $1" "$3" "mac" "$NF}')
    fi
  fi
fi

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
