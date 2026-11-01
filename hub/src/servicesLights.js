// Feu tricolore des services du hub (livraison #584) -- logique pure,
// testée sans navigateur : ordre (rouge → orange → vert), filtre texte
// (début de mot d'abord, textFilter.js), résumé et libellés.
import { rankFilter } from "./textFilter.js";

export const LIGHT_ORDER = { red: 0, orange: 1, grey: 2, green: 3 };
export const LIGHT_LABEL = { red: "en panne", orange: "à surveiller", green: "en marche", grey: "inconnu" };
export const KIND_LABEL = { api: "API", front: "front", db: "base", service: "service" };

export function sortServices(rows) {
  return [...(rows || [])].sort((a, b) => (LIGHT_ORDER[a.light] ?? 9) - (LIGHT_ORDER[b.light] ?? 9) || String(a.service).localeCompare(String(b.service)));
}

export function filterServices(rows, query, onlyProblems = false) {
  const base = onlyProblems ? (rows || []).filter((r) => r.light !== "green") : rows || [];
  return rankFilter(base, query, (r) => [r.service, r.kind, KIND_LABEL[r.kind], r.status, r.text, r.light, LIGHT_LABEL[r.light]].filter(Boolean).join(" "),
    (a, b) => (LIGHT_ORDER[a.light] ?? 9) - (LIGHT_ORDER[b.light] ?? 9));
}

export function summarize(rows) {
  const counts = { red: 0, orange: 0, green: 0, grey: 0 };
  for (const r of rows || []) counts[r.light in counts ? r.light : "grey"] += 1;
  const verdict = counts.red ? "red" : counts.orange ? "orange" : counts.green ? "green" : "grey";
  return { counts, verdict, total: (rows || []).length };
}

export function verdictText(summary) {
  if (!summary || !summary.total) return "aucun service";
  const { counts } = summary;
  if (summary.verdict === "green") return `tout est en marche (${counts.green} service${counts.green > 1 ? "s" : ""})`;
  const parts = [];
  if (counts.red) parts.push(`${counts.red} en panne`);
  if (counts.orange) parts.push(`${counts.orange} à surveiller`);
  return `${parts.join(", ")} sur ${summary.total}`;
}

export function uptimeText(startedAt, now = Date.now()) {
  if (!startedAt) return "";
  const t = Date.parse(startedAt);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.floor((now - t) / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
  return `${Math.floor(s / 86400)} j ${Math.floor((s % 86400) / 3600)} h`;
}
