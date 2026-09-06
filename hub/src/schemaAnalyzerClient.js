// Analyse de schémas (hub), livraison #156 -- I/O réseau vers
// schema-analyzer-api ET dba-api (lecture seule, juste pour lister
// les connexions existantes -- jamais un CRUD complet ici, ça reste
// le rôle de l'onglet DBA lui-même).
//
// Contrairement à logsClient.js (échecs silencieux, `undefined`),
// les fonctions ICI renvoient TOUJOURS le corps JSON de la réponse
// quand une réponse existe -- même en cas d'erreur HTTP (400/502) --
// schema-analyzer renvoie systématiquement {"error": "..."} dans ce
// cas, un message PRÉCIS que l'interface doit pouvoir afficher, pas
// juste "quelque chose a échoué". Un échec RÉSEAU (rien reçu du
// tout) renvoie aussi {"error": "..."}, construit ici -- TOUJOURS la
// même forme côté appelant, jamais besoin de vérifier `undefined`
// séparément d'un `.error`.

async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options);
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

/** Connexions DBA existantes -- LECTURE SEULE, pour peupler le
 * sélecteur de connexion. Liste vide en cas d'échec (jamais une
 * exception) -- le sélecteur affichera juste "aucune connexion
 * disponible", pas un plantage. */
export async function fetchDbaConnections(dbaApiBase) {
  const data = await fetchJson(`${dbaApiBase}/connections`);
  return Array.isArray(data) ? data : [];
}

export async function analyzeConnection(schemaApiBase, connectionId, database, sampleSize) {
  return fetchJson(`${schemaApiBase}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      connection_id: Number(connectionId),
      database: database || undefined,
      sample_size: sampleSize || undefined,
    }),
  });
}

export async function importProposals(schemaApiBase, connectionId, database, actor) {
  return fetchJson(`${schemaApiBase}/relations/import-proposals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      connection_id: Number(connectionId),
      database: database || undefined,
      actor: actor || undefined,
    }),
  });
}

/** Toujours un TABLEAU (jamais {error}) -- une erreur devient une
 * liste vide ici, l'appelant affiche l'erreur au moment de l'ACTION
 * qui a échoué (analyser/importer), pas au moment de relire la
 * liste, qui peut échouer isolément sans que ce soit l'information
 * la plus utile à montrer. */
export async function fetchRelations(schemaApiBase, connectionId, database) {
  const params = new URLSearchParams({ connection_id: connectionId });
  if (database) params.set("database", database);
  const data = await fetchJson(`${schemaApiBase}/relations?${params.toString()}`);
  return Array.isArray(data) ? data : [];
}

export async function createRelation(schemaApiBase, payload) {
  return fetchJson(`${schemaApiBase}/relations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateRelation(schemaApiBase, relationId, fields) {
  return fetchJson(`${schemaApiBase}/relations/${relationId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
}

export async function deleteRelation(schemaApiBase, relationId) {
  return fetchJson(`${schemaApiBase}/relations/${relationId}`, { method: "DELETE" });
}

// --- Validation contre les vraies données (livraison #241) ---
export async function validateRelation(schemaApiBase, payload) {
  return fetchJson(`${schemaApiBase}/relations/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** URL directe (pas un fetch) -- ouverte dans un nouvel onglet /
 * téléchargée par le navigateur lui-même, jamais chargée en mémoire
 * ici (le graphe peut être volumineux sur une grosse base). */
export function graphExportUrl(schemaApiBase, connectionId, database, format) {
  const params = new URLSearchParams({ connection_id: connectionId, format });
  if (database) params.set("database", database);
  return `${schemaApiBase}/relations/graph?${params.toString()}`;
}

// --- Navigation/édition de données (livraison #178, backlog
// BACKLOG.md #5 -- "proposition d'interface d'édition des données,
// générée à partir du graphe relationnel validé"). APPROXIMATION
// NOTÉE (demande vague au départ, jamais confirmée précisément avec
// la personne -- voir hub/README.md) : navigateur/éditeur de LIGNES
// s'appuyant DIRECTEMENT sur le CRUD déjà existant de dba-api
// (jamais reconstruit ici), enrichi par les relations CONFIRMÉES de
// schema-analyzer pour proposer un "aller à la ligne liée" -- c'est
// la lecture la plus concrète possible de "généré à partir du
// graphe relationnel validé" sans a voir pu la confirmer avec la
// personne au préalable.

function dbaFetchJson(dbaApiBase, path, options) {
  return fetchJson(`${dbaApiBase}${path}`, options);
}

export async function fetchTableColumnsForEdit(dbaApiBase, connectionId, table, database) {
  const params = database ? `?database=${encodeURIComponent(database)}` : "";
  const data = await dbaFetchJson(dbaApiBase, `/connections/${connectionId}/tables/${encodeURIComponent(table)}/columns${params}`);
  return Array.isArray(data) ? data : [];
}

export async function fetchTableRows(dbaApiBase, connectionId, table, database, limit, offset) {
  const params = new URLSearchParams({ limit: String(limit || 50), offset: String(offset || 0) });
  if (database) params.set("database", database);
  return dbaFetchJson(dbaApiBase, `/connections/${connectionId}/tables/${encodeURIComponent(table)}/rows?${params.toString()}`);
}

export async function updateTableRow(dbaApiBase, connectionId, table, database, pkValue, updates) {
  const params = database ? `?database=${encodeURIComponent(database)}` : "";
  return dbaFetchJson(dbaApiBase, `/connections/${connectionId}/tables/${encodeURIComponent(table)}/rows${params}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pk_value: pkValue, updates }),
  });
}

export async function insertTableRow(dbaApiBase, connectionId, table, database, values) {
  const params = database ? `?database=${encodeURIComponent(database)}` : "";
  return dbaFetchJson(dbaApiBase, `/connections/${connectionId}/tables/${encodeURIComponent(table)}/rows${params}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values }),
  });
}

export async function deleteTableRows(dbaApiBase, connectionId, table, database, pkValues) {
  const params = database ? `?database=${encodeURIComponent(database)}` : "";
  return dbaFetchJson(dbaApiBase, `/connections/${connectionId}/tables/${encodeURIComponent(table)}/rows${params}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pk_values: pkValues }),
  });
}

/** Utilisée UNIQUEMENT pour "aller à la ligne liée" (relations
 * CONFIRMÉES) -- table/colonne viennent du schéma déjà chargé
 * (fiables), SEULE la VALEUR vient de données -- échappée via
 * sqlLiteral ci-dessous avant d'être insérée dans la requête,
 * jamais concaténée telle quelle. `dba-api` n'expose pas de requête
 * paramétrée générique (juste `/sql`, texte brut) -- ce point EST
 * une approximation notée (voir hub/README.md) : un vrai filtre WHERE
 * paramétré côté dba-api serait plus robuste, pas construit ici pour
 * rester dans le périmètre de schema-analyzer plutôt que de modifier
 * dba-api. */
export async function executeSql(dbaApiBase, connectionId, database, sql) {
  return dbaFetchJson(dbaApiBase, `/connections/${connectionId}/sql`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, database: database || undefined }),
  });
}

/** Échappement SQL BASIQUE -- un nombre passe tel quel, tout le
 * reste est entre guillemets simples avec les guillemets internes
 * DOUBLÉS (SQL92 standard, valide MySQL ET PostgreSQL). Suffisant
 * pour une valeur de clé déjà présente en base (jamais une saisie
 * libre non validée), pas une requête paramétrée complète -- voir
 * la note sur executeSql ci-dessus. */
export function sqlLiteral(value) {
  if (typeof value === "number") return String(value);
  if (value === null || value === undefined) return "NULL";
  const asString = String(value);
  if (/^-?\d+(\.\d+)?$/.test(asString)) return asString;
  return `'${asString.replace(/'/g, "''")}'`;
}
