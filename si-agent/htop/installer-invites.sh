#!/bin/sh
# #802 : installe l'émetteur si-htop DANS les CT d'un Proxmox (htop de chaque CT : ses processus, sa mémoire), en root
# sur le nœud, après installer-emetteur.sh --transit. Rien à saisir : fichiers et clé poussés par pct push, émetteurs
# dirigés vers le relais local du nœud (IP de vmbr0, port 8399), qui les renvoie au relais central.
#   sh installer-invites.sh                 (tous les CT en marche)
#   sh installer-invites.sh --ids 102,119   (ces CT seulement)
# CT sans python3 (3.4 ou plus) ni systemd : ignoré et signalé, rien n'y est installé.
set -eu
ICI=$(cd "$(dirname "$0")" && pwd)
IDS="" ; RELAIS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ids) IDS="$2"; shift 2 ;;
    --relais) RELAIS="$2"; shift 2 ;;
    *) echo "option inconnue : $1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "à lancer en root sur le Proxmox" >&2; exit 2; }
command -v pct >/dev/null || { echo "pct absent : à lancer sur un Proxmox" >&2; exit 2; }
[ -s /etc/si-htop/cle ] || { echo "émetteur du nœud absent : sh installer-emetteur.sh --relais <relais>:8399 --transit d'abord" >&2; exit 2; }
systemctl is-active --quiet si-htop-transit || echo "ATTENTION : si-htop-transit inactif (installer-emetteur.sh ... --transit)"
[ -n "$RELAIS" ] || RELAIS="$(ip -4 -o addr show vmbr0 | awk '{print $4}' | cut -d/ -f1 | head -n 1):8399"
[ -n "$IDS" ] || IDS=$(pct list | awk 'NR>1 && $2=="running" {print $1}')
for id in $(echo "$IDS" | tr ',' ' '); do
  nom=$(pct config "$id" | awk '/^hostname:/ {print $2}')
  if ! pct exec "$id" -- sh -c 'command -v python3 >/dev/null && python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 4) else 1)" && command -v systemctl >/dev/null' 2>/dev/null; then
    echo "$id $nom : ignoré (python3 >= 3.4 ou systemd absent)"; continue
  fi
  pct exec "$id" -- mkdir -p /root/si-htop /etc/si-htop
  for f in emetteur.py si-htop-emetteur.service installer-emetteur.sh; do pct push "$id" "$ICI/$f" "/root/si-htop/$f"; done
  pct push "$id" /etc/si-htop/cle /etc/si-htop/cle --perms 600
  if pct exec "$id" -- sh /root/si-htop/installer-emetteur.sh --relais "$RELAIS" > "/tmp/si-htop-$id.log" 2>&1; then
    echo "$id $nom : installé (relais $RELAIS)"
  else
    echo "$id $nom : échec, voir /tmp/si-htop-$id.log"
  fi
done
