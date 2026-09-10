// Logique PURE de la tuile « Bases externes » (livraison #425, backlog 64
// point 4, suite) -- aucun React, testée sous Node (hub/tests/externalBases.test.mjs).
//
// Les onglets IPAM / Zenoss / Optick / TTS-GU / Cacti de l'ancienne maquette
// (« vision arbre radial au centre, JSON à droite, racines indépendantes à
// gauche ») partagent UN contrat d'API lecture seule : `GET /roots` ->
// {roots: [{id, name, ...compteurs}]}, `GET /tree/<id>` -> {tree: nœud},
// nœud = {id, type, name, children: [], raw: {...}}. Une seule tuile
// générique les couvre donc, à la place de cinq apps quasi identiques.
// OwnCloud (arbre paresseux /children) reste dans l'ancien front pour
// l'instant.

export const SOURCES = [
  { id: "ipam", label: "IPAM", envKey: "VITE_IPAM_API_BASE_URL", description: "phpipam : sections et sous-réseaux", activeFilter: true },
  { id: "zenoss", label: "Zenoss", envKey: "VITE_ZENOSS_API_BASE_URL", description: "Zenoss : classes d'équipements et événements" },
  { id: "optick", label: "Optick", envKey: "VITE_OPTICK_API_BASE_URL", description: "Optick : familles et catégories de tickets" },
  { id: "tts-gu", label: "TTS-GU", envKey: "VITE_TTSGU_API_BASE_URL", description: "TTS-GU : domaines et catégories de tickets" },
  { id: "cacti", label: "Cacti", envKey: "VITE_CACTI_API_BASE_URL", description: "Cacti : arbres de graphes et hôtes" },
];

const norm = (s) => (s == null ? "" : String(s)).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function availableSources(bases) {
  return SOURCES.filter((s) => bases && bases[s.id]);
}

// ---- Parcours ------------------------------------------------------------------

export function walk(node, fn, depth = 0, parent = null) {
  if (!node) return;
  fn(node, depth, parent);
  for (const c of node.children || []) walk(c, fn, depth + 1, node);
}

export function countNodes(tree) {
  const out = { total: 0, depth: 0, byType: {} };
  walk(tree, (n, d) => { out.total += 1; out.depth = Math.max(out.depth, d); out.byType[n.type] = (out.byType[n.type] || 0) + 1; });
  return out;
}

export function findPath(tree, id) {
  const path = [];
  const rec = (n) => {
    path.push(n);
    if (n.id === id) return true;
    for (const c of n.children || []) if (rec(c)) return true;
    path.pop();
    return false;
  };
  return tree && rec(tree) ? path : [];
}

export function searchableText(node) {
  const raw = node.raw || {};
  return [node.name, node.id, node.type, raw.description, raw.subnet, raw.label, raw.path, raw.hostname, raw.ip].filter((v) => v != null).join(" ");
}

// ---- Filtre texte (port de ipamLib.computeRelevantIds) -----------------------
// Un match garde ses ancêtres (chemin visible) ET ses descendants (trouver un
// dossier justifie de montrer ce qu'il contient). null = pas de filtre.

export function relevantIds(tree, query) {
  const q = norm(query).trim();
  if (!q) return null;
  if (!tree) return new Set();
  const matches = new Set(), below = new Set();
  const w = (n) => {
    const self = norm(searchableText(n)).includes(q);
    if (self) matches.add(n.id);
    let any = self;
    for (const c of n.children || []) if (w(c)) any = true;
    if (any) below.add(n.id);
    return any;
  };
  w(tree);
  const out = new Set();
  const collect = (n, ancestorMatched) => {
    if (matches.has(n.id) || below.has(n.id) || ancestorMatched) out.add(n.id);
    for (const c of n.children || []) collect(c, ancestorMatched || matches.has(n.id));
  };
  collect(tree, false);
  return out;
}

export function pruneToIds(tree, ids) {
  if (!tree || ids === null) return tree;
  const rec = (n) => {
    const kids = (n.children || []).map(rec).filter(Boolean);
    if (!ids.has(n.id) && !kids.length) return null;
    return { ...n, children: kids };
  };
  return rec(tree);
}

// « Actifs seulement » (IPAM) : retire structurellement les sous-réseaux
// inactifs (raw.state !== 1) sans descendant actif ; la racine reste.
export function pruneToActive(node, isRoot = true) {
  if (!node) return null;
  const kids = (node.children || []).map((c) => pruneToActive(c, false)).filter(Boolean);
  if (node.type === "subnet" && node.raw?.state !== 1 && !kids.length) return null;
  if (!isRoot && node.type !== "subnet" && !kids.length) return null;
  return { ...node, children: kids };
}

// Profondeur bornée pour l'arbre radial : au-delà, un nœud « … (+N) »
// résume ce qui est replié ; `expanded` = identifiants dépliés malgré tout.
export function limitDepth(tree, maxDepth, expanded = new Set()) {
  const rec = (n, d) => {
    const kids = n.children || [];
    if (!kids.length) return { ...n, children: [] };
    if (d >= maxDepth && !expanded.has(n.id)) {
      const hidden = countNodes({ id: "", children: kids }).total - 1;
      return { ...n, children: [{ id: `${n.id}::more`, type: "more", name: `… +${hidden}`, children: [], raw: { hidden, parentId: n.id } }] };
    }
    return { ...n, children: kids.map((c) => rec(c, d + 1)) };
  };
  return tree ? rec(tree, 0) : null;
}

// ---- Fiche du nœud sélectionné --------------------------------------------------

export function nodeSummary(node) {
  if (!node) return null;
  const c = countNodes(node);
  return { name: node.name, type: node.type, id: node.id, descendants: c.total - 1, depth: c.depth, byType: c.byType, raw: node.raw || {} };
}

// Libellé court pour l'arbre (port de truncateLabel).
export function shortLabel(label, max = 24) {
  const s = String(label == null ? "" : label);
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

// Taux d'occupation IPAM (port de usagePercent) : raw.usage {used, maxhosts} ou raw.usedPercent.
export function usagePercent(node) {
  const raw = node?.raw || {};
  if (typeof raw.usedPercent === "number") return raw.usedPercent;
  const u = raw.usage || {};
  if (u.maxhosts > 0 && typeof u.used === "number") return Math.round((u.used / u.maxhosts) * 1000) / 10;
  return null;
}

export function usageTone(percent) {
  if (percent == null) return "neutral";
  if (percent >= 90) return "bad";
  if (percent >= 70) return "warn";
  return "good";
}

// Tri des racines : nom, insensible à la casse ; compteurs conservés.
export function sortRoots(roots, query = "") {
  const q = norm(query).trim();
  return [...(roots || [])].filter((r) => !q || norm(`${r.name} ${r.description || ""}`).includes(q))
    .sort((a, b) => norm(a.name).localeCompare(norm(b.name)));
}

export function rootCounts(root) {
  const skip = new Set(["id", "name", "description"]);
  return Object.entries(root || {}).filter(([k, v]) => !skip.has(k) && typeof v === "number").map(([k, v]) => `${v} ${k.replace(/Count$/, "").replace(/([A-Z])/g, " $1").toLowerCase()}`);
}
