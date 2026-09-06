// Client API vers netmap-orchestrator-api (livraison #388-390).
// Même motif que les autres clients hub -- renvoie toujours le corps
// JSON, même en cas d'erreur.

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

export async function fetchRules(apiBase) {
  const data = await fetchJson(apiBase, "/rules");
  return Array.isArray(data.rules) ? data.rules : [];
}

export async function fetchSuggestions(apiBase, { status, ruleName } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (ruleName) params.set("rule_name", ruleName);
  const query = params.toString();
  const data = await fetchJson(apiBase, `/suggestions${query ? `?${query}` : ""}`);
  return Array.isArray(data.suggestions) ? data.suggestions : [];
}

export async function fetchSummary(apiBase) {
  const data = await fetchJson(apiBase, "/summary");
  return data && data.by_status ? data.by_status : {};
}

export async function runAllRules(apiBase) {
  return fetchJson(apiBase, "/run", { method: "POST" });
}

export async function runOneRule(apiBase, ruleName) {
  return fetchJson(apiBase, `/run/${encodeURIComponent(ruleName)}`, { method: "POST" });
}

export async function setSuggestionStatus(apiBase, suggestionId, status) {
  return fetchJson(apiBase, `/suggestions/${suggestionId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}
