// Client API vers si-proxy-admin-api (livraison #454) -- tuile « Bastion ».
// Même motif que siAgentClient.js (jamais d'exception vers le composant),
// MAIS chaque appel porte le jeton d'accès Keycloak de la personne
// (`Authorization: Bearer`) : le pont le vérifie réellement et n'agit que
// pour SI_PROXY_ADMIN_USERS. 401/403 remontent en `{error, status}`.

async function fetchJson(apiBase, path, token, options = {}) {
  try {
    const headers = { ...(options.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${apiBase}${path}`, { ...options, headers });
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})`, status: res.status };
    if (!res.ok) return { ...data, error: data.error || `HTTP ${res.status}`, status: res.status };
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

export const fetchWhoami = (apiBase, token) => fetchJson(apiBase, "/whoami", token);
export const fetchProxyStatus = (apiBase, token) => fetchJson(apiBase, "/status", token);
export const fetchProxySummary = (apiBase, token, hours = 24) => fetchJson(apiBase, `/summary?hours=${hours}`, token);
export async function fetchProxyAudit(apiBase, token, limit = 200) {
  const d = await fetchJson(apiBase, `/audit?limit=${limit}`, token);
  if (d?.error) return d;
  return { audit: Array.isArray(d?.audit) ? d.audit : [] };
}
export const killProxySession = (apiBase, token, sid) => fetchJson(apiBase, `/sessions/${encodeURIComponent(sid)}/kill`, token, { method: "POST" });
export const disableProxy = (apiBase, token) => fetchJson(apiBase, "/disable", token, { method: "POST" });
export const enableProxy = (apiBase, token) => fetchJson(apiBase, "/enable", token, { method: "POST" });
export const unbanProxyIp = (apiBase, token, ip) => fetchJson(apiBase, `/unban/${encodeURIComponent(ip)}`, token, { method: "POST" });
