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

// #472 : Vite >= 5.4.12 refuse toute requête dont l'en-tête Host n'est ni
// localhost ni une adresse IP (« Blocked request. This host is not allowed »)
// -- c'est le cas d'un nom DNS (LAN ou public derrière un frontal). Hôtes
// autorisés : HOST_IP (.env) + VITE_ALLOWED_HOSTS (liste à virgules) ;
// "*" = tous (le front n'est joignable que par la passerelle nginx).
const ALLOWED = (process.env.VITE_ALLOWED_HOSTS || "").split(",").map((s) => s.trim()).filter(Boolean);
const allowedHosts = ALLOWED.includes("*") ? true : [...new Set([process.env.HOST_IP, ...ALLOWED].filter((h) => h && !/^[0-9.]+$/.test(h)))];

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts,
    host: "0.0.0.0",
    port: 5173,
    https: httpsConfig,
  },
});
