#!/bin/sh
# Installe portage-kit (volume /opt/portage-kit) dans l'image au démarrage ; sans volume, l'API démarre quand même (/run répond 503).
if [ -f /opt/portage-kit/pyproject.toml ]; then
  pip install --no-cache-dir -q /opt/portage-kit 2>&1 | tail -1 || echo "portage-kit : installation en échec"
else
  echo "portage-kit absent (/opt/portage-kit vide) : monter PORTAGE_KIT_DIR dans .env"
fi
exec "$@"
