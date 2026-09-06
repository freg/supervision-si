// Client dédié à l'API de recherche OwnCloud — même convention que les
// autres *Api.js. Aucune requête Elasticsearch construite ici : le
// backend (owncloud/search-api/app.py) traduit une spec structurée en
// DSL ES, jamais l'inverse.
const API_BASE_URL = import.meta.env.VITE_OWNCLOUD_SEARCH_API_BASE_URL || "http://localhost:6112";

export async function fetchSearchHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", es: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", es: "injoignable" };
  }
}

/** Champs disponibles, découverts en direct sur le mapping Elasticsearch
 * réel — jamais une liste codée en dur côté frontend. */
export async function fetchSearchMapping() {
  try {
    const response = await fetch(`${API_BASE_URL}/mapping`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { fields: [], error: body.error || `HTTP ${response.status}` };
    }
    const body = await response.json();
    return { fields: body.fields || [], error: null };
  } catch (err) {
    return { fields: [], error: String(err) };
  }
}

/** clauses: [{field, operator, value}], combinator: "AND"|"OR" */
export async function runSearch(clauses, combinator, { size = 20, from = 0 } = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clauses, combinator, size, from }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { total: 0, hits: [], error: body.error || `HTTP ${response.status}` };
    }
    return { total: body.total || 0, hits: body.hits || [], error: null };
  } catch (err) {
    return { total: 0, hits: [], error: String(err) };
  }
}
