// Client dédié à l'API ipam (service indépendant, port séparé) — même
// convention que pixelGridApi.js / ticketsApi.js.
const API_BASE_URL = import.meta.env.VITE_IPAM_API_BASE_URL || "http://localhost:6106";

export async function fetchIpamHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", db: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", db: "injoignable" };
  }
}

/** Racines indépendantes (sections de tête) — panneau de gauche. */
export async function fetchIpamRoots() {
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

/** Arbre complet enraciné à une section — panneau central. */
export async function fetchIpamTree(rootId) {
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
