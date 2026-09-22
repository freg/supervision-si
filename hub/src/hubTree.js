// Arborescence de disposition du hub (livraison #516) -- logique PURE,
// testée sous Node (hub/tests/hubTree.test.mjs).
//
// Demandé : « paramétrer totalement la position des tuiles, des menus,
// des outils sous forme d'arborescence JSON, en glisser-déposer, avec
// une racine hub ; n'importe quel outil/tuile/menu/option peut aller
// n'importe où et plusieurs fois pour des regroupements de contexte ».
//
// Deux objets, jamais confondus :
//  - le CATALOGUE : les feuilles disponibles pour cette personne / ce
//    déploiement (vues internes, fronts externes, actions du hub),
//    calculé à chaque rendu depuis les mêmes conditions que les tuiles
//    (URL configurée, rôle) -- une feuille absente du catalogue n'est
//    jamais affichée, où qu'elle soit référencée ;
//  - l'ARBRE : { version, root } où root est un groupe `hub` ; un nœud est
//    soit { type: "group", id, label, icon, children } soit
//    { type: "ref", id, ref } -- `ref` est une clé du catalogue
//    ("view:cortex", "front:tickets", "action:aide", "auto:external-links").
//    Une référence n'est qu'un pointeur : la même feuille peut apparaître
//    autant de fois qu'on veut. `id` identifie le NŒUD (unique dans
//    l'arbre), pas la feuille.
//
// Rendu : les enfants de la racine font l'en-tête (un groupe = un menu
// déroulant, une référence = un bouton) et l'accueil (un groupe = une
// super-tuile, une référence = une tuile) ; un groupe ouvert montre ses
// feuilles en onglets (ThemeView). Les sous-groupes d'un menu sont des
// sections titrées du panneau.
//
// Ordre de résolution : arbre personnel (préférences) > arbre du site
// (app-settings « hub », posé par un administrateur) > arbre par défaut
// généré depuis hubThemes.js -- une personne qui n'a rien touché voit
// exactement l'accueil #457.

export const TREE_VERSION = 1;
export const ROOT_ID = "hub";
export const REF_EXTERNAL_LINKS = "auto:external-links";

let nodeCounter = 0;
export function newNodeId(prefix = "n") {
  nodeCounter += 1;
  return `${prefix}-${Date.now().toString(36)}-${nodeCounter}`;
}

export const group = (label, children = [], extra = {}) => ({ type: "group", id: extra.id || newNodeId("g"), label, icon: extra.icon || "", children });
export const ref = (key, extra = {}) => ({ type: "ref", id: extra.id || newNodeId("r"), ref: key });

/** Actions du hub disponibles comme feuilles (en plus des vues et fronts). */
export const ACTIONS = [
  { id: "action:aide", label: "Aide" },
  { id: "action:tabs", label: "Onglets" },
  { id: "action:settings", label: "Paramètres généraux" },
  { id: "action:personalize", label: "Personnaliser l'accueil" },
  { id: "action:layout", label: "Disposition du hub" },
  { id: "action:home-mode", label: "Accueil : thématiques / toutes les tuiles" },
  { id: "action:external-links", label: "Liens externes (administration)", admin: true },
  { id: "action:debug", label: "Diagnostic (jeton Keycloak)" },
];

/** Catalogue des feuilles : Map clé -> { id, label, kind, view|front|action, … }.
 *  `availableViews` : viewModes disponibles ; `viewLabels` : libellés (hubThemes.js
 *  en fournit) ; `fronts` : liste de lib.js (id, name, url, onClick, embeddable) ;
 *  `isAdmin` : actions réservées. */
export function buildCatalog({ availableViews, viewLabels = {}, fronts = [], isAdmin = false, actions = ACTIONS }) {
  const cat = new Map();
  for (const v of availableViews instanceof Set ? availableViews : new Set(availableViews || [])) {
    cat.set(`view:${v}`, { id: `view:${v}`, label: viewLabels[v] || v, kind: "view", view: v });
  }
  for (const f of fronts) {
    if (!f || !f.id) continue;
    cat.set(`front:${f.id}`, { id: `front:${f.id}`, label: f.name || f.id, kind: f.onClick ? "view-front" : "link", front: f.id, url: f.url || null, onClick: f.onClick || null, embeddable: !!f.embeddable, description: f.description || "" });
  }
  for (const a of actions) {
    if (a.admin && !isAdmin) continue;
    cat.set(a.id, { id: a.id, label: a.label, kind: "action", action: a.id.slice("action:".length) });
  }
  cat.set(REF_EXTERNAL_LINKS, { id: REF_EXTERNAL_LINKS, label: "Liens externes (déclarés par les administrateurs)", kind: "auto" });
  return cat;
}

/** « Univers du hub » (#538) : TOUTES les feuilles du catalogue (vues, fronts,
 *  actions -- jamais la feuille automatique des liens externes), triées
 *  `"alpha"` (libellé, ordre français) ou `"added"` (livraison d'apparition
 *  croissante via `since` : clé de vue/front ou id d'action -> numéro ;
 *  inconnue = à la fin, puis libellé). Filtre `query` sur le libellé, sans
 *  accents ni casse. Menu invariant : ne dépend pas de l'arbre de
 *  disposition, donc rien n'y est jamais perdu. */
export function universeEntries(catalog, { sort = "alpha", since = {}, query = "" } = {}) {
  const fold = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const q = fold(query).trim();
  const out = [];
  for (const leaf of catalog.values()) {
    if (leaf.kind === "auto") continue;
    if (q && !fold(leaf.label).includes(q)) continue;
    const key = leaf.kind === "view" ? leaf.view : leaf.kind === "action" ? leaf.id : leaf.front;
    const n = since[key];
    out.push({ ...leaf, since: Number.isFinite(n) ? n : null });
  }
  const byLabel = (a, b) => a.label.localeCompare(b.label, "fr", { sensitivity: "base" });
  out.sort(sort === "added"
    ? (a, b) => ((a.since ?? Infinity) - (b.since ?? Infinity)) || byLabel(a, b)
    : byLabel);
  return out;
}

/** Libellés des vues, tirés des thématiques (hubThemes.js) -- source unique. */
export function viewLabelsFromThemes(themes) {
  const out = {};
  for (const t of themes || []) for (const e of t.entries || []) if (e.view) out[e.view] = e.label;
  return out;
}

/** Arbre par défaut = l'accueil #457 : Aide, Onglets, une thématique par
 *  groupe, les liens externes, un groupe Paramètres. Identifiants de
 *  groupes STABLES (theme:<id>) pour que l'état « actif » de l'en-tête et
 *  les liens profonds restent les mêmes qu'avant. */
export function defaultTree(themes) {
  const children = [ref("action:aide", { id: "r-aide" }), ref("action:tabs", { id: "r-tabs" })];
  for (const t of themes || []) {
    children.push(group(t.name, t.entries.map((e, i) => ref(e.view ? `view:${e.view}` : `front:${e.front}`, { id: `r-${t.id}-${i}` })), { id: `theme:${t.id}`, icon: t.icon || "" }));
  }
  children.push(ref(REF_EXTERNAL_LINKS, { id: "r-external" }));
  children.push(group("Paramètres", [
    ref("action:settings", { id: "r-settings" }), ref("action:personalize", { id: "r-personalize" }), ref("action:layout", { id: "r-layout" }),
    ref("action:home-mode", { id: "r-home-mode" }), ref("action:external-links", { id: "r-external-links" }), ref("action:debug", { id: "r-debug" }),
  ], { id: "theme:settings", icon: "⚙" }));
  return { version: TREE_VERSION, root: { type: "group", id: ROOT_ID, label: "Hub", icon: "", children } };
}

/** Rend un arbre venu de l'extérieur (JSON collé, préférences d'une version
 *  antérieure) EXPLOITABLE : types inconnus ignorés, identifiants manquants ou
 *  en double régénérés, libellés forcés en chaîne, racine garantie. Retourne
 *  null si ce n'est pas un arbre du tout. */
export function normalizeTree(raw) {
  if (!raw || typeof raw !== "object") return null;
  const root = raw.root && typeof raw.root === "object" ? raw.root : (Array.isArray(raw.children) ? raw : null);
  if (!root) return null;
  const seen = new Set();
  const fix = (n, depth) => {
    if (!n || typeof n !== "object") return null;
    if (n.type === "ref") {
      if (typeof n.ref !== "string" || !n.ref) return null;
      const id = typeof n.id === "string" && n.id && !seen.has(n.id) ? n.id : newNodeId("r");
      seen.add(id);
      return { type: "ref", id, ref: n.ref };
    }
    if (n.type === "group" || Array.isArray(n.children)) {
      const id = depth === 0 ? ROOT_ID : (typeof n.id === "string" && n.id && !seen.has(n.id) ? n.id : newNodeId("g"));
      seen.add(id);
      const children = (Array.isArray(n.children) ? n.children : []).map((c) => fix(c, depth + 1)).filter(Boolean);
      return { type: "group", id, label: String(n.label ?? (depth === 0 ? "Hub" : "Groupe")), icon: typeof n.icon === "string" ? n.icon : "", children };
    }
    return null;
  };
  const fixed = fix(root, 0);
  return fixed ? { version: TREE_VERSION, root: fixed } : null;
}

/** Résolution : chaque référence est remplacée par sa feuille du catalogue
 *  (absente = omise), `auto:external-links` par les fronts hors catalogue de
 *  thématique (`leftover`), les groupes vides disparaissent. Sortie : même
 *  forme que l'arbre, avec `leaf` sur les références et `leaves` (feuilles
 *  aplaties, sous-groupes compris) sur les groupes. */
export function resolveTree(tree, catalog, { leftover = [] } = {}) {
  const t = tree && tree.root ? tree : null;
  if (!t) return { type: "group", id: ROOT_ID, label: "Hub", icon: "", children: [], leaves: [] };
  const res = (n) => {
    if (n.type === "ref") {
      if (n.ref === REF_EXTERNAL_LINKS) {
        return leftover.map((f, i) => ({ type: "ref", id: `${n.id}-${i}`, ref: `front:${f.id}`, leaf: { id: `front:${f.id}`, label: f.name || f.id, kind: f.onClick ? "view-front" : "link", front: f.id, url: f.url || null, onClick: f.onClick || null, embeddable: !!f.embeddable } }));
      }
      const leaf = catalog.get(n.ref);
      return leaf ? [{ type: "ref", id: n.id, ref: n.ref, leaf }] : [];
    }
    const children = (n.children || []).flatMap(res);
    if (!children.length && n.id !== ROOT_ID) return [];
    const leaves = children.flatMap((c) => (c.type === "ref" ? [c.leaf] : c.leaves));
    return [{ type: "group", id: n.id, label: n.label, icon: n.icon || "", children, leaves }];
  };
  return res(t.root)[0];
}

/** Les groupes de premier niveau sous la forme attendue par ThemeView et
 *  l'en-tête (#457) : { id, name, icon, entries, count, labels }. Une entrée
 *  est une feuille ; `kind` view | view-front | link | action. */
export function themesOf(resolved) {
  return (resolved?.children || []).filter((c) => c.type === "group").map((g) => {
    const entries = dedupe(g.leaves).map((l) => ({ ...l, id: l.id }));
    return { id: g.id, name: g.label, icon: g.icon, description: entries.map((e) => e.label).join(" · "), entries, count: entries.length, labels: entries.map((e) => e.label), sections: g.children };
  });
}

/** Références directes sous la racine (boutons de l'en-tête, tuiles seules). */
export function rootLeaves(resolved) {
  return (resolved?.children || []).filter((c) => c.type === "ref").map((c) => ({ nodeId: c.id, ...c.leaf }));
}

function dedupe(leaves) {
  const seen = new Set();
  return leaves.filter((l) => (seen.has(l.id) ? false : (seen.add(l.id), true)));
}

/** Le premier groupe de premier niveau qui contient une vue. */
export function themeOfLeaf(themes, leafId) {
  for (const t of themes || []) if (t.entries.some((e) => e.id === leafId)) return t.id;
  return null;
}

// ---------------------------------------------------------------- édition (immuable)
export function findNode(tree, id) {
  let found = null;
  const walk = (n, parent, index) => {
    if (found) return;
    if (n.id === id) { found = { node: n, parent, index }; return; }
    (n.children || []).forEach((c, i) => walk(c, n, i));
  };
  walk(tree.root, null, -1);
  return found;
}

const clone = (t) => JSON.parse(JSON.stringify(t));

export function isDescendant(tree, ancestorId, id) {
  const a = findNode(tree, ancestorId);
  if (!a) return false;
  let hit = false;
  const walk = (n) => { if (n.id === id) hit = true; (n.children || []).forEach(walk); };
  (a.node.children || []).forEach(walk);
  return hit;
}

/** Insère `node` dans le groupe `parentId` à `index` (fin si absent). */
export function insertNode(tree, parentId, node, index) {
  const t = clone(tree);
  const p = findNode(t, parentId);
  if (!p || p.node.type !== "group") return tree;
  const i = index == null || index < 0 || index > p.node.children.length ? p.node.children.length : index;
  p.node.children.splice(i, 0, node);
  return t;
}

export function removeNode(tree, id) {
  if (id === ROOT_ID) return tree;
  const t = clone(tree);
  const f = findNode(t, id);
  if (!f) return tree;
  f.parent.children.splice(f.index, 1);
  return t;
}

/** Déplace `id` dans `parentId` à `index` ; refuse la racine et un déplacement
 *  dans sa propre descendance. */
export function moveNode(tree, id, parentId, index) {
  if (id === ROOT_ID || id === parentId || isDescendant(tree, id, parentId)) return tree;
  const f = findNode(tree, id);
  if (!f) return tree;
  let i = index;
  if (f.parent.id === parentId && index != null && index > f.index) i = index - 1;
  return insertNode(removeNode(tree, id), parentId, clone(f.node), i);
}

/** Copie profonde d'un nœud avec de nouveaux identifiants (dupliquer une
 *  branche entière pour un autre contexte). */
export function cloneNode(node) {
  if (node.type === "ref") return ref(node.ref);
  return group(node.label, (node.children || []).map(cloneNode), { icon: node.icon });
}

export function updateNode(tree, id, patch) {
  const t = clone(tree);
  const f = findNode(t, id);
  if (!f) return tree;
  Object.assign(f.node, patch);
  return t;
}

/** Nombre d'occurrences d'une feuille dans l'arbre (affichage « ×2 » dans le catalogue). */
export function countRefs(tree, key) {
  let n = 0;
  const walk = (x) => { if (x.type === "ref" && x.ref === key) n += 1; (x.children || []).forEach(walk); };
  if (tree?.root) walk(tree.root);
  return n;
}

export function exportTree(tree) {
  return JSON.stringify(tree, null, 2);
}

export function importTree(text) {
  try {
    return normalizeTree(JSON.parse(text));
  } catch {
    return null;
  }
}

/** #554 : partition de la racine pour l'en-tête -- `pinned` (Aide, Onglets :
 *  boutons), `tree` (tout le reste sauf le groupe Paramètres : un seul menu
 *  arborescent), `settings` (le groupe Paramètres, menu à part). */
export function splitHeader(rootChildren) {
  const pinned = [], tree = [];
  let settings = null;
  for (const n of rootChildren || []) {
    if (n.type === "ref" && (n.ref === "action:aide" || n.ref === "action:tabs" || (n.leaf && (n.leaf.id === "action:aide" || n.leaf.id === "action:tabs")))) pinned.push(n);
    else if (n.type === "group" && n.id === "theme:settings") settings = n;
    else tree.push(n);
  }
  return { pinned, tree, settings };
}

/** #554 : tuiles en ordre alphabétique (ordre français, accents ignorés). */
export function sortTiles(tiles) {
  return [...(tiles || [])].sort((a, b) => String(a.name || a.label || "").localeCompare(String(b.name || b.label || ""), "fr", { sensitivity: "base" }));
}
