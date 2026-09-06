import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "/" -- le hub est la racine de l'entrée unique (voir
// tls-proxy/render_nginx_conf.py). GATEWAY_PORT : voir
// frontend/vite.config.js pour l'explication complète (même
// mécanisme, même mise en garde sur le HMR non vérifié ici).
const GATEWAY_PORT = Number(process.env.GATEWAY_PORT || 6443);

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    host: "0.0.0.0",
    port: 5173,
    hmr: {
      protocol: "wss",
      clientPort: GATEWAY_PORT,
      path: "/",
    },
  },
});
