// Client API vers imap-client-api (livraison #179-191, interface hub
// #230 -- AUCUNE interface n'existait encore pour ce module, malgré
// tout le backend déjà construit). Même motif que sshTunnelsClient.js
// -- toutes les fonctions renvoient TOUJOURS le corps JSON de la
// réponse, même en cas d'erreur HTTP.

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

// --- Dossiers ---
export async function fetchFolders(apiBase) {
  const data = await fetchJson(apiBase, "/folders");
  return Array.isArray(data) ? data : [];
}
export async function createFolder(apiBase, name) {
  return fetchJson(apiBase, "/folders", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  });
}
export async function deleteFolder(apiBase, name) {
  return fetchJson(apiBase, `/folders?name=${encodeURIComponent(name)}`, { method: "DELETE" });
}

// --- Messages ---
export async function fetchMessages(apiBase, { folder, limit, offset, subject, from, unseen }) {
  const params = new URLSearchParams();
  if (folder) params.set("folder", folder);
  if (limit) params.set("limit", limit);
  if (offset) params.set("offset", offset);
  if (subject) params.set("subject", subject);
  if (from) params.set("from", from);
  if (unseen) params.set("unseen", "true");
  return fetchJson(apiBase, `/messages?${params.toString()}`);
}
export async function fetchMessage(apiBase, uid, folder) {
  return fetchJson(apiBase, `/messages/${encodeURIComponent(uid)}?folder=${encodeURIComponent(folder)}`);
}
export async function moveMessage(apiBase, uid, fromFolder, toFolder) {
  return fetchJson(apiBase, `/messages/${encodeURIComponent(uid)}/move`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_folder: fromFolder, to_folder: toFolder }),
  });
}
export async function interpretMessage(apiBase, uid, folder, interpreterId) {
  const params = folder ? `?folder=${encodeURIComponent(folder)}` : "";
  return fetchJson(apiBase, `/messages/${encodeURIComponent(uid)}/interpret${params}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(interpreterId ? { interpreter_id: interpreterId } : {}),
  });
}

// --- Règles de tri ---
export async function fetchRules(apiBase) {
  const data = await fetchJson(apiBase, "/rules");
  return Array.isArray(data) ? data : [];
}
export async function createRule(apiBase, rule) {
  return fetchJson(apiBase, "/rules", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(rule),
  });
}
export async function updateRule(apiBase, ruleId, patch) {
  return fetchJson(apiBase, `/rules/${ruleId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
  });
}
export async function deleteRule(apiBase, ruleId) {
  return fetchJson(apiBase, `/rules/${ruleId}`, { method: "DELETE" });
}
export async function applyRules(apiBase) {
  return fetchJson(apiBase, "/rules/apply", { method: "POST" });
}

// --- Interpréteurs (+ connecteur source, livraison #230) ---
export async function fetchInterpreters(apiBase) {
  const data = await fetchJson(apiBase, "/interpreters");
  return Array.isArray(data) ? data : [];
}
export async function createInterpreter(apiBase, interpreter) {
  return fetchJson(apiBase, "/interpreters", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(interpreter),
  });
}
export async function updateInterpreter(apiBase, interpreterId, patch) {
  return fetchJson(apiBase, `/interpreters/${interpreterId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
  });
}
export async function deleteInterpreter(apiBase, interpreterId) {
  return fetchJson(apiBase, `/interpreters/${interpreterId}`, { method: "DELETE" });
}
