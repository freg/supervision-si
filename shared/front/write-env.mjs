// #736/#737 (commun hub et fronts) : écrit dist/env.js au démarrage du conteneur à partir des variables VITE_* de l'environnement (compose),
// pour un hub pré-compilé dans l'image : changer une URL ne demande plus de recompiler, seulement de redémarrer.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function envScript(env) {
  const vars = {};
  for (const k of Object.keys(env || {}).sort()) if (/^VITE_[A-Z0-9_]+$/.test(k)) vars[k] = String(env[k]);
  // JSON dans un fichier .js séparé ; « < » échappé par prudence (jamais interprété comme balise)
  return "window.__HUB_ENV__ = " + JSON.stringify(vars).replace(/</g, "\\u003c") + ";\n";
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const out = process.argv[2] || "dist/env.js";
  fs.writeFileSync(out, envScript(process.env));
  console.log(`hub : configuration d'exécution écrite (${out}, ${Object.keys(process.env).filter((k) => k.startsWith("VITE_")).length} variables VITE_*)`);
}
