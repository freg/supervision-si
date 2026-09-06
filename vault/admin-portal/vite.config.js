import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";

// PAS de "base" particulière (contrairement à vault/portal, servi
// sous "/vault/" via le proxy public) -- ce portail n'est JAMAIS
// routé par tls-proxy, exposé directement sur son propre port LAN
// (voir docker-compose.yml, VAULT_ADMIN_PORTAL_LAN_PORT). Servi à la
// racine, comme vault-admin-api lui-même.
//
// HTTPS OBLIGATOIRE malgré tout -- bug réel signalé : servi en HTTP
// simple, `crypto.subtle` (Web Crypto, utilisée par vaultOps.js/
// vaultCrypto.js depuis la refonte "débloquer un compte") est
// VOLONTAIREMENT indisponible par les navigateurs hors "contexte
// sécurisé" (HTTPS ou localhost) -- chaque tentative de déverrouillage
// échouait silencieusement, mal interprétée en "mot de passe
// incorrect" alors que la primitive cryptographique elle-même
// n'existait tout simplement pas dans ce contexte. Réutilise le
// certificat déjà généré pour la passerelle principale (mêmes
// entrées SAN -- localhost/127.0.0.1/HOST_IP -- un certificat
// n'encode jamais de port, valide ici aussi malgré le port différent).
const certPath = "/etc/vault-admin-portal/tls/server.crt";
const keyPath = "/etc/vault-admin-portal/tls/server.key";
const httpsConfig =
  fs.existsSync(certPath) && fs.existsSync(keyPath)
    ? { cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) }
    : undefined; // repli HTTP si jamais le certificat n'est pas monté -- pour ne jamais empêcher le démarrage, avec un avertissement affiché au démarrage (voir plus bas)

if (!httpsConfig) {
  // eslint-disable-next-line no-console
  console.warn(
    "⚠️  Certificat TLS introuvable -- ce portail démarre en HTTP simple. " +
    "Le déverrouillage par mot de passe (Web Crypto) échouera systématiquement " +
    "hors contexte sécurisé (voir vault/README.md)."
  );
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    https: httpsConfig,
  },
});
