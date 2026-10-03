// Client HTTP du module Groupware (hub → groupware-api), #664 -- toujours un objet, {error} précis sinon.
async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    if (!res.ok && data.error === undefined) return { error: `Erreur HTTP ${res.status}` };
    return data;
  } catch (e) { return { error: `Serveur groupware injoignable : ${e.message}` }; }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const q = (o) => Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
export const listGrants = (b, user, groups, app) => fetchJson(`${b}/grants?${q({ user, groups: (groups || []).join(","), app })}`);
export const createGrant = (b, body) => fetchJson(`${b}/grants`, json("POST", body));
export const deleteGrant = (b, id, actor) => fetchJson(`${b}/grants/${id}?actor=${encodeURIComponent(actor || "")}`, { method: "DELETE" });
export const listCategories = (b, app) => fetchJson(`${b}/categories?${q({ app })}`);
export const createCategory = (b, body) => fetchJson(`${b}/categories`, json("POST", body));
export const updateCategory = (b, id, body) => fetchJson(`${b}/categories/${id}`, json("PUT", body));
export const deleteCategory = (b, id) => fetchJson(`${b}/categories/${id}`, { method: "DELETE" });
export const listLinks = (b, app, id) => fetchJson(`${b}/links?${q({ app, id })}`);
export const createLink = (b, body) => fetchJson(`${b}/links`, json("POST", body));
export const deleteLink = (b, id) => fetchJson(`${b}/links/${id}`, { method: "DELETE" });
export const getPrefs = (b, app, user, groups) => fetchJson(`${b}/prefs?${q({ app, user, groups: (groups || []).join(",") })}`);
export const rawPrefs = (b) => fetchJson(`${b}/prefs?raw=1`);
export const putPref = (b, body) => fetchJson(`${b}/prefs`, json("PUT", body));
export const deletePref = (b, body) => fetchJson(`${b}/prefs`, json("DELETE", body));
export const davMe = (b, user) => fetchJson(`${b}/dav/me?user=${encodeURIComponent(user)}`);
export const rebuildDav = (b) => fetchJson(`${b}/dav/rights/rebuild`, { method: "POST" });
export const groupwareHealth = (b) => fetchJson(`${b}/health`);
