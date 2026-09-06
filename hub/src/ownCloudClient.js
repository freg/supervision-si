// Client API vers owncloud-api (arbre, lecture seule) et
// owncloud-search-api (recherche Elasticsearch, lecture seule) --
// livraison #354, backlog items 6/9 -- sous-onglets "OwnCloud" et
// "Recherche" de la tuile GED, séparés visuellement du dépôt interne
// (voir GedView.jsx). Même motif fetchJson que gedClient.js.
//
// AUCUNE fonction d'écriture ici, par construction -- les deux
// backends ne proposent eux-mêmes que des routes GET/POST-lecture
// (voir owncloud/api/app.py, owncloud/search-api/app.py), jamais de
// PUT/DELETE -- ce fichier ne fait qu'y correspondre fidèlement,
// jamais une garantie supplémentaire au-delà de ce que le backend
// applique déjà lui-même.

async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (data === null) {
      return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    }
    if (!res.ok && data.error === undefined) {
      return { error: `Erreur HTTP ${res.status}` };
    }
    return data;
  } catch {
    return { error: "Service injoignable" };
  }
}

/** Racines (storages) de l'arbre OwnCloud. Toujours un TABLEAU,
 * jamais {error} -- une erreur réseau/base donne un tableau vide,
 * l'appelant affiche alors "aucune racine" plutôt qu'un plantage. */
export async function fetchOwnCloudRoots(apiBase) {
  const data = await fetchJson(apiBase, "/roots");
  return Array.isArray(data?.roots) ? data.roots : [];
}

/** Nœud demandé + ses enfants DIRECTS. {node, children} ou
 * {error} -- laissé tel quel (pas aplati en tableau vide) car
 * l'appelant a besoin de distinguer "erreur" de "nœud sans enfant". */
export async function fetchOwnCloudChildren(apiBase, storage, fileid) {
  return fetchJson(apiBase, `/children/${storage}/${fileid}`);
}

/** Chemins dépassant `threshold` caractères (livraison #354,
 * "identifier les chemins trop longs pour Windows ou autres") --
 * {threshold, results: [{fileid, storage, path, pathLength}]} ou
 * {error}. Requête COÛTEUSE côté serveur (balaie ~2,5M lignes, voir
 * owncloud/api/app.py) -- mise en cache plusieurs minutes côté
 * serveur, jamais appelée en boucle ni au chargement automatique de
 * la page (déclenchée explicitement par un bouton, voir
 * OwnCloudTreeView.jsx). */
export async function fetchOwnCloudLongPaths(apiBase, threshold, limit) {
  const params = new URLSearchParams();
  if (threshold != null) params.set("threshold", threshold);
  if (limit != null) params.set("limit", limit);
  const qs = params.toString();
  return fetchJson(apiBase, `/long-paths${qs ? `?${qs}` : ""}`);
}

/** Mapping RÉEL de l'index Elasticsearch (noms de champs + types) --
 * jamais une liste de champs supposée en dur côté frontend, voir
 * owncloud/search-api/README.md. Toujours un TABLEAU de
 * {name, type}, jamais {error} -- un index injoignable donne une
 * liste vide, l'appelant affiche alors "champs indisponibles". */
export async function fetchSearchMapping(searchApiBase) {
  const data = await fetchJson(searchApiBase, "/mapping");
  return Array.isArray(data?.fields) ? data.fields : [];
}

/** `clauses` : [{field, operator, value}]. `combinator` : "AND"|"OR".
 * Renvoie {total, hits} ou {error} -- jamais aplati, l'appelant doit
 * pouvoir distinguer "aucun résultat" de "recherche échouée". */
export async function searchOwnCloud(searchApiBase, clauses, combinator, size, from) {
  return fetchJson(searchApiBase, "/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clauses, combinator, size, from }),
  });
}
