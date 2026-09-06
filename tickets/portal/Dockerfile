FROM node:20-slim

WORKDIR /app

COPY tickets/portal/package.json .
RUN npm install

COPY tickets/portal/ .
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
COPY shared/hubEvents.js src/hubEvents.js
COPY shared/VERSION.json src/VERSION.json

EXPOSE 5173

# Dev server — même logique que le frontend principal : à remplacer par
# un build statique servi par nginx une fois l'app stabilisée.
CMD ["npm", "run", "dev"]
