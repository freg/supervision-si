// Logique pure du module OwnCloud. Autonome (pas de partage avec les
// autres libs de modules), même convention que zenossLib.js/optickLib.js.
//
// Particularité : contrairement aux autres modules, l'arbre n'arrive
// JAMAIS complet du serveur — il est construit progressivement côté
// client au fil des dépliages (voir owncloud/README.md). Les fonctions
// mergeChildren()/buildRenderTree() gèrent cet état ; le reste
// (recherche, fil d'ariane, JSON) est le même principe que les autres
// modules.

export function normalizeText(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

/**
 * Fusionne un nœud + ses enfants directs (réponse de /children) dans
 * l'état d'arbre existant, SANS jamais effacer un dépliage déjà fait
 * plus bas : si un enfant reçu était déjà connu et déjà déplié
 * (childIds non nul), son dépliage est préservé — seules ses données
 * brutes (raw) sont rafraîchies. C'est la garantie centrale de ce
 * module : re-déplier un parent ne doit jamais faire "remonter" l'état
 * d'exploration d'un enfant déjà exploré.
 *
 * nodesById : { [id]: { id, type, name, raw, childIds: string[]|null } }
 * childIds === null signifie "pas encore déplié".
 */
export function mergeChildren(nodesById, parentNode, childrenNodes) {
  const next = { ...nodesById };

  next[parentNode.id] = {
    ...(next[parentNode.id] || {}),
    id: parentNode.id,
    type: parentNode.type,
    name: parentNode.name,
    raw: parentNode.raw,
    childIds: childrenNodes.map((c) => c.id),
  };

  for (const child of childrenNodes) {
    const existing = next[child.id];
    next[child.id] = {
      id: child.id,
      type: child.type,
      name: child.name,
      raw: child.raw,
      // Préserve un dépliage déjà en cours pour cet enfant.
      childIds: existing ? existing.childIds : null,
    };
  }

  return next;
}

/** Reconstruit l'arbre imbriqué (forme {id,name,type,raw,children})
 * pour le rendu, à partir de l'état plat courant — récursif, s'arrête
 * naturellement aux nœuds pas encore dépliés (children: []). */
export function buildRenderTree(nodesById, rootId) {
  const rootEntry = nodesById[rootId];
  if (!rootEntry) return null;

  function build(id) {
    const entry = nodesById[id];
    if (!entry) return null;
    const childIds = entry.childIds || [];
    return {
      id: entry.id,
      type: entry.type,
      name: entry.name,
      raw: entry.raw,
      hasUnloadedChildren: entry.childIds === null && (entry.raw?.childCount || 0) > 0,
      children: childIds.map(build).filter(Boolean),
    };
  }

  return build(rootId);
}

function searchableText(node) {
  const raw = node.raw || {};
  return [node.name, raw.path].filter(Boolean).join(" ");
}

export function nodeMatchesQuery(node, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  return normalizeText(searchableText(node)).includes(q);
}

/**
 * Passe commune (bas -> haut) : qui matche `predicate`, et qui a un
 * match quelque part en dessous (soi-même compris). `hasMatchBelow`
 * sert à garder les ANCÊTRES d'un match visibles (montrer où il se
 * trouve) — commun aux deux filtres ci-dessous.
 */
function computeMatchAndAncestry(tree, predicate) {
  const matches = new Set();
  const hasMatchBelow = new Set();

  function walk(node) {
    const self = predicate(node);
    if (self) matches.add(node.id);
    let below = self;
    for (const child of node.children || []) {
      if (walk(child)) below = true;
    }
    if (below) hasMatchBelow.add(node.id);
    return below;
  }
  walk(tree);

  return { matches, hasMatchBelow };
}

/**
 * Recherche texte : un match propage sa pertinence vers le BAS aussi
 * (trouver un dossier par son nom justifie de montrer tout son
 * contenu — c'est un choix de regroupement intentionnel de la
 * personne qui a nommé ce dossier).
 */
export function computeRelevantIdsByPredicate(tree, predicate) {
  if (!tree) return new Set();
  const { matches, hasMatchBelow } = computeMatchAndAncestry(tree, predicate);

  const relevant = new Set();
  function collect(node, ancestorMatched) {
    const isRelevant = matches.has(node.id) || hasMatchBelow.has(node.id) || ancestorMatched;
    if (isRelevant) relevant.add(node.id);
    const childFlag = ancestorMatched || matches.has(node.id);
    for (const child of node.children || []) {
      collect(child, childFlag);
    }
  }
  collect(tree, false);

  return relevant;
}

export function computeRelevantIds(tree, query) {
  const q = query ? query.trim() : "";
  if (!q) return null;
  if (!tree) return new Set();
  return computeRelevantIdsByPredicate(tree, (node) => nodeMatchesQuery(node, q));
}

/**
 * Motif avec joker '*' -- comme un glob shell simplifié, PAS une regex
 * complète (pas de '?', pas de classes de caractères). Sans '*' :
 * comportement IDENTIQUE à nodeMatchesQuery (sous-chaîne, rétro-
 * compatible) -- demandé explicitement : "analyse" doit matcher tout
 * nom qui CONTIENT "analyse", pas seulement une égalité exacte. Avec
 * '*' : ancré sur le nom ENTIER ("*.zip" doit se terminer par .zip,
 * jamais juste contenir ".zip" au milieu d'autre chose).
 */
export function nodeMatchesGlob(node, pattern) {
  const text = normalizeText(searchableText(node));
  const p = normalizeText(pattern).trim();
  if (!p) return true;
  if (!p.includes("*")) return text.includes(p);
  const escaped = p
    .split("*")
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join(".*");
  try {
    return new RegExp(`^${escaped}$`).test(text);
  } catch {
    return false;
  }
}

/**
 * Combine plusieurs termes de filtre (motif + mode inclure/exclure)
 * en UN SEUL prédicat. Modèle volontairement uniforme : "exclure" est
 * traité comme une NÉGATION du terme lui-même, puis tous les termes
 * (inclusion normale ou négation d'exclusion) sont combinés par ET ou
 * OU selon `combineMode` -- généralise proprement à n'importe quel
 * nombre de termes, pas seulement deux, sans cas particulier.
 *
 * terms : [{ pattern: string, mode: "include" | "exclude" }, ...]
 * combineMode : "and" | "or"
 * Renvoie null si aucun terme actif (motif vide) -- aucun filtrage.
 */
export function buildCombinedGlobPredicate(terms, combineMode) {
  const active = (terms || []).filter((t) => t.pattern && t.pattern.trim());
  if (active.length === 0) return null;
  return (node) => {
    const results = active.map((t) => {
      const matched = nodeMatchesGlob(node, t.pattern);
      return t.mode === "exclude" ? !matched : matched;
    });
    return combineMode === "or" ? results.some(Boolean) : results.every(Boolean);
  };
}

/** Applique buildCombinedGlobPredicate à un arbre -- même propagation
 * (ancêtres + descendants d'un dossier nommément trouvé) que
 * computeRelevantIds, réutilise la même mécanique commune. */
export function computeRelevantIdsByTerms(tree, terms, combineMode) {
  const predicate = buildCombinedGlobPredicate(terms, combineMode);
  if (!predicate) return null;
  if (!tree) return new Set();
  return computeRelevantIdsByPredicate(tree, predicate);
}

/** Un nœud (dossier ou fichier) est "dans la fenêtre" si son propre
 * mtime y tombe — un nœud sans mtime connu n'est jamais considéré par
 * défaut (pas de faux positif silencieux). */
export function nodeInMtimeRange(node, startTs, endTs) {
  const mtime = node.raw?.mtime;
  if (typeof mtime !== "number") return false;
  return mtime >= startTs && mtime <= endTs;
}

/**
 * Fenêtre temporelle : PAS de propagation vers le bas — le mtime d'un
 * dossier n'est qu'une conséquence mécanique du dernier changement en
 * son sein (pas un choix de regroupement comme un nom de dossier), le
 * garder dans la fenêtre ne doit donc jamais faire remonter des
 * fichiers eux-mêmes hors fenêtre. Seuls les ANCÊTRES d'un fichier qui
 * matche restent visibles (pour situer où il se trouve).
 * null si aucune fenêtre active (bornes non fournies).
 */
export function computeMtimeRelevantIds(tree, startTs, endTs) {
  if (startTs == null || endTs == null) return null;
  if (!tree) return new Set();
  const { matches, hasMatchBelow } = computeMatchAndAncestry(tree, (node) =>
    nodeInMtimeRange(node, startTs, endTs)
  );
  return new Set([...matches, ...hasMatchBelow]);
}

/** Bornes mtime (min/max) des nœuds actuellement chargés — s'élargit
 * au fil du dépliage, jamais interrogé en base (2,5M lignes : la
 * fenêtre ne porte que sur ce qui est déjà à l'écran). null si aucun
 * nœud chargé n'a de mtime exploitable. */
export function mtimeBoundsOfLoadedNodes(tree) {
  if (!tree) return null;
  let min = Infinity;
  let max = -Infinity;
  function walk(node) {
    const m = node.raw?.mtime;
    if (typeof m === "number") {
      if (m < min) min = m;
      if (m > max) max = m;
    }
    for (const c of node.children || []) walk(c);
  }
  walk(tree);
  if (min === Infinity) return null;
  return min === max ? { min, max: min + 1 } : { min, max };
}

/** Combine plusieurs ensembles de pertinence (texte + fenêtre
 * temporelle...) par INTERSECTION — un nœud doit satisfaire tous les
 * filtres actifs pour rester en pleine visibilité. Un filtre inactif
 * (null) ne restreint rien ; tous inactifs -> null (aucun filtrage). */
export function combineRelevantIds(...sets) {
  const active = sets.filter((s) => s !== null && s !== undefined);
  if (active.length === 0) return null;
  const [first, ...rest] = active;
  return new Set([...first].filter((id) => rest.every((s) => s.has(id))));
}

export function fmtTimelineDate(ts) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  return new Date(ts * 1000).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function findPathToNode(tree, targetId) {
  if (!tree) return null;
  function walk(node, path) {
    const nextPath = [...path, node];
    if (node.id === targetId) return nextPath;
    for (const child of node.children || []) {
      const found = walk(child, nextPath);
      if (found) return found;
    }
    return null;
  }
  return walk(tree, []);
}

/** Devine un texte de recherche de localisation raisonnable pour un
 * nœud sélectionné, à partir des seules métadonnées déjà lues
 * (nom, chemin — jamais le contenu du document) : son propre nom s'il
 * s'agit d'un dossier, sinon le nom du dossier parent le plus proche
 * dans le fil d'ariane (un nom de FICHIER brut, ex. "rapport.pdf",
 * est rarement un nom de lieu exploitable, contrairement au dossier
 * qui le contient). Simple suggestion de DÉPART, jamais utilisée
 * telle quelle sans confirmation humaine — la personne reste libre de
 * modifier le texte avant de lancer la recherche.
 *
 * breadcrumb : résultat de findPathToNode (racine -> ... -> nœud
 * sélectionné inclus), ou null/vide si pas encore calculé. */
export function guessLocationQuery(selectedNode, breadcrumb) {
  if (!selectedNode) return "";
  if (selectedNode.raw?.isDir && selectedNode.name) return selectedNode.name;

  const ancestors = (breadcrumb || []).slice(0, -1); // exclut le nœud lui-même
  for (let i = ancestors.length - 1; i >= 0; i--) {
    if (ancestors[i]?.name) return ancestors[i].name;
  }
  return selectedNode.name || "";
}

// --- Filtre "nœuds récurrents" ---------------------------------------
// DEUX phénomènes différents, à ne jamais mélanger (retour réel de la
// personne après une première version qui les confondait) :
//
// 1. La structure INTERNE d'ownCloud lui-même -- "files" (contenu
//    réel), "files_trashbin" (corbeille), "files_versions"
//    (historique), plus "cache"/"thumbnails"/"uploads" observés en
//    conditions réelles -- apparaît À L'IDENTIQUE sous CHAQUE racine
//    par construction du logiciel, jamais par choix d'un utilisateur.
//    Connue D'AVANCE, jamais "détectée" par comptage -- compter un
//    nom qu'on sait déjà systématique n'a aucun sens.
//
// 2. Des conventions de nommage RÉCURRENTES chez les utilisateurs
//    (ex. "Archive", "Trash") -- authentiquement découvertes en
//    observant ce qui revient sur PLUSIEURS racines différentes,
//    jamais connues d'avance. Un nom vu une seule fois n'est PAS
//    récurrent (juste "unique" pour l'instant) -- seuil >= 2
//    occurrences avant d'être traité comme tel.
export const KNOWN_OWNCLOUD_STRUCTURAL_NAMES = [
  "files", "files_trashbin", "files_versions", "cache", "thumbnails", "uploads",
];

/** Compte les DOSSIERS (jamais les fichiers) par nom, dans une liste
 * d'enfants reçue d'un seul appel /children -- brique de base pour
 * ACCUMULER un dictionnaire d'occurrences au fil du chargement (voir
 * mergeOccurrenceCounts). Jamais les fichiers : la demande porte sur
 * des DOSSIERS récurrents. Exclut aussi la structure ownCloud CONNUE
 * (voir ci-dessus) -- ces noms-là ne sont jamais "détectés" par
 * comptage, ils sont sus d'avance et traités séparément. */
export function countDirectoryNamesIn(children) {
  const counts = {};
  for (const child of children || []) {
    if (child.raw?.isDir && !KNOWN_OWNCLOUD_STRUCTURAL_NAMES.includes(child.name)) {
      counts[child.name] = (counts[child.name] || 0) + 1;
    }
  }
  return counts;
}

/** Fusionne un lot de comptages dans un accumulateur -- jamais de
 * mutation de `existing` (cohérent avec le reste : le state React
 * qui portera cet accumulateur ne doit jamais être modifié en place).
 * Volontairement PERSISTANT à travers les changements de racine
 * (contrairement à nodesById, remis à zéro à chaque nouvelle racine
 * choisie) : le but même de ce dictionnaire est de repérer ce qui
 * REVIENT d'un compte à l'autre, impossible à voir en ne regardant
 * qu'une seule racine à la fois. */
export function mergeOccurrenceCounts(existing, newCounts) {
  const merged = { ...existing };
  for (const [name, count] of Object.entries(newCounts || {})) {
    merged[name] = (merged[name] || 0) + count;
  }
  return merged;
}

/** Sépare un dictionnaire d'occurrences en deux : "récurrent" (>= 2
 * occurrences -- revient vraiment d'un compte à l'autre) et "unique"
 * (exactement 1 -- pas encore prouvé récurrent, mérite sa propre
 * liste plutôt que d'être mélangé, demandé explicitement). Chacun un
 * tableau [nom, compte] trié décroissant. */
export function splitOccurrencesByThreshold(occurrences, threshold = 2) {
  const recurring = [];
  const unique = [];
  for (const [name, count] of Object.entries(occurrences || {})) {
    if (count <= 0) continue;
    (count >= threshold ? recurring : unique).push([name, count]);
  }
  recurring.sort((a, b) => b[1] - a[1]);
  unique.sort((a, b) => a[0].localeCompare(b[0]));
  return { recurring, unique };
}

/** Retire tout nœud DONT LE NOM figure dans `hiddenNames`, à
 * N'IMPORTE QUELLE profondeur -- généralisation de l'ancien
 * pruneRecurringRootChildren (limité aux enfants directs de la
 * racine) : les dossiers structurels récurrents existent aussi plus
 * profond (Archive, Trash sous "files", par exemple), pas seulement
 * juste sous la racine. */
export function pruneNodesByNames(tree, hiddenNames) {
  if (!tree) return tree;
  const names = hiddenNames instanceof Set ? hiddenNames : new Set(hiddenNames || []);
  if (names.size === 0) return tree;
  function prune(node) {
    return {
      ...node,
      children: (node.children || []).filter((c) => !names.has(c.name)).map(prune),
    };
  }
  return prune(tree);
}

// --- Corrélation files / files_versions (timeline) --------------------
// Convention ownCloud confirmée en conditions réelles (voir
// owncloud/README.md) : une version d'un fichier `files/<chemin>` est
// stockée sous `files_versions/<chemin>.v<timestamp unix>`. Fonctions
// pures, opèrent sur ce qui est déjà chargé côté client (cohérent avec
// l'architecture par dépliage de ce module — jamais un aller-retour
// serveur dédié).
const VERSION_SUFFIX_RE = /\.v(\d+)$/;

/** {originalPath, timestamp} si `path` est bien un chemin de version
 * sous files_versions/, sinon null. Ne suppose PAS que files_versions
 * est à la racine du chemin (accepte un préfixe, ex. un id de storage
 * concaténé selon l'appelant) — cherche le segment "files_versions/"
 * où qu'il commence. */
export function parseVersionPath(path) {
  if (typeof path !== "string") return null;
  const marker = "files_versions/";
  const idx = path.indexOf(marker);
  if (idx === -1) return null;
  const afterMarker = path.slice(idx + marker.length);
  const m = afterMarker.match(VERSION_SUFFIX_RE);
  if (!m) return null;
  const timestamp = Number(m[1]);
  if (!Number.isFinite(timestamp)) return null;
  const relativePath = afterMarker.slice(0, afterMarker.length - m[0].length);
  if (!relativePath) return null;
  return { relativePath, timestamp };
}

/** Parcourt tous les nœuds déjà chargés (nodesById, état plat) et
 * regroupe les versions détectées par chemin relatif d'origine, triées
 * par date décroissante (plus récente d'abord). Ignore silencieusement
 * tout nœud sans `raw.path` exploitable ou hors de files_versions/ —
 * jamais d'exception sur un état partiellement chargé. */
export function buildVersionTimeline(nodesById) {
  const groups = new Map();
  for (const entry of Object.values(nodesById || {})) {
    const path = entry?.raw?.path;
    const parsed = parseVersionPath(path);
    if (!parsed) continue;
    if (!groups.has(parsed.relativePath)) groups.set(parsed.relativePath, []);
    groups.get(parsed.relativePath).push({
      id: entry.id,
      timestamp: parsed.timestamp,
      name: entry.name,
      size: entry.raw?.size,
    });
  }

  const result = [];
  for (const [relativePath, versions] of groups) {
    versions.sort((a, b) => b.timestamp - a.timestamp);
    result.push({ relativePath, versions });
  }
  result.sort((a, b) => a.relativePath.localeCompare(b.relativePath));
  return result;
}

export function truncateLabel(label, maxLen = 28) {
  const s = String(label || "");
  return s.length > maxLen ? `${s.slice(0, maxLen - 1)}…` : s;
}

/** Taille lisible (octets -> Ko/Mo/Go/To), 1 décimale au-delà de l'octet. */
export function fmtBytes(n) {
  const bytes = Number(n) || 0;
  if (bytes < 1024) return `${bytes} o`;
  const units = ["Ko", "Mo", "Go", "To", "Po"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

export function highlightJsonLines(value) {
  const text = JSON.stringify(value === undefined ? null : value, null, 2);
  return text.split("\n").map((line) => tokenizeJsonLine(line));
}

const TOKEN_RE = /("(?:\\.|[^"\\])*"(\s*:)?|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g;

export function tokenizeJsonLine(line) {
  const segments = [];
  let lastIndex = 0;
  let m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(line)) !== null) {
    if (m.index > lastIndex) {
      segments.push({ text: line.slice(lastIndex, m.index), cls: "punct" });
    }
    const token = m[0];
    let cls;
    if (token.endsWith(":")) {
      cls = "key";
    } else if (token.startsWith('"')) {
      cls = "string";
    } else if (token === "true" || token === "false") {
      cls = "boolean";
    } else if (token === "null") {
      cls = "null";
    } else {
      cls = "number";
    }
    segments.push({ text: token, cls });
    lastIndex = m.index + token.length;
  }
  if (lastIndex < line.length) {
    segments.push({ text: line.slice(lastIndex), cls: "punct" });
  }
  return segments.length ? segments : [{ text: line, cls: "punct" }];
}

/** Tri des racines (colonne de gauche) -- "count-desc" (nombre
 * d'éléments décroissant, DÉFAUT demandé explicitement -- plus
 * pratique pour repérer les gros comptes qu'un ordre d'arrivée API
 * sans signification) ou "alpha" (alphabétique). Copie toujours
 * renvoyée, jamais de mutation du tableau reçu en entrée. */
export function sortRoots(roots, mode) {
  const sorted = [...(roots || [])];
  if (mode === "alpha") {
    sorted.sort((a, b) => normalizeText(a.name).localeCompare(normalizeText(b.name)));
  } else {
    sorted.sort((a, b) => (b.itemCount || 0) - (a.itemCount || 0));
  }
  return sorted;
}
