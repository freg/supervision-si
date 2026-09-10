// Logique PURE du graphe d'évolution des versions d'un document (livraison
// #460) -- aucun React, testée sous Node (hub/tests/versionGraph.test.mjs).
// Le graphe vient de ged-api (/documents/<id>/graph : nœuds = versions
// avec parent, branche, statut ; voies calculées côté API). Ici : la mise
// en page façon « git log --graph » (colonne = voie de la branche, ligne =
// version, chronologique de haut en bas), les chemins d'arêtes et les
// libellés / couleurs de statut.

export const STATUS = {
  draft: { label: "brouillon", color: "#8a8f98" },
  official: { label: "officielle", color: "#2f9e5b" },
  superseded: { label: "remplacée", color: "#d69a2b" },
  archived: { label: "archivée", color: "#4c6ef5" },
};

export const ROW_H = 44;
export const LANE_W = 36;
export const LEFT = 24;
export const TOP = 22;

export function layout(graph) {
  const nodes = (graph?.nodes || []).slice().sort((a, b) => a.version - b.version);
  const lanes = graph?.lanes || {};
  const maxLane = Math.max(0, ...nodes.map((n) => Number(lanes[n.version] ?? lanes[String(n.version)] ?? 0)));
  const pos = {};
  nodes.forEach((n, i) => {
    const lane = Number(lanes[n.version] ?? lanes[String(n.version)] ?? 0);
    pos[n.version] = { x: LEFT + lane * LANE_W, y: TOP + i * ROW_H, lane, row: i };
  });
  const edges = (graph?.edges || []).filter((e) => pos[e.from] && pos[e.to]).map((e) => {
    const a = pos[e.from], b = pos[e.to];
    // même voie : trait droit ; changement de voie : courbe qui part de la voie du parent
    const d = a.x === b.x ? `M${a.x},${a.y} L${b.x},${b.y}` : `M${a.x},${a.y} C${a.x},${(a.y + b.y) / 2} ${b.x},${(a.y + b.y) / 2} ${b.x},${b.y}`;
    return { ...e, d, fork: a.x !== b.x };
  });
  return { nodes: nodes.map((n) => ({ ...n, ...pos[n.version] })), edges, width: LEFT + (maxLane + 1) * LANE_W + 12, height: TOP + Math.max(1, nodes.length) * ROW_H, maxLane };
}

// Résumé lisible d'un nœud (ligne de droite du graphe).
export function describeNode(n) {
  const st = STATUS[n.status] || STATUS.draft;
  const bits = [`v${n.version}`, st.label];
  if (n.branch && n.branch !== "principale") bits.push(`branche ${n.branch}`);
  if (n.parent != null && n.parent !== n.version - 1) bits.push(`dérivée de v${n.parent}`);
  if (n.author) bits.push(n.author);
  if (n.archived) bits.push("archive immuable");
  return bits.join(" · ");
}

// Actions possibles sur un nœud selon son statut et l'état de sortie.
export function nodeActions(n, graph, user) {
  const out = [];
  if (n.status !== "archived") {
    if (n.status !== "official") out.push("official");
    out.push("archive");
  }
  const co = graph?.checkout;
  if (!co) out.push("checkout");
  else if (co.user === user) out.push("checkin");
  return out;
}

// Texte de l'état de sortie du document.
export function checkoutText(co, user) {
  if (!co) return "disponible (personne ne l'a sorti)";
  return `sorti par ${co.user}${co.version_number ? ` (à partir de v${co.version_number})` : ""} depuis ${co.checked_out_at}${co.user === user ? " — c'est vous" : " — lecture seule pour les autres"}`;
}
