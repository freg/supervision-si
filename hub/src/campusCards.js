// Fiches du campus (livraison #566) -- logique PURE testée : regroupement
// par lab, filtre « début de mot d'abord », résumé.
import { rankFilter } from "./textFilter.js";

export const ASSET_LABELS = { kind: "Type", designation: "Désignation", model: "Modèle", serial: "N° de série", mac: "MAC", account: "Compte", klass: "Classe", subclass: "Sous-classe", location: "Localisation", storage: "Stockage", profile: "Profil", commissioned: "Mise en service", comment: "Commentaire" };
export const SERVICE_LABELS = { course: "Parcours", name: "Atelier", apk: "Livraison APK", hardware: "Matériel", site: "Site / plateforme" };

export function cardText(item) {
  return [item.name, item.kind, item.course, item.designation, item.model, item.serial, item.mac, item.lab, item.location, item.hardware, item.site, ...Object.values(item.fields || {})].filter(Boolean).join(" ");
}

/** Groupes [{lab, items}] filtrés, labs triés, « (sans lab) » en dernier. */
export function groupByLab(items, query, labFilter = "") {
  const kept = rankFilter(items.filter((i) => !labFilter || (i.lab || "") === labFilter), query, cardText);
  const groups = new Map();
  for (const it of kept) { const k = (it.lab || "").trim() || "(sans lab)"; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(it); }
  return [...groups.entries()].map(([lab, items]) => ({ lab, items })).sort((a, b) => (a.lab === "(sans lab)") - (b.lab === "(sans lab)") || a.lab.localeCompare(b.lab, "fr"));
}

export function labs(items) {
  return [...new Set(items.map((i) => (i.lab || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr"));
}

/** Résumé des matériels : total, rapprochés Nebula, en ligne, par type. */
export function assetSummary(items) {
  const byKind = new Map();
  let matched = 0, online = 0;
  for (const i of items) {
    byKind.set(i.kind || "?", (byKind.get(i.kind || "?") || 0) + 1);
    if (i.nebula) { matched++; if (i.nebula.status === "online") online++; }
  }
  return { total: items.length, matched, online, byKind: [...byKind.entries()].sort((a, b) => b[1] - a[1]) };
}
