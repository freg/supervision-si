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
