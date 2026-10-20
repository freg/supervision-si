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
export const fetchSms = (b, t) => call(b, t, "/sms/journal");   // #787 : SMS internes
export const sendSms = (b, t, to, text) => call(b, t, "/sms/envoyer", { method: "POST", body: J({ to, text }) });
export const smsAct = (b, t, id, verb) => call(b, t, `/sms/${id}/${verb}`, { method: "POST" });
// #796 : alertes poussées (Web Push) sur cet appareil
export const fetchPushKey = (b) => fetch(`${b}/push/key`).then((r) => r.json()).catch((e) => ({ error: e.message }));
export const subscribePush = (b, t, subscription, label, minSeverity) => call(b, t, "/push/subscribe", { method: "POST", body: J({ subscription, label, min_severity: minSeverity }) });
export const unsubscribePush = (b, t, endpoint) => call(b, t, "/push/subscribe", { method: "DELETE", body: J({ endpoint }) });
export const testPush = (b, t, endpoint) => call(b, t, "/push/test", { method: "POST", body: J({ endpoint }) });
export const fetchPushSubs = (b, t) => call(b, t, "/push/subscriptions");
export const deletePushSub = (b, t, id) => call(b, t, `/push/subscriptions/${id}`, { method: "DELETE" });
