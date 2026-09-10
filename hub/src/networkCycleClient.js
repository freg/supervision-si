// Client API vers les services du cycle agile réseau -- agrège les
// appels vers netmap-orchestrator, network-agent, netprobe, snmp,
// ssh-tunnels, vigilance et backup-restore pour présenter un état
// consolidé de chaque étape du cycle.

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

// --- Décider : suggestions de l'orchestrateur réseau ---
export async function fetchOrchestratorSummary(apiBase) {
  const data = await fetchJson(apiBase, "/summary");
  if (data.error) return data;
  return data;
}
export async function fetchOrchestratorSuggestions(apiBase, status = "open") {
  const data = await fetchJson(apiBase, `/suggestions${status ? `?status=${status}` : ""}`);
  return Array.isArray(data) ? data : (data?.suggestions || []);
}

// --- Explorer : état de l'agent réseau ---
export async function fetchCaptureStatus(apiBase) {
  return await fetchJson(apiBase, "/capture/status");
}
export async function fetchSites(apiBase) {
  const data = await fetchJson(apiBase, "/sites");
  return Array.isArray(data) ? data : (data?.sites || []);
}

// --- Déployer : tunnels SSH ---
export async function fetchTunnels(apiBase) {
  const data = await fetchJson(apiBase, "/tunnels");
  return Array.isArray(data) ? data : (data?.tunnels || []);
}
export async function fetchConnections(apiBase) {
  const data = await fetchJson(apiBase, "/connections");
  return Array.isArray(data) ? data : (data?.connections || []);
}

// --- Déployer : SNMP ---
export async function fetchSnmpTargets(apiBase) {
  const data = await fetchJson(apiBase, "/targets");
  return Array.isArray(data) ? data : (data?.targets || []);
}

// --- Mesurer : sondes réseau ---
export async function fetchLatestSamples(apiBase) {
  const data = await fetchJson(apiBase, "/smokeping/latest");
  return Array.isArray(data?.latest) ? data.latest : [];
}
export async function fetchProbeConfigs(apiBase) {
  const data = await fetchJson(apiBase, "/probe-config");
  return Array.isArray(data?.configs) ? data.configs : [];
}

// --- Apprendre : vigilance ---
export async function fetchVigilanceSummary(apiBase) {
  const data = await fetchJson(apiBase, "/summary");
  return Array.isArray(data) ? data : [];
}
export async function fetchSignals(apiBase, severity) {
  const qs = severity ? `?severity=${severity}` : "";
  const data = await fetchJson(apiBase, `/signals${qs}`);
  return Array.isArray(data) ? data : [];
}

// --- Apprendre : couverture backup ---
export async function fetchCoverage(apiBase) {
  return await fetchJson(apiBase, "/coverage");
}
