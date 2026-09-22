// Synoptique en arbre façon Nebula (livraisons #555/#558) -- logique PURE,
// testée sous Node (hub/tests/nebulaTree.test.mjs). Entrée : la réponse de
// /sites/<id>/topology (nœuds avec `parent`, clients par nœud). Sortie : des
// positions -- chaque parent centré sur ses enfants (Reingold-Tilford
// simplifié), les clients d'un appareil regroupés en une pastille
// « n clients » (dépliable). Deux orientations (#558, inspirées des
// exemples d3 « tree » / « cluster ») : verticale ÉTAGÉE (les frères sont
// décalés sur `stagger` sous-rangées pour que chaque étiquette s'affiche en
// entier sans chevaucher sa voisine) et horizontale (profondeur en colonnes,
// une ligne par feuille : lisible quel que soit le nombre de bornes).

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

/** Largeur d'étiquette estimée (px) pour un nom et un sous-titre. */
export function labelWidth(node, { charWidth = 6.6, min = 120, max = 280, padding = 34 } = {}) {
  const sub = `${node.model || KIND_LABEL[node.kind] || ""}${node.clients?.length ? ` · ${node.clients.length}` : ""}`;
  const chars = Math.max((node.name || "").length * 1.08, sub.length * 0.95);
  return Math.max(min, Math.min(max, Math.round(chars * charWidth + padding)));
}

/** Disposition. Options : orientation "vertical" | "horizontal", stagger (sous-rangées
 *  en vertical, 1 = aucune), nodeHeight, rowHeight (vertical) / colWidth (horizontal),
 *  clientWidth, expanded (ids dépliés). Retourne { positions: Map<id, {x, y, depth, tier}>,
 *  clientPositions, groups, width, height, nodeWidth: Map<id, px>, orientation }. */
export function treeLayout(tree, opts = {}) {
  const { orientation = "vertical", stagger = 3, nodeHeight = 46, rowHeight = 100, colWidth = 300, clientWidth = 74, clientHeight = 30, gap = 14, expanded = new Set() } = opts;
  const nodes = tree.nodes || [];
  const kids = childrenMap(nodes);
  const roots = kids.get("") || [];
  const positions = new Map(), clientPositions = new Map(), groups = new Map(), widthOf = new Map();
  for (const n of nodes) widthOf.set(n.id, labelWidth(n));
  const vertical = orientation === "vertical";
  const maxLabel = Math.max(120, ...nodes.map((n) => widthOf.get(n.id)));
  // "encombrement" d'une feuille dans l'axe de largeur : en vertical étagé, un
  // slot = (largeur max + gap) / stagger ; en horizontal, un slot = hauteur de boîte + gap
  const slotDev = vertical ? Math.ceil((maxLabel + gap) / stagger) : nodeHeight + gap;
  const slotCli = vertical ? Math.ceil((clientWidth + 8) / Math.min(stagger, 3)) : clientHeight + 6;
  // une pastille « n clients » occupe un slot d'appareil en vertical : sinon elle
  // resserre la rangée et trois étages ne suffisent plus à séparer les étiquettes
  const slotGroup = vertical ? slotDev : slotCli;
  const leafW = (n) => {
    const c = n.clients || [];
    if (!c.length) return 0;
    return expanded.has(n.id) ? c.length * slotCli : slotGroup;
  };
  const width = new Map();
  const measure = (n) => {
    const ch = kids.get(n.id) || [];
    let w = ch.reduce((s, c) => s + measure(c), 0) + leafW(n);
    w = Math.max(w, slotDev);
    width.set(n.id, w);
    return w;
  };
  const total = roots.reduce((s, r) => s + measure(r), 0);
  let maxDepth = 0;
  // profondeur -> coordonnée principale ; en vertical étagé la rangée fait
  // stagger sous-rangées (nodeHeight + 8 chacune)
  const subRow = nodeHeight + 8;
  const rowSpan = vertical ? Math.max(rowHeight, stagger * subRow + 40) : colWidth;
  const depthCoord = (depth) => 40 + depth * rowSpan;
  const place = (n, b0, depth, index) => {
    const w = width.get(n.id);
    const tier = vertical ? index % stagger : 0;
    const center = Math.round(b0 + w / 2);
    const main = depthCoord(depth) + (vertical ? tier * subRow : 0);
    positions.set(n.id, vertical ? { x: center, y: main + nodeHeight / 2, depth, tier } : { x: main + widthOf.get(n.id) / 2, y: center, depth, tier });
    maxDepth = Math.max(maxDepth, depth);
    let b = b0;
    const c = n.clients || [];
    const ch = kids.get(n.id) || [];
    const mid = Math.ceil(ch.length / 2);
    let childIndex = 0;
    const placeClients = () => {
      if (!c.length) return;
      const cmain = depthCoord(depth + 1);
      if (expanded.has(n.id)) {
        c.forEach((cl, i) => {
          const tierC = vertical ? i % Math.min(stagger, 3) : 0;
          const cc = Math.round(b + slotCli * i + slotCli / 2);
          const m = cmain + (vertical ? tierC * (clientHeight + 6) : 0);
          clientPositions.set(`${n.id}|${cl.mac || i}`, vertical ? { x: cc, y: m + clientHeight / 2, parent: n.id, client: cl } : { x: m + clientWidth / 2, y: cc, parent: n.id, client: cl });
        });
        b += c.length * slotCli;
      } else {
        const cc = Math.round(b + slotGroup / 2);
        const tierC = vertical ? childIndex % stagger : 0;
        const m = cmain + (vertical ? tierC * subRow : 0);
        groups.set(n.id, vertical ? { x: cc, y: m + clientHeight / 2, count: c.length, online: c.filter((k) => k.status === "online").length } : { x: m + clientWidth / 2, y: cc, count: c.length, online: c.filter((k) => k.status === "online").length });
        b += slotGroup;
        childIndex++;
      }
      maxDepth = Math.max(maxDepth, depth + 1);
    };
    ch.forEach((child, i) => {
      if (i === mid) placeClients();
      place(child, b, depth + 1, childIndex++);
      b += width.get(child.id);
    });
    if (ch.length <= mid) placeClients();
  };
  const margin = vertical ? Math.ceil(maxLabel / 2) + 10 : nodeHeight;  // une étiquette centrée sur le premier slot déborde de sa moitié
  let b = margin;
  roots.forEach((r, i) => { place(r, b, 0, i); b += width.get(r.id); });
  if (vertical && stagger > 1) restagger();
  // Étages par rangée (#558) : tous les éléments d'une même profondeur (nœuds,
  // pastilles, clients dépliés) triés par x ; chacun prend le premier étage
  // où il ne chevauche pas le dernier élément posé (largeur réelle + gap),
  // sinon l'étage suivant dans le cycle. Indépendant des sous-arbres.
  function restagger() {
    const rows = new Map();
    const push = (depth, item) => { if (!rows.has(depth)) rows.set(depth, []); rows.get(depth).push(item); };
    for (const [id, p] of positions) push(p.depth, { kind: "node", id, x: p.x, w: widthOf.get(id), h: nodeHeight });
    for (const [pid, g] of groups) push(positions.get(pid).depth + 1, { kind: "group", id: pid, x: g.x, w: clientWidth, h: clientHeight });
    for (const [key, cp] of clientPositions) push(positions.get(cp.parent).depth + 1, { kind: "client", id: key, x: cp.x, w: clientWidth, h: clientHeight });
    for (const [depth, items] of rows) {
      items.sort((a, c) => a.x - c.x);
      const lastAt = new Array(stagger).fill(null);
      let cursor = 0;
      for (const it of items) {
        let tier = -1;
        for (let t = 0; t < stagger; t++) {
          const k = (cursor + t) % stagger;
          const last = lastAt[k];
          if (!last || it.x - it.w / 2 >= last.x + last.w / 2 + gap) { tier = k; break; }
        }
        if (tier < 0) tier = cursor % stagger;
        cursor = tier + 1;
        lastAt[tier] = it;
        const y = depthCoord(depth) + tier * subRow + it.h / 2;
        if (it.kind === "node") { const p = positions.get(it.id); p.y = y; p.tier = tier; }
        else if (it.kind === "group") groups.get(it.id).y = y;
        else clientPositions.get(it.id).y = y;
      }
    }
  }
  const breadth = Math.max(300, total + 2 * margin);
  const depthExtent = depthCoord(maxDepth) + (vertical ? stagger * subRow + 20 : maxLabel + 40);
  return vertical ? { positions, clientPositions, groups, width: breadth, height: depthExtent, nodeWidth: widthOf, orientation }
                  : { positions, clientPositions, groups, width: depthExtent, height: breadth, nodeWidth: widthOf, orientation };
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
