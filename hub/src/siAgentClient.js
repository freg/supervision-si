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

// #487 : hyperviseurs Proxmox (dernière mesure du plugin par agent)
export async function fetchProxmox(apiBase, site) {
  const data = await fetchJson(apiBase, `/proxmox${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return Array.isArray(data?.proxmox) ? data.proxmox : [];
}

// #643 : panneau Observabilité réseau -- dernière mesure dns-observe (105) et
// resource-access (106) par agent, en un seul appel.
export async function fetchNetworkObservability(apiBase, site) {
  const data = await fetchJson(apiBase, `/network-observability${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return { dns: Array.isArray(data?.dns) ? data.dns : [], resources: Array.isArray(data?.resources) ? data.resources : [] };
}

// #504 : disponibilité des VM d'un hyperviseur (échantillons du plugin)
export const fetchProxmoxHistory = (apiBase, agentId, hours = 168) =>
  fetchJson(apiBase, `/proxmox/history?agent_id=${encodeURIComponent(agentId)}&hours=${hours}`);

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
/** #522 : déploiement contrôlé des mises à jour d'agents. */
export const fetchUpdates = (apiBase) => fetchJson(apiBase, "/updates");
export const saveUpdates = (apiBase, settings, actor) => fetchJson(apiBase, "/updates", json("PUT", { ...settings, actor }));
export const applyUpdates = (apiBase, agentId, actor) => fetchJson(apiBase, "/updates/apply", json("POST", { agent_id: agentId || null, actor }));

export const fetchEventsSummary = (apiBase, hours = 24) => fetchJson(apiBase, `/events/summary?hours=${hours}`);
export const testNotifications = (apiBase) => fetchJson(apiBase, "/notifications/test", json("POST", {}));

// #572 : contrôle d'une VM Proxmox par l'agent (commande vm_action) et suivi du résultat
export const vmAction = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "vm_action", params);
// #613 : poste -- alimentation (reboot/shutdown/cancel), réveil par un agent du même segment, lanceurs, chien de garde
export const powerAction = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "power_action", params);
export const wakeOnLan = (apiBase, viaAgentId, params) => sendCommand(apiBase, viaAgentId, "wol", params);
export const startupAction = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "startup_action", params);
export const watchdogConfig = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "watchdog_config", params);
export const benchCommand = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "bench", params);  // #616
export const imageHost = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "image_host", params);  // #621
export const browsePath = (apiBase, agentId, path) => sendCommand(apiBase, agentId, "browse", path ? { path } : {});  // #627
export const imageTransfer = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "image_transfer", params);  // #634
export const fetchImages = (apiBase, site) => fetchJson(apiBase, `/images${site ? `?site=${encodeURIComponent(site)}` : ""}`);  // #634
export const fetchWebAudit = (apiBase, site) => fetchJson(apiBase, `/web-audit${site ? `?site=${encodeURIComponent(site)}` : ""}`);  // #617
export const fetchCommand = (apiBase, cid) => fetchJson(apiBase, `/commands/${encodeURIComponent(cid)}`);

/** #607 : filtres d'alertes (catégories, groupes de règles), test à blanc ; `include_muted` sur le journal. */
export const fetchAlertFilters = (apiBase) => fetchJson(apiBase, "/alert-filters");
export const saveAlertFilters = (apiBase, groups) => fetchJson(apiBase, "/alert-filters", json("PUT", { groups }));
export const testAlertFilter = (apiBase, body) => fetchJson(apiBase, "/alert-filters/test", json("POST", body));
export async function fetchEventsMuted(apiBase, limit = 300) {
  const data = await fetchJson(apiBase, `/events?include_muted=1&limit=${limit}`);
  return Array.isArray(data?.events) ? data.events : [];
}

// #653 : plans PRA / opérations PVE (séquences de vm_action exécutées par le central)
export const fetchPraPlans = (apiBase) => fetchJson(apiBase, "/pra/plans");
export const createPraPlan = (apiBase, body) => fetchJson(apiBase, "/pra/plans", json("POST", body));
export const updatePraPlan = (apiBase, id, body) => fetchJson(apiBase, `/pra/plans/${id}`, json("PUT", body));
export const deletePraPlan = (apiBase, id) => fetchJson(apiBase, `/pra/plans/${id}`, { method: "DELETE" });
export const runPraPlan = (apiBase, id, mode, actor) => fetchJson(apiBase, `/pra/plans/${id}/run`, json("POST", { mode, actor }));
export const fetchPraRun = (apiBase, rid) => fetchJson(apiBase, `/pra/runs/${rid}`);
export const fetchPraRuns = (apiBase, id) => fetchJson(apiBase, `/pra/plans/${id}/runs`);
// #654 : rôles (bascule « celui qui répond ») et vérification
export const fetchPraRoles = (apiBase) => fetchJson(apiBase, "/pra/roles");
export const createPraRole = (apiBase, body) => fetchJson(apiBase, "/pra/roles", json("POST", body));
export const updatePraRole = (apiBase, id, body) => fetchJson(apiBase, `/pra/roles/${id}`, json("PUT", body));
export const deletePraRole = (apiBase, id) => fetchJson(apiBase, `/pra/roles/${id}`, { method: "DELETE" });
export const switchPraRole = (apiBase, id, to, actor) => fetchJson(apiBase, `/pra/roles/${id}/switch`, json("POST", { to, actor }));
export const checkPraRole = (apiBase, id) => fetchJson(apiBase, `/pra/roles/${id}/check`, { method: "POST" });
// #658 : migration serveur -> virtualisation (plan généré), transitions (Reprendre / Abandonner), retour en arrière
export const previewMigration = (apiBase, body) => fetchJson(apiBase, "/pra/migrations/plan", json("POST", body));
export const resumePraRun = (apiBase, rid) => fetchJson(apiBase, `/pra/runs/${rid}/resume`, { method: "POST" });
export const abortPraRun = (apiBase, rid, rollback, actor) => fetchJson(apiBase, `/pra/runs/${rid}/abort`, json("POST", { rollback, actor }));
export const rollbackPraRun = (apiBase, rid, actor) => fetchJson(apiBase, `/pra/runs/${rid}/rollback`, json("POST", { actor }));
