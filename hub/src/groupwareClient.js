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
// #665 : carnet d'adresses (CardDAV via le compte de service, partages vérifiés par l'API)
export const listAddressbooks = (b, user, groups) => fetchJson(`${b}/addressbooks?${q({ user, groups: (groups || []).join(",") })}`);
export const createAddressbook = (b, body) => fetchJson(`${b}/addressbooks`, json("POST", body));
export const listContacts = (b, user, groups, query, owner, book) => fetchJson(`${b}/contacts?${q({ user, groups: (groups || []).join(","), q: query, owner, book })}`);
export const createContact = (b, body) => fetchJson(`${b}/contacts`, json("POST", body));
export const updateContact = (b, owner, book, uid, body) => fetchJson(`${b}/contacts/${encodeURIComponent(owner)}/${encodeURIComponent(book)}/${encodeURIComponent(uid)}`, json("PUT", body));
export const deleteContact = (b, owner, book, uid, user) => fetchJson(`${b}/contacts/${encodeURIComponent(owner)}/${encodeURIComponent(book)}/${encodeURIComponent(uid)}?user=${encodeURIComponent(user)}`, { method: "DELETE" });
// #666 : agenda, disponibilités, ressources
export const listCalendars = (b, user, groups) => fetchJson(`${b}/calendars?${q({ user, groups: (groups || []).join(",") })}`);
export const createCalendar = (b, body) => fetchJson(`${b}/calendars`, json("POST", body));
export const listEvents = (b, user, groups, from, to, owner, book) => fetchJson(`${b}/events?${q({ user, groups: (groups || []).join(","), from, to, owner, book })}`);
export const createEvent = (b, body) => fetchJson(`${b}/events`, json("POST", body));
export const updateEvent = (b, owner, book, uid, body) => fetchJson(`${b}/events/${encodeURIComponent(owner)}/${encodeURIComponent(book)}/${encodeURIComponent(uid)}`, json("PUT", body));
export const deleteEvent = (b, owner, book, uid, user, admin) => fetchJson(`${b}/events/${encodeURIComponent(owner)}/${encodeURIComponent(book)}/${encodeURIComponent(uid)}?${q({ user, admin: admin ? 1 : "" })}`, { method: "DELETE" });
export const freeBusy = (b, users, resources, from, to) => fetchJson(`${b}/freebusy?${q({ users: (users || []).join(","), resources: (resources || []).join(","), from, to })}`);
export const listResources = (b) => fetchJson(`${b}/resources`);
export const createResource = (b, body) => fetchJson(`${b}/resources`, json("POST", body));
export const deleteResource = (b, slug) => fetchJson(`${b}/resources/${encodeURIComponent(slug)}`, { method: "DELETE" });
