// Lieux, positions et couches carto de Cortex (livraison #464) -- logique
// PURE, testée sous Node (hub/tests/cortexPlaces.test.mjs). La position
// d'une entité est mémorisée par cortex-api avec sa PROVENANCE ; ici on
// ne fait que présenter : couleur par provenance, légende des couches,
// regroupements, bornes de carte.

// Provenance -> ton et couleur (du plus sûr au moins sûr).
export const PROVENANCE = [
  ["déclarée", { color: "#1b7f3b", tone: "good", rank: 0, help: "coordonnées portées par l'appareil" }],
  ["validée", { color: "#1b7f3b", tone: "good", rank: 1, help: "correspondance validée par une personne" }],
  ["lieu déclaré", { color: "#2f6fd6", tone: "good", rank: 2, help: "lieu déclaré (site, bâtiment, salle) positionné" }],
  ["géolocalisation", { color: "#2f6fd6", tone: "good", rank: 3, help: "table des géolocalisations (nom ou IP)" }],
  ["résolue par le nom", { color: "#c58a00", tone: "warn", rank: 4, help: "correspondance automatique, à valider" }],
  ["propagée", { color: "#c58a00", tone: "warn", rank: 5, help: "prise sur l'équipement dont elle dépend" }],
  ["déduite du voisinage", { color: "#b45309", tone: "warn", rank: 6, help: "moyenne des voisins positionnés" }],
  ["repli", { color: "#9ca3af", tone: "bad", rank: 7, help: "position de repli : à traiter dans la file" }],
];
const PROV_MAP = new Map(PROVENANCE);
export function provenanceStyle(p) {
  return PROV_MAP.get(p) || { color: "#6b7280", tone: "neutral", rank: 9, help: p || "?" };
}

export const LAYERS = [
  { id: "positions", label: "Entités positionnées", help: "une pastille par entité, couleur = provenance", default: true },
  { id: "incidents", label: "Halos d'incidents", help: "rayon = sévérité × entités touchées", default: true },
  { id: "density", label: "Densité par lieu", help: "un cercle par lieu, rayon = nombre d'entités", default: false },
  { id: "unsupervised", label: "Zones sans supervision", help: "entités vues par la découverte seule (principe unsupervised)", default: true },
  { id: "dependencies", label: "Chemins de dépendance", help: "passerelle → hôte, borne → client, onduleur → site", default: false },
];
export function defaultLayers() {
  return new Set(LAYERS.filter((l) => l.default).map((l) => l.id));
}

export const SEV_COLOR = { critical: "#c92a2a", warning: "#e67700", info: "#1c7ed6" };

// Bornes [[latMin, lonMin], [latMax, lonMax]] des positions (ou null).
export function boundsOf(features) {
  let latMin = 90, latMax = -90, lonMin = 180, lonMax = -180, n = 0;
  for (const f of features || []) {
    if (f.geometry?.type !== "Point") continue;
    const [lon, lat] = f.geometry.coordinates;
    if (typeof lat !== "number" || typeof lon !== "number") continue;
    latMin = Math.min(latMin, lat); latMax = Math.max(latMax, lat); lonMin = Math.min(lonMin, lon); lonMax = Math.max(lonMax, lon); n += 1;
  }
  if (!n) return null;
  if (n === 1) return [[latMin - 0.01, lonMin - 0.01], [latMax + 0.01, lonMax + 0.01]];
  return [[latMin, lonMin], [latMax, lonMax]];
}

// Positions triées : d'abord les moins sûres (c'est là qu'il y a du travail),
// puis par nom ; filtre optionnel par provenance.
export function sortPositions(rows, provenance = null) {
  return (rows || []).filter((r) => !provenance || r.provenance === provenance)
    .sort((a, b) => provenanceStyle(b.provenance).rank - provenanceStyle(a.provenance).rank || (a.name || a.entity).localeCompare(b.name || b.entity));
}

// Compte par provenance dans l'ordre de l'échelle.
export function provenanceCounts(rows) {
  const c = new Map();
  for (const r of rows || []) c.set(r.provenance, (c.get(r.provenance) || 0) + 1);
  return PROVENANCE.map(([p]) => [p, c.get(p) || 0]).filter(([, n]) => n > 0);
}

// Phrase d'une chaîne de déduction.
export function chainText(p) {
  if (!p) return "";
  const chain = p.chain || [];
  if (!chain.length) return p.evidence || "";
  return chain.map((c) => `${c.why || c.via} ← ${c.from}${c.from_provenance ? ` [${c.from_provenance}]` : ""}${c.weight != null ? ` ×${c.weight}` : ""}`).join(" ; ");
}

// « Où aller » en une ligne : site › bâtiment › salle.
export function whereText(sheet) {
  const w = sheet?.where || [];
  if (!w.length) return sheet?.entity?.site ? `site ${sheet.entity.site} (non positionné)` : "lieu inconnu";
  return w.map((x) => x.name).join(" › ");
}

// ---- Étape 4 (#465) : règles, annonces, dérives -------------------------
export const RULE_STATE = { proposed: { label: "proposée", tone: "warn" }, confirmed: { label: "confirmée", tone: "good" }, rejected: { label: "rejetée", tone: "bad" } };
export const OUTCOME = { hit: { label: "juste", tone: "good" }, miss: { label: "fausse", tone: "bad" } };

// Phrase d'une règle : « B suit A dans n min (x fois sur n), délai 2–6 min ».
export function ruleText(r) {
  const mins = Math.max(1, Math.round((r.delay_s || 0) / 60));
  const span = r.delay_min_s != null && r.delay_max_s != null && r.delay_max_s !== r.delay_min_s ? `, entre ${Math.round(r.delay_min_s / 60)} et ${Math.round(r.delay_max_s / 60)} min` : "";
  return `${r.b_text || r.b} suit ${r.a_text || r.a} dans ${mins} min (${r.count} fois sur ${r.support_a}${span})`;
}

// Minutes restantes avant l'échéance d'une annonce (négatif = dépassée).
export function minutesLeft(p, now = Date.now()) {
  const t = Date.parse(p.expected_at);
  if (Number.isNaN(t)) return null;
  return Math.round((t - now) / 60000);
}

// Bilan des annonces : {pending, hits, misses, accuracy}
export function predictionStats(preds) {
  const s = { pending: 0, hits: 0, misses: 0, accuracy: null };
  for (const p of preds || []) { if (!p.outcome) s.pending += 1; else if (p.outcome === "hit") s.hits += 1; else s.misses += 1; }
  if (s.hits + s.misses) s.accuracy = s.hits / (s.hits + s.misses);
  return s;
}

// Mini-courbe SVG (sparkline) : points [{at, value}] -> chemin normalisé dans w×h.
export function sparkPath(points, w = 120, h = 28) {
  const vals = (points || []).map((p) => p.value).filter((v) => typeof v === "number");
  if (vals.length < 2) return "";
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  return vals.map((v, i) => `${i === 0 ? "M" : "L"}${((i / (vals.length - 1)) * (w - 2) + 1).toFixed(1)},${(h - 1 - ((v - min) / span) * (h - 2)).toFixed(1)}`).join(" ");
}

// ---- Étape 5 (#466) : politiques, silences, KPI ----------------------------
export const PRIORITY_TONE = { haute: "bad", normale: "warn", basse: "neutral" };
export const NOTIF_KIND = { open: "ouverture", escalation: "escalade", resolved: "résolu" };

export function humanizeS(s) {
  if (s == null) return "—";
  s = Math.round(s);
  if (s < 90) return `${s} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  if (s < 2 * 86400) return `${(s / 3600).toFixed(1)} h`;
  return `${(s / 86400).toFixed(1)} j`;
}

// Résumé lisible du critère d'une politique.
export function matchText(m) {
  const parts = [];
  if (m?.roles?.length) parts.push(`rôle ${m.roles.join(" / ")}`);
  if (m?.sites?.length) parts.push(`site ${m.sites.join(" / ")}`);
  if (m?.kinds?.length) parts.push(`type ${m.kinds.join(" / ")}`);
  if (m?.entities?.length) parts.push(`${m.entities.length} entité(s) nommée(s)`);
  parts.push(`sévérité ≥ ${m?.severity_min || "info"}`);
  if (m?.min_confidence) parts.push(`confiance ≥ ${Math.round(m.min_confidence * 100)} %`);
  return parts.join(", ");
}

// Formulaire -> objet politique (listes séparées par des virgules).
export function policyFromForm(f) {
  const list = (v) => String(v || "").split(",").map((x) => x.trim()).filter(Boolean);
  return { id: (f.id || "").trim(), name: f.name || f.id, order: Number(f.order) || 500,
    match: { roles: list(f.roles), sites: list(f.sites), kinds: list(f.kinds), entities: list(f.entities), severity_min: f.severity_min || "warning", min_confidence: Number(f.min_confidence) || 0 },
    priority: f.priority || "normale", notify: f.notify !== false, channels: list(f.channels), escalate_after_s: Number(f.escalate_after_s) || null,
    escalation_channels: list(f.escalation_channels), notify_resolved: !!f.notify_resolved, enabled: f.enabled !== false };
}
export function formFromPolicy(p) {
  const m = p?.match || {};
  return { id: p?.id || "", name: p?.name || "", order: p?.order ?? 500, roles: (m.roles || []).join(", "), sites: (m.sites || []).join(", "), kinds: (m.kinds || []).join(", "),
    entities: (m.entities || []).join(", "), severity_min: m.severity_min || "warning", min_confidence: m.min_confidence || 0, priority: p?.priority || "normale",
    notify: p?.notify !== false, channels: (p?.channels || []).join(", "), escalate_after_s: p?.escalate_after_s || "", escalation_channels: (p?.escalation_channels || []).join(", "),
    notify_resolved: !!p?.notify_resolved, enabled: p?.enabled !== false };
}

// Lignes du tableau MTTA/MTTR : [{label, n, mean, median, max}] depuis {clé: {n, mean_s, ...}}.
export function kpiRows(byKey) {
  return Object.entries(byKey || {}).filter(([, v]) => v).map(([label, v]) => ({ label, n: v.n, mean: humanizeS(v.mean_s), median: humanizeS(v.median_s), max: humanizeS(v.max_s) }))
    .sort((a, b) => b.n - a.n);
}

// Semaine par semaine -> barres normalisées [{week, opened, closed, critical, h}] (h ∈ [0,1]).
export function weeklyBars(weekly) {
  const max = Math.max(1, ...(weekly || []).map((w) => w.opened));
  return (weekly || []).map((w) => ({ ...w, h: w.opened / max }));
}
