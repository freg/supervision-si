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
ACTIONS = ("preparer", "lancer", "arreter", "detruire", "lister", "deployer_agent")
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
    if action in ("arreter", "detruire", "deployer_agent") or action == "lancer":
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


def script(v, inst=None):
    """Script bash (root) de l'action ; `inst` : instance enregistrée (lancer / arrêter / détruire)."""
    tete = "set -eu\nfail() { echo \"ERREUR : $*\" >&2; exit 1; }\nmkdir -p %s/instances\n" % RACINE
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
                corps += """command -v %(q)s >/dev/null || fail "%(q)s absent (paquet qemu-system-arm)"
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
command -v java >/dev/null || fail "Java absent (paquet openjdk-17-jre-headless)"
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
    i = v["instance"]
    if a == "arreter":
        return tete + """I=%(r)s/instances/%(i)s
docker stop %(i)s >/dev/null 2>&1 || true
[ -f "$I/pid" ] && kill "$(cat "$I/pid")" 2>/dev/null || true
[ -f "$I/qemu.pid" ] && kill "$(cat "$I/qemu.pid")" 2>/dev/null || true
[ -f "$I/instance.json" ] && sed -i 's/"etat": "[a-z_]*"/"etat": "arrete"/' "$I/instance.json"
echo "%(i)s arrêtée"
""" % {"r": RACINE, "i": i}
    if a == "detruire":
        return tete + """I=%(r)s/instances/%(i)s
docker rm -f %(i)s >/dev/null 2>&1 || true
[ -f "$I/pid" ] && kill "$(cat "$I/pid")" 2>/dev/null || true
[ -f "$I/qemu.pid" ] && kill "$(cat "$I/qemu.pid")" 2>/dev/null || true
rm -rf "$I"
echo "%(i)s détruite"
""" % {"r": RACINE, "i": i}
    raise ValueError(a)


def _lancer(v):
    pr, i, port = v["profil"], v["instance"], v.get("port") or 0
    ecrire = """I=%(r)s/instances/%(i)s; mkdir -p "$I"
python3 - "$I/instance.json" <<'EOJ'
import json, sys, time
json.dump(%(meta)s | {"cree": time.time()}, open(sys.argv[1], "w"))
EOJ
""" % {"r": RACINE, "i": i, "meta": json.dumps({"id": i, "profil": pr["id"], "famille": pr["famille"], "mode": v["mode"], "port": port, "etat": "demarre"})}
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
  -append "console=ttyAMA0,115200 root=/dev/mmcblk0p2 rootfstype=ext4 rootwait dwc_otg.fiq_fsm_enable=0" \\
  -device usb-net,netdev=n0 -netdev user,id=n0,hostfwd=tcp:127.0.0.1:%(port)d-:22 \\
  -display none -serial file:"$I/console.log" -daemonize -pidfile "$I/qemu.pid" || fail "QEMU n'a pas démarré"
echo "%(i)s démarre (machine %(m)s) : ssh -p %(port)d emul@127.0.0.1 depuis l'hôte (mot de passe : $I/mdp, root) ; console : $I/console.log"
""" % {"a": pr["arch"], "q": pr["qemu"], "m": pr["machine"], "mem": pr["mem"], "k": pr["noyau"], "dtb": pr["dtb"], "port": port or 52222, "i": i}
    img = "system-images;android-%d;google_apis;%s" % (pr["api"], pr["abi"])
    return ecrire + """export ANDROID_SDK_ROOT=%(sdk)s ANDROID_HOME=%(sdk)s ANDROID_AVD_HOME="$I/avd"
mkdir -p "$I/avd"
echo no | %(sdk)s/cmdline-tools/latest/bin/avdmanager create avd -n %(i)s -k "%(img)s" -d pixel_5 --force >/dev/null || fail "création de l'appareil virtuel impossible"
nohup %(sdk)s/emulator/emulator -avd %(i)s -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -port %(port)d >"$I/emulateur.log" 2>&1 &
echo $! > "$I/pid"
echo "%(i)s démarre : adb -s emulator-%(port)d (console %(port)d) ; journal $I/emulateur.log"
""" % {"sdk": SDK, "i": i, "img": img, "port": port or 5554}


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
    r = cmd(["bash", "-c", script(v)], timeout=3600 if v["action"] in ("preparer", "lancer") else 300)
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
