// Client API vers ups-monitor-api (livraison #415) -- tuile UPS.
// Même motif que netprobeClient.js : jamais d'exception vers le composant,
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

export async function fetchUpsStatus(apiBase) {
  return fetchJson(apiBase, "/status");
}

export async function fetchUpsList(apiBase) {
  const data = await fetchJson(apiBase, "/ups");
  return Array.isArray(data) ? data : [];
}

export async function fetchUps(apiBase, upsId) {
  return fetchJson(apiBase, `/ups/${upsId}`);
}

export async function createUps(apiBase, payload) {
  return fetchJson(apiBase, "/ups", json("POST", payload));
}

export async function updateUps(apiBase, upsId, payload) {
  return fetchJson(apiBase, `/ups/${upsId}`, json("PUT", payload));
}

export async function deleteUps(apiBase, upsId) {
  return fetchJson(apiBase, `/ups/${upsId}`, { method: "DELETE" });
}

export async function pollUps(apiBase, upsId) {
  return fetchJson(apiBase, `/ups/${upsId}/poll`, { method: "POST" });
}

export async function testUps(apiBase, payload) {
  return fetchJson(apiBase, "/ups/test", json("POST", payload));
}

export async function fetchUpsReadings(apiBase, upsId, { start, end, limit, fields } = {}) {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (limit) params.set("limit", String(limit));
  if (fields) params.set("fields", "1");
  const qs = params.toString();
  const data = await fetchJson(apiBase, `/ups/${upsId}/readings${qs ? `?${qs}` : ""}`);
  return Array.isArray(data?.readings) ? data.readings : [];
}

export async function fetchUpsSeries(apiBase, upsId, key, { start, end, limit } = {}) {
  const params = new URLSearchParams({ key });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (limit) params.set("limit", String(limit));
  const data = await fetchJson(apiBase, `/ups/${upsId}/series?${params.toString()}`);
  return Array.isArray(data?.points) ? data.points : [];
}
