// Logique pure — aucune dépendance réseau ici (ni ipamApi.js, ni
// api.js), pour rester testable sous Node sans buter sur
// import.meta.env (spécifique à Vite, absent en exécution Node nue).

/**
 * Combine la liste des racines et leurs arbres déjà récupérés en un
 * seul JSON exploitable comme n'importe quelle autre source
 * (corbeille, arbre JSON, arbre radial existants). Une racine dont
 * l'arbre n'a pas pu être récupéré (erreur réseau ponctuelle sur
 * CETTE racine précise) est incluse quand même, avec son erreur
 * explicite plutôt que d'être silencieusement absente de la source.
 */
export function buildIpamForestPayload(roots, treesByRootId) {
  return {
    type: "ipam-forest",
    generatedAt: new Date().toISOString(),
    rootCount: roots.length,
    roots: roots.map((root) => {
      const entry = treesByRootId[root.id];
      return {
        id: root.id,
        name: root.name,
        description: root.description || null,
        childSectionCount: root.childSectionCount,
        subnetCount: root.subnetCount,
        tree: entry?.tree ?? null,
        error: entry?.error ?? null,
      };
    }),
  };
}
