// Client de services-api (livraison #584) -- feu tricolore et redémarrage
// des conteneurs du hub. Jeton Keycloak de la session en Authorization.
async function call(apiBase, accessToken, path, init = {}) {
  try {
    const res = await fetch(`${apiBase}${path}`, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${accessToken}` } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { error: data.error || `HTTP ${res.status}` };
    return data;
  } catch (e) {
    return { error: e.message };
  }
}

export const fetchServices = (apiBase, token, refresh = false) => call(apiBase, token, `/services${refresh ? "?refresh=1" : ""}`);
export const restartService = (apiBase, token, service) => call(apiBase, token, `/services/${encodeURIComponent(service)}/restart`, { method: "POST" });
export const restartRed = (apiBase, token) => call(apiBase, token, "/services/restart-red", { method: "POST" });
export const fetchServiceLogs = (apiBase, token, service, tail = 80) => call(apiBase, token, `/services/${encodeURIComponent(service)}/logs?tail=${tail}`);
