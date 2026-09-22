// Vue « Aujourd'hui » (livraison #544) -- logique PURE, testée sous Node
// (hub/tests/today.test.mjs). Pour un responsable non technicien : trois
// questions en phrases, sans densité -- est-ce que ça marche ? où en sont
// les demandes ? y a-t-il des incidents ? Chaque phrase vient des données
// des tuiles existantes (état des services du pont, file des tickets,
// incidents Cortex) ; jamais un sigle, jamais une couleur seule.
// Voir docs/ergonomie-redesign.md.

const DAY = 86400;

/** Services : phrases depuis /demande/etat.json (pont, #541). */
export function servicesSummary(etat) {
  if (!etat || !Array.isArray(etat.services)) return { tone: "unknown", headline: "L'état des services n'est pas disponible.", lines: [] };
  const ko = etat.services.filter((s) => s.etat !== "ok");
  if (ko.length === 0) return { tone: "ok", headline: "Tout fonctionne.", lines: [] };
  const pannes = ko.filter((s) => s.etat === "panne").length;
  const headline = pannes ? `${pannes} service${pannes > 1 ? "s" : ""} en panne` + (ko.length > pannes ? `, ${ko.length - pannes} dégradé${ko.length - pannes > 1 ? "s" : ""}.` : ".") : `${ko.length} service${ko.length > 1 ? "s" : ""} dégradé${ko.length > 1 ? "s" : ""}.`;
  return { tone: pannes ? "panne" : "degrade", headline, lines: etat.phrases || [] };
}

/** Demandes : phrases depuis /queue (tickets-api, state=all). `now` en secondes. */
export function ticketsSummary(rows, now = Date.now() / 1000) {
  if (!Array.isArray(rows)) return { tone: "unknown", headline: "La file des demandes n'est pas disponible.", lines: [] };
  const open = rows.filter((t) => !t.ts_closed && !t.archived_at);
  const waiting = open.filter((t) => !t.user_id && !t.user_login);
  const late = open.filter((t) => (now - (t.ts_created || now)) > 2 * DAY);
  const closedToday = rows.filter((t) => t.ts_closed && now - t.ts_closed < DAY).length;
  const newToday = rows.filter((t) => t.ts_created && now - t.ts_created < DAY).length;
  const lines = [];
  if (waiting.length) lines.push(`${waiting.length} en attente de prise en charge`);
  if (late.length) lines.push(`${late.length} sans réponse depuis plus de deux jours`);
  lines.push(`${newToday} reçue${newToday > 1 ? "s" : ""} et ${closedToday} résolue${closedToday > 1 ? "s" : ""} depuis 24 h`);
  const tone = late.length ? "panne" : waiting.length ? "degrade" : "ok";
  const headline = open.length === 0 ? "Aucune demande en cours." : `${open.length} demande${open.length > 1 ? "s" : ""} en cours.`;
  return { tone, headline, lines, open: open.length };
}

/** Incidents Cortex (state=open) : phrases sans jargon. */
export function incidentsSummary(incidents) {
  if (!Array.isArray(incidents)) return { tone: "unknown", headline: "La supervision n'est pas disponible.", lines: [] };
  if (incidents.length === 0) return { tone: "ok", headline: "Aucun incident en cours.", lines: [] };
  const crit = incidents.filter((i) => i.severity === "critical");
  const lines = incidents.slice(0, 5).map((i) => `${i.title || i.root || i.key || "incident"}${i.state === "acked" ? " (pris en charge)" : ""}`);
  if (incidents.length > 5) lines.push(`… et ${incidents.length - 5} autre${incidents.length - 5 > 1 ? "s" : ""}`);
  const headline = `${incidents.length} incident${incidents.length > 1 ? "s" : ""} en cours` + (crit.length ? `, dont ${crit.length} critique${crit.length > 1 ? "s" : ""}.` : ".");
  return { tone: crit.length ? "panne" : "degrade", headline, lines };
}

/** Le mot du jour : la pire des trois. */
export function overall(blocks) {
  const rank = { panne: 3, degrade: 2, unknown: 1, ok: 0 };
  const worst = blocks.reduce((w, b) => (rank[b.tone] > rank[w] ? b.tone : w), "ok");
  return { ok: "Journée calme : tout fonctionne.", degrade: "Quelques points à surveiller.", panne: "Des problèmes en cours demandent une action.", unknown: "Certaines informations manquent." }[worst];
}
