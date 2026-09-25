// Menu principal en GRAPHE MÉTIER déployé (livraison #599, backlog item 94,
// étape 1 de docs/menu-graphe-metier.md) -- logique PURE, testée sous Node
// (hub/tests/hubBusiness.test.mjs).
//
// Demandé : « un arbre qui prenne la logique métier et les dépendances ; un
// nœud / tuile peut être à plusieurs endroits : c'est un graphe déployé »,
// avec cinq racines : équipements, services, droits, supervision / états,
// Cortex / IA. Ici, chaque feuille du catalogue (vue, front, action) est
// rattachée à un ou plusieurs CHEMINS métier ; le graphe est « déployé » en
// arbre : une feuille apparaît sous chacun de ses chemins et sait où elle
// est « aussi » (fil d'Ariane multiple). L'arbre de disposition (#516,
// hubTree.js) reste disponible : c'est une autre porte vers le même
// catalogue. Étape 2 (arêtes calculées : compose, registres, agents,
// Cortex, notifications, droits) viendra alimenter ces mêmes chemins.
import { rankFilter, fold, matchRank } from "./textFilter.js";

/** Les cinq racines et leurs branches (ordre = ordre d'affichage). */
export const ROOTS = [
  { id: "equipements", label: "Équipements", icon: "🖧", description: "réseau, hôtes et VM, sondes matérielles, postes, par site",
    branches: [
      { id: "reseau", label: "Réseau", children: [{ id: "routeurs", label: "Routeurs" }, { id: "switchs", label: "Switchs" }, { id: "wifi", label: "Wi-Fi et bornes" }, { id: "tunnels", label: "Tunnels et bastion" }] },
      { id: "hotes", label: "Hôtes, VM, conteneurs", children: [{ id: "hyperviseurs", label: "Hyperviseurs" }, { id: "agents", label: "Agents hôtes" }, { id: "conteneurs", label: "Conteneurs du hub" }] },
      { id: "sondes", label: "Sondes matérielles", children: [{ id: "onduleurs", label: "Onduleurs" }, { id: "snmp", label: "SNMP" }, { id: "sondes-reseau", label: "Sondes réseau" }] },
      { id: "postes", label: "Postes et logiciels" },
      { id: "inventaire", label: "Inventaire et cartographie" },
    ] },
  { id: "services", label: "Services", icon: "🧩", description: "conteneurs du hub, entrées visibles d'Internet, services métier des clients, données",
    branches: [
      { id: "hub", label: "Services du hub" },
      { id: "internet", label: "Entrées visibles d'Internet" },
      { id: "metier", label: "Services métier" },
      { id: "donnees", label: "Données et référentiels" },
      { id: "messagerie", label: "Messagerie et documents" },
    ] },
  { id: "droits", label: "Droits et accès", icon: "🛡", description: "personnes, groupes, accès d'équipements, coffres, jetons, licences",
    branches: [
      { id: "personnes", label: "Personnes et groupes" },
      { id: "acces", label: "Accès aux équipements" },
      { id: "coffres", label: "Coffres et secrets" },
      { id: "licences", label: "Licences et contrats" },
      { id: "matrice", label: "Qui voit quoi" },
    ] },
  { id: "etats", label: "Supervision et états", icon: "🚦", description: "aujourd'hui, incidents, alertes, feux tricolores, journaux, historique",
    branches: [
      { id: "maintenant", label: "Maintenant" },
      { id: "incidents", label: "Incidents et alertes" },
      { id: "feux", label: "Feux tricolores" },
      { id: "journaux", label: "Journaux et historique" },
      { id: "notifications", label: "Notifications" },
      { id: "demandes", label: "Demandes et tickets" },
    ] },
  { id: "cortex", label: "Cortex et IA", icon: "🧠", description: "assistant, corrélation, classification, règles apprises, mémoire",
    branches: [
      { id: "assistant", label: "Assistant" },
      { id: "correlation", label: "Corrélation et causes" },
      { id: "apprentissage", label: "Classification et règles" },
      { id: "memoire", label: "Mémoire et connaissance" },
    ] },
];

/** Chemins métier de chaque feuille du catalogue (clé = ref du catalogue).
 *  Une feuille absente d'ici tombe sous « Autres » de la racine la plus
 *  proche de sa thématique d'origine (voir fallbackPath). */
export const PATHS = {
  "view:aujourdhui": ["etats/maintenant", "etats/feux"],
  "view:cortex": ["cortex/correlation", "etats/incidents"],
  "view:supervision-si": ["etats/feux", "services/metier"],
  "view:si-agent": ["equipements/hotes/agents", "etats/feux"],
  "view:netprobe": ["equipements/sondes/sondes-reseau", "equipements/reseau/wifi"],
  "front:service-watch": ["services/internet", "etats/feux"],
  "view:ups": ["equipements/sondes/onduleurs", "etats/incidents"],
  "view:snmp": ["equipements/sondes/snmp"],
  "view:vigilance": ["etats/incidents"],
  "view:cyber": ["droits/matrice", "etats/incidents"],
  "view:logs": ["etats/journaux"],
  "view:history": ["etats/journaux"],
  "view:memory": ["cortex/memoire"],
  "view:network-agent": ["equipements/inventaire", "equipements/reseau"],
  "view:network-equipment": ["equipements/reseau", "equipements/inventaire"],
  "view:network-cycle": ["equipements/reseau", "etats/journaux"],
  "view:netmap-orchestrator": ["equipements/inventaire"],
  "view:architecture": ["services/hub", "equipements/inventaire"],
  "view:fusion": ["equipements/inventaire"],
  "view:nebula": ["equipements/reseau/wifi", "services/metier"],
  "view:ssh-tunnels": ["equipements/reseau/tunnels", "droits/acces"],
  "front:mikrotik": ["equipements/reseau/routeurs", "droits/acces"],
  "view:nat-map": ["equipements/reseau/routeurs", "services/internet"],
  "front:cisco": ["equipements/reseau/switchs", "droits/acces"],
  "view:proxmox": ["equipements/hotes/hyperviseurs"],
  "view:external-bases": ["services/donnees"],
  "view:glpi-inventory": ["equipements/inventaire", "services/donnees"],
  "view:geo-catalog": ["services/donnees", "equipements/inventaire"],
  "view:classifier": ["cortex/apprentissage"],
  "view:schema-analyzer": ["services/donnees", "cortex/apprentissage"],
  "view:retro": ["services/donnees"],
  "front:dba": ["services/donnees"],
  "view:licenses": ["droits/licences", "equipements/postes"],
  "view:synthese": ["etats/maintenant", "services/metier"],
  "view:ent": ["services/messagerie"],
  "view:ged": ["services/messagerie"],
  "view:file-manager": ["services/messagerie"],
  "view:imap": ["services/messagerie"],
  "view:imap-connectors": ["services/messagerie", "etats/demandes"],
  "front:assistant": ["cortex/assistant"],
  "front:tickets": ["etats/demandes"],
  "front:demande": ["etats/demandes"],
  "front:projeqtor": ["etats/demandes", "services/metier"],
  "view:si-proxy": ["equipements/reseau/tunnels", "droits/acces"],
  "front:credentials": ["droits/acces", "droits/coffres"],
  "view:rights": ["droits/matrice"],
  "view:accounts": ["droits/personnes"],
  "view:notifications": ["etats/notifications"],
  "view:backup-restore": ["services/hub"],
  "front:vault": ["droits/coffres"],
  "front:vault-admin": ["droits/coffres"],
  "front:keycloak-admin": ["droits/personnes"],
  "front:ldap-admin": ["droits/personnes"],
  "action:control": ["services/hub", "equipements/hotes/conteneurs", "etats/feux"],
  "action:external-links": ["services/internet"],
  "action:settings": ["services/hub"],
  "action:layout": ["services/hub"],
  "action:personalize": ["services/hub"],
  "action:home-mode": ["services/hub"],
  "action:aide": ["cortex/assistant"],
  "action:tabs": ["etats/maintenant"],
  "action:debug": ["droits/personnes"],
};

const THEME_ROOT = { supervision: "etats", reseau: "equipements", donnees: "services", documents: "services", securite: "droits", projeqtor: "etats", parametres: "services" };

/** Chemin de repli d'une feuille sans chemin déclaré : « <racine de sa thématique>/autres ». */
export function fallbackPath(leaf, themeId) {
  return `${THEME_ROOT[themeId] || "services"}/autres`;
}

function labelOfPath(path) {
  const [rootId, ...rest] = path.split("/");
  const root = ROOTS.find((r) => r.id === rootId);
  const parts = [root ? root.label : rootId];
  let level = root ? root.branches : [];
  for (const seg of rest) {
    const b = (level || []).find((x) => x.id === seg);
    parts.push(b ? b.label : seg === "autres" ? "Autres" : seg);
    level = b ? b.children : [];
  }
  return parts.join(" › ");
}

/** Déploie le graphe en arbre : { roots: [{ id, label, icon, description, children: [...], leaves: [...] }] }.
 *  `catalog` = Map du catalogue (#516) ; `themeOf(ref)` (facultatif) donne la
 *  thématique d'origine pour le repli. Chaque feuille placée porte `also`
 *  (libellés de ses autres chemins). Les branches vides sont retirées. */
export function businessTree(catalog, { themeOf = () => null, paths = PATHS } = {}) {
  const placed = new Map();  // path -> [leaf]
  const leafPaths = new Map();  // ref -> [paths]
  for (const leaf of catalog.values()) {
    if (leaf.kind === "auto") continue;
    const ps = paths[leaf.id] && paths[leaf.id].length ? paths[leaf.id] : [fallbackPath(leaf, themeOf(leaf.id))];
    leafPaths.set(leaf.id, ps);
    for (const p of ps) {
      if (!placed.has(p)) placed.set(p, []);
      placed.get(p).push(leaf);
    }
  }
  const build = (node, path, depth) => {
    const leaves = (placed.get(path) || []).map((l) => ({ ...l, path, also: leafPaths.get(l.id).filter((p) => p !== path).map(labelOfPath) }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr", { sensitivity: "base" }));
    const children = (node.children || node.branches || []).map((c) => build(c, `${path}/${c.id}`, depth + 1)).filter(Boolean);
    const others = placed.get(`${path}/autres`);
    if (depth === 0 && others && others.length) children.push({ id: `${path}/autres`, label: "Autres", children: [], leaves: others.map((l) => ({ ...l, path: `${path}/autres`, also: [] })).sort((a, b) => a.label.localeCompare(b.label, "fr")), count: others.length });
    const count = leaves.length + children.reduce((n, c) => n + c.count, 0);
    if (!count && depth > 0) return null;
    return { id: path, label: node.label, icon: node.icon || "", description: node.description || "", children, leaves, count };
  };
  return { roots: ROOTS.map((r) => build(r, r.id, 0)) };
}

/** Filtre début-de-mot (#562) sur les libellés de feuilles ET de branches :
 *  garde les branches menant à une correspondance ; `expanded` = tout
 *  ouvrir quand on filtre. Sans saisie : l'arbre tel quel. */
export function filterBusinessTree(tree, query) {
  const q = fold(query || "").trim();
  if (!q) return tree;
  const walk = (node) => {
    const leaves = rankFilter(node.leaves, q, (l) => l.label);
    const children = node.children.map(walk).filter(Boolean);
    const selfHit = matchRank(node.label, q) === 0;  // une branche ne « gagne » que par début de mot
    if (!leaves.length && !children.length && !selfHit) return null;
    return { ...node, leaves: selfHit && !leaves.length ? node.leaves : leaves, children: selfHit && !children.length ? node.children : children, count: (selfHit && !leaves.length ? node.leaves : leaves).length + (selfHit && !children.length ? node.children : children).reduce((n, c) => n + c.count, 0) };
  };
  return { roots: tree.roots.map(walk).filter(Boolean) };
}

/** Chemins (ids de nœuds) qui contiennent une feuille donnée -- pour ouvrir la
 *  branche de la vue courante. */
export function pathsOfLeaf(tree, leafId) {
  const out = [];
  const walk = (node) => { if (node.leaves.some((l) => l.id === leafId)) out.push(node.id); node.children.forEach(walk); };
  tree.roots.forEach(walk);
  return out;
}

/** Nombre de chemins par feuille (mesure de l'étape 1 : chaque tuile joignable par ≥ 2 chemins). */
export function reachability(catalog, opts) {
  const t = businessTree(catalog, opts);
  const counts = new Map();
  const walk = (node) => { node.leaves.forEach((l) => counts.set(l.id, (counts.get(l.id) || 0) + 1)); node.children.forEach(walk); };
  t.roots.forEach(walk);
  return counts;
}
