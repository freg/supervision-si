#!/bin/sh
# #681 : le hub est compilé AU DÉMARRAGE du conteneur (les VITE_* viennent de l'environnement du compose et sont
# figés dans le JavaScript par vite build), puis servi par serve.mjs (index.html sans cache, assets immuables).
# HUB_MODE=dev : ancien serveur de développement Vite (HMR, compilation à la volée).
# Échec du build : repli sur le serveur de développement, pour ne jamais laisser le hub éteint.
set -u
cd /app
if [ "${HUB_MODE:-prod}" = "dev" ]; then
  echo "hub : mode développement (HUB_MODE=dev)"
  exec npm run dev
fi
# #736 : hub pré-compilé dans l'image -> copie, configuration d'exécution (VITE_* du compose), service immédiat.
if [ "${HUB_PREBUILT:-1}" = "1" ] && [ -f /app/dist-prebuilt/index.html ]; then
  rm -rf /app/dist && cp -r /app/dist-prebuilt /app/dist && node /app/write-env.mjs /app/dist/env.js && exec node serve.mjs
  echo "hub : démarrage pré-compilé impossible -- compilation au démarrage" >&2
fi
echo "hub : compilation (vite build)..."
start=$(date +%s)
if NODE_OPTIONS="${HUB_BUILD_NODE_OPTIONS:---max-old-space-size=2048}" npx vite build --logLevel warn; then
  echo "hub : compilé en $(( $(date +%s) - start )) s"
  exec node serve.mjs
fi
echo "hub : ÉCHEC de la compilation -- repli sur le serveur de développement" >&2
exec npm run dev
