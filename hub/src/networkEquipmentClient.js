// Client API vers network-equipment-api (livraison #506) -- tuile
// « Équipements réseau ». Même motif que siAgentClient.js : jamais
// d'exception vers le composant, toujours un objet ({error} en cas
// d'échec). Aucune communauté SNMP n'est conservée côté client : celle
// saisie « ponctuellement » part dans le corps de la requête et c'est
// tout.

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
    if (!res.ok && data && typeof data === "object" && !data.error) {
      return { ...data, error: `HTTP ${res.status}` };
    }
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

export const fetchNeStatus = (apiBase) => fetchJson(apiBase, "/status");

export async function fetchEquipment(apiBase, filters = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v) q.set(k, v);
  const data = await fetchJson(apiBase, `/equipment${q.toString() ? `?${q}` : ""}`);
  if (data?.error) return data;
  return { equipment: Array.isArray(data?.equipment) ? data.equipment : [] };
}

export const fetchEquipmentDetail = (apiBase, id) => fetchJson(apiBase, `/equipment/${id}`);
export const createEquipment = (apiBase, body) => fetchJson(apiBase, "/equipment", json("POST", body));
export const updateEquipment = (apiBase, id, body) => fetchJson(apiBase, `/equipment/${id}`, json("PUT", body));
export const deleteEquipment = (apiBase, id) => fetchJson(apiBase, `/equipment/${id}`, { method: "DELETE" });
export const importNetworkAgent = (apiBase, body) => fetchJson(apiBase, "/import/network-agent", json("POST", body || {}));
export const identifyEquipment = (apiBase, id, body) => fetchJson(apiBase, `/equipment/${id}/identify`, json("POST", body || {}));
export const identifyBatch = (apiBase, ids, body) => fetchJson(apiBase, "/identify/batch", json("POST", { ...(body || {}), ids }));
export const pollEquipment = (apiBase, id, body) => fetchJson(apiBase, `/equipment/${id}/poll`, json("POST", body || {}));
export const previewIdentify = (apiBase, body) => fetchJson(apiBase, "/identify/preview", json("POST", body || {}));
export const fetchProfiles = (apiBase) => fetchJson(apiBase, "/profiles");
export const fetchTopology = (apiBase) => fetchJson(apiBase, "/topology");
export const fetchFdb = (apiBase, id) => fetchJson(apiBase, `/equipment/${id}/fdb`);
export const whereIs = (apiBase, mac) => fetchJson(apiBase, `/where-is?mac=${encodeURIComponent(mac)}`);

/** Import Zenoss : fichier (multipart) ; `dryRun` = analyse seulement. */
export async function importZenossFile(apiBase, file, dryRun) {
  const form = new FormData();
  form.append("file", file, file.name);
  if (dryRun) form.append("dry_run", "1");
  return fetchJson(apiBase, "/import/zenoss", { method: "POST", body: form });
}

/** Import du fichier OUI de l'IEEE (oui.csv / oui.txt). */
export async function importOuiFile(apiBase, file) {
  const form = new FormData();
  form.append("file", file, file.name);
  return fetchJson(apiBase, "/oui/import", { method: "POST", body: form });
}
