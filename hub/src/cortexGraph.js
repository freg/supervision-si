// Mise en page PURE du graphe d'architecture de Cortex (livraison #463) --
// testée sous Node (hub/tests/cortexGraph.test.mjs). Disposition par
// couches et par site : en haut les équipements amont (passerelles,
// routeurs, bornes, switches, onduleurs), au milieu les hôtes supervisés,
// en bas le reste (pairs, équipements sans rôle) ; une colonne par site.
export const UPSTREAM_ROLES = new Set(["passerelle", "routeur", "pare-feu", "switch", "borne-wifi", "equipement-reseau", "onduleur", "dns", "dhcp"]);
export const COL_W = 220, ROW_H = 34, PAD = 16, LAYER_GAP = 18, CHAR_W = 6.4, LABEL_EXTRA = 44;

// Étiquette affichée d'un nœud (nom + rôle) -- sert aussi à dimensionner
// la colonne pour que rien ne déborde sur le site voisin.
export function nodeLabel(node) {
  return `${node.name || node.key}${node.role ? " · " + node.role : ""}`;
}
export function columnWidth(nodes) {
  const longest = Math.max(0, ...nodes.map((n) => nodeLabel(n).length));
  return Math.max(COL_W, Math.ceil(longest * CHAR_W) + LABEL_EXTRA);
}

export function layerOf(node) {
  if (node.kind === "passerelle" || node.kind === "onduleur" || node.kind === "equipement-reseau") return 0;
  if (node.role && UPSTREAM_ROLES.has(node.role)) return 0;
  if (node.kind === "hote" || node.kind === "cible") return 1;
  return 2;
}

export function layoutGraph(graph, { maxNodes = 300 } = {}) {
  const nodes = (graph?.nodes || []).slice(0, maxNodes);
  const colW = columnWidth(nodes);
  const sites = [...new Set(nodes.map((n) => n.site || "(sans site)"))].sort((a, b) => (a === "(sans site)") - (b === "(sans site)") || a.localeCompare(b));
  const colOf = new Map(sites.map((s, i) => [s, i]));
  const byCell = new Map();
  for (const n of nodes) {
    const key = `${n.site || "(sans site)"}|${layerOf(n)}`;
    byCell.set(key, (byCell.get(key) || []).concat(n));
  }
  const layerHeight = [0, 1, 2].map((l) => Math.max(1, ...sites.map((s) => (byCell.get(`${s}|${l}`) || []).length)));
  const layerTop = [PAD, PAD + layerHeight[0] * ROW_H + LAYER_GAP, PAD + (layerHeight[0] + layerHeight[1]) * ROW_H + 2 * LAYER_GAP];
  const pos = {};
  for (const [key, list] of byCell) {
    const [site, l] = key.split("|");
    list.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    list.forEach((n, i) => { pos[n.key] = { x: PAD + colOf.get(site) * colW + 12, y: layerTop[Number(l)] + i * ROW_H + 10, layer: Number(l), col: colOf.get(site) }; });
  }
  const edges = (graph?.edges || []).filter((e) => pos[e.a] && pos[e.b]).map((e) => ({ ...e, x1: pos[e.a].x, y1: pos[e.a].y, x2: pos[e.b].x, y2: pos[e.b].y }));
  return { nodes: nodes.map((n) => ({ ...n, ...pos[n.key] })), edges, sites, width: PAD * 2 + Math.max(1, sites.length) * colW, colW,
    height: layerTop[2] + layerHeight[2] * ROW_H + PAD, layerTop, truncated: (graph?.nodes || []).length > maxNodes };
}

export const EDGE_STYLE = { gateway_of: { color: "#c2410c", width: 2 }, uplink: { color: "#c2410c", width: 1.6 }, powers_site: { color: "#7b61ff", width: 1.5 }, flow: { color: "#6c8ebf", width: 1 }, talks_to: { color: "#6c8ebf", width: 1 }, neighbor: { color: "#bbb", width: 1 }, watches: { color: "#2f9e5b", width: 1 } };
export const KIND_ICON = { passerelle: "🛰", onduleur: "🔋", "equipement-reseau": "🕸", hote: "🖥", cible: "🎯", pair: "•", equipement: "▫" };

// Résumé lisible d'un changement.
export const CHANGE_LABEL = { "entity-new": "nouvelle entité", "entity-gone": "entité disparue", "relation-new": "nouvelle relation", "relation-gone": "relation disparue",
  "role-changed": "rôle changé", "role-new": "rôle attribué", "site-changed": "site changé", "gateway-changed": "passerelle changée",
  "position-found": "position trouvée", "position-changed": "provenance de position changée", "position-moved": "position déplacée" };
export function changeTone(kind) {
  if (kind === "entity-gone" || kind === "relation-gone" || kind === "gateway-changed") return "warn";
  if (kind === "entity-new" || kind === "relation-new" || kind === "position-found") return "good";
  return "neutral";
}
// Routes regroupées par hôte.
export function routesByHost(routes) {
  const m = new Map();
  for (const r of routes || []) {
    const cur = m.get(r.host) || { host: r.host, name: r.host_name || r.host, default: null, attached: [], reachable: [] };
    if (r.kind === "default") cur.default = r; else if (r.kind === "attached") cur.attached.push(r.destination); else cur.reachable.push(r);
    m.set(r.host, cur);
  }
  return [...m.values()].sort((a, b) => a.name.localeCompare(b.name));
}
