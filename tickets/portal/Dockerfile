FROM node:20-slim

WORKDIR /app

COPY tickets/portal/package.json .
RUN npm install

COPY tickets/portal/ .
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
COPY shared/hubEvents.js src/hubEvents.js
COPY shared/VERSION.json src/VERSION.json

# #737 : pré-compilé dans l'image (configuration lue à l'exécution dans env.js) et servi statiquement ;
# FRONT_MODE=dev pour l'ancien serveur de développement Vite. Échec de la compilation : repli sur ce serveur.
COPY shared/front/serve.mjs /app/front-serve.mjs
COPY shared/front/write-env.mjs /app/front-write-env.mjs
COPY shared/front/entrypoint.sh /app/front-entrypoint.sh
ENV FRONT_BASE=/tickets/
RUN FRONT_RUNTIME_ENV=1 NODE_OPTIONS=--max-old-space-size=1536 npx vite build --logLevel warn --outDir dist-prebuilt \
    || (echo "front : pré-compilation échouée, serveur de développement au démarrage" && rm -rf dist-prebuilt)
EXPOSE 5173
CMD ["sh", "/app/front-entrypoint.sh"]
