#!/bin/sh
# Assemble la commande du relais ; --require-client-cert + --allow-cn si une
# CA de vérification est montée et SI_PROXY_MTLS=1 (durcissement recommandé).
set -e
ARGS="--cert /certs/relay.crt --key /certs/relay.key --port ${SI_PROXY_PORT:-6450}"
ARGS="$ARGS --host-token $SI_PROXY_HOST_TOKEN --client-token $SI_PROXY_CLIENT_TOKEN"
ARGS="$ARGS --log-level ${SI_PROXY_LOG_LEVEL:-INFO}"
# #453 : journal d'audit JSONL (volume /data), garde-fou anti-force-brute
# (fail2ban maison) et interface de contrôle (port séparé, jeton d'admin).
ARGS="$ARGS --audit-log ${SI_PROXY_AUDIT_LOG:-/data/si-proxy-audit.jsonl}"
ARGS="$ARGS --ban-threshold ${SI_PROXY_BAN_THRESHOLD:-5} --ban-window ${SI_PROXY_BAN_WINDOW:-300} --ban-minutes ${SI_PROXY_BAN_MINUTES:-15}"
if [ -n "$SI_PROXY_ADMIN_TOKEN" ]; then
  ARGS="$ARGS --control-port ${SI_PROXY_CONTROL_PORT:-6452} --admin-token $SI_PROXY_ADMIN_TOKEN"
else
  echo "si-proxy : SI_PROXY_ADMIN_TOKEN absent -> interface de contrôle NON démarrée" >&2
fi
if [ "${SI_PROXY_MTLS:-0}" = "1" ] && [ -f /ca/ca.crt ]; then
  ARGS="$ARGS --ca /ca/ca.crt --require-client-cert"
  for cn in ${SI_PROXY_ALLOW_CN:-freg}; do ARGS="$ARGS --allow-cn $cn"; done
fi
exec python3 -m siproxy.relay $ARGS
