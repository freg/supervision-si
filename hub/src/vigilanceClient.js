// Client API vers vigilance-api (livraison #262, automates d'analyse
// cyber-vigilance/santé du parc).

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

export async function fetchSignals(apiBase, { signalType, severity, deviceMac } = {}) {
  const params = new URLSearchParams();
  if (signalType) params.set("signal_type", signalType);
  if (severity) params.set("severity", severity);
  if (deviceMac) params.set("device_mac", deviceMac);
  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await fetchJson(apiBase, `/signals${query}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchSummary(apiBase) {
  const data = await fetchJson(apiBase, "/summary");
  return Array.isArray(data) ? data : [];
}
export async function triggerAnalysis(apiBase) {
  return fetchJson(apiBase, "/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
}
