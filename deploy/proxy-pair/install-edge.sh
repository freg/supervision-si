#!/usr/bin/env bash
# #776 : prépare une VM (Debian 12 / 13) comme proxy d'entrée du couple interchangeable -- HAProxy (configuration
# fournie ensuite par le hub, via l'agent), WireGuard pour joindre les serveurs internes, réglages réseau.
# À lancer en root sur CHAQUE VM du couple (deux VM sur deux nœuds Proxmox différents) :
#   ./install-edge.sh                     # HAProxy + WireGuard + réglages ; n'écrit aucune route
#   ./install-edge.sh --check             # contrôle seul : rien n'est installé ni modifié
# Ensuite : agent du hub (Agents hôtes › Déploiement, ligne Linux), tunnel wg0 vers le LAN (deploy/wg-mesh.sh),
# puis la tuile « Proxys d'entrée » : déclarer les deux proxys, ajouter les routes, Appliquer aux deux proxys.
set -uo pipefail
CHECK=false
[ "${1:-}" = "--check" ] && CHECK=true
[ "$(id -u)" = 0 ] || { echo "à lancer en root"; exit 1; }
ok() { echo "  ok   $*"; }
ko() { echo "  KO   $*"; BAD=$((BAD + 1)); }
BAD=0
if ! $CHECK; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q && apt-get install -y -q haproxy wireguard-tools socat curl ca-certificates || { echo "installation des paquets impossible"; exit 1; }
  mkdir -p /run/haproxy
  # ports 80 et 443 sans root pour HAProxy (déjà le cas avec le paquet Debian, conservé si absent)
  sysctl -q -w net.ipv4.ip_unprivileged_port_start=80 >/dev/null 2>&1 || true
  cat > /etc/sysctl.d/90-si-edge.conf <<'SYS'
# #776 : proxy d'entrée -- beaucoup de connexions courtes, ports locaux larges, réutilisation des TIME_WAIT
net.ipv4.ip_local_port_range = 10240 65535
net.ipv4.tcp_tw_reuse = 1
net.core.somaxconn = 4096
SYS
  sysctl -q --system >/dev/null 2>&1 || true
  systemctl enable --now haproxy >/dev/null 2>&1 || true
fi
echo "Contrôle de $(hostname) :"
command -v haproxy >/dev/null && ok "haproxy $(haproxy -v 2>/dev/null | head -1 | awk '{print $3}')" || ko "haproxy absent"
systemctl is-active --quiet haproxy && ok "service haproxy actif" || ko "service haproxy arrêté"
command -v wg >/dev/null && ok "wireguard-tools" || ko "wireguard-tools absent"
if ip link show wg0 >/dev/null 2>&1; then ok "tunnel wg0 présent ($(wg show wg0 latest-handshakes 2>/dev/null | wc -l) pair(s))"; else ko "tunnel wg0 absent : deploy/wg-mesh.sh puis systemctl enable --now wg-quick@wg0"; fi
systemctl is-active --quiet si-agent && ok "agent du hub actif" || ko "agent du hub absent : Agents hôtes › Déploiement (ligne Linux)"
for p in 80 443; do
  if ss -ltnH "sport = :$p" | grep -q .; then ok "port $p écouté"; else echo "  --   port $p pas encore écouté (normal avant la première route)"; fi
done
pub=$(curl -fsS --max-time 5 https://ifconfig.me 2>/dev/null || true)
[ -n "$pub" ] && ok "IP publique vue de l'extérieur : $pub (à déclarer dans la tuile)" || echo "  --   IP publique non déterminée"
echo "$BAD point(s) à régler."
exit $BAD
