#!/bin/bash
# Prépare la partition de démarrage d'une carte SD fraîchement écrite avec Raspberry Pi OS Lite (Bookworm) par Raspberry Pi
# Imager (livraison #657). Usage, depuis la racine du dépôt, carte montée :
#   netprobe/rpi/make-boot-files.sh --role collector --hostname sonde-3b --token <jeton> [--iperf HOTE] [--connections SSID1,SSID2] [--boot /Volumes/bootfs]
#   netprobe/rpi/make-boot-files.sh --role satellite --hostname sonde-zero --token <jeton> --collector https://<IP du 3B>:6444 [--boot /Volumes/bootfs]
# Dépose si-probe.env, firstrun-si.sh, si-agent-kit.tar.gz (agent + central local + make-archive) et accroche firstrun-si.sh au
# premier démarrage via cmdline.txt (systemd.run, comme l'Imager). Le même jeton sert au collecteur et à ses satellites.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
ROLE="" HOST="" TOKEN="" COLLECTOR="" IPERF="" CONN="" BOOT="" IFACE="wlan0"
while [ $# -gt 0 ]; do case "$1" in
  --role) ROLE="$2"; shift 2;; --hostname) HOST="$2"; shift 2;; --token) TOKEN="$2"; shift 2;; --collector) COLLECTOR="$2"; shift 2;;
  --iperf) IPERF="$2"; shift 2;; --connections) CONN="$2"; shift 2;; --boot) BOOT="$2"; shift 2;; --iface) IFACE="$2"; shift 2;;
  *) echo "option inconnue : $1" >&2; exit 2;; esac; done
[ "$ROLE" = collector ] || [ "$ROLE" = satellite ] || { echo "--role collector|satellite" >&2; exit 2; }
[ -n "$HOST" ] && [ -n "$TOKEN" ] || { echo "--hostname et --token requis" >&2; exit 2; }
[ "$ROLE" = satellite ] && [ -z "$COLLECTOR" ] && { echo "--collector https://<ip du collecteur>:6444 requis pour un satellite" >&2; exit 2; }
if [ -z "$BOOT" ]; then for c in /Volumes/bootfs /Volumes/boot /media/*/bootfs /run/media/*/bootfs; do [ -f "$c/cmdline.txt" ] && BOOT="$c" && break; done; fi
[ -n "$BOOT" ] && [ -f "$BOOT/cmdline.txt" ] || { echo "partition de démarrage introuvable (--boot /Volumes/bootfs)" >&2; exit 2; }
echo "partition : $BOOT ; rôle : $ROLE ; hôte : $HOST"
cat > "$BOOT/si-probe.env" <<EOV
SI_ROLE=$ROLE
SI_HOSTNAME=$HOST
SI_TOKEN=$TOKEN
SI_COLLECTOR=$COLLECTOR
SI_IFACE=$IFACE
SI_IPERF=$IPERF
SI_CONNECTIONS=$CONN
EOV
cp "$HERE/firstrun-si.sh" "$BOOT/firstrun-si.sh"; cp "$HERE/report-wifi-day.py" "$BOOT/report-wifi-day.py"; chmod +x "$BOOT/firstrun-si.sh" 2>/dev/null || true
tar czf "$BOOT/si-agent-kit.tar.gz" -C "$ROOT" --exclude='__pycache__' --exclude='*/data/*' --exclude='*.pyc' si-agent/agent si-agent/local-central si-agent/make-archive.sh si-agent/README.md
grep -q "firstrun-si.sh" "$BOOT/cmdline.txt" || sed -i.bak 's|$| systemd.run=/boot/firmware/firstrun-si.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target|' "$BOOT/cmdline.txt"
rm -f "$BOOT/cmdline.txt.bak"
echo "prêt : au premier démarrage, $HOST installe les outils$( [ "$ROLE" = collector ] && echo ', le central local (https://<ip>:6444)' ) et l'agent. Journal : /var/log/si-probe-firstrun.log"
