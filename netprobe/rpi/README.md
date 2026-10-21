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

## 5. Option radio du Pi 3B : Alfa AWUS036ACM et HackRF / PortaPack (#801)

    netprobe/rpi/make-boot-files.sh --role collector --hostname sonde-3b --token "$TOKEN" --alfa monitor --hackrf

- **Alimentation** : Alfa (jusqu'à ~600 mA en 5 GHz) + HackRF / PortaPack (~500-700 mA) dépassent les 1,2 A des ports USB
  du Pi 3B → **hub USB alimenté obligatoire** (sinon déconnexions aléatoires), alimentation du Pi 2,5 A officielle.
- **Alfa AWUS036ACM** (MediaTek MT7612U, pilote `mt76x2u` du noyau, firmware `mediatek/mt7662u` de
  `firmware-misc-nonfree`) : nommée `alfa0` par une règle udev.
  - `--alfa monitor` (défaut conseillé) : NetworkManager ne la gère pas, sonde **`wifi-monitor`** = écoute passive de
    tous les canaux 2,4 / 5 GHz (trames, retransmissions, occupation, désauthentifications, bornes, clients, BSS Load ;
    borne pirate si `/etc/si-agent/wifi-monitor.json` liste SSID et BSSID connus). N'émet jamais.
  - `--alfa client` : la carte porte la connexion au SSID audité et les mesures « expérience client » (`wifi-probe`) —
    utile car le Wi-Fi intégré du **Pi 3B (BCM43438) n'a que le 2,4 GHz** (le 3B+ a le 5 GHz).
- **HackRF One / PortaPack** : paquet `hackrf`, sonde **`rf-spectrum`** (`hackrf_sweep`, 2,4 GHz et 5 GHz bandes 1-2,
  **réception seule**, l'outil d'émission n'est jamais appelé). Sur la PortaPack (Mayhem) : choisir le mode **HackRF**
  dans le menu avant de la brancher (sinon « HackRF non détecté »). Si `hackrf_info` signale un micrologiciel trop
  récent pour l'outil de Debian, mettre à jour l'outil hôte ou le micrologiciel pour les aligner.
- Lecture croisée : occupation élevée au spectre (`rf-spectrum`) mais peu de trames Wi-Fi sur le même canal
  (`wifi-monitor`) = brouillage non Wi-Fi (micro-ondes, émetteur vidéo, Bluetooth, matériel défectueux).
- Contrôle sur le Pi : `iw dev alfa0 info` (type monitor), `hackrf_info`, puis l'interface du collecteur
  (mesures `plugin:wifi-monitor` chaque minute, `plugin:rf-spectrum` toutes les 2 min).

## 6. Collecteur permanent sur le mini-PC du site et tuile « Data RF » (#806)

Pour un suivi permanent, les sondes du site s'enrôlent au **collecteur du mini-PC** du site (déjà agent du hub), qui
remonte leurs mesures au hub par son propre agent : rien ne transite vers le LAN du client.

1. Mini-PC (root) : `sh si-agent/local-central/installer-collecteur.sh [--ref <commit>]` -- service `si-collecteur`
   (https://<IP>:6444), jeton des sondes : `sh installer-collecteur.sh --jeton`.
2. Sonde (root) : `systemctl disable --now si-local-central` (le collecteur intégré n'est plus utile), puis
   `curl -fsSL -k "https://<IP du mini-PC>:6444/deploy/linux?token=<jeton>" | sh` (l'agent passe au collecteur du
   mini-PC, avec les sondes wifi-probe, path-probe, dns-observe, wifi-monitor, rf-spectrum).
3. Hub : fiche de l'agent du mini-PC › Sondes › activer **collecte-sondes** ; tuile **Data RF** (Thèmes › réseau).

## Limites et notes

- Wi-Fi intégré (brcmfmac) : pas de mode moniteur sans firmware nexmon ; l'audit est « expérience client » (lien, survey,
  scan, chemin), ce qui est l'objectif. Un dongle USB (Realtek/Atheros/MediaTek) devient `wlan1` : `--iface wlan1`.
- Le satellite n'a que le Wi-Fi : administration par le SSID audité ; s'il décroche, l'agent garde ses mesures en file
  (store-and-forward) et les remonte au retour.
- Remontée vers le hub principal : le central local est autonome pour ce test ; pour un audit permanent, installer les
  agents contre le hub (tuile Agents hôtes) et garder le Pi 3B comme simple sonde.
- #801 non vérifié sur matériel : Alfa en mode moniteur (canaux, survey du pilote mt76), HackRF / PortaPack réels.
- Non vérifié : sur matériel réel (aucun Pi dans la session) — procédure écrite depuis les mécanismes connus de
  Raspberry Pi OS Bookworm (`/boot/firmware`, `systemd.run`), `make-boot-files.sh` testé sur une fausse partition.
