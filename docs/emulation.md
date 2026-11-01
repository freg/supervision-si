# Émulation et déploiement supervisé (#831)

Tuile **Équipements > Émulation**. Les ordres passent par la commande `emulation` de l'agent de l'hôte choisi
(`si-agent/agent/si_agent/emulctl.py`) ; la sonde `plugin:emulation` remonte capacités et instances (60 s).

## Profils

| Profil | Niveau | Émulateur | Machine QEMU | Hôte |
|---|---|---|---|---|
| rpi3b | conteneur / système | qemu-system-aarch64 | `raspi3b` (bcm2710-rpi-3-b.dtb, kernel8.img, 1 Go) | tout |
| rpi02w | conteneur / système | qemu-system-aarch64 | `raspi3b` + bcm2710-rpi-zero-2-w.dtb (1 Go) | tout |
| rpi0w | conteneur / système | qemu-system-arm | `raspi0` (bcm2708-rpi-zero-w.dtb, kernel.img, 512 Mo) | tout |
| android x86_64 / x86 | AVD | emulator (SDK) | — | x86_64 + KVM (x86 ≤ API 30) |
| android arm64-v8a | AVD | emulator (SDK) | — | ARM64 + KVM |

- Conteneur : rootfs Raspberry Pi OS Lite officiel (`downloads.raspberrypi.com`, SHA-256 vérifié) importé en
  `rpios-lite:<arch>`, exécuté via binfmt (`tonistiigi/binfmt --install arm,arm64`).
- Système : image complète redimensionnée à 4 Go, `ssh` + `userconf.txt` dans /boot, réseau usb-net, SSH sur 52200+n.
- Android : API 24 à 35, `google_apis`, `-no-window -gpu swiftshader_indirect`, adb sur 5554+2n.
- Registre sur l'hôte : `/var/lib/si-emulation/instances/<id>/instance.json`, label Docker `si-emulation=1`.

## Préparer un hôte

Pas de lien : opération manuelle — installer l'agent (root), puis « Préparer » dans la tuile (installe QEMU,
binfmt, SDK Android si demandé). Licences Android : seulement si la case est cochée.

## Déployer l'agent dans une instance

« Installer l'agent » (instances conteneur) : colle la ligne d'enrôlement de **Agents > Ajouter** ; elle est masquée
dans l'historique. `install.sh` détecte l'absence de systemd et démarre l'agent par `/etc/si-agent/demarrer.sh`.

## Accès, image installable, APK (#835)

- **Écran** (machines complètes et Android) : VNC local (QEMU `-display vnc`, clavier USB, pointeur absolu ; Android dans
  Xvfb + x11vnc, souris = toucher), websockify + noVNC sur le pont Docker de l'hôte (ports 69xx / 70xx). Depuis le poste :
  pas de lien : opération manuelle -- `ssh -L 69xx:<écoute>:69xx root@<hôte>` puis `http://127.0.0.1:69xx/vnc.html`.
- **SSH** : `ssh -J root@<hôte> -p 522xx emul@127.0.0.1` (mot de passe : `/var/lib/si-emulation/instances/<id>/mdp`).
- **adb** : `ssh -L 555x:127.0.0.1:555x root@<hôte>` puis `adb connect 127.0.0.1:555x`.
- **Exporter l'image** : copie de la machine complète, généralisation (clés SSH, machine-id, journaux, identité de l'agent,
  mot de passe d'émulation verrouillé), service de premier démarrage, réduction, `xz` + SHA-256 dans
  `/var/lib/si-emulation/exports/`. Graver : `xzcat <image>.img.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress`.
  Réglages du premier démarrage : `si-premier-demarrage.conf` sur la partition de démarrage (UTILISATEUR,
  MOT_DE_PASSE_HASH = `openssl passwd -6`, CLE_SSH, NOM_HOTE, WIFI_SSID / WIFI_CLE / WIFI_PAYS, AGENT_LIGNE), effacé après usage.
- **Installer une APK** (Android) : adresse https (+ SHA-256 conseillé) ; `adb install -r -g`. Un téléphone reçoit la même APK
  (adb ou enrôlement), pas l'image système de l'émulateur.

## Écran d'un clic dans le hub supervision (#839)

Chaque hôte d'émulation lance une **porte des écrans** : websockify à jetons sur 127.0.0.1:6899 (un jeton aléatoire par
instance, fichiers `/var/lib/si-emulation/ecrans/<instance>`, retirés à l'arrêt). Mise en service, une fois par hôte
(pas de lien : opération manuelle) :

1. `.env` du hub : `SI_PROXY_PUBLISH=…,64xx=<shim de l'hôte>:127.0.0.1:6899` et `NAVIGATEURS=…,emu-<hôte>=64xx`, puis
   `cd ~/SRC/data2/tickets/supervision-si && ./scripts/run.sh up -d si-proxy tls-proxy` ;
2. tuile Navigateurs des hôtes › + Déclarer : ce nom, l'agent de l'hôte, usage « écrans d'émulation ».

Le bouton **Écran** ouvre alors `/navigateur/emu-<hôte>/vnc.html` (même origine que le hub) avec le jeton de l'instance.
