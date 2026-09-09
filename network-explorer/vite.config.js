import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Contrairement à hub/frontend, ce module n'est JAMAIS routé par
// tls-proxy (accès direct uniquement, voir docker-compose.yml et
// network-explorer/README.md) -- pas de `base`, pas de configuration
// HMR spécifique à un chemin de passerelle, le port exposé est
// directement celui du serveur de dev Vite.
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
  },
});
