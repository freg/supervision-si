// Client dédié à l'API zenoss — même convention que ipamApi.js / optickApi.js.
const API_BASE_URL = import.meta.env.VITE_ZENOSS_API_BASE_URL || "http://localhost:6108";

export async function fetchZenossHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", db: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", db: "injoignable" };
  }
}

/** Racines indépendantes (premiers segments des chemins de classe) — panneau de gauche. */
export async function fetchZenossRoots() {
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

/** Arbre complet enraciné à un premier segment de classe — panneau central.
 * rootId arrive sous forme "/App" (tel que renvoyé par /roots) : on
 * retire le slash initial avant d'encoder, pour ne jamais dépendre du
 * traitement (variable selon les piles WSGI) d'un %2F dans l'URL. */
export async function fetchZenossTree(rootId, timelineRange = null) {
  const bareId = rootId.replace(/^\/+/, "");
  try {
    const qs = timelineRange ? `?start=${timelineRange.start}&end=${timelineRange.end}` : "";
    const response = await fetch(`${API_BASE_URL}/tree/${encodeURIComponent(bareId)}${qs}`);
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

/** Racines indépendantes de l'inventaire physique (premiers segments de
 * Location) — EXCEPTION délibérée et scopée (voir en-tête de
 * zenoss/api/app.py et zenoss/README.md, section "Inventaire physique"). */
export async function fetchZenossLocationRoots(ipPrefix = null) {
  try {
    const qs = ipPrefix ? `?ip_prefix=${encodeURIComponent(ipPrefix)}` : "";
    const response = await fetch(`${API_BASE_URL}/location_roots${qs}`);
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

/** Arbre de localisation complet enraciné à un premier segment de Location.
 * Même convention d'id que fetchZenossTree (slash initial retiré avant
 * encodage). Pas de fenêtre temporelle ici (voir commentaire de la route
 * côté API — simplification délibérée pour cette v1). */
export async function fetchZenossLocationTree(rootId, ipPrefix = null) {
  const bareId = rootId.replace(/^\/+/, "");
  try {
    const qs = ipPrefix ? `?ip_prefix=${encodeURIComponent(ipPrefix)}` : "";
    const response = await fetch(`${API_BASE_URL}/location_tree/${encodeURIComponent(bareId)}${qs}`);
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
