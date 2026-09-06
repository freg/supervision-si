// Client pour relations-api (livraison #335) -- même motif que les
// autres clients du hub (fetchJson minimal, jamais de dépendance
// externe). Voir hub/README.md pour le cadrage du modèle de relations.

async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    const data = await res.json().catch(() => null);
    if (!res.ok) return { error: data?.error || `Erreur ${res.status}` };
    return data;
  } catch (e) {
    return { error: e.message || "Erreur réseau" };
  }
}

export async function fetchEntityRelations(apiBase, entityType, entityId) {
  return fetchJson(apiBase, `/relations?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(entityId)}`);
}

export async function fetchRelationsGraph(apiBase) {
  return fetchJson(apiBase, "/graph");
}
