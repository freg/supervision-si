// #903 : client du blog du hub (service messages-api, jeton Keycloak du hub).
import { getApiToken } from "./apiAuth.js";

const BASE = import.meta.env.VITE_MESSAGES_API_BASE_URL || "/api/messages";

async function req(path, init = {}) {
  const token = getApiToken();
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(init.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init.body ? { "Content-Type": "application/json" } : {}) },
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `erreur ${r.status}`);
  return d;
}

export const fetchMessages = () => req("/messages");
export const postMessage = (m) => req("/messages", { method: "POST", body: JSON.stringify(m) });
export const deleteMessage = (id) => req(`/messages/${encodeURIComponent(id)}`, { method: "DELETE" });
