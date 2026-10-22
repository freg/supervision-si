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
