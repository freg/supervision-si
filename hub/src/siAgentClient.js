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

// #432 : vue réseau passive de chaque agent (voisins, pairs, sous-réseaux)
export async function fetchNetviews(apiBase, site) {
  const data = await fetchJson(apiBase, `/netview${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return Array.isArray(data?.netviews) ? data.netviews : [];
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
// #446 : fichier .cmd silencieux (secret inclus) généré par le central
export const installCmdUrl = (apiBase, agentId) => `${apiBase}/agents/${encodeURIComponent(agentId)}/install.cmd`;

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

// #422 : blocage, journal d'événements, synthèse, notifications
export const blockFleet = (apiBase, reason) => fetchJson(apiBase, "/block", json("POST", { reason }));
export const unblockFleet = (apiBase) => fetchJson(apiBase, "/unblock", json("POST", {}));
export const blockAgent = (apiBase, agentId, reason) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/block`, json("POST", { reason }));
export const unblockAgent = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/unblock`, json("POST", {}));
export const setPluginBlocked = (apiBase, agentId, pluginId, blocked, reason) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/plugins/${encodeURIComponent(pluginId)}`, json("PUT", { blocked, reason }));

export async function fetchEvents(apiBase, { agent, severity, minSeverity, kind, since, limit = 200 } = {}) {
  const q = new URLSearchParams();
  if (agent) q.set("agent", agent);
  if (severity) q.set("severity", severity);
  if (minSeverity) q.set("min_severity", minSeverity);
  if (kind) q.set("kind", kind);
  if (since) q.set("since", since);
  if (limit) q.set("limit", String(limit));
  const data = await fetchJson(apiBase, `/events?${q.toString()}`);
  return Array.isArray(data?.events) ? data.events : [];
}
export const fetchEventsSummary = (apiBase, hours = 24) => fetchJson(apiBase, `/events/summary?hours=${hours}`);
export const testNotifications = (apiBase) => fetchJson(apiBase, "/notifications/test", json("POST", {}));
