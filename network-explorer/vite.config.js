import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Contrairement à hub/frontend, ce module n'est JAMAIS routé par
// tls-proxy (accès direct uniquement, voir docker-compose.yml et
// network-explorer/README.md) -- pas de `base`, pas de configuration
// HMR spécifique à un chemin de passerelle, le port exposé est
// directement celui du serveur de dev Vite.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
