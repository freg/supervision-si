// Logique pure du module IPAM — aucune dépendance React/d3 ici, pour
// rester testable en Node isolément (convention du projet, cf.
// tickets/portal/src/lib.js).

export function normalizeText(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

/** Une valeur "cherchable" d'un nœud : son nom + quelques champs utiles
 * du détail brut (description, vlan, vrf) — pour que la recherche
 * retrouve un subnet par sa description ou son VLAN, pas seulement
 * par son CIDR. */
function searchableText(node) {
  const raw = node.raw || {};
  return [node.name, raw.description, raw.vlanName, raw.vrfName].filter(Boolean).join(" ");
}

export function nodeMatchesQuery(node, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  return normalizeText(searchableText(node)).includes(q);
}

/**
 * Passe commune (bas -> haut) : qui matche `predicate`, et qui a un
 * match quelque part en dessous (soi-même compris) — sert à garder
 * les ANCÊTRES d'un match visibles. Commune à la recherche texte et
 * au filtre de fenêtre temporelle ci-dessous.
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
 * (trouver un dossier/subnet par son nom justifie de montrer tout ce
 * qu'il contient).
 * Retourne null si la requête est vide (= pas de filtrage) ; un Set
 * (potentiellement vide) sinon.
 */
export function computeRelevantIds(tree, query) {
  const q = query ? query.trim() : "";
  if (!q) return null;
  if (!tree) return new Set();

  const { matches, hasMatchBelow } = computeMatchAndAncestry(tree, (node) => nodeMatchesQuery(node, q));

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

/** Un nœud (section ou subnet) est "dans la fenêtre" si sa PROPRE date
 * de modification y tombe — jamais de faux positif pour un nœud sans
 * editDate connu (jamais modifié depuis création). */
export function nodeInEditDateRange(node, startTs, endTs) {
  const editDate = node.raw?.editDate;
  if (typeof editDate !== "number") return false;
  return editDate >= startTs && editDate <= endTs;
}

/**
 * Fenêtre temporelle : PAS de propagation vers le bas — la date de
 * modification d'une section n'est qu'une conséquence mécanique du
 * dernier changement en son sein (pas un regroupement voulu comme un
 * nom), la garder dans la fenêtre ne doit donc jamais faire remonter
 * des subnets eux-mêmes hors fenêtre. Seuls les ANCÊTRES d'un nœud qui
 * matche restent visibles (pour situer où il se trouve).
 * null si aucune fenêtre active (bornes non fournies).
 */
export function computeEditDateRelevantIds(tree, startTs, endTs) {
  if (startTs == null || endTs == null) return null;
  if (!tree) return new Set();
  const { matches, hasMatchBelow } = computeMatchAndAncestry(tree, (node) =>
    nodeInEditDateRange(node, startTs, endTs)
  );
  return new Set([...matches, ...hasMatchBelow]);
}

/** Bornes editDate (min/max) des nœuds actuellement chargés (l'arbre
 * entier de la racine sélectionnée, déjà tout chargé pour IPAM). null
 * si aucun nœud n'a de editDate exploitable. */
export function editDateBoundsOfLoadedNodes(tree) {
  if (!tree) return null;
  let min = Infinity;
  let max = -Infinity;
  function walk(node) {
    const d = node.raw?.editDate;
    if (typeof d === "number") {
      if (d < min) min = d;
      if (d > max) max = d;
    }
    for (const c of node.children || []) walk(c);
  }
  walk(tree);
  if (min === Infinity) return null;
  return min === max ? { min, max: min + 1 } : { min, max };
}

/** Combine plusieurs ensembles de pertinence par INTERSECTION — un
 * nœud doit satisfaire tous les filtres actifs pour rester en pleine
 * visibilité. Un filtre inactif (null) ne restreint rien. */
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

/** Chemin racine -> nœud ciblé (fil d'ariane), ou null si absent. */
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

/** Nombre total d'adresses IPv4 pour un masque CIDR (chaîne ou nombre) ;
 * null si le masque est absent/hors plage. */
export function addressesForMask(mask) {
  const n = typeof mask === "number" ? mask : parseInt(mask, 10);
  if (!Number.isInteger(n) || n < 0 || n > 32) return null;
  return 2 ** (32 - n);
}

/** Taux d'occupation (0–100) d'un subnet, ou null si non calculable
 * (dossier, masque absent, adresses inconnues). */
export function usagePercent(node) {
  const raw = node.raw || {};
  if (node.type !== "subnet" || raw.isFolder) return null;
  const total = addressesForMask(raw.mask);
  if (!total || typeof raw.ipCount !== "number") return null;
  return Math.min(100, (raw.ipCount / total) * 100);
}

/** Classe CSS de charge selon le taux d'occupation — seuils alignés
 * sur les tokens de thème ok/warn/critical du projet. */
export function usageClass(percent) {
  if (percent === null || percent === undefined) return "ipam-usage-unknown";
  if (percent >= 90) return "ipam-usage-critical";
  if (percent >= 70) return "ipam-usage-warn";
  return "ipam-usage-ok";
}

/**
 * Élague l'arbre pour ne garder QUE ce qui est actif — convention
 * phpipam : subnets.state vaut 0 (hors ligne), 1 (en ligne/actif) ou
 * 2 (non surveillé, valeur par défaut). Un subnet est gardé s'il est
 * lui-même actif (state===1) OU s'il lui reste au moins un descendant
 * actif après élagage (les subnets peuvent être nichés). Une section
 * est gardée si c'est la racine (toujours visible, même vide — la
 * personne a choisi ce point d'entrée, pas de le faire disparaître),
 * ou s'il lui reste au moins un enfant après élagage. Les nœuds "more"
 * (troncature de profondeur) passent inchangés.
 *
 * Contrairement au filtrage texte/temporel (qui ESTOMPE), ceci
 * RETIRE structurellement les nœuds inactifs — géométrie du rendu
 * radial recalculée sur un arbre réellement plus petit, pas juste
 * visuellement estompé.
 */
export function pruneToActive(node, isRoot = true) {
  if (!node) return null;
  if (node.type === "more") return node;

  const prunedChildren = (node.children || [])
    .map((c) => pruneToActive(c, false))
    .filter(Boolean);

  if (node.type === "subnet") {
    const isActive = node.raw?.state === 1;
    if (!isActive && prunedChildren.length === 0) return null;
    return { ...node, children: prunedChildren };
  }

  // section (ou type générique) : garde toujours la racine.
  if (!isRoot && prunedChildren.length === 0) return null;
  return { ...node, children: prunedChildren };
}

export function truncateLabel(label, maxLen = 28) {
  const s = String(label || "");
  return s.length > maxLen ? `${s.slice(0, maxLen - 1)}…` : s;
}

/**
 * Tokenise un JSON.stringify(valeur, null, 2) ligne par ligne pour une
 * coloration syntaxique légère, sans dangerouslySetInnerHTML : chaque
 * ligne devient une liste de segments {text, cls}, assemblables en
 * <span> côté React.
 */
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
    if (token.endsWith(":") || /^".*":\s*$/.test(token)) {
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
