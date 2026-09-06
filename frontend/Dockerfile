FROM node:20-slim

WORKDIR /app

COPY frontend/package.json .
RUN npm install

COPY frontend/ .
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
COPY shared/VERSION.json src/VERSION.json

EXPOSE 5173

# Dev server pour ce squelette — à remplacer par un build statique
# servi par nginx une fois l'app stabilisée pour un déploiement prod.
CMD ["npm", "run", "dev"]
