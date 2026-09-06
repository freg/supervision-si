// Client API vers memory-api (livraison #259, tuile "Mémoire" --
// rémanence du tampon de logs Memcached).

async function fetchJson(apiBase, path) {
  try {
    const res = await fetch(`${apiBase}${path}`);
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

export async function fetchStats(apiBase, since) {
  const query = since ? `?since=${encodeURIComponent(since)}` : "";
  const data = await fetchJson(apiBase, `/stats${query}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchServices(apiBase) {
  const data = await fetchJson(apiBase, "/services");
  return Array.isArray(data) ? data : [];
}
export async function fetchEntries(apiBase, { service, level, since, limit } = {}) {
  const params = new URLSearchParams();
  if (service) params.set("service", service);
  if (level) params.set("level", level);
  if (since) params.set("since", since);
  if (limit) params.set("limit", limit);
  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await fetchJson(apiBase, `/entries${query}`);
  return Array.isArray(data) ? data : [];
}
