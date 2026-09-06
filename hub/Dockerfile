FROM node:20-slim

WORKDIR /app

COPY hub/package.json .
RUN npm install

COPY hub/ .
# Jetons de design + gestion de préférences partagés (voir
# shared/theme.css et shared/preferences.js) -- copiés depuis la
# racine du dépôt, contexte de build changé en conséquence dans
# docker-compose.yml (context: . / dockerfile: hub/Dockerfile).
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
COPY shared/hubEvents.js src/hubEvents.js
COPY shared/VERSION.json src/VERSION.json

EXPOSE 5173

# Dev server — même logique que les autres frontends de ce projet : à
# remplacer par un build statique servi par nginx une fois l'app stabilisée.
CMD ["npm", "run", "dev"]
