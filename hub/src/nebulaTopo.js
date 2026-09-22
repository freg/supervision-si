// Synoptique du réseau Nebula (livraison #553) -- logique PURE, testée sous
// Node (hub/tests/nebulaTopo.test.mjs). À partir de la carte des VLAN
// (#548 : commutateurs, liaisons LLDP, voisins externes, inventaire) et de
// l'état des équipements (#546), construit un graphe : nœuds (passerelle,
// commutateurs, bornes, inconnus) placés par niveaux depuis la passerelle,
// arêtes avec les VLAN portés et les manquants. Le rendu (NebulaTopo.jsx)
// ne fait que dessiner.

const KIND = { GWH: "gateway", GW: "gateway", FIREWALL: "gateway", USG: "gateway", SW: "switch", SWITCH: "switch", AP: "ap" };
export const KIND_LABEL = { gateway: "Passerelle", switch: "Commutateur", ap: "Borne Wi-Fi", other: "Équipement", unknown: "Voisin LLDP" };

const norm = (s) => String(s || "").trim().toLowerCase();

/** Nœuds et arêtes. `vmap` = réponse /vlan-map ; `statuses` = {name: status} (facultatif). */
export function buildGraph(vmap, statuses = {}) {
  const nodes = new Map();
  for (const d of vmap.devices || []) {
    if (!d.devId) continue;
    nodes.set(d.devId, { id: d.devId, name: d.name || d.devId, model: d.model || "", kind: KIND[String(d.type || "").toUpperCase()] || "other", status: statuses[d.name] || "inconnu" });
  }
  const byName = new Map([...nodes.values()].map((n) => [norm(n.name), n.id]));
  const edges = [];
  const seen = new Set();
  for (const l of vmap.links || []) {
    let b = l.b;
    if (l.external) {
      b = byName.get(norm(l.b_name)) || null;
      if (!b) {
        const id = `ext:${norm(l.b_name)}`;
        if (!nodes.has(id)) nodes.set(id, { id, name: l.b_name || "?", model: "", kind: "unknown", status: "inconnu" });
        b = id;
      }
    }
    if (!b || !nodes.has(l.a)) continue;
    const key = [l.a, l.a_port, b, l.b_port].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    const missing = (l.missing_on_a || []).length + (l.missing_on_b || []).length;
    edges.push({ id: key, a: l.a, a_port: l.a_port, b, b_port: l.b_port, a_vlans: l.a_vlans || [], b_vlans: l.b_vlans || [],
                 missing_on_a: l.missing_on_a || [], missing_on_b: l.missing_on_b || [], bare: !!l.bare, external: !!l.external,
                 tone: missing ? "bad" : l.bare ? "muted" : "ok" });
  }
  return { nodes: [...nodes.values()], edges };
}

/** Niveaux : passerelle en haut (0), puis largeur d'abord le long des arêtes ;
 *  sans passerelle, le commutateur le plus connecté sert de racine ; les
 *  nœuds isolés vont au dernier niveau. */
export function assignTiers(graph) {
  const adj = new Map(graph.nodes.map((n) => [n.id, []]));
  for (const e of graph.edges) { adj.get(e.a)?.push(e.b); adj.get(e.b)?.push(e.a); }
  const roots = graph.nodes.filter((n) => n.kind === "gateway").map((n) => n.id);
  if (roots.length === 0 && graph.nodes.length) {
    const best = [...adj.entries()].sort((x, y) => y[1].length - x[1].length)[0];
    if (best) roots.push(best[0]);
  }
  const tier = new Map(roots.map((r) => [r, 0]));
  const queue = [...roots];
  while (queue.length) {
    const cur = queue.shift();
    for (const nb of adj.get(cur) || []) {
      if (!tier.has(nb)) { tier.set(nb, tier.get(cur) + 1); queue.push(nb); }
    }
  }
  const maxTier = Math.max(0, ...tier.values());
  for (const n of graph.nodes) {
    if (!tier.has(n.id)) tier.set(n.id, n.kind === "gateway" ? 0 : maxTier + 1);
  }
  // les bornes toujours sous leur commutateur, jamais au même niveau qu'un commutateur
  return tier;
}

/** Positions (x, y) dans une boîte width × height, par niveau, ordre stable :
 *  passerelles, commutateurs, bornes, inconnus, puis nom. */
export function layout(graph, width = 1000, rowHeight = 120, nodeWidth = 150, maxPerRow = 8) {
  const tier = assignTiers(graph);
  const order = { gateway: 0, switch: 1, ap: 2, other: 3, unknown: 4 };
  const rows = new Map();
  for (const n of graph.nodes) {
    const t = tier.get(n.id) || 0;
    if (!rows.has(t)) rows.set(t, []);
    rows.get(t).push(n);
  }
  const positions = new Map();
  const tiers = [...rows.keys()].sort((a, b) => a - b);
  let y = 60;
  let maxCols = 1;
  for (const t of tiers) {
    const list = rows.get(t).sort((x, y2) => (order[x.kind] - order[y2.kind]) || x.name.localeCompare(y2.name, "fr"));
    // un niveau trop large (bornes) se replie en plusieurs rangées
    const chunks = Math.max(1, Math.ceil(list.length / maxPerRow));
    const per = Math.ceil(list.length / chunks);
    for (let c = 0; c < chunks; c++) {
      const part = list.slice(c * per, (c + 1) * per);
      maxCols = Math.max(maxCols, part.length);
      const step = Math.max(nodeWidth + 20, width / (part.length + 1));
      part.forEach((n, i) => positions.set(n.id, { x: Math.round(step * (i + 1)), y, tier: t }));
      y += rowHeight * (c < chunks - 1 ? 0.7 : 1);
    }
  }
  const height = y;
  const neededWidth = Math.max(width, maxCols * (nodeWidth + 20) + 40);
  return { positions, width: neededWidth, height };
}

/** Un VLAN est-il porté par une arête (d'un côté au moins) ? */
export function edgeCarries(edge, vid) {
  const has = (v) => v === "all" || (Array.isArray(v) && v.includes(vid));
  return has(edge.a_vlans) || has(edge.b_vlans);
}

/** Résumé d'un nœud pour le panneau : VLAN par port (commutateur), SSID (borne). */
export function nodeSummary(node, vmap) {
  const out = { node, vlans: [], ssids: [] };
  if (node.kind === "switch") {
    for (const v of vmap.vlans || []) {
      const p = v.switches && v.switches[node.name];
      if (p) out.vlans.push({ vid: v.vid, untagged: p.untagged, tagged: p.tagged, subnet: v.subnet, ssids: (v.ssids || []).map((s) => s.name) });
    }
  }
  if (node.kind === "ap") {
    for (const v of vmap.vlans || []) for (const s of v.ssids || []) out.ssids.push({ name: s.name, vid: v.vid, enabled: s.enabled });
  }
  if (node.kind === "gateway") {
    for (const v of vmap.vlans || []) if (v.gateway_interface) out.vlans.push({ vid: v.vid, subnet: v.subnet, iface: v.gateway_interface, guest: v.guest });
  }
  return out;
}
