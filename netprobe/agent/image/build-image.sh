#!/usr/bin/env bash
# build-image.sh -- construit une image SD prête à flasher pour une sonde
# (Raspberry Pi Zero W) ou un collecteur (Raspberry Pi 3B) netprobe, à
# partir de l'image OFFICIELLE Raspberry Pi OS Lite (32 bits -- la seule
# qui démarre sur un Zero W, et qui convient aussi au 3B).
#
# Principe : l'image officielle n'est PAS reconstruite (pas de pi-gen, pas
# de chroot, pas de droits root). On y INJECTE, sur la partition de boot
# (FAT, écrite avec mtools sans montage), le paquet netprobe_agent, la
# configuration de l'appareil, et un script de premier démarrage lancé par
# systemd (`systemd.run=` dans cmdline.txt -- exactement le mécanisme de
# Raspberry Pi Imager). Au premier boot, le Pi installe tout lui-même,
# puis redémarre en service. Reproductible, versionnable, testable.
#
# Prérequis sur la machine qui construit : bash, python3, curl, xz, mtools
# (macOS : `brew install mtools xz` ; Debian/Ubuntu : `apt install mtools xz-utils`).
#
# Exemples :
#   # sonde, configuration récupérée du central (secret compris)
#   ./build-image.sh --api https://vm:6443/api/netprobe --api-insecure \
#       --agent alpha-sonde-01 --collector-url http://192.168.10.20:6127 \
#       --wifi-ssid Alpha-Prod --wifi-psk 'motdepasse' --password 'sonde-pi'
#   # collecteur avec adresse fixe, certificat de l'AC du projet embarqué
#   ./build-image.sh --api https://vm:6443/api/netprobe --api-insecure \
#       --agent alpha-collecteur-01 --central-url https://vm:6443/api/netprobe \
#       --ca ../../../pki/ca/ca.crt --static-ip 192.168.10.20/24 --gateway 192.168.10.1 \
#       --password 'collecteur-pi'
#   # hors ligne : configuration déjà écrite (voir examples/)
#   ./build-image.sh --config ../examples/agent.json --wifi-ssid X --wifi-psk Y
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$HERE/.." && pwd)"
LATEST_URL="https://downloads.raspberrypi.com/raspios_lite_armhf_latest"

API=""; API_INSECURE=0; AGENT=""; CONFIG=""; ROLE=""
COLLECTOR_URL=""; CENTRAL_URL=""; CA_FILE=""; CENTRAL_INSECURE=0
WIFI_SSID=""; WIFI_PSK=""; WIFI_COUNTRY="FR"; IFACE="wlan0"
HOSTNAME_NP=""; USER_NAME="pi"; PASSWORD=""; SSH_KEY=""; TIMEZONE="Europe/Paris"
STATIC_IP=""; GATEWAY=""; DNS=""; STATIC_IFACE="eth0"; INSTALL_IPERF3=0
BASE_IMAGE=""; OUT=""; CACHE="$HERE/cache"; BOOT_MOUNT=""; FLEET_FILE=""; KEEP_BASE=1

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --api) API="${2%/}"; shift 2 ;;
    --api-insecure) API_INSECURE=1; shift ;;
    --agent) AGENT="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --collector-url) COLLECTOR_URL="$2"; shift 2 ;;
    --central-url) CENTRAL_URL="$2"; shift 2 ;;
    --ca) CA_FILE="$2"; shift 2 ;;
    --central-insecure) CENTRAL_INSECURE=1; shift ;;
    --fleet) FLEET_FILE="$2"; shift 2 ;;
    --wifi-ssid) WIFI_SSID="$2"; shift 2 ;;
    --wifi-psk) WIFI_PSK="$2"; shift 2 ;;
    --wifi-country) WIFI_COUNTRY="$2"; shift 2 ;;
    --interface) IFACE="$2"; shift 2 ;;
    --hostname) HOSTNAME_NP="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --ssh-key) SSH_KEY="$2"; shift 2 ;;
    --timezone) TIMEZONE="$2"; shift 2 ;;
    --static-ip) STATIC_IP="$2"; shift 2 ;;
    --gateway) GATEWAY="$2"; shift 2 ;;
    --dns) DNS="$2"; shift 2 ;;
    --static-iface) STATIC_IFACE="$2"; shift 2 ;;
    --iperf3) INSTALL_IPERF3=1; shift ;;
    --base-image) BASE_IMAGE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --cache) CACHE="$2"; shift 2 ;;
    --boot-mount) BOOT_MOUNT="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "option inconnue : $1" >&2; usage 1 ;;
  esac
done

die() { echo "ERREUR : $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "outil requis absent : $1 ($2)"; }
need python3 "python3"; need mcopy "mtools"; need mmd "mtools"; need mdir "mtools"; need xz "xz"; need tar "tar"

# ---------------------------------------------------------------------
# 1. Configuration de l'appareil : depuis le central (--api/--agent) ou
#    un fichier (--config)
# ---------------------------------------------------------------------
WORK="$(mktemp -d "${TMPDIR:-/tmp}/netprobe-image.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
DEVICE_JSON="$WORK/device.json"

if [ -n "$CONFIG" ]; then
  [ -f "$CONFIG" ] || die "--config : fichier introuvable : $CONFIG"
  cp "$CONFIG" "$DEVICE_JSON"
elif [ -n "$API" ] && [ -n "$AGENT" ]; then
  need curl "curl"
  Q=""
  [ -n "$COLLECTOR_URL" ] && Q="$Q&collector_url=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$COLLECTOR_URL")"
  [ -n "$CENTRAL_URL" ] && Q="$Q&central_url=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$CENTRAL_URL")"
  Q="$Q&interface=$IFACE"
  URL="$API/agents/$AGENT/provision?${Q#&}"
  echo "-> configuration depuis $URL"
  CURL_OPTS=(-sS -f -L)
  [ "$API_INSECURE" = 1 ] && CURL_OPTS+=(-k)
  curl "${CURL_OPTS[@]}" "$URL" -o "$DEVICE_JSON" || die "récupération de la configuration impossible (appareil déclaré dans le hub ? --api-insecure pour un certificat auto-signé ?)"
else
  die "indiquer --api URL --agent ID (configuration depuis le central) ou --config fichier.json"
fi

# Rôle, identifiant, cohérence -- lus par python3 (pas de jq requis)
eval "$(python3 - "$DEVICE_JSON" "$CENTRAL_URL" "$CA_FILE" "$CENTRAL_INSECURE" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
central_url, ca_file, insecure = sys.argv[2], sys.argv[3], sys.argv[4] == "1"
if "collector_id" in cfg:
    role, ident = "collector", cfg["collector_id"]
    if central_url: cfg["central_url"] = central_url
    if ca_file: cfg["central_ca_file"] = "/etc/netprobe-collector/central-ca.crt"
    if insecure: cfg["central_insecure"] = True
    cfg.setdefault("port", 6127)
else:
    role, ident = "probe", cfg.get("agent_id", "")
    cfg.setdefault("role", "probe")
if not ident or not cfg.get("secret"):
    print("die 'configuration incomplète (identifiant/secret)'"); sys.exit(0)
json.dump(cfg, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
print("ROLE=%s; IDENT=%s; SITE=%s; COLLECTOR_URL_CFG=%s; CENTRAL_URL_CFG=%s" % (
    role, json.dumps(ident), json.dumps(cfg.get("site", "")), json.dumps(cfg.get("collector_url", "")), json.dumps(cfg.get("central_url", ""))))
PY
)"
[ "$ROLE" = "probe" ] && [ -z "$COLLECTOR_URL_CFG" ] && die "sonde sans collector_url (--collector-url http://IP-DU-COLLECTEUR:6127)"
[ "$ROLE" = "probe" ] && [ -z "$WIFI_SSID" ] && die "sonde sans WiFi (--wifi-ssid / --wifi-psk) : elle ne joindrait jamais le collecteur"
[ "$ROLE" = "collector" ] && [ -z "$CENTRAL_URL_CFG" ] && echo "AVERTISSEMENT : collecteur sans central_url -- mode local uniquement, aucun relais" >&2
[ -z "$HOSTNAME_NP" ] && HOSTNAME_NP="$IDENT"
[ -z "$PASSWORD" ] && [ -z "$SSH_KEY" ] && die "--password ou --ssh-key requis (Raspberry Pi OS n'a plus d'utilisateur par défaut)"
if [ -n "$STATIC_IP" ] && [ -z "$GATEWAY" ]; then die "--static-ip demande --gateway"; fi
echo "-> rôle $ROLE, appareil $IDENT, site $SITE, hostname $HOSTNAME_NP"

# ---------------------------------------------------------------------
# 2. Image de base (téléchargée dans le cache, ou fournie)
# ---------------------------------------------------------------------
mkdir -p "$CACHE"
if [ -z "$BASE_IMAGE" ]; then
  need curl "curl"
  BASE_XZ="$CACHE/raspios_lite_armhf_latest.img.xz"
  if [ ! -s "$BASE_XZ" ]; then
    echo "-> téléchargement de l'image officielle Raspberry Pi OS Lite (32 bits) dans $CACHE"
    curl -L --fail --progress-bar -o "$BASE_XZ" "$LATEST_URL" || die "téléchargement impossible"
  else
    echo "-> image de base en cache : $BASE_XZ"
  fi
  BASE_IMAGE="$BASE_XZ"
fi
[ -f "$BASE_IMAGE" ] || die "image de base introuvable : $BASE_IMAGE"
[ -z "$OUT" ] && OUT="$PWD/netprobe-$ROLE-$IDENT.img"
case "$BASE_IMAGE" in
  *.xz) echo "-> décompression vers $OUT"; xz -dc "$BASE_IMAGE" > "$OUT" ;;
  *) echo "-> copie vers $OUT"; cp "$BASE_IMAGE" "$OUT" ;;
esac

# ---------------------------------------------------------------------
# 3. Partition de boot (FAT) : décalage lu dans la table MBR
# ---------------------------------------------------------------------
BOOT_OFFSET="$(python3 - "$OUT" <<'PY'
import struct, sys
with open(sys.argv[1], "rb") as fh:
    mbr = fh.read(512)
if mbr[510:512] != b"\x55\xaa":
    sys.exit("pas une image MBR (signature absente)")
for i in range(4):
    e = mbr[446 + 16 * i: 446 + 16 * (i + 1)]
    ptype, lba, size = e[4], struct.unpack("<I", e[8:12])[0], struct.unpack("<I", e[12:16])[0]
    if ptype in (0x0b, 0x0c, 0x0e, 0x01, 0x04, 0x06) and size:
        print(lba * 512); break
else:
    sys.exit("aucune partition FAT dans la table MBR")
PY
)" || die "$BOOT_OFFSET"
IMG="$OUT@@$BOOT_OFFSET"
echo "-> partition de boot au décalage $BOOT_OFFSET"
mdir -i "$IMG" ::/ >/dev/null 2>&1 || die "la partition de boot n'est pas lisible avec mtools (image inattendue ?)"

# Bookworm monte la partition de boot sur /boot/firmware, Bullseye sur /boot.
# Détection par la date de l'image (issue.txt), surchargeable (--boot-mount).
if [ -z "$BOOT_MOUNT" ]; then
  ISSUE="$(mtype -i "$IMG" ::/issue.txt 2>/dev/null | head -1 || true)"
  IMG_DATE="$(echo "$ISSUE" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1 || true)"
  if [ -n "$IMG_DATE" ] && [ "$IMG_DATE" \> "2023-10-01" ]; then BOOT_MOUNT=/boot/firmware; else BOOT_MOUNT=/boot; fi
  echo "-> image datée ${IMG_DATE:-?} : partition de boot montée sur $BOOT_MOUNT"
fi

# ---------------------------------------------------------------------
# 4. Charge utile : paquet + unités systemd
# ---------------------------------------------------------------------
STAGE="$WORK/netprobe"; mkdir -p "$STAGE"
( cd "$AGENT_DIR" && tar czf "$STAGE/payload.tgz" --exclude='__pycache__' --exclude='*.pyc' netprobe_agent systemd )
cp "$HERE/firstrun.sh" "$STAGE/firstrun.sh"
cp "$DEVICE_JSON" "$STAGE/device.json"
[ -n "$FLEET_FILE" ] && cp "$FLEET_FILE" "$STAGE/fleet.json"
[ -n "$CA_FILE" ] && { [ -f "$CA_FILE" ] || die "--ca introuvable : $CA_FILE"; cp "$CA_FILE" "$STAGE/central-ca.crt"; }

q() { printf "%s" "$1" | sed "s/'/'\\\\''/g"; }
cat > "$STAGE/settings.env" <<EOF
ROLE='$ROLE'
USER_NAME='$(q "$USER_NAME")'
HOSTNAME_NP='$(q "$HOSTNAME_NP")'
TIMEZONE='$(q "$TIMEZONE")'
WIFI_SSID='$(q "$WIFI_SSID")'
WIFI_PSK='$(q "$WIFI_PSK")'
WIFI_COUNTRY='$(q "$WIFI_COUNTRY")'
STATIC_IP='$(q "$STATIC_IP")'
STATIC_GATEWAY='$(q "$GATEWAY")'
STATIC_DNS='$(q "$DNS")'
STATIC_IFACE='$(q "$STATIC_IFACE")'
INSTALL_IPERF3='$INSTALL_IPERF3'
EOF

# Utilisateur : userconf.txt (username:hash) -- mécanisme officiel, lu par
# userconf-pi au premier démarrage. Mot de passe haché en SHA-512 crypt.
if [ -n "$PASSWORD" ]; then
  HASH="$(python3 -c 'import sys
try:
    import crypt
    print(crypt.crypt(sys.argv[1], crypt.mksalt(crypt.METHOD_SHA512)))
except Exception:
    sys.exit(1)' "$PASSWORD" 2>/dev/null || openssl passwd -6 "$PASSWORD")" || die "impossible de hacher le mot de passe (python3 crypt ou openssl passwd -6)"
  printf "%s:%s\n" "$USER_NAME" "$HASH" > "$WORK/userconf.txt"
else
  # Sans mot de passe : compte verrouillé, clé SSH obligatoire (fournie)
  printf "%s:*\n" "$USER_NAME" > "$WORK/userconf.txt"
fi
if [ -n "$SSH_KEY" ]; then
  [ -f "$SSH_KEY" ] || die "--ssh-key introuvable : $SSH_KEY"
  cp "$SSH_KEY" "$STAGE/authorized_keys"
fi
: > "$WORK/ssh"   # fichier vide 'ssh' = SSH activé par Raspberry Pi OS

# ---------------------------------------------------------------------
# 5. Injection dans la partition de boot + premier démarrage
# ---------------------------------------------------------------------
echo "-> injection dans la partition de boot"
mdir -i "$IMG" ::/netprobe >/dev/null 2>&1 && mdeltree -i "$IMG" ::/netprobe
mmd -i "$IMG" ::/netprobe
for f in "$STAGE"/*; do mcopy -i "$IMG" -o "$f" ::/netprobe/; done
mcopy -i "$IMG" -o "$WORK/userconf.txt" ::/userconf.txt
mcopy -i "$IMG" -o "$WORK/ssh" ::/ssh

# cmdline.txt : une seule ligne ; on retire toute directive systemd.run
# précédente puis on ajoute la nôtre (chemin selon le point de montage).
mcopy -i "$IMG" ::/cmdline.txt "$WORK/cmdline.txt"
python3 - "$WORK/cmdline.txt" "$BOOT_MOUNT" <<'PY'
import re, sys
p, mount = sys.argv[1], sys.argv[2]
line = open(p).read().strip().split("\n")[0]
line = re.sub(r"\s*systemd\.run(_success_action)?=\S+", "", line)
line = re.sub(r"\s*systemd\.unit=kernel-command-line\.target", "", line)
line += " systemd.run=%s/netprobe/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target" % mount
open(p, "w").write(line + "\n")
PY
mcopy -i "$IMG" -o "$WORK/cmdline.txt" ::/cmdline.txt

# Le script doit être exécutable : sur FAT tout l'est, mais systemd.run
# l'exécute par son chemin -- vérifions qu'il est bien là, avec un shebang.
mtype -i "$IMG" ::/netprobe/firstrun.sh | head -1 | grep -q '^#!/bin/bash' || die "firstrun.sh mal écrit"

echo
echo "== image prête : $OUT"
echo "   appareil    : $IDENT ($ROLE, site $SITE, hostname $HOSTNAME_NP)"
[ "$ROLE" = probe ] && echo "   collecteur  : $COLLECTOR_URL_CFG" || echo "   central     : ${CENTRAL_URL_CFG:-aucun (local)}"
echo "   utilisateur : $USER_NAME (SSH activé)"
echo "   premier boot: $BOOT_MOUNT/netprobe/firstrun.sh (journal : /var/log/netprobe-firstrun.log sur le Pi)"
echo "   flasher     : Raspberry Pi Imager (« Utiliser une image personnalisée », SANS personnalisation OS)"
echo "                 ou : sudo dd if=$OUT of=/dev/rdiskN bs=4m status=progress"
mdir -i "$IMG" ::/netprobe | sed 's/^/   boot: /'
