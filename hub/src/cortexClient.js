// Client API vers cortex-api (livraison #462) -- même motif que les autres
// clients : jamais d'exception vers le composant.
async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    if (!res.ok && !data.error) return { ...data, error: `HTTP ${res.status}` };
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
export const fetchCortexStatus = (b) => fetchJson(b, "/status");
export const fetchIncidents = (b, state = "open") => fetchJson(b, `/incidents?state=${state}`);
export const fetchIncident = (b, key) => fetchJson(b, `/incidents/${encodeURIComponent(key)}`);
export const ackIncident = (b, key, by) => fetchJson(b, `/incidents/${encodeURIComponent(key)}/ack`, json("POST", { by }));
export const closeIncident = (b, key, by) => fetchJson(b, `/incidents/${encodeURIComponent(key)}/close`, json("POST", { by }));
export const feedbackIncident = (b, key, payload) => fetchJson(b, `/incidents/${encodeURIComponent(key)}/feedback`, json("POST", payload));
export const fetchEntities = (b, q) => fetchJson(b, `/entities${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const fetchEntity = (b, key) => fetchJson(b, `/entities/${encodeURIComponent(key)}`);
export const fetchEvents = (b, state = "open") => fetchJson(b, `/events?state=${state}&limit=300`);
export const fetchPrinciples = (b) => fetchJson(b, "/principles");
export const fetchCortexStats = (b, days = 7) => fetchJson(b, `/stats?days=${days}`);
export const fetchRuns = (b) => fetchJson(b, "/runs?limit=10");
export const runCollect = (b, groups) => fetchJson(b, "/collect", json("POST", { groups }));
// #463 : graphe d'architecture, routes, changements
export const fetchGraph = (b) => fetchJson(b, "/graph");
export const fetchRoutes = (b) => fetchJson(b, "/routes");
export const fetchChanges = (b, since) => fetchJson(b, since ? `/changes?since=${encodeURIComponent(since)}&limit=300` : "/changes?limit=300");
// #464 : lieux, positions, fiche d'intervention, couches carto
export const fetchPositions = (b, provenance) => fetchJson(b, provenance ? `/positions?provenance=${encodeURIComponent(provenance)}` : "/positions");
export const fetchPositionsQueue = (b) => fetchJson(b, "/positions/queue");
export const resolvePositions = (b, groups) => fetchJson(b, "/positions/resolve", json("POST", { groups }));
export const fetchPlaces = (b) => fetchJson(b, "/places");
export const savePlaceNote = (b, key, payload) => fetchJson(b, `/places/${encodeURIComponent(key)}`, json("PUT", payload));
export const fetchIntervention = (b, key) => fetchJson(b, `/entities/${encodeURIComponent(key)}/intervention`);
export const fetchLayers = (b) => fetchJson(b, "/layers");
// #465 : règles apprises, annonces, dérives
export const fetchRules = (b) => fetchJson(b, "/rules");
export const ruleAction = (b, id, action, payload) => fetchJson(b, `/rules/${encodeURIComponent(id)}/${action}`, json("POST", payload));
export const fetchPredictions = (b, pendingOnly = false) => fetchJson(b, `/predictions?limit=200${pendingOnly ? "&pending=1" : ""}`);
export const fetchDrifts = (b) => fetchJson(b, "/drifts");
export const fetchSamples = (b, entity, metric) => fetchJson(b, `/samples?entity=${encodeURIComponent(entity)}&metric=${encodeURIComponent(metric)}`);
export const runLearn = (b, groups) => fetchJson(b, "/learn", json("POST", { groups }));
// #466 : politiques, silences, notifications, KPI
export const fetchPolicies = (b) => fetchJson(b, "/policies");
export const savePolicy = (b, policyObj, by, groups) => fetchJson(b, "/policies", json("PUT", { policy: policyObj, by, groups }));
export const deletePolicy = (b, id, by, groups) => fetchJson(b, `/policies/${encodeURIComponent(id)}`, json("DELETE", { by, groups }));
export const previewPolicies = (b) => fetchJson(b, "/policies/preview");
export const fetchSilences = (b) => fetchJson(b, "/silences");
export const addSilence = (b, payload) => fetchJson(b, "/silences", json("POST", payload));
export const deleteSilence = (b, id, by, groups) => fetchJson(b, `/silences/${id}`, json("DELETE", { by, groups }));
export const fetchNotifications = (b) => fetchJson(b, "/notifications?limit=100");
export const notifyNow = (b, groups) => fetchJson(b, "/notify", json("POST", { groups }));
export const fetchKpis = (b, days = 30) => fetchJson(b, `/kpis?days=${days}`);
