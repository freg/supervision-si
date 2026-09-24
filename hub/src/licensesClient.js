// Client de licenses-api (livraison #595) -- tuile « Licences logicielles ». Jeton Keycloak de la session (écritures).
async function call(apiBase, token, path, init = {}) {
  try {
    const isForm = init.body instanceof FormData;
    const res = await fetch(`${apiBase}${path}`, { ...init, headers: { ...(init.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init.body && !isForm ? { "Content-Type": "application/json" } : {}) } });
    const data = await res.json().catch(() => ({}));
    return res.ok ? data : { error: data.error || `HTTP ${res.status}` };
  } catch (e) { return { error: e.message }; }
}
const J = (b) => JSON.stringify(b);
const site = (s) => (s ? `?site=${encodeURIComponent(s)}` : "");
export const fetchSoftware = (b, t) => call(b, t, "/software");
export const saveSoftware = (b, t, body, id) => call(b, t, id ? `/software/${id}` : "/software", { method: id ? "PUT" : "POST", body: J(body) });
export const deleteSoftware = (b, t, id) => call(b, t, `/software/${id}`, { method: "DELETE" });
export const fetchContracts = (b, t, s) => call(b, t, `/contracts${site(s)}`);
export const saveContract = (b, t, body, id) => call(b, t, id ? `/contracts/${id}` : "/contracts", { method: id ? "PUT" : "POST", body: J(body) });
export const deleteContract = (b, t, id) => call(b, t, `/contracts/${id}`, { method: "DELETE" });
export const fetchAssignments = (b, t) => call(b, t, "/assignments");
export const addAssignment = (b, t, body) => call(b, t, "/assignments", { method: "POST", body: J(body) });
export const deleteAssignment = (b, t, id) => call(b, t, `/assignments/${id}`, { method: "DELETE" });
export const fetchInstallations = (b, t, s) => call(b, t, `/installations${site(s)}`);
export const fetchInstallation = (b, t, agentId, q = "") => call(b, t, `/installations/${encodeURIComponent(agentId)}${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const fetchGaps = (b, t, s) => call(b, t, `/gaps${site(s)}`);
export const fetchGrid = (b, t, s) => call(b, t, `/grid${site(s)}`);
export const fetchSites = (b, t) => call(b, t, "/sites");
export const importFile = (b, t, file, s, dryRun, format) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("site", s || "");
  fd.append("dry_run", dryRun ? "1" : "0");
  if (format) fd.append("format", format);
  return call(b, t, "/import", { method: "POST", body: fd });
};
export const fetchUsers = (b, t, s) => call(b, t, `/users${site(s)}`);
export const saveUser = (b, t, body) => call(b, t, "/users", { method: "POST", body: J(body) });
export const deleteUser = (b, t, login) => call(b, t, `/users/${encodeURIComponent(login)}`, { method: "DELETE" });
export const syncUsers = (b, t) => call(b, t, "/users/sync", { method: "POST" });
export const fetchOwncloud = (b, t) => call(b, t, "/owncloud");
export const saveOwncloud = (b, t, body) => call(b, t, "/owncloud", { method: "PUT", body: J(body) });
export const testOwncloud = (b, t) => call(b, t, "/owncloud/test", { method: "POST" });
export const syncOwncloud = (b, t) => call(b, t, "/owncloud/sync", { method: "POST" });
export const readFiche = (b, t, login) => call(b, t, `/users/${encodeURIComponent(login)}/fiche`, { method: "POST" });
export const fetchVendors = (b, t) => call(b, t, "/vendors");
export const saveVendor = (b, t, body) => call(b, t, "/vendors", { method: "POST", body: J(body) });
export const deleteVendor = (b, t, name) => call(b, t, `/vendors/${encodeURIComponent(name)}`, { method: "DELETE" });
export const syncVendor = (b, t, name) => call(b, t, `/vendors/${encodeURIComponent(name)}/sync`, { method: "POST" });
export const fetchActions = (b, t) => call(b, t, "/actions");
export const createAction = (b, t, body) => call(b, t, "/actions", { method: "POST", body: J(body) });
export const fetchEvents = (b, t) => call(b, t, "/events");
