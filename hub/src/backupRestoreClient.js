// Client API vers backup-restore-api (livraison #249, backlog item
// 27 -- sous-volet "backup-restore", marqué URGENT par la personne).

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

export async function fetchImages(apiBase, deviceMac) {
  const query = deviceMac ? `?device_mac=${encodeURIComponent(deviceMac)}` : "";
  const data = await fetchJson(apiBase, `/images${query}`);
  return Array.isArray(data) ? data : [];
}

export async function createImage(apiBase, payload) {
  return fetchJson(apiBase, "/images", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteImage(apiBase, imageId) {
  return fetchJson(apiBase, `/images/${imageId}`, { method: "DELETE" });
}

export async function fetchCoverage(apiBase) {
  return fetchJson(apiBase, "/coverage");
}

// --- Sauvegardes DU HUB (livraison #459) : catalogue des sessions
// (totales / incrémentales chaînées), exécution, rotation GFS, export ---
const jsonOpts = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
export const fetchHubBackups = (apiBase) => fetchJson(apiBase, "/hub-backups");
export const fetchHubBackupStatus = (apiBase) => fetchJson(apiBase, "/hub-backups/status");
export const runHubBackup = (apiBase, kind, groups) => fetchJson(apiBase, "/hub-backups/run", jsonOpts("POST", { kind, groups }));
export const deleteHubBackup = (apiBase, name, groups) => fetchJson(apiBase, `/hub-backups/${encodeURIComponent(name)}`, jsonOpts("DELETE", { groups }));
export const pruneHubBackups = (apiBase, apply, groups) => fetchJson(apiBase, "/hub-backups/prune", jsonOpts("POST", { apply, groups }));
export const hubBackupDownloadUrl = (apiBase, name) => `${apiBase}/hub-backups/${encodeURIComponent(name)}/download`;
