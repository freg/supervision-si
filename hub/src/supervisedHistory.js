// Logique PURE des outils redistribués dans la tuile Supervision SI
// (livraison #424, backlog 64 point 4) -- aucun React, testée sous Node
// (hub/tests/supervisedHistory.test.mjs). Les outils de l'ancienne maquette
// (timeline, mosaïque pixel-grid, calendrier de densité, arbre radial,
// corbeille de sélection) reviennent ici mais NOURRIS PAR LES TUILES (relevés
// netprobe, relevés UPS, risques des agents) au lieu de JSON versés à la
// main : même idée, données vivantes.

import { STATE_ORDER } from "./supervisedItems.js";

export const HISTORY_WINDOWS = [
  { id: "6h", label: "6 h", seconds: 6 * 3600, bucketSeconds: 900 },
  { id: "24h", label: "24 h", seconds: 24 * 3600, bucketSeconds: 3600 },
  { id: "7d", label: "7 j", seconds: 7 * 86400, bucketSeconds: 6 * 3600 },
  { id: "30d", label: "30 j", seconds: 30 * 86400, bucketSeconds: 86400 },
];

export function windowById(id) {
  return HISTORY_WINDOWS.find((w) => w.id === id) || HISTORY_WINDOWS[1];
}

// ---- Normalisation des historiques en points {at (ms), state, text} -------

export function pointsFromNetprobeSamples(samples) {
  return (samples || []).map((s) => ({
    at: Date.parse(s.sampled_at), text: s.success ? (s.latency_ms != null ? `${Math.round(s.latency_ms)} ms` : "répond") : (s.error || "injoignable"),
    state: !s.success ? "critical" : (s.packet_loss_percent || 0) > 0 ? "warning" : "ok",
  })).filter((p) => Number.isFinite(p.at)).sort((a, b) => a.at - b.at);
}

export function pointsFromUpsReadings(readings) {
  return (readings || []).map((r) => ({
    at: Date.parse(r.polled_at), text: r.ok ? (r.state || "relevé") : (r.error || "échec"),
    state: !r.ok ? "critical" : r.state === "alarm" ? "critical" : r.state === "ok" ? "ok" : "unknown",
  })).filter((p) => Number.isFinite(p.at)).sort((a, b) => a.at - b.at);
}

export function pointsFromAgentRisks(measurements) {
  return (measurements || []).map((m) => {
    const st = m.data?.summary?.state;
    return { at: Date.parse(m.at), state: st === "critical" ? "critical" : st === "warning" ? "warning" : st === "ok" || st === "info" ? "ok" : "unknown",
      text: st ? `risques : ${st}` : "—" };
  }).filter((p) => Number.isFinite(p.at)).sort((a, b) => a.at - b.at);
}

// ---- Timeline : segments d'état contigus ----------------------------------

// Chaque point vaut jusqu'au suivant (ou jusqu'à `endMs`) ; un trou plus long
// que `gapMs` devient un segment « unknown » (pas de relevé).
export function stateSegments(points, { startMs, endMs, gapMs }) {
  const pts = (points || []).filter((p) => p.at <= endMs).sort((a, b) => a.at - b.at);
  const out = [];
  const push = (s, e, state, text) => { if (e > s && e > startMs) out.push({ start: Math.max(s, startMs), end: e, state, text }); };
  if (!pts.length) { push(startMs, endMs, "unknown", "aucun relevé"); return out; }
  if (pts[0].at > startMs) push(startMs, pts[0].at, "unknown", "aucun relevé");
  for (let i = 0; i < pts.length; i += 1) {
    const p = pts[i], next = pts[i + 1];
    const until = next ? next.at : endMs;
    if (gapMs && until - p.at > gapMs) {
      push(p.at, p.at + gapMs, p.state, p.text);
      push(p.at + gapMs, until, "unknown", "aucun relevé");
    } else push(p.at, until, p.state, p.text);
  }
  // fusion des segments contigus de même état
  const merged = [];
  for (const s of out) {
    const last = merged[merged.length - 1];
    if (last && last.state === s.state && last.end === s.start) last.end = s.end; else merged.push({ ...s });
  }
  return merged;
}

// ---- Mosaïque (esprit pixel-grid) : matrice items × créneaux ---------------

export function worstState(states) {
  let w = null;
  for (const s of states) if (s && (w == null || STATE_ORDER[s] < STATE_ORDER[w])) w = s;
  return w;
}

export function bucketize(points, { startMs, endMs, bucketMs }) {
  const n = Math.max(1, Math.ceil((endMs - startMs) / bucketMs));
  const cells = new Array(n).fill(null).map((_, i) => ({ start: startMs + i * bucketMs, end: startMs + (i + 1) * bucketMs, states: [], count: 0 }));
  for (const p of points || []) {
    if (p.at < startMs || p.at >= endMs) continue;
    const c = cells[Math.min(n - 1, Math.floor((p.at - startMs) / bucketMs))];
    c.states.push(p.state); c.count += 1;
  }
  return cells.map((c) => ({ start: c.start, end: c.end, count: c.count, state: c.count ? worstState(c.states) : null }));
}

// ---- Calendrier de densité : événements « pas ok » par jour ---------------

export function calendarDays(pointsByItem, { startMs, endMs }) {
  const days = new Map();
  for (let t = startOfDay(startMs); t < endMs; t += 86400000) days.set(dayKey(t), { day: dayKey(t), start: t, events: 0, items: new Set() });
  for (const [id, pts] of Object.entries(pointsByItem || {})) {
    for (const p of pts) {
      if (p.at < startMs || p.at >= endMs || p.state === "ok" || p.state === "unknown") continue;
      const d = days.get(dayKey(p.at));
      if (d) { d.events += 1; d.items.add(id); }
    }
  }
  return [...days.values()].map((d) => ({ day: d.day, start: d.start, events: d.events, items: d.items.size }));
}

export function startOfDay(ms) { const d = new Date(ms); d.setHours(0, 0, 0, 0); return d.getTime(); }
export function dayKey(ms) { const d = new Date(ms); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }

// Seuils de couleur paramétrables (vert = 0, rouge >= 1 par défaut, comme
// la vue calendrier d'origine) ; `thresholds` = {warn, bad}.
export function dayTone(events, thresholds = { warn: 1, bad: 3 }) {
  if (events >= thresholds.bad) return "bad";
  if (events >= thresholds.warn) return "warn";
  return "good";
}

// ---- Arbre radial : site → type → équipement, sans dépendance ----------------

export function buildHierarchy(items) {
  const root = { name: "Supervisés", children: new Map(), kind: "root" };
  for (const it of items || []) {
    const site = it.site || "sans site";
    if (!root.children.has(site)) root.children.set(site, { name: site, kind: "site", children: new Map() });
    const s = root.children.get(site);
    if (!s.children.has(it.type)) s.children.set(it.type, { name: it.type, kind: "type", children: new Map() });
    s.children.get(it.type).children.set(it.identity, { name: it.name, kind: "item", state: it.state, identity: it.identity, children: new Map() });
  }
  // sites réels d'abord, « sans site » en dernier
  const toArr = (n) => ({ ...n, children: [...n.children.values()].map(toArr).sort((a, b) => (a.name === "sans site") - (b.name === "sans site") || a.name.localeCompare(b.name)) });
  return toArr(root);
}

// Disposition radiale : feuilles réparties uniformément en angle, chaque
// nœud interne au centre angulaire de ses feuilles, rayon = profondeur.
export function radialLayout(tree, { radius = 200, depthRadius = null } = {}) {
  const leaves = [];
  const count = (n) => { if (!n.children.length) { leaves.push(n); return 1; } n.leafCount = n.children.reduce((a, c) => a + count(c), 0); return n.leafCount; };
  count(tree);
  const maxDepth = (n, d = 0) => (n.children.length ? Math.max(...n.children.map((c) => maxDepth(c, d + 1))) : d);
  const depth = Math.max(1, maxDepth(tree));
  const step = depthRadius || radius / depth;
  const nodes = [], links = [];
  let leafIdx = 0;
  const place = (n, d, parent) => {
    let angle;
    if (!n.children.length) { angle = (leafIdx / Math.max(1, leaves.length)) * 2 * Math.PI; leafIdx += 1; }
    const childNodes = n.children.map((c) => place(c, d + 1, n));
    if (n.children.length) angle = childNodes.reduce((a, c) => a + c.angle, 0) / childNodes.length;
    // correction : si les enfants enjambent 0/2π, la moyenne serait fausse
    if (n.children.length > 1 && Math.max(...childNodes.map((c) => c.angle)) - Math.min(...childNodes.map((c) => c.angle)) > Math.PI) {
      angle = Math.atan2(childNodes.reduce((a, c) => a + Math.sin(c.angle), 0), childNodes.reduce((a, c) => a + Math.cos(c.angle), 0));
      if (angle < 0) angle += 2 * Math.PI;
    }
    const r = d * step;
    const node = { name: n.name, kind: n.kind, state: n.state, identity: n.identity, depth: d, angle, r, x: r * Math.cos(angle - Math.PI / 2), y: r * Math.sin(angle - Math.PI / 2), leafCount: n.leafCount || 1 };
    nodes.push(node);
    for (const c of childNodes) links.push({ source: node, target: c });
    return node;
  };
  place(tree, 0, null);
  return { nodes, links, radius: depth * step };
}

// ---- Corbeille de sélection ---------------------------------------------------

// Sélection courante = identités cochées ; vide = les priorisés, sinon les
// N premiers visibles (les outils ne chargent jamais tout l'historique).
export function effectiveSelection(selectedIds, visible, priorities, limit = 12) {
  const set = new Set(selectedIds || []);
  const visibleIds = (visible || []).map((i) => i.identity);
  const kept = visibleIds.filter((id) => set.has(id));
  if (kept.length) return kept.slice(0, limit);
  const prio = visibleIds.filter((id) => (priorities || {})[id] != null);
  if (prio.length) return prio.slice(0, limit);
  return visibleIds.slice(0, limit);
}

export function toggleSelection(selectedIds, identity) {
  const set = new Set(selectedIds || []);
  if (set.has(identity)) set.delete(identity); else set.add(identity);
  return [...set];
}
