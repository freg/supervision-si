// Logique pure du méta-graphe (#448, phase 4) : disposition des entités
// par application (une colonne par application), tracé des arêtes,
// styles par genre de relation, résumés. Testée par tests/metaGraph.test.mjs.
export const NODE_W = 190;
export const ROW_H = 16;
export const HEAD_H = 26;
export const MAX_ROWS = 8;
export const COL_GAP = 120;
export const NODE_GAP = 18;
export const PAD = 20;
export const SIDE_MARGIN = 110; // place pour les arêtes internes à la dernière colonne (courbes à droite)

export const EDGE_STYLES = {
  fk: { stroke: "var(--accent, #2b5797)", dash: "", label: "relation (clé étrangère)" },
  equiv: { stroke: "var(--good, #2e8b57)", dash: "6 4", label: "même notion dans deux applications" },
  xref: { stroke: "var(--warning, #b7791f)", dash: "2 4", label: "référence inter-gestion probable" },
};

export function nodeHeight(node) {
  const rows = Math.min((node?.columns || []).length, MAX_ROWS) + ((node?.columns || []).length > MAX_ROWS ? 1 : 0);
  return HEAD_H + rows * ROW_H + 6;
}

// Colonnes par application, nœuds empilés ; retourne {width, height, nodes:{id:{x,y,w,h}}, columns:[{app,x}]}.
export function layoutGraph(graph) {
  const apps = graph?.apps || [];
  const nodes = graph?.nodes || [];
  const pos = {};
  const columns = [];
  let height = 0;
  apps.forEach((app, i) => {
    const x = PAD + i * (NODE_W + COL_GAP);
    columns.push({ app, x });
    let y = PAD + 24;
    for (const n of nodes.filter((n) => n.app === app)) {
      const h = nodeHeight(n);
      pos[n.id] = { x, y, w: NODE_W, h };
      y += h + NODE_GAP;
    }
    height = Math.max(height, y);
  });
  return { width: PAD * 2 + apps.length * NODE_W + Math.max(0, apps.length - 1) * COL_GAP + SIDE_MARGIN, height: height + PAD, nodes: pos, columns };
}

// Chemin SVG d'une arête entre deux nœuds : courbe entre les bords les plus proches.
export function edgePath(layout, edge) {
  const a = layout.nodes[edge.from];
  const b = layout.nodes[edge.to];
  if (!a || !b) return null;
  const sameColumn = a.x === b.x;
  if (sameColumn) {
    const x = a.x + a.w;
    const y1 = a.y + a.h / 2;
    const y2 = b.y + b.h / 2;
    const bulge = 40 + Math.abs(y2 - y1) / 8;
    return `M ${x} ${y1} C ${x + bulge} ${y1}, ${x + bulge} ${y2}, ${x} ${y2}`;
  }
  const leftToRight = a.x < b.x;
  const x1 = leftToRight ? a.x + a.w : a.x;
  const x2 = leftToRight ? b.x : b.x + b.w;
  const y1 = a.y + a.h / 2;
  const y2 = b.y + b.h / 2;
  const mx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
}

// Milieu d'une arête (pour l'étiquette).
export function edgeMidpoint(layout, edge) {
  const a = layout.nodes[edge.from];
  const b = layout.nodes[edge.to];
  if (!a || !b) return null;
  if (a.x === b.x) return { x: a.x + a.w + 30 + Math.abs((b.y + b.h / 2) - (a.y + a.h / 2)) / 10, y: (a.y + a.h / 2 + b.y + b.h / 2) / 2 };
  return { x: (Math.max(a.x, b.x) + Math.min(a.x + a.w, b.x + b.w)) / 2, y: (a.y + a.h / 2 + b.y + b.h / 2) / 2 };
}

// Étiquette courte : première paire de colonnes, et le nombre des autres.
export function edgeLabel(edge) {
  const cols = (edge?.columns || []).slice(0, 1).map((p) => `${p[0]} ↔ ${p[1]}`).join(", ");
  const more = (edge?.columns || []).length > 1 ? ` (+${edge.columns.length - 1})` : "";
  return cols + more;
}

export function graphSummary(graph) {
  if (!graph) return "";
  const c = graph.counts || {};
  return `${c.nodes || 0} entité(s), ${c.columns || 0} attribut(s), ${c.fk || 0} relation(s), ${c.equiv || 0} équivalence(s), ${c.xref || 0} référence(s) inter-gestion`;
}

export function proposalSummary(proposal) {
  if (!proposal) return "";
  const c = proposal.counts || {};
  return `${c.entities || 0} entité(s) cible(s) : ${c.merged || 0} fusionnée(s), ${c.kept || 0} reprise(s) telle(s) quelle(s) ; ${c.relations || 0} relation(s) ; ${c.conflicts || 0} conflit(s) de type, ${c.orphans || 0} attribut(s) propre(s)`;
}

// Relevé des champs : une ligne par attribut avec son équivalent éventuel dans les autres applications.
export function fieldInventory(graph) {
  if (!graph) return [];
  const equiv = {};
  for (const e of graph.edges || []) {
    if (e.kind !== "equiv") continue;
    for (const [ca, cb] of e.columns || []) {
      (equiv[`${e.from}.${ca}`] = equiv[`${e.from}.${ca}`] || []).push(`${e.to}.${cb}`);
      (equiv[`${e.to}.${cb}`] = equiv[`${e.to}.${cb}`] || []).push(`${e.from}.${ca}`);
    }
  }
  const rows = [];
  for (const n of graph.nodes || []) {
    for (const c of n.columns || []) {
      rows.push({ app: n.app, table: n.table, column: c.name, type: c.type, pk: !!c.pk, term: c.term, screens: c.screens || [], equivalents: equiv[`${n.id}.${c.name}`] || [] });
    }
  }
  return rows;
}
