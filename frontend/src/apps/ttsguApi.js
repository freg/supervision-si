// Client dédié à l'API tts-gu (service indépendant, port séparé) —
// même convention qu'ipamApi.js / optickApi.js.
const API_BASE_URL = import.meta.env.VITE_TTSGU_API_BASE_URL || "http://localhost:6109";

export async function fetchTtsguHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", db: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", db: "injoignable" };
  }
}

/** Racines indépendantes (domaines) — panneau de gauche. */
export async function fetchTtsguRoots() {
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

/** Arbre complet enraciné à un domaine — panneau central. */
/** Arbre complet enraciné à un domaine — panneau central. Fenêtre
 * temporelle optionnelle : recalcule les comptages côté serveur. */
export async function fetchTtsguTree(rootId, timelineRange = null) {
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
