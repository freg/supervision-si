/**
 * Compte les nœuds et la profondeur maximale d'un arbre {name,
 * children} — utilisé par RadialTree.jsx pour décider s'il est
 * raisonnable de rendre un arbre en entier ou s'il faut afficher un
 * résumé à la place, AVANT tout calcul D3 coûteux. Extrait dans son
 * propre module (aucune dépendance externe) pour rester testable
 * sans D3 ni React.
 *
 * Itératif (pas récursif) pour rester sûr même sur un arbre
 * pathologiquement large sans risquer une pile d'appels trop
 * profonde.
 */
export function countNodesAndDepth(root) {
  if (!root) return { nodeCount: 0, maxDepth: 0 };
  let nodeCount = 0;
  let maxDepth = 0;
  const stack = [[root, 0]];
  while (stack.length > 0) {
    const [node, depth] = stack.pop();
    nodeCount += 1;
    if (depth > maxDepth) maxDepth = depth;
    if (node.children) {
      for (const child of node.children) stack.push([child, depth + 1]);
    }
  }
  return { nodeCount, maxDepth };
}
