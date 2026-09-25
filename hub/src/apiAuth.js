// A0 (livraison #615) : jeton Keycloak sur TOUS les appels d'API du hub.
// Un seul intercepteur `fetch`, plutôt qu'une ligne dans chacun des ~30
// clients JS : toute requête vers une base d'API du hub (VITE_*_API_BASE_URL,
// ou chemin /api/ sur la même origine) reçoit `Authorization: Bearer` si elle
// ne porte pas déjà d'en-tête Authorization. Le jeton est celui de la session
// OIDC courante, mis à jour par App.jsx à chaque renouvellement silencieux.
// Le frontal public (docs/acces-public-frontal.md, mod_auth_openidc) refuse
// tout /api/ sans jeton valide depuis Internet ; sur le LAN les API gardent
// leur modèle actuel -- l'en-tête est simplement ignoré par celles qui ne le
// lisent pas encore.
let currentToken = "";
let installed = false;

export function apiBases(env = import.meta.env) {
  return Object.entries(env || {})
    .filter(([k, v]) => /^VITE_.*_(API_)?BASE_URL$/.test(k) && typeof v === "string" && /^https?:\/\//.test(v))
    .map(([, v]) => v.replace(/\/+$/, ""));
}

/** Vrai si l'URL vise une API du hub (base connue, ou /api/ de la même origine). */
export function isApiUrl(url, bases, origin) {
  const u = String(url || "");
  if (u.startsWith("/api/")) return true;
  if (origin && u.startsWith(origin + "/api/")) return true;
  return bases.some((b) => u === b || u.startsWith(b + "/") || u.startsWith(b + "?"));
}

/** Ajoute Authorization à des options fetch, sans écraser un en-tête déjà posé. */
export function withToken(init, token) {
  if (!token) return init;
  const headers = new Headers((init && init.headers) || undefined);
  if (headers.has("Authorization")) return init;
  headers.set("Authorization", `Bearer ${token}`);
  return { ...(init || {}), headers };
}

export function setApiToken(token) { currentToken = token || ""; }
export function getApiToken() { return currentToken; }

export function installApiAuth(win = typeof window !== "undefined" ? window : null, env = import.meta.env) {
  if (!win || installed || typeof win.fetch !== "function") return;
  installed = true;
  const bases = apiBases(env);
  const origin = win.location ? win.location.origin : "";
  const native = win.fetch.bind(win);
  win.fetch = (input, init) => {
    try {
      const url = typeof input === "string" ? input : input && input.url;
      if (currentToken && isApiUrl(url, bases, origin)) {
        if (typeof input !== "string" && input && input.headers && input.headers.has && input.headers.has("Authorization")) return native(input, init);
        return native(input, withToken(init, currentToken));
      }
    } catch (_) { /* jamais bloquer un appel pour une erreur d'intercepteur */ }
    return native(input, init);
  };
}
