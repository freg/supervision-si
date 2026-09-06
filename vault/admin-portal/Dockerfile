FROM node:20-slim

WORKDIR /app

COPY vault/admin-portal/package.json .
RUN npm install

COPY vault/admin-portal/ .
COPY shared/vaultCrypto.js src/vaultCrypto.js
COPY shared/theme.css src/theme.css
COPY shared/preferences.js src/preferences.js
# vaultOps.js et api.js -- copiés depuis vault-portal (source
# CANONIQUE), jamais un fork dupliqué dans ce dossier : ce portail a
# désormais besoin de la MÊME logique de déverrouillage/usurpation
# maître_principal (voir vaultOps.js, usurpMaitrePrincipal) que le
# coffre principal -- toute correction faite là-bas se répercute ici
# automatiquement au prochain build, jamais une divergence silencieuse
# entre deux copies.
COPY vault/portal/src/vaultOps.js src/vaultOps.js
COPY vault/portal/src/api.js src/api.js

EXPOSE 5173

CMD ["npm", "run", "dev"]
