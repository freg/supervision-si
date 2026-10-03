#!/bin/bash
# Premier démarrage d'une sonde Wi-Fi Raspberry (livraison #657) -- lancé par le noyau (systemd.run dans cmdline.txt,
# même mécanisme que le firstrun de Raspberry Pi Imager), puis retiré. Lit /boot/firmware/si-probe.env :
#   SI_ROLE=collector|satellite  SI_HOSTNAME=...  SI_TOKEN=...  SI_COLLECTOR=https://<ip ou nom du collecteur>:6444
#   SI_IFACE=wlan0  SI_IPERF=<hôte iperf3 optionnel>  SI_CONNECTIONS=<SSID1,SSID2 pour path-probe, optionnel>
# collector (Pi 3B) : outils + central local (service) + agent local ; satellite (Pi Zero 2 W) : outils + agent vers le collecteur.
set -u
BOOT=/boot/firmware; [ -d "$BOOT" ] || BOOT=/boot
LOG=/var/log/si-probe-firstrun.log; exec > >(tee -a "$LOG") 2>&1
echo "=== si-probe firstrun $(date -Is) ==="
# retirer le crochet du noyau dès maintenant (un seul passage, même en cas d'échec plus loin)
sed -i 's| systemd.run=[^ ]*||; s| systemd.run_success_action=[^ ]*||; s| systemd.unit=kernel-command-line.target||' "$BOOT/cmdline.txt"
[ -f "$BOOT/si-probe.env" ] && . "$BOOT/si-probe.env"
ROLE="${SI_ROLE:-satellite}"; IFACE="${SI_IFACE:-wlan0}"
[ -n "${SI_HOSTNAME:-}" ] && { hostnamectl set-hostname "$SI_HOSTNAME" 2>/dev/null || echo "$SI_HOSTNAME" > /etc/hostname; sed -i "s/127.0.1.1.*/127.0.1.1\t$SI_HOSTNAME/" /etc/hosts; }
for i in $(seq 1 60); do ping -c1 -W2 deb.debian.org >/dev/null 2>&1 && break; sleep 5; done
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
# pilotes : brcmfmac (Wi-Fi intégré des Pi 3B / Zero 2 W) est dans le noyau ; firmwares pour un dongle USB éventuel (Realtek, Atheros, MediaTek…)
apt-get install -y -q iw wireless-tools wavemon tcpdump iperf3 mtr-tiny dnsutils curl jq python3 bc rfkill \
  firmware-brcm80211 firmware-realtek firmware-atheros firmware-misc-nonfree 2>&1 | tail -3
rfkill unblock wifi 2>/dev/null || true
# pas d'économie d'énergie sur la radio pendant l'audit
cat > /etc/NetworkManager/conf.d/si-wifi-powersave.conf <<'EONM'
[connection]
wifi.powersave = 2
EONM
mkdir -p /etc/systemd/system/timers.target.wants
install -d /opt/si-probe
tar xzf "$BOOT/si-agent-kit.tar.gz" -C /opt/si-probe 2>/dev/null || { echo "si-agent-kit.tar.gz absent : relancer make-boot-files.sh"; exit 1; }
PLUGARGS="--plugin-arg wifi-probe=\"--iface $IFACE --target auto${SI_IPERF:+ --iperf $SI_IPERF}\""
if [ "$ROLE" = "collector" ]; then
  cat > /etc/systemd/system/si-local-central.service <<EOS
[Unit]
Description=si-agent central local (collecteur de sondes Wi-Fi)
After=network-online.target
Wants=network-online.target
[Service]
WorkingDirectory=/opt/si-probe/si-agent/local-central
ExecStart=/usr/bin/python3 local_central.py --site audit --interval 60 --history auto --token "${SI_TOKEN}" --plugins wifi-probe,path-probe,dns-observe $PLUGARGS ${SI_CONNECTIONS:+--plugin-arg path-probe="--connections $SI_CONNECTIONS"}
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOS
  systemctl daemon-reload; systemctl enable --now si-local-central.service
  COLLECTOR="https://127.0.0.1:6444"
  for i in $(seq 1 30); do curl -skf "$COLLECTOR/ca" >/dev/null && break; sleep 2; done
else
  COLLECTOR="${SI_COLLECTOR:?SI_COLLECTOR requis pour un satellite}"
  for i in $(seq 1 120); do curl -skf "$COLLECTOR/ca" >/dev/null && break; echo "attente du collecteur $COLLECTOR"; sleep 10; done
fi
# agent : installé depuis le collecteur (archive + CA épinglée + plugins activés), comme n'importe quel poste
curl -fsSL -k "$COLLECTOR/deploy/linux?token=${SI_TOKEN}" | sudo -E sh || echo "installation de l'agent en échec (voir $LOG)"
echo "=== terminé $(date -Is) ; rôle $ROLE ; collecteur $COLLECTOR ==="
