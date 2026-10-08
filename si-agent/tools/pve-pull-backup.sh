#!/bin/bash
# #714 : sauvegarde « tirée » d'un CT d'un Proxmox VE ancien (5.x : pas de stockage PBS) vers le serveur de
# sauvegarde du LAN. La connexion part du LAN (aucun port ouvert chez soi, aucun espace temporaire sur l'hyperviseur) :
#   ssh root@<hôte> "vzdump <vmid> --mode <mode> --stdout --compress gzip"  >  <dest>/<hôte>/vzdump-lxc-<vmid>-<date>.tar.gz
# Archive vérifiée (gzip -t), empreinte SHA-256, ligne JSON dans <dest>/pulls.jsonl (lue par la sonde pulled-backups
# de l'agent : le hub voit la sauvegarde), rétention des N dernières par CT.
#
# Usage : pve-pull-backup.sh <hôte> <vmid> [stop|snapshot|suspend] [garder=3]
# Variables : PULL_DEST (/srv/backup/dumps), PULL_KEY (/root/.ssh/pve_backup si présente), PULL_NAME (nom du nœud
# pour le hub, défaut = hôte).  Exemple cron (pbs10) : 30 1 * * 0 root /usr/local/sbin/pve-pull-backup.sh 203.0.113.21 113
set -uo pipefail
HOST="${1:-}"; VMID="${2:-}"; MODE="${3:-stop}"; KEEP="${4:-3}"
DEST_ROOT="${PULL_DEST:-/srv/backup/dumps}"; KEY="${PULL_KEY:-/root/.ssh/pve_backup}"; NAME="${PULL_NAME:-$HOST}"
[[ "$HOST" =~ ^[A-Za-z0-9.:-]{1,100}$ ]] || { echo "hôte invalide" >&2; exit 2; }
[[ "$VMID" =~ ^[0-9]{1,9}$ ]] || { echo "vmid invalide" >&2; exit 2; }
[[ "$MODE" =~ ^(stop|snapshot|suspend)$ ]] || { echo "mode : stop, snapshot ou suspend" >&2; exit 2; }
[[ "$KEEP" =~ ^[0-9]{1,3}$ ]] && [ "$KEEP" -ge 1 ] || { echo "garder : 1 ou plus" >&2; exit 2; }
[[ "$NAME" =~ ^[A-Za-z0-9.:_-]{1,100}$ ]] || { echo "PULL_NAME invalide" >&2; exit 2; }
DEST="$DEST_ROOT/$NAME"; mkdir -p "$DEST" || exit 3
STAMP="$(date +%Y_%m_%d-%H_%M_%S)"; OUT="$DEST/vzdump-lxc-$VMID-$STAMP.tar.gz"
SSHOPT=(-o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10)
[ -f "$KEY" ] && SSHOPT+=(-i "$KEY")
START=$(date +%s); OK=false; ERR=""
if ssh "${SSHOPT[@]}" "root@$HOST" "vzdump $VMID --mode $MODE --stdout --compress gzip" > "$OUT.part" 2> "$OUT.log"; then
  if gzip -t "$OUT.part" 2>/dev/null; then mv "$OUT.part" "$OUT"; OK=true; else ERR="archive gzip invalide"; fi
else
  ERR="$(grep -E 'ERROR|error' "$OUT.log" | tail -1 | tr -d '"\\' | cut -c1-200)"; [ -n "$ERR" ] || ERR="ssh / vzdump en échec"
fi
END=$(date +%s); SIZE=0; SHA=""
if $OK; then SIZE=$(stat -c %s "$OUT"); SHA=$(sha256sum "$OUT" | cut -d' ' -f1); mv "$OUT.log" "$OUT.log.ok" 2>/dev/null; else rm -f "$OUT.part"; fi
printf '{"host":"%s","vmid":%s,"mode":"%s","file":"%s","ok":%s,"size":%s,"sha256":"%s","started":%s,"ended":%s,"error":"%s"}\n' \
  "$NAME" "$VMID" "$MODE" "$( $OK && echo "$OUT" )" "$OK" "$SIZE" "$SHA" "$START" "$END" "$ERR" >> "$DEST_ROOT/pulls.jsonl"
if $OK; then   # rétention : les KEEP dernières archives de ce CT
  ls -1t "$DEST"/vzdump-lxc-"$VMID"-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r f; do rm -f -- "$f" "$f.log.ok"; done
  echo "ok : $OUT ($SIZE octets, $((END - START)) s)"; exit 0
fi
echo "échec : $ERR (journal : $OUT.log)" >&2; exit 1
