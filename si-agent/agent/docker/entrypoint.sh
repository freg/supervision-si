#!/bin/sh
# Premier démarrage : plugins livrés -> volume (jamais écrasés ensuite).
set -e
mkdir -p /var/lib/si-agent/plugins
for d in /opt/si-agent/plugins-bundled/*/; do
  [ -d "$d" ] || continue
  id="$(basename "$d")"
  [ -d "/var/lib/si-agent/plugins/$id" ] || cp -r "$d" "/var/lib/si-agent/plugins/$id"
done
chmod 755 /var/lib/si-agent/plugins/*/*.sh /var/lib/si-agent/plugins/*/*.py 2>/dev/null || true
exec "$@"
