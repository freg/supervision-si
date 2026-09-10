#!/bin/bash
# Désinstallation de si-agent sur macOS (livraison #451). --keep-data
# conserve /usr/local/etc/si-agent (configuration) et /usr/local/var/lib/si-agent.
set -euo pipefail
PLIST="/Library/LaunchDaemons/fr.exemple.si-agent.plist"; LABEL="fr.exemple.si-agent"
KEEP="false"; [ "${1:-}" = "--keep-data" ] && KEEP="true"
[ "$(id -u)" = "0" ] || { echo "à lancer avec sudo" >&2; exit 1; }
launchctl bootout system "$PLIST" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
rm -rf /usr/local/opt/si-agent
if [ "$KEEP" = "false" ]; then
  rm -rf /usr/local/etc/si-agent /usr/local/var/lib/si-agent
  echo "si-agent désinstallé (configuration et données comprises)"
else
  echo "si-agent désinstallé (configuration et données conservées)"
fi
