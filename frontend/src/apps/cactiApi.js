// Client dédié à l'API cacti (service indépendant, port séparé) --
// même convention que ipamApi.js / optickApi.js / zenossApi.js.
// Livraison #362 -- module backend construit depuis longtemps
// ("pour alimenter l'onglet Cacti du frontend", voir cacti/api/app.py)
// mais jamais relié à une interface avant cette livraison, découvert
// en vérifiant systématiquement quels services API n'avaient AUCUN
// consommateur frontend évident (même motif que la découverte
// OwnCloud côté hub, livraison #354).
const API_BASE_URL = import.meta.env.VITE_CACTI_API_BASE_URL || "http://localhost:6111";

export async function fetchCactiHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", db: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", db: "injoignable" };
  }
}

/** Racines indépendantes (les graph_tree Cacti eux-mêmes) — panneau de gauche. */
export async function fetchCactiRoots() {
  try {
    const response = await fetch(`${API_BASE_URL}/roots`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { roots: [], error: body.error || `HTTP ${response.status}` };
    }
    const body = await response.json();
    return { roots: body.roots || [], error: null };
  } catch (err) {
    return { roots: [], error: String(err) };
  }
}

/** Arbre complet (dossiers/hôtes/graphes) enraciné à une racine Cacti
 * -- une seule réponse, jamais de chargement paresseux par niveau
 * (contrairement à owncloud-api) : cacti-api renvoie déjà tout
 * l'arbre d'un coup (voir cacti/README.md). */
export async function fetchCactiTree(rootId) {
  try {
    const response = await fetch(`${API_BASE_URL}/tree/${encodeURIComponent(rootId)}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { tree: null, error: body.error || `HTTP ${response.status}` };
    }
    const body = await response.json();
    return { tree: body.tree, error: null };
  } catch (err) {
    return { tree: null, error: String(err) };
  }
}
