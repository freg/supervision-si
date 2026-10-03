// Client HTTP du module Tests QA (hub → qa-api), #651 -- toujours un objet JSON, {error} précis sinon.
async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    if (!res.ok && data.error === undefined) return { error: `Erreur HTTP ${res.status}` };
    return data;
  } catch (e) { return { error: `Serveur QA injoignable : ${e.message}` }; }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const getCatalog = (b) => fetchJson(`${b}/catalog`);
export const listSites = (b) => fetchJson(`${b}/sites`);
export const createSite = (b, body) => fetchJson(`${b}/sites`, json("POST", body));
export const updateSite = (b, id, body) => fetchJson(`${b}/sites/${id}`, json("PUT", body));
export const deleteSite = (b, id) => fetchJson(`${b}/sites/${id}`, { method: "DELETE" });
export const probeSite = (b, id) => fetchJson(`${b}/sites/${id}/probe`, { method: "POST" });
export const listScenarios = (b, id) => fetchJson(`${b}/sites/${id}/scenarios`);
export const createScenario = (b, id, body) => fetchJson(`${b}/sites/${id}/scenarios`, json("POST", body));
export const updateScenario = (b, xid, body) => fetchJson(`${b}/scenarios/${xid}`, json("PUT", body));
export const deleteScenario = (b, xid) => fetchJson(`${b}/scenarios/${xid}`, { method: "DELETE" });
export const runScenario = (b, xid, byUser) => fetchJson(`${b}/scenarios/${xid}/run`, json("POST", { by_user: byUser }));
export const listRuns = (b, xid) => fetchJson(`${b}/scenarios/${xid}/runs`);
export const runCampaign = (b, id, kind, byUser) => fetchJson(`${b}/sites/${id}/campaign`, json("POST", { kind, by_user: byUser }));
export const listCampaigns = (b, id) => fetchJson(`${b}/sites/${id}/campaigns`);
export const createTicket = (b, rid, body) => fetchJson(`${b}/runs/${rid}/ticket`, json("POST", body));
export const shotUrl = (b, rid, name) => `${b}/runs/${rid}/shot/${name}`;
