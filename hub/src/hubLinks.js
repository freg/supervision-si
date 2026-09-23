// Liens internes du hub (livraison #570) -- règle d'ergonomie : quand le hub
// dit « activer X », « déposer Y », « régler Z », il donne le lien vers
// l'endroit du hub où on le fait. Un lien = `?view=<vue>&<paramètres>` :
// App.jsx ouvre la vue (#559, lien profond), la vue lit ses paramètres
// (`viewParams()`) pour se placer (agent sélectionné, section ouverte…).
export function hubLink(view, params = {}) {
  const q = new URLSearchParams({ view, ...Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== "")) });
  return `${window.location.pathname}?${q.toString()}`;
}

/** Paramètres de la vue courante (hors `view`), lus une fois à l'ouverture. */
export function viewParams() {
  try {
    const p = new URLSearchParams(window.location.search);
    const out = {};
    for (const [k, v] of p.entries()) if (k !== "view") out[k] = v;
    return out;
  } catch { return {}; }
}

/** Efface les paramètres de l'URL sans recharger (une fois consommés). */
export function clearViewParams() {
  try { window.history.replaceState(null, "", window.location.pathname); } catch { /* sans importance */ }
}
