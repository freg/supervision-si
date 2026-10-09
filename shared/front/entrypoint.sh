#!/bin/sh
# #737 : démarrage commun des fronts pré-compilés dans l'image (comme le hub, #736) : copie de la compilation, /env.js
# écrit depuis les VITE_* du compose, service statique (front-serve.mjs, base FRONT_BASE). FRONT_MODE=dev : ancien
# serveur de développement Vite (rechargement à chaud) ; sans pré-compilation : repli sur ce même serveur.
set -u
cd /app
if [ "${FRONT_MODE:-prod}" = "dev" ]; then
  echo "front : mode développement (FRONT_MODE=dev)"
  exec npm run dev
fi
if [ -f /app/dist-prebuilt/index.html ]; then
  rm -rf /app/dist && cp -r /app/dist-prebuilt /app/dist && node /app/front-write-env.mjs /app/dist/env.js && exec node /app/front-serve.mjs
fi
echo "front : pas de compilation dans l'image -- serveur de développement" >&2
exec npm run dev
