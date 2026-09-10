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
RELAY="" TOKEN="" CA="$HERE/certs/ca.crt" USER_="freg" CERT="" KEY="" LOG="INFO" DENY=()
while [ $# -gt 0 ]; do case "$1" in
  --relay) RELAY="$2"; shift 2;; --token) TOKEN="$2"; shift 2;; --ca) CA="$2"; shift 2;;
  --shell-user) USER_="$2"; shift 2;; --cert) CERT="$2"; shift 2;; --key) KEY="$2"; shift 2;;
  --log-level) LOG="$2"; shift 2;; --deny) DENY+=("$2"); shift 2;;
  *) echo "argument inconnu : $1" >&2; exit 2;; esac; done
[ -n "$RELAY" ] && [ -n "$TOKEN" ] || { echo "usage : sudo ./si-proxy/install-host.sh --relay host:port --token TOKEN [--ca ca.crt] [--shell-user freg]" >&2; exit 2; }
[ "$(id -u)" = "0" ] || { echo "à lancer avec sudo" >&2; exit 1; }
id "$USER_" >/dev/null 2>&1 || { echo "utilisateur du shell introuvable : $USER_" >&2; exit 1; }
install -d /opt/si-proxy /etc/si-proxy
rm -rf /opt/si-proxy/siproxy; cp -r "$HERE/siproxy" /opt/si-proxy/
[ -f "$CA" ] && install -m 644 "$CA" /etc/si-proxy/ca.crt
umask 077
{ echo "SI_PROXY_RELAY=$RELAY"; echo "SI_PROXY_CA=/etc/si-proxy/ca.crt"; echo "SI_PROXY_HOST_TOKEN=$TOKEN";
  echo "SI_PROXY_SHELL_USER=$USER_"; echo "SI_PROXY_LOG_LEVEL=$LOG"; } > /etc/si-proxy/host.env
chmod 600 /etc/si-proxy/host.env
install -m 644 "$HERE/systemd/si-proxy-host.service" /etc/systemd/system/si-proxy-host.service
systemctl daemon-reload
systemctl enable --now si-proxy-host.service
echo "shim host installé : systemctl status si-proxy-host ; journalctl -u si-proxy-host -f"
