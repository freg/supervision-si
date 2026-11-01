#!/bin/bash
# #717 : campagne de sauvegardes tirées en série (pve-pull-backup.sh, #714) -- vider des PVE hébergés pendant un
# week-end, depuis le serveur de sauvegarde du LAN, sans surveillance : une sauvegarde à la fois (bande passante),
# un échec n'arrête pas la campagne, arrêt propre si l'espace libre passe sous le seuil, une seule campagne à la fois.
# Chaque résultat va dans pulls.jsonl : sonde pulled-backups -> hub (Maintenance des Proxmox) -> notifications
# (si-agent.backup-done / backup-alert, destinataires réglés dans la tuile Notifications).
#
# Usage : pve-pull-batch.sh <liste>      lancé détaché : systemd-run --unit=pull-campagne pve-pull-batch.sh /root/campagne.list
# Liste : une ligne par CT « hôte vmid [mode=stop] [garder=2] [nom pour le hub] » ; lignes vides et « # » ignorées.
#   ATTENTION mode stop : le CT est ARRÊTÉ pendant toute la copie (vzdump le redémarre ensuite s'il tournait).
# Variables : PULL_DEST (/srv/backup/dumps), PULL_KEY, PULL_MIN_FREE_GB (100), PULL_NOTIFY_OK (1), PULL_SCRIPT.
set -uo pipefail
LIST="${1:-}"; [ -f "$LIST" ] || { echo "usage : pve-pull-batch.sh <liste>" >&2; exit 2; }
DEST="${PULL_DEST:-/srv/backup/dumps}"; MINFREE="${PULL_MIN_FREE_GB:-100}"
SCRIPT="${PULL_SCRIPT:-$(dirname "$(readlink -f "$0")")/pve-pull-backup.sh}"; [ -f "$SCRIPT" ] || SCRIPT=/usr/local/sbin/pve-pull-backup.sh
[[ "$MINFREE" =~ ^[0-9]+$ ]] || { echo "PULL_MIN_FREE_GB : entier attendu" >&2; exit 2; }
mkdir -p "$DEST" || exit 3
exec 9>"$DEST/.pull-batch.lock"; flock -n 9 || { echo "une campagne est déjà en cours ($DEST/.pull-batch.lock)" >&2; exit 4; }
LOG="$DEST/campagne-$(date +%Y%m%d-%H%M%S).log"
TOTAL=$(grep -cvE '^\s*(#|$)' "$LIST"); N=0; OK=0; KO=0
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
say "campagne : $TOTAL sauvegarde(s) depuis $LIST, destination $DEST, arrêt sous $MINFREE Go libres"
while read -r host vmid mode keep name _rest <&3; do
  [[ -z "${host:-}" || "$host" == \#* ]] && continue
  N=$((N + 1))
  FREE=$(( $(df -Pk "$DEST" | awk 'NR==2 {print $4}') / 1048576 ))
  if [ "$FREE" -lt "$MINFREE" ]; then
    say "ARRÊT avant $host/$vmid : $FREE Go libres < $MINFREE Go ; $((TOTAL - N + 1)) sauvegarde(s) non faite(s)"; break
  fi
  say "[$N/$TOTAL] début $host CT $vmid (mode ${mode:-stop}, $FREE Go libres)"
  T0=$(date +%s)
  if PULL_DEST="$DEST" PULL_NAME="${name:-$host}" PULL_NOTIFY_OK="${PULL_NOTIFY_OK:-1}" bash "$SCRIPT" "$host" "$vmid" "${mode:-stop}" "${keep:-2}" >>"$LOG" 2>&1 </dev/null; then
    OK=$((OK + 1)); say "[$N/$TOTAL] OK $host CT $vmid en $(( ($(date +%s) - T0) / 60 )) min"
  else
    KO=$((KO + 1)); say "[$N/$TOTAL] ÉCHEC $host CT $vmid (détail plus haut dans $LOG)"
  fi
done 3< "$LIST"
say "fin de campagne : $OK réussie(s), $KO échec(s), $((TOTAL - OK - KO)) non faite(s)"
[ "$KO" -eq 0 ] && [ $((OK)) -eq "$TOTAL" ]
