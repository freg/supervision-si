// Équipements réseau (livraison #506) -- logique PURE de la vue
// NetworkEquipmentView.jsx, testée sous Node (hub/tests/networkEquipment.test.mjs).
// Rien de React ici : libellés, tons, tris, synthèses.

export const KIND_LABELS = {
  routeur: "Routeur", switch: "Switch", "pare-feu": "Pare-feu", "point d'accès": "Point d'accès",
  "équipement réseau": "Équipement réseau", "hôte": "Hôte", hyperviseur: "Hyperviseur", imprimante: "Imprimante",
  onduleur: "Onduleur", stockage: "Stockage", inconnu: "Inconnu",
};
export const KIND_ORDER = ["routeur", "pare-feu", "switch", "équipement réseau", "point d'accès", "hyperviseur", "hôte", "stockage", "onduleur", "imprimante", "inconnu"];
export const NETWORK_KINDS = new Set(["routeur", "pare-feu", "switch", "équipement réseau", "point d'accès"]);
export const GENERATION_LABELS = { recent: "Récent", ancien: "Ancien" };
export const KIND_CHOICES = ["routeur", "switch", "pare-feu", "point d'accès", "hôte", "hyperviseur", "imprimante", "onduleur", "stockage", "inconnu"];

export function kindLabel(kind) {
  return KIND_LABELS[kind] || kind || "Inconnu";
}

export function isNetworkGear(row) {
  return NETWORK_KINDS.has(row?.kind);
}

/** Ton (np-tone) de la génération : ancien = à surveiller, récent = bon. */
export function generationTone(generation) {
  if (generation === "ancien") return "warn";
  if (generation === "recent") return "good";
  return "neutral";
}

export function generationLabel(generation) {
  return GENERATION_LABELS[generation] || "—";
}

/** Confiance 0-1 -> libellé + ton. */
export function confidenceLabel(confidence) {
  const c = Number(confidence);
  if (!Number.isFinite(c) || c <= 0) return { text: "aucune", tone: "neutral" };
  if (c >= 0.8) return { text: "forte", tone: "good" };
  if (c >= 0.45) return { text: "moyenne", tone: "neutral" };
  return { text: "faible", tone: "warn" };
}

/** Synthèse de la flotte : compteurs par genre, constructeur, génération,
 *  et les équipements réseau anciens (ce que la demande vise). */
export function summarizeFleet(rows) {
  const out = { total: 0, network: 0, byKind: {}, byVendor: {}, byGeneration: { recent: 0, ancien: 0, inconnue: 0 }, oldNetwork: [], unidentified: 0 };
  for (const r of rows || []) {
    out.total += 1;
    const kind = r.kind || "inconnu";
    out.byKind[kind] = (out.byKind[kind] || 0) + 1;
    if (NETWORK_KINDS.has(kind)) out.network += 1;
    const vendor = r.vendor || "?";
    out.byVendor[vendor] = (out.byVendor[vendor] || 0) + 1;
    if (r.generation === "recent") out.byGeneration.recent += 1;
    else if (r.generation === "ancien") out.byGeneration.ancien += 1;
    else out.byGeneration.inconnue += 1;
    if (r.generation === "ancien" && NETWORK_KINDS.has(kind)) out.oldNetwork.push(r);
    if (!r.vendor && !r.model) out.unidentified += 1;
  }
  return out;
}

/** Tri : équipements réseau d'abord (routeurs, pare-feu, switchs…), puis
 *  constructeur, puis nom/IP. */
export function sortEquipment(rows) {
  const rank = (k) => { const i = KIND_ORDER.indexOf(k || "inconnu"); return i < 0 ? KIND_ORDER.length : i; };
  return [...(rows || [])].sort((a, b) => {
    const d = rank(a.kind) - rank(b.kind);
    if (d) return d;
    const v = (a.vendor || "~").localeCompare(b.vendor || "~", "fr");
    if (v) return v;
    return (a.name || a.hostname || a.ip || a.mac || "").localeCompare(b.name || b.hostname || b.ip || b.mac || "", "fr", { numeric: true });
  });
}

/** Filtrage local (recherche libre + genre + génération + constructeur). */
export function filterEquipment(rows, { q = "", kind = "", generation = "", vendor = "", networkOnly = false } = {}) {
  const needle = q.trim().toLowerCase();
  return (rows || []).filter((r) => {
    if (kind && (r.kind || "inconnu") !== kind) return false;
    if (generation && (r.generation || "inconnue") !== generation) return false;
    if (vendor && (r.vendor || "?") !== vendor) return false;
    if (networkOnly && !NETWORK_KINDS.has(r.kind)) return false;
    if (!needle) return true;
    return [r.name, r.hostname, r.ip, r.mac, r.vendor, r.model, r.sys_name, r.serial, r.site].some((v) => v && String(v).toLowerCase().includes(needle));
  });
}

/** Nom d'affichage d'une fiche. */
export function displayName(row) {
  return row?.name || row?.hostname || row?.sys_name || row?.ip || row?.mac || `#${row?.id ?? "?"}`;
}

/** Ton du dernier relevé de profil (synthèse) : alarmes = mauvais,
 *  CPU/mémoire élevés = avertissement, sinon bon ; sans relevé = neutre. */
export function pollTone(lastPoll) {
  const s = lastPoll?.summary;
  if (!s) return { tone: "neutral", text: "—" };
  const parts = [];
  if (s.cpu_percent != null) parts.push(`CPU ${s.cpu_percent} %`);
  if (s.memory_percent != null) parts.push(`RAM ${s.memory_percent} %`);
  if (s.temperature_c != null) parts.push(`${s.temperature_c} °C`);
  const alarms = (s.alarms || []).length;
  if (alarms) parts.push(`${alarms} alarme(s)`);
  let tone = "good";
  if (alarms) tone = "bad";
  else if ((s.cpu_percent ?? 0) >= 85 || (s.memory_percent ?? 0) >= 90 || (s.temperature_c ?? 0) >= 70) tone = "warn";
  if (!parts.length) return { tone: (lastPoll.errors || []).length ? "warn" : "neutral", text: (lastPoll.errors || []).length ? "sans valeur" : "relevé vide" };
  return { tone, text: parts.join(" · ") };
}

/** Liens de topologie -> lignes lisibles {from, to, via, ports}. */
export function topologyRows(topology) {
  const nodes = new Map((topology?.nodes || []).map((n) => [n.id, n]));
  const label = (id) => { const n = nodes.get(id); return n ? (n.name || `#${id}`) : `#${id}`; };
  return (topology?.links || []).map((l) => ({
    from: label(l.from), fromId: l.from, to: label(l.to), toId: l.to, via: l.protocol.toUpperCase(),
    ports: [l.local_port, l.remote_port].filter(Boolean).join(" ↔ ") || "—",
  })).sort((a, b) => a.from.localeCompare(b.from, "fr") || a.to.localeCompare(b.to, "fr"));
}

/** Aperçu d'import Zenoss -> compte des fiches par genre identifié. */
export function previewSummary(preview) {
  const byKind = {};
  for (const p of preview || []) {
    const k = p.kind || "inconnu";
    byKind[k] = (byKind[k] || 0) + 1;
  }
  return Object.entries(byKind).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${kindLabel(k).toLowerCase()}`).join(", ");
}
