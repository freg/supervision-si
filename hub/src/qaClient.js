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
export const hubTour = (b, id, body) => fetchJson(`${b}/sites/${id}/hub-tour`, json("POST", body));   // #721
export const setReference = (b, xid, runId) => fetchJson(`${b}/scenarios/${xid}/reference`, json("PUT", { run_id: runId }));   // #727
export const runDiff = (b, rid, against) => fetchJson(`${b}/runs/${rid}/diff${against ? `?against=${against}` : ""}`);       // #727
// #728 : maquettes en étapes (variantes CSS injectées dans le navigateur de test, présentation, décision → ticket évolution)
export const listMockups = (b, xid) => fetchJson(`${b}/scenarios/${xid}/mockups`);
export const createMockup = (b, xid, body) => fetchJson(`${b}/scenarios/${xid}/mockups`, json("POST", body));
export const getMockup = (b, mid) => fetchJson(`${b}/mockups/${mid}`);
export const updateMockup = (b, mid, body) => fetchJson(`${b}/mockups/${mid}`, json("PUT", body));
export const deleteMockup = (b, mid) => fetchJson(`${b}/mockups/${mid}`, { method: "DELETE" });
export const renderMockup = (b, mid, variant, byUser) => fetchJson(`${b}/mockups/${mid}/render${variant === undefined ? "" : `?variant=${variant}`}`, json("POST", { by_user: byUser }));
export const decideMockup = (b, mid, body) => fetchJson(`${b}/mockups/${mid}/decision`, json("POST", body));
export const runDesign = (b, rid) => fetchJson(`${b}/runs/${rid}/design`);                      // #729
export const clearTarget = (b, xid) => fetchJson(`${b}/scenarios/${xid}/target`, { method: "DELETE" });
