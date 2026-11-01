// Build statique de la tuile « Agents hôtes » seule (livraison #517).
// Racine = ce dossier ; `@hub` pointe vers les sources du hub (SiAgentView.jsx
// et sa logique pure), jamais copiées. Sortie : dist/ servie sous /agents/.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const hubSrc = process.env.SI_HUB_SRC || path.resolve(here, "../../../hub/src");

export default defineConfig({
  root: here,
  base: "/agents/",
  plugins: [react()],
  resolve: { alias: { "@hub": hubSrc } },
  server: { fs: { allow: [here, hubSrc] } },
  build: { outDir: path.resolve(here, "dist"), emptyOutDir: true },
});
