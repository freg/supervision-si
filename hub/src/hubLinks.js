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

/** #790 : pose des paramètres d'écran (ex. {tab: "sms"}) dans l'URL sans recharger, lus par viewParams() à l'ouverture. */
export function setViewParams(params) {
  try {
    const q = new URLSearchParams(Object.entries(params || {}).filter(([, v]) => v != null && v !== "")).toString();
    window.history.replaceState(null, "", window.location.pathname + (q ? "?" + q : ""));
  } catch { /* sans importance */ }
}

/** Efface les paramètres de l'URL sans recharger (une fois consommés). */
export function clearViewParams() {
  try { window.history.replaceState(null, "", window.location.pathname); } catch { /* sans importance */ }
}

/** #768 : liens « journal » d'un agent à joindre à tout message d'erreur : événements de l'agent (filtrés sur un mot),
 *  ses sondes, le journal système de l'hôte. -> [{label, href}] */
export function agentJournalLinks(agentId, q = "") {
  if (!agentId) return [];
  return [
    { label: "événements", href: hubLink("si-agent", { tab: "events", agent: agentId, q }) },
    { label: "sondes", href: hubLink("si-agent", { agent: agentId, section: "plugins" }) },
    { label: "journal de l'hôte", href: hubLink("si-agent", { agent: agentId, section: "logs" }) },
  ];
}
