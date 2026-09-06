// Logique pure de l'écran de recherche par localisation (voir
// vault/README.md, section "Recherche par localisation"). Autonome,
// jamais de chiffrement ici -- travaille sur des données DÉJÀ
// déchiffrées côté client (libellés) ou jamais sensibles au départ
// (géolocalisations, elles-mêmes non chiffrées, voir la décision de
// sécurité assumée documentée dans vault/README.md).

/** Vrai si `str` a la forme d'une adresse IPv4 (ex. "10.116.0.105")
 * -- utilisé pour exclure du coffre-fort les entrées de géolocalisation
 * issues du géocodage réseau (équipements scannés automatiquement,
 * jamais choisis comme nom de lieu par une personne). Volontairement
 * CIBLÉ sur le motif IP précisément, PAS sur l'absence de hiérarchie
 * (location_type) -- une entrée orpheline peut très bien être un nom
 * abrégé ou un numéro d'équipement légitime, jamais à exclure pour
 * cette seule raison. Ne valide pas que chaque octet est <= 255 :
 * suffisant pour ce tri (jamais un contrôle de validité réseau), et
 * plus simple à lire/maintenir. */
export function looksLikeIpAddress(str) {
  return /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test((str || "").trim());
}

/** Compte combien de secrets référencent CHAQUE localisation exacte
 * -- brique de base pour enrichLocationTreeWithUsage ci-dessous. */
export function countSecretsByLocation(secrets) {
  const counts = {};
  for (const s of secrets || []) {
    if (s.localisation) {
      counts[s.localisation] = (counts[s.localisation] || 0) + 1;
    }
  }
  return counts;
}

/**
 * Enrichit l'arbre de localisation avec le nombre de codes réels
 * attachés à chaque nœud (secretCount), ET ajoute les localisations
 * saisies dans des secrets mais ABSENTES de l'arbre (nom encore
 * jamais créé côté géolocalisations) -- demandé explicitement : une
 * localisation saisie dans un code ne doit jamais rester invisible
 * depuis la navigation, même si elle ne fait pas encore partie de la
 * hiérarchie connue.
 *
 * Priorité : les localisations SAISIES DANS UN CODE mais absentes de
 * la hiérarchie remontent en tête (jamais noyées, toujours visibles
 * immédiatement). Dans le reste de l'arbre, à chaque niveau, les
 * nœuds AVEC au moins un code passent avant ceux sans code -- toujours
 * alphabétique en cas d'égalité. Jamais de mutation de l'arbre reçu,
 * toujours un nouvel arbre.
 */
export function enrichLocationTreeWithUsage(tree, secrets) {
  const counts = countSecretsByLocation(secrets);
  const knownNames = new Set();

  function collectNames(nodes) {
    for (const n of nodes) {
      knownNames.add(n.localisation);
      collectNames(n.children || []);
    }
  }
  collectNames(tree || []);

  function enrichAndSort(nodes) {
    const enriched = nodes.map((n) => ({
      ...n,
      secretCount: counts[n.localisation] || 0,
      children: enrichAndSort(n.children || []),
    }));
    enriched.sort((a, b) => {
      const aHas = a.secretCount > 0 ? 1 : 0;
      const bHas = b.secretCount > 0 ? 1 : 0;
      if (aHas !== bHas) return bHas - aHas; // ceux AVEC des codes en priorité
      return (a.localisation || "").localeCompare(b.localisation || "");
    });
    return enriched;
  }

  const enrichedTree = enrichAndSort(tree || []);

  const missingNames = Object.keys(counts).filter((name) => !knownNames.has(name));
  const missingNodes = missingNames
    .map((name) => ({
      localisation: name,
      location_type: null,
      children: [],
      secretCount: counts[name],
      // Marqueur -- jamais dans la vraie hiérarchie géographique,
      // juste une saisie libre pas (encore) répertoriée ailleurs.
      isUnregistered: true,
    }))
    .sort((a, b) => a.localisation.localeCompare(b.localisation));

  return [...missingNodes, ...enrichedTree];
}

/** Filtre une liste de secrets par template_id -- même esprit que
 * filterSecretsByLocationNames, pour composer les deux filtres
 * (localisation ET modèle peuvent s'appliquer simultanément, ex.
 * "cartes SIM du Bâtiment A"). `null` = aucun filtre. */
export function filterSecretsByTemplate(secrets, templateId) {
  if (!templateId) return secrets || [];
  return (secrets || []).filter((s) => s.templateId === templateId);
}

/** Compte, pour chaque modèle connu, combien de secrets CHARGÉS
 * (voir loadAllDecryptedSecretLabels) l'utilisent -- pour l'affichage
 * "Par modèle" de l'écran de recherche. Ne compte QUE ce qui est déjà
 * accessible/chargé (contrairement aux mots-clés, volontairement pas
 * étendu à toutes les collections -- voir vault/README.md pour le
 * choix de portée). */
export function countSecretsByTemplate(secrets, templates) {
  const counts = {};
  for (const s of secrets || []) {
    if (s.templateId) counts[s.templateId] = (counts[s.templateId] || 0) + 1;
  }
  return (templates || [])
    .map((t) => ({ ...t, count: counts[t.id] || 0 }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

/** Masque les localisations SANS AUCUN code -- ni elles-mêmes, ni
 * aucun de leurs descendants -- demandé explicitement pour l'écran de
 * recherche (par défaut) : parcourir la hiérarchie complète des
 * géolocalisations, souvent bien plus vaste que ce qui a réellement
 * des codes, noyait l'essentiel. Un nœud dont un DESCENDANT a des
 * codes reste visible (contexte de navigation préservé, même esprit
 * que filterLocationTree) même si LUI n'en a aucun directement.
 * S'applique à un arbre déjà enrichi (voir enrichLocationTreeWithUsage
 * ci-dessus, secretCount déjà calculé) -- jamais l'inverse. */
export function filterTreeToUsedOnly(tree) {
  function filterNode(node) {
    const filteredChildren = (node.children || []).map(filterNode).filter(Boolean);
    const hasOwnUsage = (node.secretCount || 0) > 0;
    if (hasOwnUsage || filteredChildren.length > 0) {
      return { ...node, children: filteredChildren };
    }
    return null;
  }
  return (tree || []).map(filterNode).filter(Boolean);
}

/** Construit un arbre imbriqué depuis la liste PLATE des
 * géolocalisations (parent_localisation -- voir pixel-grid/api). Les
 * entrées au format IP (voir looksLikeIpAddress) sont exclues
 * d'emblée -- géocodage réseau automatique, jamais un nom de lieu
 * choisi par une personne, sans rapport avec le coffre-fort. Les
 * AUTRES localisations sans hiérarchie (nom abrégé, numéro
 * d'équipement -- légitimes, juste pas encore classées) sont
 * regroupées sous un nœud racine "(sans hiérarchie)" séparé, plutôt
 * que mélangées avec la vraie hiérarchie ou perdues silencieusement. */
export function buildLocationTree(geolocations) {
  const byName = new Map();
  for (const g of geolocations || []) {
    if (looksLikeIpAddress(g.localisation)) continue;
    byName.set(g.localisation, { ...g, children: [] });
  }

  const roots = [];
  const orphans = [];
  for (const node of byName.values()) {
    if (node.parent_localisation) {
      const parent = byName.get(node.parent_localisation);
      if (parent) {
        parent.children.push(node);
        continue;
      }
      // Parent référencé mais absent des données reçues -- traité
      // comme une racine plutôt que perdu silencieusement.
    }
    if (node.location_type) {
      roots.push(node);
    } else {
      orphans.push(node);
    }
  }

  if (orphans.length > 0) {
    roots.push({
      localisation: "__sans_hierarchie__",
      location_type: "groupe",
      children: orphans,
      isVirtualGroup: true,
    });
  }

  return roots;
}

/** Tous les noms de localisation sous (et y compris) `localisation`
 * dans l'arbre -- pour "voir les codes de ce bâtiment ET tous ses
 * étages/pièces", pas seulement une correspondance exacte. */
export function collectLocationDescendants(tree, localisation) {
  const names = new Set();
  function find(nodes) {
    for (const node of nodes) {
      if (node.localisation === localisation) {
        collectAll(node);
        return true;
      }
      if (find(node.children || [])) return true;
    }
    return false;
  }
  function collectAll(node) {
    names.add(node.localisation);
    for (const child of node.children || []) collectAll(child);
  }
  find(tree || []);
  return names;
}

/** Filtre une liste de secrets (déjà enrichis d'un champ `localisation`
 * en clair, voir vaultOps.js) sur un ensemble de noms de localisation
 * acceptés. `null`/`undefined` en 2e argument = aucun filtre (tout
 * renvoyé) -- jamais un ensemble vide traité comme "rien ne
 * correspond" par erreur de la part de l'appelant. */
export function filterSecretsByLocationNames(secrets, acceptedNames) {
  if (!acceptedNames) return secrets || [];
  return (secrets || []).filter((s) => s.localisation && acceptedNames.has(s.localisation));
}

/** Filtre texte libre sur le libellé DÉJÀ déchiffré -- jamais sur le
 * contenu chiffré, évidemment. Insensible à la casse/accents (même
 * convention que owncloudLib.js/normalizeText, dupliquée ici --
 * modules volontairement autonomes, voir en-tête de fichier). */
function normalizeText(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export function filterSecretsByQuery(secrets, query) {
  const q = normalizeText(query).trim();
  if (!q) return secrets || [];
  return (secrets || []).filter((s) => normalizeText(s.label).includes(q));
}

/** Tri de la liste centrale -- "alpha" (défaut demandé), "most-used"
 * (access_count décroissant), "recent" (last_accessed_at décroissant,
 * jamais consulté = toujours en dernier, pas en premier par un tri
 * naïf sur une valeur null/undefined). */
export function sortSecrets(secrets, mode) {
  const sorted = [...(secrets || [])];
  if (mode === "most-used") {
    sorted.sort((a, b) => (b.access_count || 0) - (a.access_count || 0));
  } else if (mode === "recent") {
    sorted.sort((a, b) => {
      if (!a.last_accessed_at && !b.last_accessed_at) return 0;
      if (!a.last_accessed_at) return 1;
      if (!b.last_accessed_at) return -1;
      return new Date(b.last_accessed_at) - new Date(a.last_accessed_at);
    });
  } else {
    sorted.sort((a, b) => normalizeText(a.label).localeCompare(normalizeText(b.label)));
  }
  return sorted;
}

/** Tous les codes déjà utilisés, triés par usage décroissant --
 * remplace l'ancien "Top 10" (trop "ludique", demandé explicitement :
 * "une liste ordonnée de TOUS les codes"). Jamais les jamais-utilisés
 * (access_count=0) pour ne pas polluer une liste "par usage" avec du
 * silence -- ceux-là restent visibles ailleurs (liste alphabétique).
 * `n` optionnel, conservé pour compatibilité (undefined = pas de
 * limite, tout renvoyer). */
export function usedSecretsByFrequency(secrets, n) {
  const sorted = (secrets || [])
    .filter((s) => (s.access_count || 0) > 0)
    .sort((a, b) => b.access_count - a.access_count);
  return n ? sorted.slice(0, n) : sorted;
}

/** Fusionne des secrets déjà déchiffrés avec leur résumé
 * d'observations (voir vaultOps.fetchObservationsSummary) --
 * observationCount=0/mostRecentObservationAt=null pour un secret
 * absent du résumé (jamais eu d'observation, cas normal et courant,
 * jamais une erreur). Nouvel objet à chaque fois, jamais de mutation
 * des secrets reçus. */
export function mergeSecretsWithObservationsSummary(secrets, summary) {
  const safeSummary = summary || {};
  return (secrets || []).map((s) => {
    const entry = safeSummary[s.id];
    return {
      ...s,
      observationCount: entry ? entry.count : 0,
      mostRecentObservationAt: entry ? entry.most_recent_at : null,
    };
  });
}

/** Filtre par présence/absence d'observation -- demandé explicitement
 * (page "Observations", tableau filtrable). "with" | "without" |
 * toute autre valeur (dont "all") = pas de filtre. */
export function filterSecretsByObservationPresence(secrets, mode) {
  if (mode === "with") return (secrets || []).filter((s) => s.observationCount > 0);
  if (mode === "without") return (secrets || []).filter((s) => s.observationCount === 0);
  return secrets || [];
}

/** Tri du tableau "Observations" -- "count" (nombre décroissant) |
 * "recent" (observation la plus récente en premier, jamais-observé
 * TOUJOURS en dernier peu importe le sens) | autre valeur (dont
 * "alpha") = libellé alphabétique. Nouveau tableau, jamais de
 * mutation de celui reçu (même principe que sortSecrets
 * ci-dessus). */
export function sortSecretsByObservationCriteria(secrets, sortBy) {
  const sorted = [...(secrets || [])];
  if (sortBy === "count") {
    sorted.sort((a, b) => b.observationCount - a.observationCount);
  } else if (sortBy === "recent") {
    sorted.sort((a, b) => {
      if (!a.mostRecentObservationAt && !b.mostRecentObservationAt) return 0;
      if (!a.mostRecentObservationAt) return 1;
      if (!b.mostRecentObservationAt) return -1;
      return new Date(b.mostRecentObservationAt) - new Date(a.mostRecentObservationAt);
    });
  } else {
    sorted.sort((a, b) => normalizeText(a.label).localeCompare(normalizeText(b.label)));
  }
  return sorted;
}

/** Filtre l'arbre de localisation par motif texte -- même principe
 * que owncloudLib.js (préserve les ANCÊTRES d'un match pour garder le
 * contexte visible), volontairement réécrit ici en plus simple : les
 * arbres de localisation (bâtiments/étages/pièces) restent
 * typiquement bien plus petits qu'une arborescence de fichiers, pas
 * besoin de la même mécanique de propagation vers le bas. Renvoie un
 * NOUVEL arbre ne contenant que les branches pertinentes -- jamais de
 * mutation de l'arbre reçu. */
export function filterLocationTree(tree, query) {
  const q = normalizeText(query).trim();
  if (!q) return tree;

  function filterNode(node) {
    const selfMatches = normalizeText(node.localisation).includes(q);
    const filteredChildren = (node.children || []).map(filterNode).filter(Boolean);
    if (selfMatches || filteredChildren.length > 0) {
      return { ...node, children: filteredChildren };
    }
    return null;
  }

  return (tree || []).map(filterNode).filter(Boolean);
}

/** Statistiques globales pour le tableau de bord maître_système --
 * PURE calcul côté client sur une liste de secrets déjà déchiffrés
 * (voir loadAllDecryptedSecretLabels) : le serveur ne peut jamais
 * produire ça lui-même (libellés chiffrés), aucune route dédiée
 * n'existe côté vault-api pour cette raison. */
export function computeVaultStats(secrets) {
  const collectionIds = new Set();
  let totalAccesses = 0;
  for (const s of secrets || []) {
    if (s.collectionId) collectionIds.add(s.collectionId);
    totalAccesses += s.access_count || 0;
  }
  return {
    totalSecrets: (secrets || []).length,
    totalCollections: collectionIds.size,
    totalAccesses,
  };
}

/** Compte les modifications par auteur -- à partir du journal global
 * (voir fetchGlobalHistory), jamais des secrets eux-mêmes. Trié par
 * nombre décroissant. */
export function computeMostActiveEditors(history, n = 10) {
  const counts = {};
  for (const h of history || []) {
    counts[h.changed_by] = (counts[h.changed_by] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([login, count]) => ({ login, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, n);
}

/** Associe à chaque entrée du journal global le libellé DÉJÀ
 * déchiffré du secret concerné (croisement client-side, jamais le
 * serveur -- voir GET /history, jamais de libellé). Une entrée dont
 * le secret n'est plus dans la liste (accès révoqué depuis, ou
 * secret supprimé) reçoit un libellé de repli explicite, jamais une
 * exception. */
export function annotateHistoryWithLabels(history, secrets) {
  const labelById = {};
  for (const s of secrets || []) labelById[s.id] = s.label;
  return (history || []).map((h) => ({
    ...h,
    label: labelById[h.secret_id] || "(secret non accessible ou supprimé)",
  }));
}
