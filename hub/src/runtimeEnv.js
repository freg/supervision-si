// #736 : variables VITE_* du hub -- figées à la compilation (import.meta.env) ou fournies à l'exécution par /env.js
// (window.__HUB_ENV__) quand le hub est pré-compilé dans l'image ; l'exécution l'emporte.
export function hubEnv() {
  const rt = (typeof globalThis !== "undefined" && globalThis.__HUB_ENV__) || {};
  return { ...(import.meta.env || {}), ...rt };
}
