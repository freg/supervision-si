FROM node:20-slim

WORKDIR /app

COPY ldap-admin/portal/package.json .
RUN npm install

COPY ldap-admin/portal/ .
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
COPY shared/VERSION.json src/VERSION.json

EXPOSE 5173

# Dev server -- même logique que les autres fronts.
CMD ["npm", "run", "dev"]
