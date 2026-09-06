// Construction d'un arbre hiérarchique à partir d'une liste plate
// d'entrées LDAP ({dn, attrs}) -- demandé explicitement : navigateur
// en colonnes façon phpLDAPadmin/Finder. Chaque DN encode déjà sa
// propre hiérarchie (ex. "uid=bob,ou=external,ou=accounts,
// dc=exemple,dc=fr") -- aucun appel réseau supplémentaire nécessaire,
// l'arbre entier se déduit de l'export déjà récupéré (GET /entries).

/** Découpe un DN en ses composants RDN, du plus spécifique au moins
 * spécifique -- gère les virgules échappées (`\,`) dans une valeur,
 * rares mais valides en LDAP (ex. un cn contenant une virgule). */
export function splitDn(dn) {
  if (!dn) return [];
  const parts = [];
  let current = "";
  for (let i = 0; i < dn.length; i++) {
    if (dn[i] === "\\" && i + 1 < dn.length) {
      current += dn[i] + dn[i + 1];
      i++;
      continue;
    }
    if (dn[i] === ",") {
      parts.push(current.trim());
      current = "";
      continue;
    }
    current += dn[i];
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
}

/** Le DN du parent -- tout sauf le premier composant (le plus
 * spécifique). `null` pour une racine (DN à un seul composant, ou
 * vide). */
export function parentDn(dn) {
  const parts = splitDn(dn);
  if (parts.length <= 1) return null;
  return parts.slice(1).join(",");
}

/** Construit l'arbre complet -- {nodes: {dn: node}, roots: [dn...]}.
 * Chaque node : {dn, label, attrs, children: [dn...], hasUid}.
 * Une entrée dont le DN parent n'est PAS dans la liste fournie
 * (la racine elle-même, ou une entrée dont le parent n'a pas été
 * exporté) devient une racine de l'arbre -- jamais une entrée
 * perdue silencieusement. Enfants triés alphabétiquement par
 * libellé, pour un affichage stable. */
export function buildTree(entries) {
  const nodes = {};
  for (const { dn, attrs } of entries || []) {
    nodes[dn] = {
      dn,
      label: splitDn(dn)[0] || dn,
      attrs: attrs || {},
      children: [],
      hasUid: Boolean((attrs || {}).uid && attrs.uid.length > 0),
    };
  }
  const roots = [];
  for (const dn of Object.keys(nodes)) {
    const parent = parentDn(dn);
    if (parent && nodes[parent]) {
      nodes[parent].children.push(dn);
    } else {
      roots.push(dn);
    }
  }
  for (const node of Object.values(nodes)) {
    node.children.sort((a, b) => nodes[a].label.localeCompare(nodes[b].label));
  }
  roots.sort((a, b) => nodes[a].label.localeCompare(nodes[b].label));
  return { nodes, roots };
}

/** Tous les descendants (récursif, l'entrée elle-même incluse) d'un
 * DN donné qui ont un attribut uid -- la colonne finale du
 * navigateur ("les utilisateurs résultants des filtres activés").
 * DN inconnu -- tableau vide, jamais une exception. */
export function usersUnder(tree, dn) {
  const result = [];
  function walk(currentDn) {
    const node = tree.nodes[currentDn];
    if (!node) return;
    if (node.hasUid) result.push(node);
    for (const childDn of node.children) walk(childDn);
  }
  walk(dn);
  return result;
}

/** Construit les colonnes du navigateur -- une par niveau de
 * `selectedPath`, PLUS une colonne supplémentaire pour les enfants
 * du dernier élément sélectionné (demandé explicitement : quand un
 * nœud a un sous-arbre et qu'on le sélectionne, la colonne SUIVANTE
 * doit montrer ses attributs en tête). `parentDn` (null pour la
 * colonne 0, les racines) permet d'afficher les attributs de ce
 * parent en tête de CETTE colonne, `dns` ses enfants juste en
 * dessous. Une feuille sélectionnée (aucun enfant) produit quand
 * même UNE colonne supplémentaire, avec `dns` vide -- c'est cette
 * colonne-là qui permet de voir/éditer les attributs de la feuille
 * elle-même (ex. un groupe avec son attribut `member`), jamais
 * perdue simplement parce qu'elle n'a pas de descendance. */
export function buildColumns(tree, selectedPath) {
  const columns = [];
  let currentDns = tree.roots;
  for (let level = 0; level <= selectedPath.length; level++) {
    const parentDn = level > 0 ? selectedPath[level - 1] : null;
    columns.push({ level, dns: currentDns, parentDn });
    const selectedAtLevel = selectedPath[level];
    if (!selectedAtLevel) break; // rien de sélectionné à ce niveau -- dernière colonne
    const node = tree.nodes[selectedAtLevel];
    currentDns = node ? node.children : [];
  }
  return columns;
}
