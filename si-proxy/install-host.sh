#!/bin/bash
# Installe le shim host du bastion si-proxy (#452) sur la VM du hub : copie
# le paquet dans /opt/si-proxy, écrit /etc/si-proxy/host.env, installe et
# démarre le service systemd si-proxy-host. À lancer avec sudo, à la racine
# du dépôt.
#
#   sudo ./si-proxy/install-host.sh --relay localhost:6450 --token "$HOST_TOKEN" \
#        [--ca si-proxy/certs/ca.crt] [--shell-user freg] [--cert h.crt --key h.key]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RELAY="" TOKEN="" CA="$HERE/certs/ca.crt" USER_="freg" CERT="" KEY="" LOG="INFO" DENY=() NAME="hub" SSH_JUMP="" SSH_KEY=""
while [ $# -gt 0 ]; do case "$1" in
  --relay) RELAY="$2"; shift 2;; --token) TOKEN="$2"; shift 2;; --ca) CA="$2"; shift 2;;
  --shell-user) USER_="$2"; shift 2;; --cert) CERT="$2"; shift 2;; --key) KEY="$2"; shift 2;;
  --log-level) LOG="$2"; shift 2;; --deny) DENY+=("$2"); shift 2;;
  --name) NAME="$2"; shift 2;;                    # #575 : nom du shim (hub, campus…)
  --ssh-jump) SSH_JUMP="$2"; shift 2;;            # #575 : user@hôte[:port] d'entrée SSH ; le relais est joint par un tunnel SSH local
  --ssh-key) SSH_KEY="$2"; shift 2;;
  *) echo "argument inconnu : $1" >&2; exit 2;; esac; done
[ -n "$RELAY" ] && [ -n "$TOKEN" ] || { echo "usage : sudo ./si-proxy/install-host.sh --relay host:port --token TOKEN [--ca ca.crt] [--shell-user freg]" >&2; exit 2; }
[ "$(id -u)" = "0" ] || { echo "à lancer avec sudo" >&2; exit 1; }
id "$USER_" >/dev/null 2>&1 || { echo "utilisateur du shell introuvable : $USER_" >&2; exit 1; }
install -d /opt/si-proxy /etc/si-proxy
rm -rf /opt/si-proxy/siproxy; cp -r "$HERE/siproxy" /opt/si-proxy/
[ -f "$CA" ] && install -m 644 "$CA" /etc/si-proxy/ca.crt
umask 077
{ echo "SI_PROXY_RELAY=$RELAY"; echo "SI_PROXY_CA=/etc/si-proxy/ca.crt"; echo "SI_PROXY_HOST_TOKEN=$TOKEN";
  echo "SI_PROXY_SHELL_USER=$USER_"; echo "SI_PROXY_LOG_LEVEL=$LOG"; echo "SI_PROXY_HOST_NAME=$NAME"; } > /etc/si-proxy/host.env
chmod 600 /etc/si-proxy/host.env
install -m 644 "$HERE/systemd/si-proxy-host.service" /etc/systemd/system/si-proxy-host.service
if [ -n "$SSH_JUMP" ]; then
  # #575 : le poste n'a pas de route vers le relais : tunnel SSH local permanent vers
  # l'entrée SSH du SI (clé dédiée, restreinte côté serveur à ce seul port), et
  # le shim joint 127.0.0.1 en vérifiant le nom du relais dans le certificat.
  JUMP_HOST="${SSH_JUMP#*@}"; JUMP_USER="${SSH_JUMP%%@*}"; JUMP_PORT="${JUMP_HOST##*:}"; JUMP_HOST="${JUMP_HOST%%:*}"
  [ "$JUMP_PORT" = "$JUMP_HOST" ] && JUMP_PORT=22
  RELAY_HOST="${RELAY%%:*}"; RELAY_PORT="${RELAY##*:}"
  [ -n "$SSH_KEY" ] && install -m 600 "$SSH_KEY" /etc/si-proxy/jump.key
  { echo "SI_PROXY_JUMP=$JUMP_USER@$JUMP_HOST"; echo "SI_PROXY_JUMP_PORT=$JUMP_PORT"; echo "SI_PROXY_JUMP_FORWARD=127.0.0.1:$RELAY_PORT:$RELAY"; } >> /etc/si-proxy/host.env
  sed -i "s#^SI_PROXY_RELAY=.*#SI_PROXY_RELAY=127.0.0.1:$RELAY_PORT#; s#^SI_PROXY_HOST_NAME=.*#SI_PROXY_HOST_NAME=$NAME#" /etc/si-proxy/host.env
  echo "SI_PROXY_SERVER_NAME=$RELAY_HOST" >> /etc/si-proxy/host.env
  install -m 644 "$HERE/systemd/si-proxy-jump.service" /etc/systemd/system/si-proxy-jump.service
  systemctl daemon-reload
  systemctl enable --now si-proxy-jump.service
fi
systemctl daemon-reload
systemctl enable --now si-proxy-host.service
echo "shim host installé : systemctl status si-proxy-host ; journalctl -u si-proxy-host -f"
