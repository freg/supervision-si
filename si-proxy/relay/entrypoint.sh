#!/bin/sh
# Assemble la commande du relais ; --require-client-cert + --allow-cn si une
# CA de vérification est montée et SI_PROXY_MTLS=1 (durcissement recommandé).
set -e
ARGS="--cert /certs/relay.crt --key /certs/relay.key --port ${SI_PROXY_PORT:-6450}"
ARGS="$ARGS --host-token $SI_PROXY_HOST_TOKEN --client-token $SI_PROXY_CLIENT_TOKEN"
ARGS="$ARGS --log-level ${SI_PROXY_LOG_LEVEL:-INFO}"
if [ "${SI_PROXY_MTLS:-0}" = "1" ] && [ -f /ca/ca.crt ]; then
  ARGS="$ARGS --ca /ca/ca.crt --require-client-cert"
  for cn in ${SI_PROXY_ALLOW_CN:-freg}; do ARGS="$ARGS --allow-cn $cn"; done
fi
exec python3 -m siproxy.relay $ARGS
