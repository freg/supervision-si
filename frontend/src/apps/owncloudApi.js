// Client dédié à l'API owncloud. Contrat différent des autres modules
// (ipam/optick/zenoss) : /children ne renvoie JAMAIS tout un
// sous-arbre, seulement un nœud + ses enfants DIRECTS — la table
// source compte ~2,5 millions de lignes, voir owncloud/README.md.
const API_BASE_URL = import.meta.env.VITE_OWNCLOUD_API_BASE_URL || "http://localhost:6110";

export async function fetchOwncloudHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded", db: "injoignable" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", db: "injoignable" };
  }
}

/** Racines indépendantes (storages) — panneau de gauche. Chaque racine
 * porte rootFileId, à utiliser pour le premier appel à fetchOwncloudChildren. */
export async function fetchOwncloudRoots() {
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

/** Un nœud + ses enfants directs — utilisé aussi bien pour le premier
 * niveau d'une racine que pour déplier n'importe quel dossier ensuite. */
export async function fetchOwncloudChildren(storage, fileid) {
  try {
    const response = await fetch(`${API_BASE_URL}/children/${storage}/${fileid}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { node: null, children: [], error: body.error || `HTTP ${response.status}` };
    }
    const body = await response.json();
    return { node: body.node, children: body.children || [], error: null };
  } catch (err) {
    return { node: null, children: [], error: String(err) };
  }
}
