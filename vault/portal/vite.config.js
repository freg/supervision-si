import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "/vault/" -- voir frontend/vite.config.js pour l'explication
// complète (même mécanisme GATEWAY_PORT, même mise en garde HMR).
const GATEWAY_PORT = Number(process.env.GATEWAY_PORT || 6443);

export default defineConfig({
  plugins: [react()],
  base: "/vault/",
  server: {
    host: "0.0.0.0",
    port: 5173,
    hmr: {
      protocol: "wss",
      clientPort: GATEWAY_PORT,
      path: "/vault/",
    },
  },
});
