#!/bin/sh
# #800 : installe l'émetteur si-htop sur l'hôte courant (VM, CT ou Proxmox), en root.
#   sh installer-emetteur.sh --relais relais.example.org:8399 [--nom NOM] [--transit]
# --transit (#802, sur un Proxmox) : ajoute le relais local des CT (service si-htop-transit, UDP 8399 du nœud) ; installer
# ensuite les émetteurs des CT avec installer-invites.sh. --transit-depuis IP1,IP2 : sources admises en plus des CT du
# cluster (ex. un nœud hors cluster et ses CT qui passent par ce nœud).
# La clé des émetteurs (HTOP_CLE_EMETTEURS du central) est demandée au clavier et écrite dans /etc/si-htop/cle (600) :
# jamais en argument (elle resterait dans l'historique et dans ps).
# Prérequis : python3 (3.5 ou plus), systemd. Désinstaller : systemctl disable --now si-htop-emetteur
set -eu
ICI=$(cd "$(dirname "$0")" && pwd)
RELAIS="" ; NOM="" ; TRANSIT="" ; DEPUIS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --relais) RELAIS="$2"; shift 2 ;;
    --nom) NOM="$2"; shift 2 ;;
    --transit) TRANSIT=1; shift ;;
    --transit-depuis) TRANSIT=1; DEPUIS="$2"; shift 2 ;;
    *) echo "option inconnue : $1" >&2; exit 2 ;;
  esac
done
[ -n "$RELAIS" ] || { echo "--relais hote:port requis" >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo "à lancer en root" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 absent (apt install python3-minimal)" >&2; exit 2; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 4) else 1)' || { echo "python3 3.4 ou plus requis" >&2; exit 2; }
install -d -m 755 /usr/local/lib/si-htop
install -m 644 "$ICI/emetteur.py" /usr/local/lib/si-htop/emetteur.py
install -d -m 700 /etc/si-htop
if [ ! -s /etc/si-htop/cle ]; then
  printf "clé des émetteurs (HTOP_CLE_EMETTEURS) : " ; stty -echo 2>/dev/null || true ; read -r CLE ; stty echo 2>/dev/null || true ; echo
  [ ${#CLE} -ge 16 ] || { echo "clé trop courte (16 caractères au moins)" >&2; exit 2; }
  umask 077 ; printf '%s\n' "$CLE" > /etc/si-htop/cle
fi
chmod 600 /etc/si-htop/cle
{ echo "SI_HTOP_RELAIS=$RELAIS" ; echo "SI_HTOP_CLE_FICHIER=/etc/si-htop/cle" ; [ -n "$NOM" ] && echo "SI_HTOP_NOM=$NOM" ; true ; } > /etc/si-htop/emetteur.env
install -m 644 "$ICI/si-htop-emetteur.service" /etc/systemd/system/si-htop-emetteur.service
systemctl daemon-reload
systemctl enable si-htop-emetteur >/dev/null 2>&1
systemctl restart si-htop-emetteur
if [ -n "$TRANSIT" ]; then
  { echo "SI_HTOP_RELAIS=$RELAIS" ; echo "SI_HTOP_TRANSIT=0.0.0.0:8399" ; [ -n "$DEPUIS" ] && echo "SI_HTOP_TRANSIT_DEPUIS=$DEPUIS" ; true ; } > /etc/si-htop/transit.env
  install -m 644 "$ICI/si-htop-transit.service" /etc/systemd/system/si-htop-transit.service
  systemctl daemon-reload
  systemctl enable si-htop-transit >/dev/null 2>&1
  systemctl restart si-htop-transit
  command -v pve-firewall >/dev/null && pve-firewall status 2>/dev/null | grep -q enabled && echo "ATTENTION : pare-feu Proxmox actif sur le nœud : autoriser UDP 8399 en entrée depuis les CT"
fi
sleep 3
systemctl --no-pager --lines=5 status si-htop-emetteur || true
[ -n "$TRANSIT" ] && { systemctl --no-pager --lines=3 status si-htop-transit || true ; }
echo "relevé local (contrôle) :"
python3 /usr/local/lib/si-htop/emetteur.py --afficher | head -n 12
