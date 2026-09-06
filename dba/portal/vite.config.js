import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "/dba/" -- même mécanisme GATEWAY_PORT/HMR que les autres
// fronts (voir frontend/vite.config.js pour l'explication complète).
const GATEWAY_PORT = Number(process.env.GATEWAY_PORT || 6443);

export default defineConfig({
  plugins: [react()],
  base: "/dba/",
  server: {
    host: "0.0.0.0",
    port: 5173,
    hmr: {
      protocol: "wss",
      clientPort: GATEWAY_PORT,
      path: "/dba/",
    },
  },
});
