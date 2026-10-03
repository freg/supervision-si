# Sondes Wi-Fi Raspberry : collecteur Pi 3B + satellite Pi Zero 2 W (livraison #657)

Kit pour un **premier audit continu d'une journée** : un Pi 3B « collecteur » (central local + sonde) et un Pi Zero 2 W
« satellite » (sonde) qui remonte au collecteur. Tout se fait depuis la carte SD : Raspberry Pi Imager écrit l'OS, le kit
dépose les fichiers de premier démarrage, le Pi s'installe seul au premier boot (outils, pilotes, agent, central local).

## 1. Écrire les cartes (Raspberry Pi Imager)

Pour chaque carte : **Raspberry Pi OS Lite (64-bit, Bookworm)** — Pi 3B et Pi Zero 2 W sont tous deux arm64 ; sur le
Zero 2 W (512 Mo) Lite 64-bit reste à l'aise. Dans les réglages de l'Imager : nom d'hôte (`sonde-3b`, `sonde-zero`),
utilisateur + mot de passe, **SSH activé**, Wi-Fi = le SSID à auditer (c'est ce lien que la sonde mesure, en vrai client),
pays Wi-Fi FR, locale. Le Pi 3B peut en plus être relié en Ethernet pour l'administration.

## 2. Déposer le kit sur la partition de démarrage (carte encore dans le Mac/PC)

Depuis la racine du dépôt, carte montée (`/Volumes/bootfs` sur macOS) :

    cd ~/SRC/data2/tickets/supervision-si
    TOKEN=$(openssl rand -hex 12)      # même jeton pour le collecteur et ses satellites
    netprobe/rpi/make-boot-files.sh --role collector --hostname sonde-3b --token "$TOKEN" [--iperf 192.0.2.10] [--connections SSID-A,SSID-B]
    # … écrire la seconde carte, puis :
    netprobe/rpi/make-boot-files.sh --role satellite --hostname sonde-zero --token "$TOKEN" --collector https://<IP du Pi 3B>:6444

Le script dépose `si-probe.env`, `firstrun-si.sh`, `si-agent-kit.tar.gz` et accroche le premier démarrage dans
`cmdline.txt` (mécanisme `systemd.run` de l'Imager). L'IP du Pi 3B : réservation DHCP conseillée (ou `sonde-3b.local`
si mDNS fonctionne sur le réseau audité) — le satellite attend le collecteur jusqu'à 20 min au premier démarrage.

## 3. Premier démarrage (5 à 10 min, réseau requis)

`firstrun-si.sh` : nom d'hôte, outils (`iw`, `wireless-tools`, `wavemon`, `tcpdump`, `iperf3`, `mtr`, `dig`, `jq`, Python 3),
firmwares (`firmware-brcm80211` = Wi-Fi intégré, + Realtek/Atheros/misc pour un dongle USB éventuel), économie d'énergie
Wi-Fi désactivée, puis :
- **collecteur** : service `si-local-central` (`https://<IP>:6444`, jeton imposé, `--history auto` = toutes les mesures en
  `data/history.jsonl`, plugins `wifi-probe`, `path-probe`, `dns-observe`) et agent local enrôlé dessus ;
- **satellite** : agent enrôlé sur le collecteur (archive + CA épinglée, plugins activés par le collecteur).
Journal : `/var/log/si-probe-firstrun.log`. Le crochet `systemd.run` est retiré dès le début du script (un seul passage).

Vérifier : `ssh sonde-3b`, puis `systemctl status si-local-central si-agent` et l'interface `https://<IP du 3B>:6444/`
(deux agents, mesures `plugin:wifi-probe` chaque minute). Sur le Zero : `systemctl status si-agent`.

## 4. Fin de journée : rapport

    ssh sonde-3b 'cd /opt/si-probe/si-agent/local-central && python3 /boot/firmware/report-wifi-day.py data/history.jsonl /tmp/audit.html --md /tmp/audit.md'
    scp sonde-3b:/tmp/audit.{html,md} .

(ou copier `netprobe/rpi/report-wifi-day.py` sur le Pi). Rapport : constats des sondes (signal faible, canal saturé, borne
chargée, pertes…), courbes RSSI / occupation du canal / débit négocié / latence-pertes / HTTP réel par sonde, synthèse par
heure, bornes vues (BSSID, SSID, fréquence, RSSI max, stations max). Options `--since` / `--until` (ISO).

## Limites et notes

- Wi-Fi intégré (brcmfmac) : pas de mode moniteur sans firmware nexmon ; l'audit est « expérience client » (lien, survey,
  scan, chemin), ce qui est l'objectif. Un dongle USB (Realtek/Atheros/MediaTek) devient `wlan1` : `--iface wlan1`.
- Le satellite n'a que le Wi-Fi : administration par le SSID audité ; s'il décroche, l'agent garde ses mesures en file
  (store-and-forward) et les remonte au retour.
- Remontée vers le hub principal : le central local est autonome pour ce test ; pour un audit permanent, installer les
  agents contre le hub (tuile Agents hôtes) et garder le Pi 3B comme simple sonde.
- Non vérifié : sur matériel réel (aucun Pi dans la session) — procédure écrite depuis les mécanismes connus de
  Raspberry Pi OS Bookworm (`/boot/firmware`, `systemd.run`), `make-boot-files.sh` testé sur une fausse partition.
