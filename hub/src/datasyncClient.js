// Client HTTP du module Synchronisation centrale (hub → datasync-api), #652 -- toujours un objet, {error} précis sinon.
async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    if (!res.ok && data.error === undefined) return { error: `Erreur HTTP ${res.status}` };
    return data;
  } catch (e) { return { error: `Serveur datasync injoignable : ${e.message}` }; }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const listSources = (b) => fetchJson(`${b}/sources`);
export const createSource = (b, body) => fetchJson(`${b}/sources`, json("POST", body));
export const updateSource = (b, id, body) => fetchJson(`${b}/sources/${id}`, json("PUT", body));
export const deleteSource = (b, id) => fetchJson(`${b}/sources/${id}`, { method: "DELETE" });
export const rotateToken = (b, id) => fetchJson(`${b}/sources/${id}/rotate-token`, { method: "POST" });
export const sourceLog = (b, id) => fetchJson(`${b}/sources/${id}/log`);
export const profiles = (b) => fetchJson(`${b}/analysis/profiles`);
export const runAnalysis = (b) => fetchJson(`${b}/analysis/run`, { method: "POST" });
export const listLinks = (b) => fetchJson(`${b}/links`);
export const decideLink = (b, id, status, byUser) => fetchJson(`${b}/links/${id}`, json("PUT", { status, by_user: byUser }));
export const createLink = (b, body) => fetchJson(`${b}/links`, json("POST", body));
export const search = (b, q, source, table) => fetchJson(`${b}/search?q=${encodeURIComponent(q)}${source ? `&source=${source}` : ""}${table ? `&table=${encodeURIComponent(table)}` : ""}`);
export const related = (b, sid, table, pk, depth) => fetchJson(`${b}/rows/${sid}/${encodeURIComponent(table)}/${encodeURIComponent(pk)}/related?depth=${depth || 1}`);
export const listRows = (b, sid, table, offset) => fetchJson(`${b}/rows/${sid}/${encodeURIComponent(table)}?offset=${offset || 0}&limit=50`);
