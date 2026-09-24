// Notifications (livraison #590) -- logique pure de la tuile : regroupement
// des actions par module, libellés d'état de la file, résumé des groupes.
import { rankFilter } from "./textFilter.js";

export const STATUS_LABEL = { queued: "en file", sent: "envoyé", failed: "échec", held: "retenu", dropped: "abandonné", "no-recipients": "sans destinataire", merged: "regroupé" };
export const STATUS_TONE = { queued: "orange", sent: "green", failed: "red", held: "orange", dropped: "grey", "no-recipients": "red" };
export const SEVERITY_LABEL = { info: "info", warning: "alerte", critical: "critique" };

export function byModule(actions) {
  const out = new Map();
  for (const a of actions || []) {
    const m = a.module || String(a.id).split(".")[0];
    if (!out.has(m)) out.set(m, []);
    out.get(m).push(a);
  }
  return [...out.entries()].sort((x, y) => x[0].localeCompare(y[0]));
}

export function filterActions(actions, query) {
  return rankFilter(actions || [], query, (a) => [a.id, a.label, a.module, ...(a.groups || [])].join(" "));
}

export function groupLabel(g) {
  if (!g) return "";
  const n = (g.resolved || []).length;
  return `${g.name}${g.kind === "meta" ? " (méta)" : ""} — ${n} adresse${n > 1 ? "s" : ""}`;
}

/** Groupes effectifs d'une action : affectés, sinon ceux du module (« module.* »), sinon le défaut. */
export function effectiveGroups(action, actions) {
  if (action.groups?.length) return { groups: action.groups, source: "action" };
  const star = (actions || []).find((a) => a.id === `${action.module}.*`);
  if (star?.groups?.length) return { groups: star.groups, source: "module" };
  return { groups: [action.default_group], source: "défaut" };
}

export function parseEmails(text) {
  return [...new Set(String(text || "").split(/[\s,;]+/).map((e) => e.trim().toLowerCase()).filter(Boolean))];
}

export function queueSummary(counts) {
  const c = counts || {};
  const parts = [];
  for (const k of ["queued", "held", "failed", "no-recipients", "sent"]) if (c[k]) parts.push(`${c[k]} ${STATUS_LABEL[k]}`);
  return parts.join(", ") || "file vide";
}
