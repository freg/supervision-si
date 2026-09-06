// Client API vers nebula-api (livraison #196-200, interface hub
// #228) et le pont d'import vers glpi-api (#208). Même motif que
// sshTunnelsClient.js/snmpClient.js -- toutes les fonctions renvoient
// TOUJOURS le corps JSON de la réponse, même en cas d'erreur HTTP.

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

// --- Consultation des imports CSV (voie principale, sans Pro Pack ni clé API) ---
export async function fetchImportedSites(nebulaApiBase, history) {
  const data = await fetchJson(nebulaApiBase, `/imported/sites${history ? "?history=true" : ""}`);
  return Array.isArray(data) ? data : [];
}

export async function fetchImportedDevices(nebulaApiBase, history) {
  const data = await fetchJson(nebulaApiBase, `/imported/devices${history ? "?history=true" : ""}`);
  return Array.isArray(data) ? data : [];
}

export async function fetchImportedClients(nebulaApiBase, history) {
  const data = await fetchJson(nebulaApiBase, `/imported/clients${history ? "?history=true" : ""}`);
  return Array.isArray(data) ? data : [];
}

// --- Import d'un fichier CSV (multipart/form-data, champ "file") ---
async function uploadCsv(nebulaApiBase, path, file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(nebulaApiBase, path, { method: "POST", body: formData });
}

export const importSitesCsv = (nebulaApiBase, file) => uploadCsv(nebulaApiBase, "/import/sites", file);
export const importDevicesCsv = (nebulaApiBase, file) => uploadCsv(nebulaApiBase, "/import/devices", file);
export const importClientsCsv = (nebulaApiBase, file) => uploadCsv(nebulaApiBase, "/import/clients", file);

// --- Annulation d'un import (livraison #235) ---
export async function deleteImportedBatch(nebulaApiBase, type, importedAt) {
  return fetchJson(nebulaApiBase, `/imported/${type}?imported_at=${encodeURIComponent(importedAt)}`, { method: "DELETE" });
}

// --- Historique des lots + suppression par sélection (livraison #237) ---
export async function fetchImportBatches(nebulaApiBase, type) {
  const data = await fetchJson(nebulaApiBase, `/import-batches?type=${type}`);
  return Array.isArray(data) ? data : [];
}
export async function deleteImportBatches(nebulaApiBase, batchIds) {
  return fetchJson(nebulaApiBase, "/import-batches", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ batch_ids: batchIds }),
  });
}

// --- Voie API directe (nécessite Pro Pack + clé support Zyxel) ---
export async function testNebulaConnection(nebulaApiBase) {
  return fetchJson(nebulaApiBase, "/test-connection");
}

// --- Pont vers GLPI (livraison #208) -- appelé côté glpi-api, pas nebula-api ---
export async function importNebulaDevicesToGlpi(glpiApiBase, dryRun) {
  return fetchJson(glpiApiBase, `/import/nebula-devices?dry_run=${dryRun ? "true" : "false"}`, { method: "POST" });
}
