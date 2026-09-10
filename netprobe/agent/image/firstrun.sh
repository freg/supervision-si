#!/bin/bash
# netprobe -- script de PREMIER DÉMARRAGE d'une sonde (Pi Zero W) ou d'un
# collecteur (Pi 3B). Déposé sur la partition de boot par build-image.sh,
# lancé UNE fois par systemd (`systemd.run=` dans cmdline.txt, même
# mécanisme que Raspberry Pi Imager), puis retiré de cmdline.txt.
#
# Tout ce qui suit est volontairement tolérant : une étape qui échoue est
# journalisée dans /var/log/netprobe-firstrun.log et n'empêche pas les
# suivantes -- une sonde qui démarre sans fuseau horaire vaut mieux qu'une
# sonde qui ne démarre pas. Aucune dépendance au réseau, sauf l'installation
# OPTIONNELLE d'iperf3 (meilleur effort, avec délai).
set +e
export DEBIAN_FRONTEND=noninteractive

BOOT=/boot/firmware
[ -f "$BOOT/netprobe/settings.env" ] || BOOT=/boot
NP="$BOOT/netprobe"
LOG=/var/log/netprobe-firstrun.log
exec >>"$LOG" 2>&1
echo "== netprobe firstrun $(date -u +%FT%TZ) -- boot=$BOOT =="

if [ ! -f "$NP/settings.env" ]; then
  echo "settings.env introuvable dans $NP -- abandon"
  exit 0
fi
# shellcheck disable=SC1090
. "$NP/settings.env"
ROLE="${ROLE:-probe}"

step() { echo "-- $*"; }

# ---- identité de la machine ------------------------------------------
if [ -n "$HOSTNAME_NP" ]; then
  step "hostname $HOSTNAME_NP"
  if ! raspi-config nonint do_hostname "$HOSTNAME_NP"; then
    echo "$HOSTNAME_NP" > /etc/hostname
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$HOSTNAME_NP/" /etc/hosts
    hostnamectl set-hostname "$HOSTNAME_NP" 2>/dev/null
  fi
fi
if [ -n "$TIMEZONE" ]; then
  step "fuseau $TIMEZONE"
  raspi-config nonint do_change_timezone "$TIMEZONE" || timedatectl set-timezone "$TIMEZONE"
fi
step "ssh"
raspi-config nonint do_ssh 0 || systemctl enable --now ssh
if [ -f "$NP/authorized_keys" ] && [ -n "$USER_NAME" ]; then
  # L'utilisateur est créé par userconf-pi (userconf.txt) au même premier
  # démarrage : on l'attend un peu plutôt que de supposer l'ordre des unités.
  for _ in $(seq 1 30); do id "$USER_NAME" >/dev/null 2>&1 && break; sleep 2; done
  if id "$USER_NAME" >/dev/null 2>&1; then
    H="$(getent passwd "$USER_NAME" | cut -d: -f6)"
    mkdir -p "$H/.ssh" && cp "$NP/authorized_keys" "$H/.ssh/authorized_keys"
    chown -R "$USER_NAME:$USER_NAME" "$H/.ssh" && chmod 700 "$H/.ssh" && chmod 600 "$H/.ssh/authorized_keys"
    step "clé SSH installée pour $USER_NAME"
  else
    echo "utilisateur $USER_NAME absent après 60 s -- clé SSH non installée (userconf.txt ?)"
  fi
fi

# ---- WiFi (sonde : obligatoire ; collecteur : optionnel) ---------------
if [ -n "$WIFI_SSID" ]; then
  step "wifi pays=${WIFI_COUNTRY:-FR} ssid=$WIFI_SSID"
  raspi-config nonint do_wifi_country "${WIFI_COUNTRY:-FR}"
  rfkill unblock wifi 2>/dev/null
  raspi-config nonint do_wifi_ssid_passphrase "$WIFI_SSID" "$WIFI_PSK" || echo "do_wifi_ssid_passphrase a échoué"
fi

# ---- adresse fixe (collecteur : recommandé, les sondes pointent dessus) --
if [ -n "$STATIC_IP" ]; then
  step "adresse fixe $STATIC_IP via ${STATIC_IFACE:-eth0}"
  if command -v nmcli >/dev/null 2>&1; then
    # Bookworm : NetworkManager -- profil dédié en fichier de clés, actif
    # au démarrage, prioritaire sur le DHCP automatique.
    cat > "/etc/NetworkManager/system-connections/netprobe-${STATIC_IFACE:-eth0}.nmconnection" <<EOF
[connection]
id=netprobe-${STATIC_IFACE:-eth0}
type=ethernet
interface-name=${STATIC_IFACE:-eth0}
autoconnect=true
autoconnect-priority=100

[ipv4]
method=manual
addresses=$STATIC_IP
gateway=$STATIC_GATEWAY
dns=${STATIC_DNS:-$STATIC_GATEWAY}

[ipv6]
method=auto
EOF
    chmod 600 "/etc/NetworkManager/system-connections/netprobe-${STATIC_IFACE:-eth0}.nmconnection"
  else
    # Bullseye : dhcpcd
    cat >> /etc/dhcpcd.conf <<EOF

# netprobe -- adresse fixe du collecteur
interface ${STATIC_IFACE:-eth0}
static ip_address=$STATIC_IP
static routers=$STATIC_GATEWAY
static domain_name_servers=${STATIC_DNS:-$STATIC_GATEWAY}
EOF
  fi
fi

# ---- code et configuration ------------------------------------------
step "installation du paquet netprobe_agent dans /opt/netprobe-agent"
mkdir -p /opt/netprobe-agent
tar xzf "$NP/payload.tgz" -C /opt/netprobe-agent
find /opt/netprobe-agent -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

if [ "$ROLE" = "collector" ]; then
  step "rôle collecteur"
  id netprobe >/dev/null 2>&1 || useradd --system --home /var/lib/netprobe-collector --shell /usr/sbin/nologin netprobe
  mkdir -p /etc/netprobe-collector /var/lib/netprobe-collector
  cp "$NP/device.json" /etc/netprobe-collector/collector.json
  [ -f "$NP/fleet.json" ] && cp "$NP/fleet.json" /etc/netprobe-collector/fleet.json
  [ -f "$NP/central-ca.crt" ] && cp "$NP/central-ca.crt" /etc/netprobe-collector/central-ca.crt
  chown -R netprobe:netprobe /etc/netprobe-collector /var/lib/netprobe-collector
  chmod 600 /etc/netprobe-collector/collector.json
  [ -f /etc/netprobe-collector/fleet.json ] && chmod 600 /etc/netprobe-collector/fleet.json
  cp /opt/netprobe-agent/systemd/netprobe-collector.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable netprobe-collector.service
else
  step "rôle sonde"
  mkdir -p /etc/netprobe-agent /var/lib/netprobe-agent
  cp "$NP/device.json" /etc/netprobe-agent/agent.json
  chmod 600 /etc/netprobe-agent/agent.json
  cp /opt/netprobe-agent/systemd/netprobe-agent.service /etc/systemd/system/
  cp /opt/netprobe-agent/systemd/netprobe-wifi-powersave.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable netprobe-wifi-powersave.service
  systemctl enable netprobe-agent.service
fi

# ---- outils optionnels (meilleur effort, réseau requis) ---------------
if [ "${INSTALL_IPERF3:-0}" = "1" ]; then
  step "iperf3 (optionnel, 3 min max)"
  (timeout 180 apt-get update && timeout 180 apt-get install -y --no-install-recommends iperf3) \
    || echo "iperf3 non installé (pas de réseau au premier démarrage ?) -- 'apt install iperf3' plus tard"
fi

# ---- nettoyage : ne plus relancer ce script, effacer le PSK du boot -----
step "nettoyage"
for f in "$BOOT/cmdline.txt"; do
  [ -f "$f" ] && sed -i 's| systemd\.run=[^ ]*||g; s| systemd\.run_success_action=[^ ]*||g; s| systemd\.unit=kernel-command-line\.target||g' "$f"
done
rm -f "$NP/settings.env" "$NP/firstrun.sh" "$BOOT/firstrun.sh"
echo "== terminé $(date -u +%FT%TZ) -- redémarrage =="
exit 0
