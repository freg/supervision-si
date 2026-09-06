// Client dédié à l'API optick (service indépendant, port séparé) —
// même convention que ipamApi.js / pixelGridApi.js.
const API_BASE_URL = import.meta.env.VITE_OPTICK_API_BASE_URL || "http://localhost:6107";

export async function fetchOptickHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", db: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", db: "injoignable" };
  }
}

/** Racines indépendantes (familles de catégories) — panneau de gauche. */
export async function fetchOptickRoots() {
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

/** Arbre complet enraciné à une famille — panneau central. */
/** Arbre complet enraciné à une famille — panneau central. Fenêtre
 * temporelle optionnelle (epoch secondes) : recalcule les comptages de
 * tickets par catégorie côté serveur (agrégats, pas un simple filtre
 * visuel — voir optick/README.md). */
export async function fetchOptickTree(rootId, timelineRange = null) {
  try {
    const qs = timelineRange ? `?start=${timelineRange.start}&end=${timelineRange.end}` : "";
    const response = await fetch(`${API_BASE_URL}/tree/${encodeURIComponent(rootId)}${qs}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { tree: null, dateBounds: null, error: body.error || `HTTP ${response.status}` };
    }
    const body = await response.json();
    return { tree: body.tree, dateBounds: body.dateBounds || null, error: null };
  } catch (err) {
    return { tree: null, dateBounds: null, error: String(err) };
  }
}
