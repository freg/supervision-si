#!/bin/bash
# Premier démarrage d'une sonde Wi-Fi Raspberry (livraison #657) -- lancé par le noyau (systemd.run dans cmdline.txt,
# même mécanisme que le firstrun de Raspberry Pi Imager), puis retiré. Lit /boot/firmware/si-probe.env :
#   SI_ROLE=collector|satellite  SI_HOSTNAME=...  SI_TOKEN=...  SI_COLLECTOR=https://<ip ou nom du collecteur>:6444
#   SI_IFACE=wlan0  SI_IPERF=<hôte iperf3 optionnel>  SI_CONNECTIONS=<SSID1,SSID2 pour path-probe, optionnel>
#   #801 : SI_ALFA=monitor|client (carte Alfa AWUS036ACM nommée alfa0)  SI_HACKRF=1 (HackRF / PortaPack, réception seule)
# collector (Pi 3B) : outils + central local (service) + agent local ; satellite (Pi Zero 2 W) : outils + agent vers le collecteur.
set -u
BOOT=/boot/firmware; [ -d "$BOOT" ] || BOOT=/boot
LOG=/var/log/si-probe-firstrun.log; exec > >(tee -a "$LOG") 2>&1
echo "=== si-probe firstrun $(date -Is) ==="
# retirer le crochet du noyau dès maintenant (un seul passage, même en cas d'échec plus loin)
sed -i 's| systemd.run=[^ ]*||; s| systemd.run_success_action=[^ ]*||; s| systemd.unit=kernel-command-line.target||' "$BOOT/cmdline.txt"
[ -f "$BOOT/si-probe.env" ] && . "$BOOT/si-probe.env"
ROLE="${SI_ROLE:-satellite}"; IFACE="${SI_IFACE:-wlan0}"; ALFA="${SI_ALFA:-}"; HACKRF="${SI_HACKRF:-}"
PLUGINS="wifi-probe,path-probe,dns-observe"
[ -n "${SI_HOSTNAME:-}" ] && { hostnamectl set-hostname "$SI_HOSTNAME" 2>/dev/null || echo "$SI_HOSTNAME" > /etc/hostname; sed -i "s/127.0.1.1.*/127.0.1.1\t$SI_HOSTNAME/" /etc/hosts; }
for i in $(seq 1 60); do ping -c1 -W2 deb.debian.org >/dev/null 2>&1 && break; sleep 5; done
export DEBIAN_FRONTEND=noninteractive
# pilotes : brcmfmac (Wi-Fi intégré des Pi 3B / Zero 2 W) est dans le noyau ; firmwares pour un dongle USB éventuel (Realtek, Atheros, MediaTek…)
# #804 : DNS ou miroir instables au premier démarrage (vu en réel : « Temporary failure resolving ») -> 5 tentatives,
# et la liste manquante est relancée à chaque démarrage par si-probe-paquets tant qu'il en manque
PAQUETS="iw wireless-tools wavemon tcpdump iperf3 mtr-tiny dnsutils curl jq python3 bc rfkill firmware-brcm80211 firmware-realtek firmware-atheros firmware-misc-nonfree${HACKRF:+ hackrf}"
echo "$PAQUETS" > /etc/si-probe-paquets
for essai in 1 2 3 4 5; do
  apt-get update -q && apt-get install -y -q $PAQUETS 2>&1 | tail -3
  manque=$(for p in $PAQUETS; do dpkg -s "$p" >/dev/null 2>&1 || echo "$p"; done)
  [ -z "$manque" ] && break
  echo "paquets manquants (essai $essai/5) : $manque" ; sleep 20
done
cat > /etc/systemd/system/si-probe-paquets.service <<'EOPK'
[Unit]
Description=si-probe : installe les paquets de la sonde encore manquants (premier démarrage sans réseau fiable)
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
# ($$ : systemd remplace sinon les $VAR lui-même)
ExecStart=/bin/sh -c 'm=$$(for p in $$(cat /etc/si-probe-paquets); do dpkg -s "$$p" >/dev/null 2>&1 || echo "$$p"; done); [ -z "$$m" ] || { apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q $$m; }'
[Install]
WantedBy=multi-user.target
EOPK
systemctl enable si-probe-paquets.service 2>/dev/null || true
# #801 : carte Alfa AWUS036ACM (MT7612U, pilote mt76x2u du noyau, firmware mediatek/mt7662u dans firmware-misc-nonfree) -> alfa0
if [ -n "$ALFA" ]; then
  echo 'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="mt76x2u", NAME="alfa0"' > /etc/udev/rules.d/70-si-alfa.rules
  udevadm control --reload; udevadm trigger --subsystem-match=net --action=add || true
  if [ "$ALFA" = monitor ]; then   # écoute passive : NetworkManager ne touche pas à la carte
    printf '[keyfile]\nunmanaged-devices=interface-name:alfa0\n' > /etc/NetworkManager/conf.d/si-alfa-monitor.conf
    PLUGINS="$PLUGINS,wifi-monitor"
  else                              # client 5 GHz : la carte porte la connexion au SSID audité et les mesures client
    IFACE=alfa0
    for c in $(nmcli -g NAME,TYPE connection show | awk -F: '$2=="802-11-wireless"{print $1}'); do nmcli connection modify "$c" connection.interface-name alfa0 || true; done
  fi
  systemctl reload NetworkManager 2>/dev/null || true
fi
[ -n "$HACKRF" ] && PLUGINS="$PLUGINS,rf-spectrum" && { hackrf_info 2>&1 | head -5 || true; }
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
ExecStart=/usr/bin/python3 local_central.py --site audit --interval 60 --history auto --token "${SI_TOKEN}" --plugins $PLUGINS $PLUGARGS ${SI_CONNECTIONS:+--plugin-arg path-probe="--connections $SI_CONNECTIONS"}
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
