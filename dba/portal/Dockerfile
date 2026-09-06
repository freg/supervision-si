FROM node:20-slim

WORKDIR /app

COPY dba/portal/package.json .
RUN npm install

COPY dba/portal/ .
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
COPY shared/useUnsavedChangesWarning.js src/useUnsavedChangesWarning.js
COPY shared/VERSION.json src/VERSION.json

EXPOSE 5173

# Dev server — même logique que les autres fronts : à remplacer par
# un build statique servi par nginx une fois l'app stabilisée.
CMD ["npm", "run", "dev"]
