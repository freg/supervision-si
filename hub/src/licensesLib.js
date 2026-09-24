// Licences logicielles (livraison #595) -- logique pure de la tuile :
// libellés, filtres début-de-mot, résumé des écarts, lampe par contrat,
// lecture de la grille, gestionnaire de paquets par défaut selon l'OS.
import { rankFilter } from "./textFilter.js";

export const KIND_LABEL = { "per-user": "par utilisateur", "per-device": "par poste", subscription: "abonnement", perpetual: "perpétuelle", site: "site", free: "gratuit / libre" };
export const GAP_LABEL = {
  "installed-no-contract": "installé sans contrat", expired: "contrat expiré", expiring: "expire bientôt", "over-assigned": "sur-attribué",
  "over-installed": "sur-installé", unused: "payé, inutilisé", spare: "licences disponibles", "assigned-not-installed": "attribué, non installé", "installed-not-assigned": "installé, non attribué",
};
export const SEVERITY_TONE = { critical: "red", warning: "orange", info: "grey" };
export const ACTION_STATUS = { pending: "en attente", acked: "reçue par l'agent", done: "terminée", failed: "échec" };
export const VENDOR_KIND_LABEL = { "microsoft-graph": "Microsoft 365 (Graph)", "csv-export": "export du vendeur (fichier)", manual: "saisie manuelle" };

/** Lampe d'un contrat : rouge (expiré / dépassé), orange (expire bientôt), vert. */
export function contractTone(c, expiringDays = 60) {
  if (!c) return "grey";
  const d = c.days_left;
  if (d != null && d < 0) return "red";
  const q = c.quantity || 0;
  if (q && ["per-user", "subscription"].includes(c.kind) && (c.assigned || 0) > q) return "red";
  if (d != null && d <= expiringDays) return "orange";
  return "green";
}

export function filterContracts(contracts, query) {
  return rankFilter(contracts || [], query, (c) => [c.software, c.vendor, c.label, c.site, KIND_LABEL[c.kind], c.sku, c.reference].filter(Boolean).join(" "));
}
export function filterSoftware(list, query) {
  return rankFilter(list || [], query, (s) => [s.name, s.vendor, s.category, ...(s.patterns || [])].join(" "));
}
export function filterGaps(gaps, query, severity = "") {
  const base = (gaps || []).filter((g) => !severity || g.severity === severity);
  return rankFilter(base, query, (g) => [g.software, GAP_LABEL[g.kind], g.text].join(" "));
}
export function filterHosts(hosts, query) {
  return rankFilter(hosts || [], query, (h) => [h.hostname, h.site, h.os, ...(h.users || [])].join(" "));
}
export function filterUsers(users, query) {
  return rankFilter(users || [], query, (u) => [u.login, u.name, u.mail, u.site, ...(u.aliases || [])].filter(Boolean).join(" "));
}
export function filterRows(rows, query) {
  return rankFilter(rows || [], query, (r) => [r.subject, r.kind === "host" ? "poste" : "utilisateur", r.site].filter(Boolean).join(" "));
}

/** Résumé des écarts : { critical, warning, info, total, tone }. */
export function gapSummary(gaps) {
  const s = { critical: 0, warning: 0, info: 0, total: 0 };
  for (const g of gaps || []) { s[g.severity] = (s[g.severity] || 0) + 1; s.total += 1; }
  s.tone = s.critical ? "red" : s.warning ? "orange" : "green";
  return s;
}

/** Totaux par logiciel pour le tableau de bord : licences, attribuées, installées (postes), coût annuel connu. */
export function softwareTotals(contracts, found) {
  const by = new Map();
  for (const c of contracts || []) {
    const cur = by.get(c.software_id) || { software_id: c.software_id, software: c.software, vendor: c.vendor, quantity: 0, assigned: 0, installed: 0, cost: 0, contracts: 0, tone: "green" };
    cur.quantity += c.quantity || 0; cur.assigned += c.assigned || 0; cur.cost += c.cost || 0; cur.contracts += 1;
    const tone = contractTone(c);
    if (tone === "red" || (tone === "orange" && cur.tone !== "red")) cur.tone = tone;
    by.set(c.software_id, cur);
  }
  for (const [sid, insts] of Object.entries(found || {})) {
    const cur = by.get(Number(sid));
    if (cur) cur.installed = new Set((insts || []).map((i) => i.host)).size;
  }
  return [...by.values()].sort((a, b) => String(a.software).localeCompare(String(b.software)));
}

/** Contrat de la colonne à utiliser pour attribuer un sujet : le premier qui a de la place, sinon le premier. */
export function pickContract(column, subjectKind) {
  const cs = (column && column.contracts) || [];
  const fits = cs.filter((c) => (subjectKind === "host" ? c.kind !== "per-user" : c.kind !== "per-device"));
  const pool = fits.length ? fits : cs;
  return pool.find((c) => !c.quantity || (c.assigned || 0) < c.quantity) || pool[0] || null;
}

/** Gestionnaire de paquets attendu par la commande software_action selon l'OS du poste. */
export function defaultManager(os) {
  const o = String(os || "").toLowerCase();
  if (o.startsWith("win")) return "winget";
  if (o.startsWith("dar") || o.includes("mac")) return "brew";
  if (/(fedora|rhel|centos|rocky|alma)/.test(o)) return "dnf";
  return "apt";
}

export const fmtDays = (d) => (d == null ? "" : d < 0 ? `expiré depuis ${-d} j` : d === 0 ? "expire aujourd'hui" : `${d} j`);
