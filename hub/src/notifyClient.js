// Client de notify-api (livraison #590) -- tuile « Notifications ». Jeton Keycloak de la session.
async function call(apiBase, token, path, init = {}) {
  try {
    const res = await fetch(`${apiBase}${path}`, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) } });
    const data = await res.json().catch(() => ({}));
    return res.ok ? data : { error: data.error || `HTTP ${res.status}` };
  } catch (e) { return { error: e.message }; }
}
const J = (b) => JSON.stringify(b);
export const fetchActions = (b, t) => call(b, t, "/actions");
export const setActionGroups = (b, t, action, groups) => call(b, t, `/actions/${encodeURIComponent(action)}/groups`, { method: "PUT", body: J({ groups }) });
export const fetchGroups = (b, t) => call(b, t, "/groups");
export const createGroup = (b, t, body) => call(b, t, "/groups", { method: "POST", body: J(body) });
export const saveGroup = (b, t, id, body) => call(b, t, `/groups/${encodeURIComponent(id)}`, { method: "PUT", body: J(body) });
export const deleteGroup = (b, t, id) => call(b, t, `/groups/${encodeURIComponent(id)}`, { method: "DELETE" });
export const fetchBlacklist = (b, t) => call(b, t, "/blacklist");
export const addBlacklist = (b, t, body) => call(b, t, "/blacklist", { method: "POST", body: J(body) });
export const delBlacklist = (b, t, kind, value) => call(b, t, `/blacklist/${kind}/${encodeURIComponent(value)}`, { method: "DELETE" });
export const fetchConsumers = (b, t) => call(b, t, "/consumers");
export const createConsumer = (b, t, body) => call(b, t, "/consumers", { method: "POST", body: J(body) });
export const deleteConsumer = (b, t, name) => call(b, t, `/consumers/${encodeURIComponent(name)}`, { method: "DELETE" });
export const fetchQueue = (b, t, status = "", limit = 100) => call(b, t, `/queue?limit=${limit}${status ? `&status=${status}` : ""}`);
export const fetchQueueItem = (b, t, id) => call(b, t, `/queue/${id}`);
export const queueAct = (b, t, id, verb) => call(b, t, `/queue/${id}/${verb}`, { method: "POST" });
export const releaseHeld = (b, t) => call(b, t, "/queue/release", { method: "POST" });
export const fetchSettings = (b, t) => call(b, t, "/settings");
export const saveSettings = (b, t, body) => call(b, t, "/settings", { method: "PUT", body: J(body) });
export const fetchEvents = (b, t) => call(b, t, "/events");
export const testSend = (b, t, to) => call(b, t, "/test", { method: "POST", body: J({ to }) });
