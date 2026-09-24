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

// -- #586 : tour de contrôle ----------------------------------------------------
export const rebuildService = (apiBase, token, service) => call(apiBase, token, `/services/${encodeURIComponent(service)}/rebuild`, { method: "POST" });
export const reloadGateway = (apiBase, token) => call(apiBase, token, "/gateway/reload", { method: "POST" });
export const fetchSettings = (apiBase, token) => call(apiBase, token, "/settings");
export const saveSettings = (apiBase, token, body) => call(apiBase, token, "/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const fetchEvents = (apiBase, token, limit = 200) => call(apiBase, token, `/events?limit=${limit}`);
export const fetchConfigs = (apiBase, token) => call(apiBase, token, "/configs");
export const fetchConfig = (apiBase, token, id) => call(apiBase, token, `/configs/${encodeURIComponent(id)}`);
export async function saveConfig(apiBase, token, id, items) {
  try {
    const res = await fetch(`${apiBase}/configs/${encodeURIComponent(id)}`, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ data: items }) });
    const data = await res.json().catch(() => ({}));
    return res.ok ? data : { error: data.error || `HTTP ${res.status}`, errors: data.errors || [], warnings: data.warnings || [] };
  } catch (e) {
    return { error: e.message };
  }
}
export const fetchJobs = (apiBase, token) => call(apiBase, token, "/jobs");
export const fetchJob = (apiBase, token, id) => call(apiBase, token, `/jobs/${encodeURIComponent(id)}`);
export const fetchDeliveries = (apiBase, token) => call(apiBase, token, "/deliveries");
export const applyDelivery = (apiBase, token, id, allowDowngrade = false) => call(apiBase, token, `/deliveries/${encodeURIComponent(id)}/apply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ allow_downgrade: allowDowngrade }) });

/** Envoi d'un zip de livraison avec progression (XMLHttpRequest : fetch n'expose pas l'avancement de l'envoi). */
export function uploadDelivery(apiBase, token, file, onProgress) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiBase}/deliveries`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText || "{}"); } catch { /* réponse non JSON */ }
      resolve(xhr.status >= 200 && xhr.status < 300 ? data : { error: data.error || `HTTP ${xhr.status}` });
    };
    xhr.onerror = () => resolve({ error: "envoi interrompu" });
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}

// -- #593 : santé de l'hôte -------------------------------------------------------
export const fetchHost = (apiBase, token, refresh = false) => call(apiBase, token, `/host${refresh ? "?refresh=1" : ""}`);
export const pruneHost = (apiBase, token, body) => call(apiBase, token, "/host/prune", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
/** Bandeau : sans jeton (lampe + texte seulement). */
export async function fetchHostPublic(apiBase) {
  try {
    const res = await fetch(`${apiBase}/host/public`);
    return res.ok ? await res.json() : null;
  } catch { return null; }
}
