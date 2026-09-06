// Utilitaires génériques, partagés entre les 5 modules "bases en
// lecture seule" (IPAM, Optick, TTS-GU, Zenoss, OwnCloud) — aucune
// connaissance métier : ne dépendent que de la forme commune des
// arbres ({id, type, name, children, raw}), jamais d'un champ
// spécifique à un module. Extrait après constat de duplication réelle
// (5 fois la même logique), pas par principe — chaque module garde sa
// propre logique de filtrage (computeRelevantIds, timeline...) dans
// son propre fichier, seule la mécanique de réduction/nommage
// générique est ici.

/**
 * Réduit un arbre aux seuls nœuds retenus par `relevantIds` (et à
 * leurs ancêtres, déjà inclus dans ce Set par construction dans
 * chaque module — voir leurs fonctions compute*RelevantIds propres).
 * Sert à figer une vue filtrée en JSON autonome, indépendant de
 * l'affichage (qui ne fait qu'estomper, jamais retirer).
 *
 * - `relevantIds === null` (aucun filtre actif) renvoie l'arbre tel
 *   quel, inchangé (même référence).
 * - Un Set vide (rien de pertinent sous les filtres actifs) renvoie
 *   `null` plutôt qu'une racine fantôme — rien d'utile à figer.
 */
export function pruneToRelevant(tree, relevantIds) {
  if (!tree) return null;
  if (relevantIds === null) return tree;

  function walk(node) {
    const prunedChildren = (node.children || []).map(walk).filter(Boolean);
    if (!relevantIds.has(node.id) && prunedChildren.length === 0) return null;
    return { ...node, children: prunedChildren };
  }
  return walk(tree);
}

export function slugifyForSourceName(label) {
  const base = (label || "source")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return base || "source";
}

/** Nom de source unique et lisible pour une vue figée — inclut un
 * horodatage compact pour ne jamais entrer en collision avec une
 * capture précédente du même module/racine. */
export function buildSnapshotSourceName(prefix, rootName, now = new Date()) {
  const ts = now.toISOString().replace(/[:.]/g, "-").slice(0, 19);
  return `${prefix}_${slugifyForSourceName(rootName)}_${ts}`;
}
