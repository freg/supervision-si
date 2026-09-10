// Client de geo-catalog-api (livraison #429). Jamais d'exception vers le composant.
async function call(base, path, init) {
  try {
    const res = await fetch(`${base}${path}`, init);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (!res.ok) return { error: data?.error || `HTTP ${res.status}` };
    return data ?? { error: "réponse vide" };
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const fetchStatus = (base) => call(base, "/status");
export async function fetchPositions(base, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== "")).toString();
  const d = await call(base, `/positions${qs ? `?${qs}` : ""}`);
  return d?.error ? { positions: [], summary: null, error: d.error } : { positions: d.positions || [], summary: d.summary || null, error: null };
}
export const fetchPosition = (base, id) => call(base, `/positions/${id}`);
export const sync = (base, groups, only) => call(base, "/sync", json("POST", { groups: groups || [], only }));
export const loadCommunes = (base, groups) => call(base, "/referentials/communes/load", json("POST", { groups: groups || [] }));
export const validate = (base, id, groups, note) => call(base, `/positions/${id}/validate`, json("PUT", { groups: groups || [], note }));
export const correct = (base, id, { lat, lon, note }, groups) => call(base, `/positions/${id}/correct`, json("PUT", { lat, lon, note, groups: groups || [] }));
export const reset = (base, id, groups) => call(base, `/positions/${id}/reset`, json("PUT", { groups: groups || [] }));
export const useRef = (base, id, refId, groups) => call(base, `/positions/${id}/refs/${refId}/use`, json("PUT", { groups: groups || [] }));
export const push = (base, id, groups) => call(base, `/positions/${id}/push`, json("POST", { groups: groups || [] }));
export const lookup = (base, label) => call(base, `/referentials/lookup?label=${encodeURIComponent(label)}`);
