# -*- coding: utf-8 -*-
"""Émulation sur un hôte (livraison #831) -- commande `emulation` du central (hub supervision) et coureur du hub maison.

Profils :
  - Raspberry Pi 3 B, Zero W, Zero 2 W, à deux niveaux :
      * conteneur : Raspberry Pi OS Lite officiel (image vérifiée par SHA-256) importé en image Docker, exécuté par
        émulation utilisateur QEMU (binfmt) -- armv6 (CPU arm1176) pour la Zero W, arm64 (Cortex-A53) pour la 3 B et la
        Zero 2 W ; rapide, pour l'agent, ses sondes logicielles et son installation ;
      * système : machine QEMU complète (raspi3b, raspi0 ; la Zero 2 W = même puce que la 3 B, machine raspi3b avec son
        arbre de périphériques), noyau et DTB de l'image, réseau usb-net, SSH redirigé sur 127.0.0.1 de l'hôte ; lent.
  - Android (émulateur officiel, sans fenêtre) : API 24 (7.0) à 35 (15), x86_64 et x86 avec KVM ; arm64-v8a seulement
    sur un hôte ARM. Licences du SDK : acceptées seulement si la personne coche la case (paramètre accepter_licences).
Actions : preparer, lancer, arreter, detruire, lister, deployer_agent (installation SUPERVISÉE de l'agent dans un
conteneur Raspberry : la ligne d'installation du central, puis l'enrôlement se voit dans Agents hôtes).
L'hôte : root, Docker, qemu-system-arm / qemu-system-aarch64 (paquet qemu-system-arm), qemu-utils ; Android : KVM.
Pur et testé : profils, valider, script."""
import json
import os
import re
import shlex

RACINE = "/var/lib/si-emulation"
ANDROID_API = {24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9", 29: "10", 30: "11", 31: "12", 32: "12L", 33: "13", 34: "14", 35: "15"}
ANDROID_ABIS = ("x86_64", "x86", "arm64-v8a")
SDK = "/opt/android-sdk"
OUTILS_ANDROID = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
RASPBERRY = {
    "rpi3b": {"titre": "Raspberry Pi 3 B", "arch": "arm64", "plateforme": "linux/arm64", "cpu": "cortex-a53",
              "qemu": "qemu-system-aarch64", "machine": "raspi3b", "mem": "1G", "noyau": "kernel8.img", "dtb": "bcm2710-rpi-3-b.dtb"},
    "rpi0w": {"titre": "Raspberry Pi Zero W", "arch": "armhf", "plateforme": "linux/arm/v6", "cpu": "arm1176",
              "qemu": "qemu-system-arm", "machine": "raspi0", "mem": "512M", "noyau": "kernel.img", "dtb": "bcm2708-rpi-zero-w.dtb"},
    "rpi02w": {"titre": "Raspberry Pi Zero 2 W", "arch": "arm64", "plateforme": "linux/arm64", "cpu": "cortex-a53",
               "qemu": "qemu-system-aarch64", "machine": "raspi3b", "mem": "1G", "noyau": "kernel8.img", "dtb": "bcm2710-rpi-zero-2-w.dtb"},
}
ACTIONS = ("preparer", "lancer", "arreter", "detruire", "lister", "deployer_agent", "exporter_image", "supprimer_export", "installer_apk")
_EXPORT = re.compile(r"^emu-[a-z0-9-]{1,40}-\d{8}-\d{4}\.img\.xz$")
_URL = re.compile(r"^https://[^\s'\"\\`$]{1,500}$")
_APK = re.compile(r"^[A-Za-z0-9._-]{1,120}\.apk$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^emu-[a-z0-9-]{1,40}$")


def profils(arch_hote="x86_64"):
    """Catalogue avec disponibilité sur cet hôte (Android arm64 : hôte ARM ; x86 : hôte x86)."""
    out = []
    for k, r in RASPBERRY.items():
        out.append({"id": k, "famille": "raspberry", "titre": r["titre"], "modes": ["conteneur", "systeme"], "arch": r["arch"], "disponible": True})
    arm = arch_hote in ("aarch64", "arm64")
    for api, ver in sorted(ANDROID_API.items()):
        for abi in ANDROID_ABIS:
            if abi == "x86" and api > 30:
                continue                                     # plus d'image x86 32 bits au-delà d'Android 11
            dispo = (abi == "arm64-v8a") == arm
            out.append({"id": "android-%d-%s" % (api, abi), "famille": "android", "titre": "Android %s (API %d) %s" % (ver, api, abi),
                        "modes": ["avd"], "arch": abi, "api": api, "disponible": dispo,
                        "raison": None if dispo else ("hôte ARM requis" if abi == "arm64-v8a" else "hôte x86_64 requis")})
    return out


def _profil(pid):
    if pid in RASPBERRY:
        return dict(RASPBERRY[pid], id=pid, famille="raspberry")
    m = re.match(r"^android-(\d+)-(x86_64|x86|arm64-v8a)$", str(pid or ""))
    if m and int(m.group(1)) in ANDROID_API:
        return {"id": pid, "famille": "android", "api": int(m.group(1)), "abi": m.group(2)}
    return None


def valider(params, arch_hote="x86_64"):
    p = params or {}
    action = str(p.get("action") or "")
    if action not in ACTIONS:
        return None, "action : " + ", ".join(ACTIONS)
    v = {"action": action}
    if action == "lister":
        return v, None
    if action == "supprimer_export":
        if not _EXPORT.match(str(p.get("nom") or "")):
            return None, "nom : <instance>-AAAAMMJJ-HHMM.img.xz"
        v["nom"] = p["nom"]
        return v, None
    if action in ("arreter", "detruire", "deployer_agent", "exporter_image", "installer_apk") or action == "lancer":
        iid = str(p.get("instance") or "")
        if not _ID.match(iid):
            return None, "instance : emu-<nom> (minuscules, chiffres, tirets)"
        v["instance"] = iid
    if action in ("preparer", "lancer"):
        pr = _profil(p.get("profil"))
        if not pr:
            return None, "profil inconnu"
        mode = str(p.get("mode") or ("avd" if pr["famille"] == "android" else "conteneur"))
        if (pr["famille"] == "android") != (mode == "avd") or mode not in ("conteneur", "systeme", "avd"):
            return None, "mode : conteneur ou systeme (Raspberry), avd (Android)"
        if pr["famille"] == "android":
            dispo = next(x for x in profils(arch_hote) if x["id"] == pr["id"])
            if not dispo["disponible"]:
                return None, "profil %s indisponible sur cet hôte : %s" % (pr["id"], dispo["raison"])
            if not p.get("accepter_licences"):
                return None, "Android : cocher l'acceptation des licences du SDK Android (sdkmanager --licenses)"
        v.update(profil=pr, mode=mode, accepter_licences=bool(p.get("accepter_licences")))
        try:
            v["port"] = int(p.get("port") or 0)
        except (TypeError, ValueError):
            return None, "port entier"
    if action == "installer_apk":
        url, fichier, sha = str(p.get("url") or "").strip(), str(p.get("fichier") or ""), str(p.get("sha256") or "").strip().lower()
        if fichier:
            if not (fichier.startswith(RACINE + "/apk/") and _APK.match(fichier[len(RACINE) + 5:])):
                return None, "fichier : APK déposé dans %s/apk/" % RACINE
            v["fichier"] = fichier
        elif _URL.match(url) and url.lower().split("?")[0].endswith(".apk") or _URL.match(url) and sha:
            v["url"] = url
        else:
            return None, "APK : adresse https://….apk (ou empreinte SHA-256 fournie), ou fichier déposé sur le hub"
        if sha and not _SHA.match(sha):
            return None, "sha256 : 64 caractères hexadécimaux"
        v["sha256"] = sha or None
    if action == "deployer_agent":
        ligne = str(p.get("ligne") or "").strip()
        if not ligne or len(ligne) > 2000 or "\n" in ligne:
            return None, "deployer_agent : ligne d'installation Linux du central (une ligne)"
        v["ligne"] = ligne
    return v, None


def _rpios(arch):
    """Image Raspberry Pi OS Lite officielle (dernière), SHA-256 vérifié, décompressée -> $D/rpios-<arch>.img."""
    return """D=%(r)s/images; mkdir -p "$D"; cd "$D"
U=$(curl -fsSIL -o /dev/null -w '%%{url_effective}' https://downloads.raspberrypi.com/raspios_lite_%(a)s_latest) || fail "dépôt Raspberry Pi injoignable"
F=$(basename "$U")
if [ ! -f "$F" ]; then
  curl -fSL --retry 3 -o "$F.part" "$U" || fail "téléchargement impossible : $U"
  S=$(curl -fsSL "$U.sha256" | awk '{print $1}')
  [ -n "$S" ] && [ "$(sha256sum "$F.part" | cut -d' ' -f1)" = "$S" ] || { rm -f "$F.part"; fail "empreinte SHA-256 de l'image différente ou absente : refusée"; }
  mv "$F.part" "$F"
fi
IMG="${F%%.xz}"; [ -f "$IMG" ] || xz -dk "$F" || fail "décompression impossible"
ln -sf "$IMG" rpios-%(a)s.img
part() { sfdisk -J "$1" | python3 -c 'import json,sys; t=json.load(sys.stdin)["partitiontable"]; print(t["partitions"][int(sys.argv[1])]["start"]*t.get("sectorsize",512))' "$2"; }
""" % {"r": RACINE, "a": arch}


PAQUETS = r"""paquets() { m=; for p in "$@"; do dpkg -s "$p" >/dev/null 2>&1 || m="$m $p"; done; [ -z "$m" ] && return 0
  command -v apt-get >/dev/null || fail "paquets manquants :$m (pas d'apt-get : installation manuelle)"
  DEBIAN_FRONTEND=noninteractive apt-get update -q >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q $m >/dev/null || fail "installation impossible :$m"; echo "paquets installés :$m"; }
champ() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); [d := (d or {}).get(k) for k in sys.argv[2:]]; print("" if d is None else d)' "$@"; }
ecran_arreter() { W=$(champ "$1/instance.json" ecran web 2>/dev/null || true); V=$(champ "$1/instance.json" ecran vnc 2>/dev/null || true)
  [ -n "$W" ] && pkill -f "websockify.*:$W " 2>/dev/null || true; [ -n "$V" ] && pkill -f "rfbport $V" 2>/dev/null || true
  [ -f "$1/xvfb.pid" ] && kill "$(cat "$1/xvfb.pid")" 2>/dev/null || true; }
"""


def ecran_ports(mode, port):
    """Écran d'une instance : (vnc, web) -- web = websockify + noVNC (navigateur), vnc lié à 127.0.0.1."""
    if mode == "systeme":
        n = max(0, int(port or 52200) - 52200)
        return 5900 + n, 6900 + n
    if mode == "avd":
        n = max(0, (int(port or 5554) - 5554) // 2)
        return 6000 + n, 7000 + n
    return None, None


def script(v, inst=None):
    """Script bash (root) de l'action ; `inst` : instance enregistrée (lancer / arrêter / détruire)."""
    tete = "set -eu\nfail() { echo \"ERREUR : $*\" >&2; exit 1; }\nmkdir -p %s/instances\n" % RACINE + PAQUETS
    a = v["action"]
    if a == "lister":
        return tete + """for f in %s/instances/*/instance.json; do [ -f "$f" ] && cat "$f" && echo; done
docker ps -a --filter label=si-emulation=1 --format '{{json .}}' 2>/dev/null | sed 's/^/DOCKER /' || true
""" % RACINE
    if a in ("preparer", "lancer"):
        pr = v["profil"]
        if pr["famille"] == "raspberry":
            corps = _rpios(pr["arch"])
            if v["mode"] == "conteneur":
                corps += """command -v docker >/dev/null || fail "Docker absent"
docker run --privileged --rm tonistiigi/binfmt --install arm,arm64 >/dev/null || fail "émulation binfmt (qemu-user) non installée"
if ! docker image inspect rpios-lite:%(a)s >/dev/null 2>&1; then
  M=$(mktemp -d); mount -o loop,ro,offset=$(part rpios-%(a)s.img 1) rpios-%(a)s.img "$M" || fail "montage de la racine impossible (loop)"
  tar -C "$M" -c . | docker import --platform %(pl)s --change 'CMD ["/bin/bash"]' - rpios-lite:%(a)s >/dev/null || { umount "$M"; fail "import Docker impossible"; }
  umount "$M"; rmdir "$M"
fi
echo "image rpios-lite:%(a)s prête (%(pl)s)"
""" % {"a": pr["arch"], "pl": pr["plateforme"]}
            else:
                corps += """paquets qemu-system-arm qemu-utils novnc websockify
command -v %(q)s >/dev/null || fail "%(q)s absent (paquet qemu-system-arm)"
B="$D/boot-%(a)s"
if [ ! -f "$B/%(k)s" ]; then
  mkdir -p "$B"; M=$(mktemp -d); mount -o loop,ro,offset=$(part rpios-%(a)s.img 0) rpios-%(a)s.img "$M" || fail "montage de la partition de démarrage impossible"
  cp "$M"/*.img "$M"/*.dtb "$B"/ 2>/dev/null; umount "$M"; rmdir "$M"
fi
[ -f "$B/%(k)s" ] && [ -f "$B/%(dtb)s" ] || fail "noyau %(k)s ou %(dtb)s absent de l'image"
echo "noyau et arbre de périphériques prêts ($B)"
""" % {"q": pr["qemu"], "a": pr["arch"], "k": pr["noyau"], "dtb": pr["dtb"]}
        else:
            img = "system-images;android-%d;google_apis;%s" % (pr["api"], pr["abi"])
            corps = """[ -e /dev/kvm ] || fail "KVM absent : émulateur Android impossible (activer la virtualisation imbriquée pour une VM)"
command -v java >/dev/null || paquets default-jre-headless
paquets xvfb x11vnc novnc websockify
export ANDROID_SDK_ROOT=%(sdk)s ANDROID_HOME=%(sdk)s
if [ ! -x %(sdk)s/cmdline-tools/latest/bin/sdkmanager ]; then
  mkdir -p %(sdk)s/cmdline-tools; T=$(mktemp -d)
  curl -fSL -o "$T/outils.zip" '%(outils)s' || fail "outils du SDK Android injoignables"
  echo "outils du SDK : sha256 $(sha256sum "$T/outils.zip" | cut -d' ' -f1) (à comparer à developer.android.com/studio)"
  python3 -c 'import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$T/outils.zip" "$T" && mv "$T/cmdline-tools" %(sdk)s/cmdline-tools/latest
  chmod +x %(sdk)s/cmdline-tools/latest/bin/*
fi
S=%(sdk)s/cmdline-tools/latest/bin/sdkmanager
yes | "$S" --licenses >/dev/null 2>&1 || true
"$S" --install "platform-tools" "emulator" "%(img)s" >/dev/null || fail "installation de %(img)s impossible"
echo "Android API %(api)d %(abi)s prêt"
""" % {"sdk": SDK, "outils": OUTILS_ANDROID, "img": img, "api": pr["api"], "abi": pr["abi"]}
            if not v.get("accepter_licences"):
                corps = 'fail "licences du SDK Android non acceptées"\n'
        if a == "preparer":
            return tete + corps
        return tete + corps + _lancer(v)
    if a == "deployer_agent":
        return tete + """I=%(r)s/instances/%(i)s; [ -f "$I/instance.json" ] || fail "instance inconnue"
grep -q '"mode": "conteneur"' "$I/instance.json" || fail "installation supervisée : instances conteneur Raspberry seulement pour l'instant"
docker exec %(i)s sh -c %(l)s || fail "installation de l'agent en échec"
echo "agent installé dans %(i)s : son enrôlement apparaît dans Agents hôtes"
""" % {"r": RACINE, "i": v["instance"], "l": shlex.quote(v["ligne"])}
    if a == "supprimer_export":
        return tete + 'rm -f %s/exports/%s %s/exports/%s.sha256\necho "export %s supprimé"\n' % (RACINE, v["nom"], RACINE, v["nom"], v["nom"])
    if a == "exporter_image":
        return tete + _exporter(v["instance"])
    if a == "installer_apk":
        return tete + _apk(v)
    i = v["instance"]
    if a == "arreter":
        return tete + """I=%(r)s/instances/%(i)s
docker stop %(i)s >/dev/null 2>&1 || true
[ -f "$I/instance.json" ] && ecran_arreter "$I"
[ -f "$I/pid" ] && kill "$(cat "$I/pid")" 2>/dev/null || true
[ -f "$I/qemu.pid" ] && kill "$(cat "$I/qemu.pid")" 2>/dev/null || true
[ -f "$I/instance.json" ] && sed -i 's/"etat": "[a-z_]*"/"etat": "arrete"/' "$I/instance.json"
echo "%(i)s arrêtée"
""" % {"r": RACINE, "i": i}
    if a == "detruire":
        return tete + """I=%(r)s/instances/%(i)s
docker rm -f %(i)s >/dev/null 2>&1 || true
[ -f "$I/instance.json" ] && ecran_arreter "$I"
[ -f "$I/pid" ] && kill "$(cat "$I/pid")" 2>/dev/null || true
[ -f "$I/qemu.pid" ] && kill "$(cat "$I/qemu.pid")" 2>/dev/null || true
rm -rf "$I"
echo "%(i)s détruite"
""" % {"r": RACINE, "i": i}
    raise ValueError(a)


def _web(ports):
    """websockify + noVNC : écoute sur le pont Docker (docker0, joignable par le hub de l'hôte, pas par le réseau local)
    sinon 127.0.0.1 ; l'adresse retenue est notée dans instance.json."""
    vnc, web = ports
    return """E=$(ip -4 -o addr show docker0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1); E=${E:-127.0.0.1}
if command -v websockify >/dev/null && [ -f /usr/share/novnc/vnc.html ]; then
  pkill -f "websockify.*:%(w)d " 2>/dev/null || true
  websockify -D --web /usr/share/novnc "$E:%(w)d" 127.0.0.1:%(v)d >/dev/null 2>&1 || echo "websockify n'a pas démarré"
  python3 - "$I/instance.json" "$E" <<'EOJ'
import json, sys
d = json.load(open(sys.argv[1])); d["ecran"] = dict(d.get("ecran") or {}, ecoute=sys.argv[2]); json.dump(d, open(sys.argv[1], "w"))
EOJ
  echo "écran : noVNC sur $E:%(w)d (VNC 127.0.0.1:%(v)d)"
else echo "noVNC absent : pas d'écran dans le navigateur (Préparer installe novnc et websockify)"; fi
""" % {"w": web, "v": vnc}


def _lancer(v):
    pr, i, port = v["profil"], v["instance"], v.get("port") or 0
    ecrire = """I=%(r)s/instances/%(i)s; mkdir -p "$I"
python3 - "$I/instance.json" <<'EOJ'
import json, sys, time
json.dump(%(meta)s | {"cree": time.time()}, open(sys.argv[1], "w"))
EOJ
""" % {"r": RACINE, "i": i, "meta": json.dumps({"id": i, "profil": pr["id"], "famille": pr["famille"], "mode": v["mode"], "port": port, "etat": "demarre",
                       "ecran": dict(zip(("vnc", "web"), ecran_ports(v["mode"], port))) if v["mode"] != "conteneur" else None})}
    if v["mode"] == "conteneur":
        return """docker rm -f %(i)s >/dev/null 2>&1 || true
docker run -d --name %(i)s --hostname %(i)s --label si-emulation=1 --label si-emulation.profil=%(p)s --platform %(pl)s -e QEMU_CPU=%(cpu)s rpios-lite:%(a)s sleep infinity >/dev/null || fail "démarrage du conteneur impossible"
docker exec %(i)s uname -m
""" % {"i": i, "p": pr["id"], "pl": pr["plateforme"], "cpu": pr["cpu"], "a": pr["arch"]} + ecrire + 'echo "conteneur %s démarré"\n' % i
    if v["mode"] == "systeme":
        return ecrire + """cp --reflink=auto "$D/rpios-%(a)s.img" "$I/disque.img"
qemu-img resize -f raw "$I/disque.img" 4G >/dev/null
M=$(mktemp -d); mount -o loop,offset=$(part "$I/disque.img" 0) "$I/disque.img" "$M" || fail "montage de la partition de démarrage du clone impossible"
touch "$M/ssh"; MDP=$(head -c 12 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)
echo "emul:$(openssl passwd -6 "$MDP")" > "$M/userconf.txt"; umount "$M"; rmdir "$M"
umask 077; echo "$MDP" > "$I/mdp"
%(q)s -M %(m)s -m %(mem)s -kernel "$B/%(k)s" -dtb "$B/%(dtb)s" -drive file="$I/disque.img",if=sd,format=raw \\
  -append "console=ttyAMA0,115200 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 rootwait dwc_otg.fiq_fsm_enable=0" \\
  -device usb-net,netdev=n0 -netdev user,id=n0,hostfwd=tcp:127.0.0.1:%(port)d-:22 \\
  -device usb-kbd -device usb-tablet -display vnc=127.0.0.1:%(vn)d \\
  -serial file:"$I/console.log" -daemonize -pidfile "$I/qemu.pid" || fail "QEMU n'a pas démarré"
echo "%(i)s démarre (machine %(m)s) : ssh -p %(port)d emul@127.0.0.1 depuis l'hôte (mot de passe : $I/mdp, root) ; console : $I/console.log"
""" % {"a": pr["arch"], "q": pr["qemu"], "m": pr["machine"], "mem": pr["mem"], "k": pr["noyau"], "dtb": pr["dtb"], "port": port or 52222, "i": i, "vn": ecran_ports("systeme", port)[0] - 5900} + _web(ecran_ports("systeme", port))
    img = "system-images;android-%d;google_apis;%s" % (pr["api"], pr["abi"])
    return ecrire + """export ANDROID_SDK_ROOT=%(sdk)s ANDROID_HOME=%(sdk)s ANDROID_AVD_HOME="$I/avd"
mkdir -p "$I/avd"
echo no | %(sdk)s/cmdline-tools/latest/bin/avdmanager create avd -n %(i)s -k "%(img)s" -d pixel_5 --force >/dev/null || fail "création de l'appareil virtuel impossible"
nohup Xvfb :%(d)d -screen 0 1280x2400x24 -nolisten tcp >"$I/xvfb.log" 2>&1 &
echo $! > "$I/xvfb.pid"; sleep 1
DISPLAY=:%(d)d nohup %(sdk)s/emulator/emulator -avd %(i)s -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -port %(port)d >"$I/emulateur.log" 2>&1 &
echo $! > "$I/pid"
x11vnc -display :%(d)d -localhost -rfbport %(vnc)d -forever -shared -nopw -bg -o "$I/x11vnc.log" >/dev/null 2>&1 || echo "x11vnc absent : pas d'écran (Préparer l'installe)"
echo "%(i)s démarre : adb -s emulator-%(port)d (console %(port)d) ; journal $I/emulateur.log"
""" % {"sdk": SDK, "i": i, "img": img, "port": port or 5554, "d": 100 + ecran_ports("avd", port)[0] - 6000, "vnc": ecran_ports("avd", port)[0]} + _web(ecran_ports("avd", port))


# Premier démarrage d'une image exportée (posé dans l'image, exécuté une fois sur le vrai Raspberry Pi).
PREMIER_DEMARRAGE = r"""#!/bin/sh
# Premier démarrage d'une image exportée par le hub : identité unique (machine-id, clés SSH), partition racine agrandie
# à la taille de la carte, puis -- si /boot/firmware/si-premier-demarrage.conf existe -- utilisateur, clé SSH, nom,
# Wi-Fi et enrôlement de l'agent. Le fichier de réglages est effacé après usage ; le service se désactive.
L=/var/log/si-premier-demarrage.log; exec >>"$L" 2>&1; echo "== $(date)"
[ -s /etc/machine-id ] || systemd-machine-id-setup
ls /etc/ssh/ssh_host_*_key >/dev/null 2>&1 || ssh-keygen -A
R=$(findmnt -no SOURCE /); D=/dev/$(lsblk -no pkname "$R"); N=$(echo "$R" | sed 's/.*[^0-9]//')
echo ", +" | sfdisk --force --no-reread -N "$N" "$D" && partx -u "$D" && resize2fs "$R" && echo "partition agrandie"
C=; for f in /boot/firmware/si-premier-demarrage.conf /boot/si-premier-demarrage.conf; do [ -f "$f" ] && C=$f; done
val() { [ -n "$C" ] && sed -n "s/^$1=//p" "$C" | head -1 | sed 's/^"//; s/"$//'; }
U=$(val UTILISATEUR); H=$(val MOT_DE_PASSE_HASH); K=$(val CLE_SSH); NH=$(val NOM_HOTE)
S=$(val WIFI_SSID); P=$(val WIFI_CLE); PAYS=$(val WIFI_PAYS); A=$(val AGENT_LIGNE)
if [ -n "$U" ]; then
  id "$U" >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo,adm,video,plugdev,dialout "$U"
  [ -n "$H" ] && echo "$U:$H" | chpasswd -e
  if [ -n "$K" ]; then mkdir -p "/home/$U/.ssh"; echo "$K" >> "/home/$U/.ssh/authorized_keys"; chown -R "$U:$U" "/home/$U/.ssh"; chmod 700 "/home/$U/.ssh"; chmod 600 "/home/$U/.ssh/authorized_keys"; fi
  echo "utilisateur $U prêt"
fi
if [ -n "$NH" ]; then echo "$NH" > /etc/hostname; hostname "$NH"; sed -i "s/^127.0.1.1.*/127.0.1.1\t$NH/" /etc/hosts; fi
if [ -n "$S" ]; then
  command -v raspi-config >/dev/null && raspi-config nonint do_wifi_country "${PAYS:-FR}" || rfkill unblock wifi || true
  if command -v nmcli >/dev/null; then
    nmcli connection add type wifi ifname wlan0 con-name si-wifi ssid "$S" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$P" connection.autoconnect yes && nmcli connection up si-wifi || true
  else
    printf 'country=%s\nctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\nnetwork={\n ssid="%s"\n psk="%s"\n}\n' "${PAYS:-FR}" "$S" "$P" > /etc/wpa_supplicant/wpa_supplicant.conf
    wpa_cli -i wlan0 reconfigure || true
  fi
  echo "Wi-Fi $S configuré"
fi
if [ -n "$A" ]; then
  for i in $(seq 1 60); do ip route | grep -q '^default' && break; sleep 2; done
  sh -c "$A" && echo "agent installé (enrôlement visible dans le hub)" || echo "ERREUR installation de l'agent"
fi
[ -n "$C" ] && { shred -u "$C" 2>/dev/null || rm -f "$C"; }
systemctl disable si-premier-demarrage.service
"""
UNITE_PREMIER = """[Unit]
Description=Premier démarrage d'une image exportée par le hub (identité, partition, utilisateur, Wi-Fi, agent)
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/si-premier-demarrage
[Install]
WantedBy=multi-user.target
"""
CONF_EXEMPLE = """# Réglages du premier démarrage -- renommer en si-premier-demarrage.conf (partition de démarrage), effacé après usage.
# Mot de passe : openssl passwd -6 'le-mot-de-passe'  (coller le résultat, jamais le mot de passe en clair)
UTILISATEUR=pi
MOT_DE_PASSE_HASH=
CLE_SSH=
NOM_HOTE=raspi-01
WIFI_SSID=
WIFI_CLE=
WIFI_PAYS=FR
# Ligne d'installation Linux de l'agent (hub supervision > Agents hôtes > Enrôler) ; vide = pas d'agent
AGENT_LIGNE=
"""


def _exporter(i):
    """Image installable (carte SD) à partir d'une machine complète : copie, généralisation, réduction, xz + SHA-256."""
    return (("""I=%(r)s/instances/%(i)s; [ -f "$I/instance.json" ] || fail "instance inconnue"
[ "$(champ "$I/instance.json" mode)" = systeme ] || fail "export : instances Raspberry « machine complète » seulement"
for c in losetup e2fsck resize2fs dumpe2fs sfdisk xz; do command -v $c >/dev/null || fail "$c absent"; done
if [ -f "$I/qemu.pid" ] && kill -0 "$(cat "$I/qemu.pid")" 2>/dev/null; then
  ecran_arreter "$I"; kill "$(cat "$I/qemu.pid")"; for t in $(seq 1 30); do kill -0 "$(cat "$I/qemu.pid")" 2>/dev/null || break; sleep 1; done
  sed -i 's/"etat": "[a-z_]*"/"etat": "arrete"/' "$I/instance.json"; echo "instance arrêtée pour l'export (conseil : sudo poweroff dans la machine avant)"
fi
X=%(r)s/exports; mkdir -p "$X"; N=%(i)s-$(date +%%Y%%m%%d-%%H%%M); W="$X/$N.img"
cp --reflink=auto "$I/disque.img" "$W"
L=$(losetup -fP --show "$W") || fail "losetup impossible"; MR=$(mktemp -d)
nettoie() { umount "$MR/boot/firmware" 2>/dev/null; umount "$MR/boot" 2>/dev/null; umount "$MR" 2>/dev/null; losetup -d "$L" 2>/dev/null; rmdir "$MR" 2>/dev/null; true; }
trap nettoie EXIT
rc=0; e2fsck -fy "${L}p2" >/dev/null 2>&1 || rc=$?; [ $rc -lt 4 ] || fail "système de fichiers racine en erreur"
mount "${L}p2" "$MR" || fail "montage de la racine impossible"
BD="$MR/boot/firmware"; [ -d "$BD" ] || BD="$MR/boot"; mount "${L}p1" "$BD" || fail "montage de la partition de démarrage impossible"
rm -f "$MR"/etc/ssh/ssh_host_* "$MR/var/lib/dbus/machine-id" "$BD/userconf.txt" "$BD/ssh" "$BD/si-premier-demarrage.conf"
: > "$MR/etc/machine-id"
rm -f "$MR"/root/.bash_history "$MR"/home/*/.bash_history "$MR/etc/si-agent/agent.json" "$MR/var/lib/si-agent/state.json"
find "$MR/var/log" -type f -exec truncate -s 0 {} + 2>/dev/null || true
sed -i 's/^emul:[^:]*:/emul:!:/' "$MR/etc/shadow"
cat > "$MR/usr/local/sbin/si-premier-demarrage" <<'EOS'
""" % {"r": RACINE, "i": i}) + PREMIER_DEMARRAGE + """EOS
chmod 755 "$MR/usr/local/sbin/si-premier-demarrage"
cat > "$MR/etc/systemd/system/si-premier-demarrage.service" <<'EOS'
""" + UNITE_PREMIER + """EOS
mkdir -p "$MR/etc/systemd/system/multi-user.target.wants"
ln -sf /etc/systemd/system/si-premier-demarrage.service "$MR/etc/systemd/system/multi-user.target.wants/si-premier-demarrage.service"
touch "$BD/ssh"
cat > "$BD/si-premier-demarrage.conf.exemple" <<'EOS'
""" + CONF_EXEMPLE + """EOS
sync; umount "$BD"; umount "$MR"
e2fsck -fy "${L}p2" >/dev/null 2>&1 || true
resize2fs -M "${L}p2" >/dev/null 2>&1 || fail "réduction du système de fichiers impossible"
BC=$(dumpe2fs -h "${L}p2" 2>/dev/null | awk -F: '/^Block count/{print $2+0}'); BS=$(dumpe2fs -h "${L}p2" 2>/dev/null | awk -F: '/^Block size/{print $2+0}')
losetup -d "$L"; trap - EXIT; rmdir "$MR" 2>/dev/null || true
S2=$(sfdisk -J "$W" | python3 -c 'import json,sys; print(json.load(sys.stdin)["partitiontable"]["partitions"][1]["start"])')
NS=$(( (BC * BS + 511) / 512 + 131072 ))
echo "$S2,$NS" | sfdisk --force -N 2 "$W" >/dev/null 2>&1 || fail "réduction de la partition impossible"
truncate -s $(( (S2 + NS) * 512 )) "$W"
xz -T0 -6 -f "$W" || fail "compression impossible"
( cd "$X" && sha256sum "$N.img.xz" > "$N.img.xz.sha256" )
echo "EXPORT $N.img.xz $(stat -c %%s "$X/$N.img.xz") $(cut -d' ' -f1 "$X/$N.img.xz.sha256")"
echo "graver : xzcat $N.img.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress (ou Raspberry Pi Imager, image personnalisée)"
echo "réglages du 1er démarrage : copier si-premier-demarrage.conf.exemple en si-premier-demarrage.conf sur la partition de démarrage"
""").replace("%%", "%")


def _apk(v):
    """Installe une APK dans un émulateur Android démarré (adb), comme sur un téléphone."""
    src = ('curl -fSL --max-filesize 500000000 -o "$F" %s || fail "téléchargement de l\'APK impossible"' % shlex.quote(v["url"])) if v.get("url") \
        else 'cp %s "$F"' % shlex.quote(v["fichier"])
    return """I=%(r)s/instances/%(i)s; [ -f "$I/instance.json" ] || fail "instance inconnue"
[ "$(champ "$I/instance.json" mode)" = avd ] || fail "APK : instances Android seulement"
P=$(champ "$I/instance.json" port); A=%(sdk)s/platform-tools/adb; [ -x "$A" ] || fail "adb absent (Préparer)"
mkdir -p "$I/apk"; F="$I/apk/app-$(date +%%s).apk"
%(src)s
[ "$(head -c 2 "$F")" = PK ] || fail "le fichier n'est pas une APK (archive zip)"
%(sha)s
S="emulator-$P"; timeout 180 "$A" -s "$S" wait-for-device || fail "émulateur $S injoignable (démarré ?)"
for t in $(seq 1 90); do [ "$("$A" -s "$S" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && break; sleep 2; done
AV=$("$A" -s "$S" shell pm list packages -3 | sort)
"$A" -s "$S" install -r -g "$F" || fail "installation refusée par Android"
AP=$("$A" -s "$S" shell pm list packages -3 | sort)
echo "APK installée ($(sha256sum "$F" | cut -d' ' -f1)) ; paquets ajoutés : $(comm -13 <(echo "$AV") <(echo "$AP") | sed 's/package://' | tr '\n' ' ')"
""" % {"r": RACINE, "i": v["instance"], "sdk": SDK, "src": src,
       "sha": ('[ "$(sha256sum "$F" | cut -d\' \' -f1)" = %s ] || fail "empreinte SHA-256 différente : refusée"' % v["sha256"]) if v.get("sha256") else 'echo "sans empreinte fournie : sha256 $(sha256sum "$F" | cut -d\' \' -f1)"'}


def lire_liste(stdout):
    """Sortie de `lister` -> [instances] (registre + état Docker)."""
    inst, docker = {}, {}
    for l in (stdout or "").splitlines():
        l = l.strip()
        try:
            if l.startswith("DOCKER "):
                d = json.loads(l[7:])
                docker[d.get("Names")] = d
            elif l.startswith("{"):
                d = json.loads(l)
                inst[d.get("id")] = d
        except ValueError:
            continue
    for k, d in inst.items():
        if d.get("mode") == "conteneur":
            dk = docker.get(k) or {}
            d["etat"] = "en_marche" if dk.get("State") == "running" else ("arrete" if dk else "absent")
            d["docker"] = dk.get("Status")
    return sorted(inst.values(), key=lambda x: x.get("id") or "")


def run(cmd, params, arch_hote=None):
    arch_hote = arch_hote or os.uname().machine
    v, err = valider(params, arch_hote)
    if err:
        return {"ok": False, "error": err}
    r = cmd(["bash", "-c", script(v)], timeout=3600 if v["action"] in ("preparer", "lancer", "exporter_image") else 900 if v["action"] == "installer_apk" else 300)
    rc = getattr(r, "returncode", -1)
    out, errt = (getattr(r, "stdout", "") or "")[-4000:], (getattr(r, "stderr", "") or "")[-2000:]
    if rc != 0:
        msg = next((l for l in errt.splitlines()[::-1] if l.startswith("ERREUR")), None) or errt.strip()[-400:] or "code %s" % rc
        return {"ok": False, "error": msg, "result": {"stdout": out, "stderr": errt}}
    res = {"stdout": out, "action": v["action"], "arch_hote": arch_hote}
    if v["action"] == "lister":
        res["instances"] = lire_liste(out)
        res["profils"] = profils(arch_hote)
    return {"ok": True, "error": None, "result": res}
