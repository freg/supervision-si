// Client API vers si-agent-api (livraison #421) -- tuile « Agents hôtes ».
// Même motif que upsClient.js : jamais d'exception vers le composant,
// toujours un objet (`{error}` en cas d'échec) ou une liste vide.

async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (data === null) {
      return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    }
    if (!res.ok && data && typeof data === "object" && !data.error) {
      return { ...data, error: `HTTP ${res.status}` };
    }
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

export const fetchSiAgentStatus = (apiBase) => fetchJson(apiBase, "/status");

export async function fetchFleet(apiBase, site) {
  const data = await fetchJson(apiBase, `/fleet${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return Array.isArray(data?.agents) ? data.agents : [];
}

export async function fetchFleetRisks(apiBase) {
  const data = await fetchJson(apiBase, "/risks");
  return Array.isArray(data?.risks) ? data.risks : [];
}

export const fetchAgent = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}`);
export const createAgent = (apiBase, body) => fetchJson(apiBase, "/agents", json("POST", body));
export const updateAgent = (apiBase, agentId, body) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}`, json("PUT", body));
export const deleteAgent = (apiBase, agentId, purge) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}${purge ? "?purge=true" : ""}`, { method: "DELETE" });
export const rotateAgentSecret = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/rotate-secret`, json("POST", {}));
export const fetchInstall = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/install`);

export async function fetchAgentMeasurements(apiBase, agentId, { task, limit = 200, since } = {}) {
  const q = new URLSearchParams();
  if (task) q.set("task", task);
  if (limit) q.set("limit", String(limit));
  if (since) q.set("since", since);
  const data = await fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/measurements?${q.toString()}`);
  return Array.isArray(data?.measurements) ? data.measurements : [];
}

export async function fetchPlugins(apiBase) {
  const data = await fetchJson(apiBase, "/plugins");
  return Array.isArray(data?.plugins) ? data.plugins : [];
}
export const fetchPlugin = (apiBase, pluginId) => fetchJson(apiBase, `/plugins/${encodeURIComponent(pluginId)}?body=true`);
export const savePlugin = (apiBase, body) => fetchJson(apiBase, "/plugins", json("POST", body));
export const deletePlugin = (apiBase, pluginId) => fetchJson(apiBase, `/plugins/${encodeURIComponent(pluginId)}`, { method: "DELETE" });

export const assignPlugin = (apiBase, agentId, pluginId, enabled = true) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/plugins/${encodeURIComponent(pluginId)}`, json("PUT", { enabled }));
export const unassignPlugin = (apiBase, agentId, pluginId) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/plugins/${encodeURIComponent(pluginId)}`, { method: "DELETE" });

export const sendCommand = (apiBase, agentId, type, params) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/commands`, json("POST", { type, params: params || {} }));
export async function fetchCommands(apiBase, agentId) {
  const data = await fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/commands?limit=30`);
  return Array.isArray(data?.commands) ? data.commands : [];
}
