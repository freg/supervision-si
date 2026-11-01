#!/bin/bash
# #725 : copie de secours ZFS DIFFÉRENTIELLE de VM/CT entiers vers un disque externe (opération ponctuelle, sans
# rotation de disques). Sur l'hyperviseur qui porte la VM (ex. la VM du PBS) : brancher le disque, lancer, débrancher.
#   1re fois : copie complète ; ensuite seuls les blocs modifiés depuis la dernière copie (zfs send -i).
#   Système de fichiers des invités figé pendant l'instantané si l'agent invité répond (qm guest fsfreeze), sinon
#   cohérence « coupure de courant » (suffisante pour un datastore PBS : morceaux immuables, vérification ensuite).
#   Configuration de chaque VM/CT copiée sur le disque ; journal JSON lu par la sonde pulled-backups -> le hub affiche
#   l'ancienneté de chaque copie et alerte au-delà de SECOURS_MAX_AGE_H (« décompte » sans disque tournant).
#
# Préparer le disque UNE fois (EFFACE le disque) :  zpool create -o ashift=12 -O compression=lz4 secours /dev/disk/by-id/usb-…
# Usage : zfs-secours.sh <pool du disque> <vmid> [vmid…]     ex. zfs-secours.sh secours 110
# Variables : SECOURS_KEEP_SRC (2 instantanés gardés côté hyperviseur), SECOURS_KEEP_DST (10 sur le disque),
#   SECOURS_MAX_AGE_H (336 = 14 jours avant alerte), SECOURS_JOURNAL (/var/lib/si-agent/secours.jsonl),
#   SECOURS_EXPORT (1 : pool exporté à la fin, disque débranchable), SECOURS_FREEZE (1).
set -uo pipefail
POOL="${1:-}"; shift 2>/dev/null; VMIDS=("$@")
KEEP_SRC="${SECOURS_KEEP_SRC:-2}"; KEEP_DST="${SECOURS_KEEP_DST:-10}"; MAX_AGE_H="${SECOURS_MAX_AGE_H:-336}"
JOURNAL="${SECOURS_JOURNAL:-/var/lib/si-agent/secours.jsonl}"; EXPORT="${SECOURS_EXPORT:-1}"; FREEZE="${SECOURS_FREEZE:-1}"
die() { echo "$*" >&2; exit 2; }
[[ "$POOL" =~ ^[A-Za-z][A-Za-z0-9_.-]{0,60}$ ]] && [ ${#VMIDS[@]} -gt 0 ] || die "usage : zfs-secours.sh <pool> <vmid> [vmid…]"
for v in "${VMIDS[@]}"; do [[ "$v" =~ ^[0-9]{1,9}$ ]] || die "vmid invalide : $v"; done
for n in "$KEEP_SRC" "$KEEP_DST" "$MAX_AGE_H"; do [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] || die "réglage numérique invalide : $n"; done

snaps() { zfs list -H -t snapshot -o name -s creation -d 1 "$1" 2>/dev/null | sed 's/.*@//' | grep '^secours-' || true; }
common_snap() {   # dernier instantané secours-* présent des deux côtés (hors celui qu'on vient de prendre)
  local s d; s="$(snaps "$1" | grep -vx "$3")"; d="$(snaps "$2")"
  grep -Fxf <(printf '%s\n' "$d") <(printf '%s\n' "$s") | tail -1
}
prune() {         # garde les N derniers secours-* d'un volume
  snaps "$1" | head -n -"$2" | while read -r sn; do [ -n "$sn" ] && zfs destroy "$1@$sn"; done
}

zpool list -H "$POOL" >/dev/null 2>&1 || zpool import "$POOL" >/dev/null 2>&1 || die "pool $POOL absent : brancher le disque (zpool import pour le voir)"
DEST="$POOL/secours"; CONF="$POOL/secours-conf"
zfs list -H "$DEST" >/dev/null 2>&1 || zfs create -o canmount=off "$DEST" || die "création de $DEST impossible"
zfs list -H "$CONF" >/dev/null 2>&1 || zfs create "$CONF" || die "création de $CONF impossible"
CONFDIR="$(zfs get -H -o value mountpoint "$CONF")"
mkdir -p "$(dirname "$JOURNAL")"
STAMP="secours-$(date +%Y%m%d-%H%M%S)"; RC=0
for vmid in "${VMIDS[@]}"; do
  START=$(date +%s); OK=true; ERR=""; SIZE=0
  mapfile -t VOLS < <(zfs list -H -o name -t volume,filesystem | grep -v "^$POOL/" | grep -E "/(vm|subvol|base)-$vmid-disk-[0-9]+$")   # jamais les copies du disque de secours
  if [ ${#VOLS[@]} -eq 0 ]; then OK=false; ERR="aucun volume ZFS pour $vmid"; fi
  if $OK; then
    FROZEN=0
    if [ "$FREEZE" = 1 ] && command -v qm >/dev/null && qm guest cmd "$vmid" ping >/dev/null 2>&1; then
      qm guest cmd "$vmid" fsfreeze-freeze >/dev/null 2>&1 && FROZEN=1
    fi
    zfs snapshot "${VOLS[@]/%/@$STAMP}" || { OK=false; ERR="instantané impossible"; }    # atomique pour tous les disques
    [ "$FROZEN" = 1 ] && qm guest cmd "$vmid" fsfreeze-thaw >/dev/null 2>&1
  fi
  if $OK; then
    for v in "${VOLS[@]}"; do
      dst="$DEST/${v##*/}"
      if zfs list -H "$dst" >/dev/null 2>&1; then
        base="$(common_snap "$v" "$dst" "$STAMP")"
        if [ -z "$base" ]; then OK=false; ERR="pas d'instantané commun pour $v : supprimer $dst pour repartir d'une copie complète"; break; fi
        zfs send -i "@$base" "$v@$STAMP" | zfs recv -F "$dst" || { OK=false; ERR="envoi différentiel de $v en échec"; break; }
      else
        zfs send "$v@$STAMP" | zfs recv "$dst" || { OK=false; ERR="envoi complet de $v en échec"; break; }
      fi
      w="$(zfs get -Hp -o value written "$dst@$STAMP" 2>/dev/null)"; [[ "$w" =~ ^[0-9]+$ ]] && SIZE=$((SIZE + w))
      prune "$v" "$KEEP_SRC"; prune "$dst" "$KEEP_DST"
    done
    for f in /etc/pve/qemu-server/$vmid.conf /etc/pve/lxc/$vmid.conf; do [ -f "$f" ] && cp -p "$f" "$CONFDIR/$vmid.conf.$STAMP"; done
  fi
  $OK || RC=1
  LINE=$(printf '{"host":"secours-%s","job":"vm-%s","ok":%s,"size":%s,"sha256":"","file":"","started":%s,"ended":%s,"error":"%s","max_age_h":%s,"notify_ok":true}' \
    "$POOL" "$vmid" "$OK" "$SIZE" "$START" "$(date +%s)" "$(printf '%s' "$ERR" | tr -d '"\\')" "$MAX_AGE_H")
  echo "$LINE" >> "$JOURNAL"; echo "$LINE" >> "$CONFDIR/secours.jsonl"
  if $OK; then echo "VM/CT $vmid : copie $STAMP faite ($((SIZE / 1048576)) Mio écrits)"; else echo "VM/CT $vmid : ÉCHEC -- $ERR" >&2; fi
done
if [ "$EXPORT" = 1 ]; then zpool export "$POOL" && echo "pool $POOL exporté : le disque peut être débranché"; fi
exit $RC
