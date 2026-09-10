// Client des API lecture seule des bases externes (livraison #425) --
// contrat commun ipam / zenoss / optick / tts-gu / cacti : /health, /roots,
// /tree/<id>. Jamais d'exception vers le composant.
async function fetchJson(base, path) {
  try {
    const res = await fetch(`${base}${path}`);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (!res.ok) return { error: data?.error || `HTTP ${res.status}` };
    return data ?? { error: "réponse vide" };
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

export const fetchBaseHealth = (base) => fetchJson(base, "/health");
export async function fetchBaseRoots(base) {
  const d = await fetchJson(base, "/roots");
  return d?.error ? { roots: [], error: d.error } : { roots: Array.isArray(d.roots) ? d.roots : [], error: null };
}
export async function fetchBaseTree(base, rootId) {
  const d = await fetchJson(base, `/tree/${encodeURIComponent(rootId)}`);
  return d?.error ? { tree: null, error: d.error } : { tree: d.tree || null, error: null };
}
