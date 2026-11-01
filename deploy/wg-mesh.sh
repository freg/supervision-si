#!/usr/bin/env bash
# VPN WireGuard entre les nœuds (livraison #509) : génère une configuration
# wg0 par nœud dans deploy/generated/wg/<nœud>.conf (clés privées incluses :
# dossier ignoré par git, à copier sur chaque nœud dans /etc/wireguard/wg0.conf
# puis `systemctl enable --now wg-quick@wg0`). Maillage complet : chaque nœud
# est pair de tous les autres ; un nœud sans endpoint (derrière NAT) initie
# vers ceux qui en ont un (PersistentKeepalive) ; deux nœuds du même site
# gardent le trafic direct via leur adresse LAN quand elle est renseignée.
# Prérequis : jq, wireguard-tools (wg) sur la machine qui génère.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
NODES=${1:-$HERE/nodes.json}
OUT=$HERE/generated/wg
[ -f "$NODES" ] || { echo "nodes.json absent (copier nodes.example.json)"; exit 1; }
command -v wg >/dev/null || { echo "wireguard-tools requis (wg)"; exit 1; }
command -v jq >/dev/null || { echo "jq requis"; exit 1; }
mkdir -p "$OUT"; chmod 700 "$OUT"
port=$(jq -r '.wg_port // 51820' "$NODES")
subnet=$(jq -r '.wg_subnet' "$NODES")
names=$(jq -r '.nodes[].name' "$NODES")
for n in $names; do
  [ -f "$OUT/$n.key" ] || wg genkey > "$OUT/$n.key"
  wg pubkey < "$OUT/$n.key" > "$OUT/$n.pub"
done
for n in $names; do
  addr=$(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .wg_address' "$NODES")
  ep_self=$(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .endpoint' "$NODES")
  lan_self=$(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .lan_address' "$NODES")
  zone_self=$(jq -r --arg n "$n" '.nodes[] | select(.name==$n) | .zone' "$NODES")
  {
    echo "[Interface]"; echo "Address = $addr/${subnet#*/}"; echo "ListenPort = $port"; echo "PrivateKey = $(cat "$OUT/$n.key")"
    for p in $names; do
      [ "$p" = "$n" ] && continue
      paddr=$(jq -r --arg n "$p" '.nodes[] | select(.name==$n) | .wg_address' "$NODES")
      pep=$(jq -r --arg n "$p" '.nodes[] | select(.name==$n) | .endpoint' "$NODES")
      plan=$(jq -r --arg n "$p" '.nodes[] | select(.name==$n) | .lan_address' "$NODES")
      pzone=$(jq -r --arg n "$p" '.nodes[] | select(.name==$n) | .zone' "$NODES")
      echo; echo "[Peer]"; echo "# $p"; echo "PublicKey = $(cat "$OUT/$p.pub")"; echo "AllowedIPs = $paddr/32"
      if [ -n "$pep" ]; then echo "Endpoint = $pep"; echo "PersistentKeepalive = 25"
      elif [ "$pzone" = "$zone_self" ] && [ -n "$plan" ]; then echo "Endpoint = $plan:$port"; fi
    done
  } > "$OUT/$n.conf"
  chmod 600 "$OUT/$n.conf"
  echo "$OUT/$n.conf"
done
echo "Sur chaque nœud : apt install wireguard ; copier <nœud>.conf en /etc/wireguard/wg0.conf ; systemctl enable --now wg-quick@wg0 ; ouvrir UDP/$port (OVH : pare-feu du Proxmox)."
