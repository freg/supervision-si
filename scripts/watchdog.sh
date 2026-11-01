#!/usr/bin/env bash
# Chien de garde du socle (livraison #745) -- relance les conteneurs indispensables à l'accès au hub
# (Keycloak, passerelle HTTPS, hub) s'ils sont arrêtés, et la passerelle si elle ne répond plus.
# Cas réel (13/10/2026) : après une migration de VM, ces trois conteneurs étaient restés « Exited (137) »
# (tués), le reste du socle tournait, et supervision.optline.fr répondait 503 pendant des heures.
#
#   ./scripts/watchdog.sh              un passage (journal sur la sortie standard)
#   ./scripts/watchdog.sh --install    pose le service + minuteur systemd (toutes les 2 min, root)
#   ./scripts/watchdog.sh --uninstall  les retire
#   touch .watchdog-pause              suspend les relances (chantier, down volontaire) ; rm pour reprendre
#
# Réglages (environnement ou .env) : WATCHDOG_CONTAINERS (liste, dans l'ordre de démarrage),
# GATEWAY_PORT (port HTTPS local de la passerelle), WATCHDOG_FAILS (échecs HTTPS consécutifs avant relance).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER=${DOCKER:-docker}
CURL=${CURL:-curl}
STATE=${WATCHDOG_STATE:-/run/supervision-watchdog}
envget() { [ -f "$ROOT/.env" ] && sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | tr -d '"'"'" || true; }
CONTAINERS=${WATCHDOG_CONTAINERS:-$(envget WATCHDOG_CONTAINERS)}
CONTAINERS=${CONTAINERS:-supervision-si-gateway-keycloak-1 supervision-si-gateway-tls-proxy-1 supervision-si-hub-1}
PORT=${GATEWAY_PORT:-$(envget GATEWAY_PORT)}; PORT=${PORT:-6443}
MAXFAIL=${WATCHDOG_FAILS:-3}
log() { echo "watchdog: $*"; }

case "${1:-}" in
  --install)
    cat > /etc/systemd/system/supervision-watchdog.service <<UNIT
[Unit]
Description=Chien de garde du socle supervision-si (Keycloak, passerelle, hub)
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
ExecStart=/bin/bash $ROOT/scripts/watchdog.sh
UNIT
    cat > /etc/systemd/system/supervision-watchdog.timer <<UNIT
[Unit]
Description=Chien de garde supervision-si toutes les 2 minutes
[Timer]
OnActiveSec=1min
OnBootSec=3min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
UNIT
    systemctl daemon-reload && systemctl enable --now supervision-watchdog.timer && systemctl list-timers supervision-watchdog.timer --no-pager
    exit $? ;;
  --uninstall)
    systemctl disable --now supervision-watchdog.timer 2>/dev/null
    rm -f /etc/systemd/system/supervision-watchdog.{service,timer}; systemctl daemon-reload; exit 0 ;;
esac

[ -e "$ROOT/.watchdog-pause" ] && { log "en pause ($ROOT/.watchdog-pause)"; exit 0; }
$DOCKER info >/dev/null 2>&1 || { log "docker indisponible"; exit 1; }
mkdir -p "$STATE"
started=0
for c in $CONTAINERS; do
  st=$($DOCKER inspect -f '{{.State.Status}}' "$c" 2>/dev/null) || { log "$c absent (jamais créé ?) -- ignoré"; continue; }
  case "$st" in
    running|restarting) ;;
    *) code=$($DOCKER inspect -f '{{.State.ExitCode}}' "$c" 2>/dev/null)
       if $DOCKER start "$c" >/dev/null 2>&1; then log "$c était $st (code $code) -- relancé"; started=$((started+1)); sleep 20
       else log "ÉCHEC de relance de $c ($st, code $code)"; fi ;;
  esac
done
[ "$started" -gt 0 ] && exit 0   # laisser démarrer avant de juger la passerelle

# Passerelle : toute réponse HTTP = vivante ; aucune réponse = morte
code=$($CURL -sk -o /dev/null -m 10 -w '%{http_code}' "https://localhost:$PORT/" 2>/dev/null); code=${code:-000}
if [ "$code" = "000" ]; then   # aucune réponse ; un 502/503 vient d'un service derrière, pas de la passerelle
  n=$(( $(cat "$STATE/fails" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE/fails"
  log "passerelle https://localhost:$PORT/ -> $code ($n/$MAXFAIL)"
  if [ "$n" -ge "$MAXFAIL" ]; then
    gw=$(for c in $CONTAINERS; do case "$c" in *tls-proxy*) echo "$c";; esac; done | head -1)
    [ -n "$gw" ] && $DOCKER restart "$gw" >/dev/null 2>&1 && log "$gw redémarré"
    echo 0 > "$STATE/fails"
  fi
else
  echo 0 > "$STATE/fails"
fi
exit 0
