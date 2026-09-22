// Synoptique en arbre façon Nebula (livraison #555) -- logique PURE, testée
// sous Node (hub/tests/nebulaTree.test.mjs). Entrée : la réponse de
// /sites/<id>/topology (nœuds avec `parent`, clients par nœud). Sortie : des
// positions -- chaque parent centré au-dessus de ses enfants, les clients
// d'un appareil regroupés en une pastille « n clients » (dépliable) pour
// que la largeur reste lisible ; l'ordre sous un parent : commutateurs,
// bornes, autres, puis nom.

const ORDER = { gateway: 0, switch: 1, ap: 2, other: 3 };
export const KIND_LABEL = { gateway: "Passerelle", switch: "Commutateur", ap: "Borne Wi-Fi", other: "Équipement" };

/** Enfants par parent, triés ; la racine (parent null) en premier. */
export function childrenMap(nodes) {
  const kids = new Map();
  for (const n of nodes) {
    const p = n.parent || "";
    if (!kids.has(p)) kids.set(p, []);
    kids.get(p).push(n);
  }
  for (const list of kids.values()) list.sort((a, b) => (ORDER[a.kind] - ORDER[b.kind]) || (b.clients?.length || 0) - (a.clients?.length || 0) || a.name.localeCompare(b.name, "fr"));
  return kids;
}

/** Disposition. `expanded` = ensemble des ids dont les clients sont dépliés
 *  (chaque client devient une feuille), sinon une seule feuille « n clients ».
 *  Retourne { positions: Map<id, {x, y, depth}>, clientPositions: Map<key, {x, y, parent}>,
 *  groups: Map<parentId, {x, y, count}>, width, height }. */
export function treeLayout(tree, { nodeWidth = 150, gap = 16, rowHeight = 110, clientWidth = 74, expanded = new Set() } = {}) {
  const nodes = tree.nodes || [];
  const kids = childrenMap(nodes);
  const roots = kids.get("") || [];
  const positions = new Map(), clientPositions = new Map(), groups = new Map();
  const leafW = (n) => {
    const c = n.clients || [];
    if (!c.length) return 0;
    return expanded.has(n.id) ? c.length * (clientWidth + 8) : clientWidth + 8;
  };
  // largeur de sous-arbre
  const width = new Map();
  const measure = (n) => {
    const ch = kids.get(n.id) || [];
    let w = ch.reduce((s, c) => s + measure(c), 0) + leafW(n);
    w = Math.max(w, nodeWidth + gap);
    width.set(n.id, w);
    return w;
  };
  let total = roots.reduce((s, r) => s + measure(r), 0);
  let maxDepth = 0;
  const place = (n, x0, depth) => {
    const w = width.get(n.id);
    positions.set(n.id, { x: Math.round(x0 + w / 2), y: 50 + depth * rowHeight, depth });
    maxDepth = Math.max(maxDepth, depth);
    let x = x0;
    const c = n.clients || [];
    const ch = kids.get(n.id) || [];
    // les clients de l'appareil au MILIEU de ses enfants (lignes courtes), en
    // une pastille ou dépliés
    const mid = Math.ceil(ch.length / 2);
    const placeClients = () => {
      if (!c.length) return;
      const cy = 50 + (depth + 1) * rowHeight;
      if (expanded.has(n.id)) {
        c.forEach((cl, i) => { clientPositions.set(`${n.id}|${cl.mac || i}`, { x: Math.round(x + (clientWidth + 8) * i + (clientWidth + 8) / 2), y: cy, parent: n.id, client: cl }); });
        x += c.length * (clientWidth + 8);
      } else {
        groups.set(n.id, { x: Math.round(x + (clientWidth + 8) / 2), y: cy, count: c.length, online: c.filter((k) => k.status === "online").length });
        x += clientWidth + 8;
      }
      maxDepth = Math.max(maxDepth, depth + 1);
    };
    ch.forEach((child, i) => {
      if (i === mid) placeClients();
      place(child, x, depth + 1); x += width.get(child.id);
    });
    if (ch.length <= mid) placeClients();
  };
  let x = 20;
  for (const r of roots) { place(r, x, 0); x += width.get(r.id); }
  return { positions, clientPositions, groups, width: Math.max(400, total + 40), height: 50 + (maxDepth + 1) * rowHeight };
}

/** Arêtes parent → enfant à dessiner, avec ton : rouge si VLAN manquants,
 *  pointillé si nue, grise si l'enfant n'est pas relié (rattaché d'office). */
export function treeEdges(tree) {
  const out = [];
  for (const n of tree.nodes || []) {
    if (!n.parent) continue;
    const missing = ((n.link && n.link.missing_on_a) || []).length + ((n.link && n.link.missing_on_b) || []).length;
    out.push({ id: `${n.parent}>${n.id}`, a: n.parent, b: n.id, a_port: n.parent_port, b_port: n.uplink_port,
               tone: n.unlinked ? "unlinked" : missing ? "bad" : n.link && n.link.bare ? "muted" : "ok", unlinked: !!n.unlinked });
  }
  return out;
}

/** Résumé chiffré pour l'en-tête. */
export function treeSummary(tree) {
  const nodes = tree.nodes || [];
  const by = (k) => nodes.filter((n) => n.kind === k).length;
  const clients = nodes.reduce((s, n) => s + (n.clients?.length || 0), 0);
  const online = nodes.reduce((s, n) => s + (n.clients || []).filter((c) => c.status === "online").length, 0);
  return { gateways: by("gateway"), switches: by("switch"), aps: by("ap"), clients, clientsOnline: online, loose: (tree.loose_clients || []).length,
           offline: nodes.filter((n) => n.status === "offline").length, unlinked: nodes.filter((n) => n.unlinked).length };
}
