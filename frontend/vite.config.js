import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// #737 : FRONT_RUNTIME_ENV=1 (pré-compilation dans l'image) -- chaque import.meta.env.VITE_X devient une lecture de
// globalThis.__HUB_ENV__ (fichier env.js, toujours présent : public/env.js par défaut, réécrit au démarrage).
function runtimeDefines() {
  if (process.env.FRONT_RUNTIME_ENV !== "1") return {};
  const names = new Set();
  const walk = (d) => { for (const f of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, f.name);
    if (f.isDirectory()) walk(p); else if (/\.(jsx?|mjs)$/.test(f.name)) for (const m of fs.readFileSync(p, "utf8").matchAll(/import\.meta\.env\.(VITE_[A-Z0-9_]+)/g)) names.add(m[1]);
  } };
  walk(path.resolve("src"));
  return Object.fromEntries([...names].map((n) => [`import.meta.env.${n}`, `globalThis.__HUB_ENV__.${n}`]));
}

// base "/app/" -- doit correspondre EXACTEMENT au chemin utilisé par
// tls-proxy pour router vers ce service (voir
// tls-proxy/render_nginx_conf.py, SERVICES). GATEWAY_PORT lu depuis
// l'environnement (pas VITE_*, ce fichier tourne côté Node au
// démarrage du serveur de dev, pas dans le bundle client) pour que le
// client HMR sache où reconnecter son WebSocket à travers le proxy --
// jamais codé en dur, resterait synchronisé avec .env même si
// GATEWAY_PORT change. Partie la plus fragile du passage à une
// entrée unique par chemin (voir tls-proxy/README.md) : jamais
// vérifiée en conditions réelles ici, faute de navigateur.
const GATEWAY_PORT = Number(process.env.GATEWAY_PORT || 6443);

// #472 : Vite >= 5.4.12 refuse toute requête dont l'en-tête Host n'est ni
// localhost ni une adresse IP (« Blocked request. This host is not allowed »)
// -- c'est le cas d'un nom DNS (LAN ou public derrière un frontal). Hôtes
// autorisés : HOST_IP (.env) + VITE_ALLOWED_HOSTS (liste à virgules) ;
// "*" = tous (le front n'est joignable que par la passerelle nginx).
const ALLOWED = (process.env.VITE_ALLOWED_HOSTS || "").split(",").map((s) => s.trim()).filter(Boolean);
const allowedHosts = ALLOWED.includes("*") ? true : [...new Set([process.env.HOST_IP, ...ALLOWED].filter((h) => h && !/^[0-9.]+$/.test(h)))];

export default defineConfig({
  plugins: [react()],
  define: runtimeDefines(),
  base: "/app/",
  server: {
    allowedHosts,
    host: "0.0.0.0",
    port: 5173,
    hmr: {
      protocol: "wss",
      clientPort: GATEWAY_PORT,
      path: "/app/",
    },
  },
});
