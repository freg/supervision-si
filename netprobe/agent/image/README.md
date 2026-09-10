# Images Raspberry Pi — sonde (Zero W) et collecteur (3B)

Livraison #408. Un seul constructeur, `build-image.sh`, pour les deux
rôles : il part de l'image **officielle** Raspberry Pi OS Lite 32 bits (la
seule qui démarre sur un Pi Zero W — ARMv6 — et qui convient au 3B) et y
injecte, sur la partition de boot, tout ce qu'il faut pour que le Pi
s'installe **lui-même au premier démarrage**, puis redémarre en service.

Aucune reconstruction d'image (pas de pi-gen, pas de chroot, pas de
`sudo`) : la partition FAT est écrite avec `mtools`, sans montage. C'est
le mécanisme de Raspberry Pi Imager (`userconf.txt`, fichier `ssh`,
`systemd.run=` dans `cmdline.txt`), reproduit de façon scriptable et
versionnée.

## Prérequis (machine qui construit)

macOS : `brew install mtools xz` — Debian/Ubuntu : `apt install mtools xz-utils`.
Plus `python3`, `curl`, `tar` (déjà présents). Aucun droit administrateur.

## Étapes

1. **Déclarer l'appareil dans le hub** — tuile Sondes réseau → onglet
   « 📶 Sondes WiFi » → « + » (rôle *sonde* pour un Zero W, *collecteur*
   pour un 3B). Le central génère son secret ; `build-image.sh` le
   récupère par `GET /agents/<id>/provision`.

2. **Construire l'image**

   Collecteur (Pi 3B, Ethernet, adresse fixe — les sondes pointent dessus) :
   ```bash
   cd netprobe/agent/image
   ./build-image.sh --api https://VM:6443/api/netprobe --api-insecure \
       --agent alpha-collecteur-01 \
       --central-url https://VM:6443/api/netprobe --ca ../../../pki/ca/ca.crt \
       --static-ip 192.168.10.20/24 --gateway 192.168.10.1 --dns 192.168.10.1 \
       --password 'un-mot-de-passe' --ssh-key ~/.ssh/id_ed25519.pub
   ```
   Sonde (Pi Zero W, WiFi du site) :
   ```bash
   ./build-image.sh --api https://VM:6443/api/netprobe --api-insecure \
       --agent alpha-sonde-01 --collector-url http://192.168.10.20:6127 \
       --wifi-ssid 'Alpha-Prod' --wifi-psk 'clé-wifi' --wifi-country FR \
       --password 'un-mot-de-passe' --iperf3
   ```
   La première exécution télécharge l'image officielle dans `cache/`
   (≈ 500 Mo, `*.xz` ignoré par git) ; les suivantes la réutilisent.
   `--base-image chemin.img.xz` pour une image choisie ; `--config
   fichier.json` pour construire hors ligne à partir d'une configuration
   déjà écrite (voir `../examples/`).

3. **Flasher** — Raspberry Pi Imager, « Utiliser une image personnalisée »,
   en répondant **NON** à la personnalisation de l'OS (elle écraserait la
   nôtre) ; ou `sudo dd if=netprobe-probe-alpha-sonde-01.img of=/dev/rdiskN bs=4m`.

4. **Premier démarrage** (2 à 4 minutes, deux redémarrages) : le Pi crée
   l'utilisateur, applique hostname/fuseau/WiFi/adresse fixe, installe le
   paquet dans `/opt/netprobe-agent`, active le service, retire la
   directive de premier démarrage de `cmdline.txt`, efface la clé WiFi de
   la partition de boot, redémarre. Journal : `/var/log/netprobe-firstrun.log`.

5. **Vérifier** — sur le collecteur : `curl http://192.168.10.20:6127/api/v1/status`
   (sondes vues, file, dernier contact central) ; sur une sonde :
   `sudo python3 -m netprobe_agent.agent --status` ; dans le hub : la
   ligne de l'appareil passe en « vue il y a N s ».

## Ce que contient la partition de boot après construction

```
/netprobe/payload.tgz      paquet netprobe_agent + unités systemd
/netprobe/device.json      agent.json ou collector.json (secret compris)
/netprobe/settings.env     hostname, fuseau, WiFi, adresse fixe -- EFFACÉ au premier boot
/netprobe/firstrun.sh      script de premier démarrage (retiré ensuite)
/netprobe/fleet.json       (collecteur, optionnel) flotte initiale hors ligne
/netprobe/central-ca.crt   (collecteur, optionnel) AC du projet pour le TLS vers le central
/netprobe/authorized_keys  (optionnel) clé SSH de l'utilisateur
/userconf.txt              utilisateur:hash SHA-512  (mécanisme officiel)
/ssh                       fichier vide = SSH activé
cmdline.txt                + systemd.run=<boot>/netprobe/firstrun.sh ...
```

`<boot>` vaut `/boot/firmware` (Bookworm, images datées après octobre
2023) ou `/boot` (Bullseye) — détecté d'après `issue.txt`, forçable avec
`--boot-mount`. `firstrun.sh` se relocalise lui-même dans les deux cas.

## Choix et limites

- **32 bits pour tous** : une seule image de base, un seul chemin testé.
  Le 3B accepterait du 64 bits, sans bénéfice pour un collecteur.
- **Économie d'énergie WiFi désactivée** sur la sonde
  (`netprobe-wifi-powersave.service`) : sur brcmfmac elle introduit une
  latence variable et des pertes apparentes — la sonde mesure le réseau,
  pas ses propres artefacts.
- **Secret dans `device.json` sur la partition FAT** : lisible par
  quiconque tient la carte SD en main. C'est le niveau de confiance d'un
  appareil physique sur site ; un secret compromis se révoque depuis le
  hub (🔑 régénérer) et n'ouvre rien d'autre que l'envoi de mesures
  pour cet appareil. La clé WiFi, elle, est effacée de la FAT au premier
  boot (elle reste dans la configuration réseau du Pi, comme sur tout
  client).
- **TLS vers le central** : le collecteur vérifie le certificat de
  tls-proxy avec l'AC du projet (`--ca`) ; `--central-insecure`
  désactive la vérification pour dépanner, jamais par défaut.
- **iperf3** (`--iperf3`) s'installe par `apt` au premier démarrage si le
  réseau est disponible à ce moment-là (meilleur effort, 3 min max) ; sinon
  `sudo apt install iperf3` plus tard. Le collecteur peut servir de
  serveur de référence : `iperf3 -s -D` (à ajouter en service si utile).

## Vérifié / non vérifié

**Vérifié** (environnement de développement) : construction complète des
deux rôles sur une image **synthétique** au format Raspberry Pi OS (MBR +
partition FAT32 de boot + `cmdline.txt`/`issue.txt`), inspection du
résultat avec mtools — payload, `device.json`, `settings.env` (y compris
une clé WiFi contenant des apostrophes, relue par bash sans altération),
`userconf.txt` (hash SHA-512), fichier `ssh`, `cmdline.txt` avec la
directive et le bon point de montage, `fleet.json`/`central-ca.crt`/
`authorized_keys` pour un collecteur, image de base laissée intacte ;
**provisionnement de bout en bout** contre un `netprobe-api` réel lancé
localement (création de la sonde par l'API → `build-image.sh --api` →
`device.json` avec le secret et les tâches) ; syntaxe bash des deux scripts.

**Non vérifié** — et c'est la partie qui compte : **aucun Raspberry Pi
n'a démarré ici**. Le téléchargement de l'image officielle est bloqué
depuis l'environnement de développement (proxy), donc ni la structure
réelle de l'image du jour, ni `raspi-config nonint`, ni `userconf-pi`, ni
l'ordre des unités au premier boot n'ont été observés. Points à regarder
en priorité au premier essai réel, dans `/var/log/netprobe-firstrun.log` :
le point de montage détecté (`boot=…` en première ligne), la création de
l'utilisateur, la connexion WiFi (`do_wifi_ssid_passphrase`), l'activation
des services. Si le script n'a pas tourné du tout : vérifier que
`cmdline.txt` contient bien `systemd.run=` et que le chemin correspond au
point de montage de cette image (`--boot-mount` pour forcer).
