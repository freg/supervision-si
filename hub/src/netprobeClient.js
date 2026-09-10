// Client API vers netprobe-api (livraisons #295/#297) -- collecteur
// d'IP, système de contrôle, sondage smokeping.

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
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

// --- Collecteur d'IP ---
export async function fetchTargets(apiBase, activeOnly = false) {
  const data = await fetchJson(apiBase, `/targets${activeOnly ? "?active_only=true" : ""}`);
  return Array.isArray(data?.targets) ? data.targets : [];
}
export async function addTarget(apiBase, ipAddress, label) {
  return fetchJson(apiBase, "/targets", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ip_address: ipAddress, label: label || null }),
  });
}
export async function setTargetActive(apiBase, targetId, active) {
  return fetchJson(apiBase, `/targets/${targetId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active }),
  });
}
export async function deleteTarget(apiBase, targetId) {
  return fetchJson(apiBase, `/targets/${targetId}`, { method: "DELETE" });
}
export async function importFromNetworkAgent(apiBase) {
  return fetchJson(apiBase, "/targets/import-from-network-agent", { method: "POST" });
}

// --- Système de contrôle ---
export async function fetchProbeConfigs(apiBase, probeType) {
  const data = await fetchJson(apiBase, `/probe-config${probeType ? `?probe_type=${probeType}` : ""}`);
  return Array.isArray(data?.configs) ? data.configs : [];
}
export async function setProbeConfig(apiBase, { probeType, enabled, frequencySeconds, scheduleStartHour, scheduleEndHour, targetId }) {
  return fetchJson(apiBase, "/probe-config", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      probe_type: probeType, enabled,
      frequency_seconds: frequencySeconds === "" || frequencySeconds == null ? null : Number(frequencySeconds),
      schedule_start_hour: scheduleStartHour === "" || scheduleStartHour == null ? null : Number(scheduleStartHour),
      schedule_end_hour: scheduleEndHour === "" || scheduleEndHour == null ? null : Number(scheduleEndHour),
      target_id: targetId || null,
    }),
  });
}
export async function setProbeConfigEnabled(apiBase, configId, enabled) {
  return fetchJson(apiBase, `/probe-config/${configId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}
export async function deleteProbeConfig(apiBase, configId) {
  return fetchJson(apiBase, `/probe-config/${configId}`, { method: "DELETE" });
}

// --- Smokeping ---
export async function fetchLatestSamples(apiBase) {
  const data = await fetchJson(apiBase, "/smokeping/latest");
  return Array.isArray(data?.latest) ? data.latest : [];
}
export async function fetchSamples(apiBase, targetId, limit = 100) {
  const data = await fetchJson(apiBase, `/smokeping/samples?target_id=${targetId}&limit=${limit}`);
  return Array.isArray(data?.samples) ? data.samples : [];
}

// --- nmap à la demande (livraison #302) ---
export async function scanTarget(apiBase, targetId, ports) {
  return fetchJson(apiBase, "/nmap/scan", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_id: targetId, ports: ports || null }),
  });
}
export async function fetchNmapScans(apiBase, targetId, limit = 50) {
  const data = await fetchJson(apiBase, `/nmap/scans?target_id=${targetId}&limit=${limit}`);
  return Array.isArray(data?.scans) ? data.scans : [];
}

// --- tcpdump partagé, sans stockage (livraison #305) ---
export async function tcpdumpCapture(apiBase, interfaceName, packetCount) {
  return fetchJson(apiBase, "/tcpdump/capture", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interface: interfaceName || null, packet_count: packetCount || undefined }),
  });
}

// --- Analyseur multi-scripts (livraison #307) ---
export async function fetchAnalysisResults(apiBase, targetId, limit = 100) {
  const qs = targetId ? `?target_id=${targetId}&limit=${limit}` : `?limit=${limit}`;
  const data = await fetchJson(apiBase, `/analysis/results${qs}`);
  return Array.isArray(data?.results) ? data.results : [];
}
export async function runAnalysis(apiBase, analyzerName) {
  return fetchJson(apiBase, "/analysis/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analyzer_name: analyzerName || null }),
  });
}

// --- Sondes distribuées (livraison #407, items 45/47/48) -- flotte de
// sondes/collecteurs Raspberry Pi et mesures remontées par les
// collecteurs de site. Voir netprobe/agent/README.md.
export async function fetchAgents(apiBase, site) {
  const q = site ? `?site=${encodeURIComponent(site)}` : "";
  const data = await fetchJson(apiBase, `/agents${q}`);
  return Array.isArray(data?.agents) ? data.agents : [];
}
export async function createAgent(apiBase, { agentId, site, role, label, tasks }) {
  return fetchJson(apiBase, "/agents", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, site, role, label, tasks }),
  });
}
export async function updateAgent(apiBase, agentId, patch) {
  return fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
  });
}
export async function deleteAgent(apiBase, agentId, purge = false) {
  return fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}?purge=${purge ? "true" : "false"}`, { method: "DELETE" });
}
export async function rotateAgentSecret(apiBase, agentId) {
  return fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/rotate-secret`, { method: "POST" });
}
export async function fetchAgentsLatest(apiBase, site) {
  const q = site ? `?site=${encodeURIComponent(site)}` : "";
  const data = await fetchJson(apiBase, `/agents/latest${q}`);
  return Array.isArray(data?.latest) ? data.latest : [];
}
export async function fetchAgentMeasurements(apiBase, agentId, task, limit = 300) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (task) q.set("task", task);
  const data = await fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/measurements?${q.toString()}`);
  return Array.isArray(data?.measurements) ? data.measurements : [];
}
