// Client API vers architecture-api (livraison #253, vue/outil de
// parcours de l'architecture réseau).

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

export async function fetchEquipmentList(apiBase, search) {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const data = await fetchJson(apiBase, `/equipment${query}`);
  return Array.isArray(data) ? data : [];
}
export async function createEquipment(apiBase, payload) {
  return fetchJson(apiBase, "/equipment", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}
export async function importFromNetworkAgent(apiBase) {
  return fetchJson(apiBase, "/import/network-agent", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  });
}
export async function deleteEquipment(apiBase, id) {
  return fetchJson(apiBase, `/equipment/${id}`, { method: "DELETE" });
}
export async function fetchOverview(apiBase, id) {
  return fetchJson(apiBase, `/equipment/${id}/overview`);
}
export async function fetchInterfaces(apiBase, equipmentId) {
  const data = await fetchJson(apiBase, `/equipment/${equipmentId}/interfaces`);
  return Array.isArray(data) ? data : [];
}
export async function createInterface(apiBase, equipmentId, payload) {
  return fetchJson(apiBase, `/equipment/${equipmentId}/interfaces`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}
export async function deleteInterface(apiBase, interfaceId) {
  return fetchJson(apiBase, `/interfaces/${interfaceId}`, { method: "DELETE" });
}
export async function createLink(apiBase, payload) {
  return fetchJson(apiBase, "/links", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}
export async function deleteLink(apiBase, linkId) {
  return fetchJson(apiBase, `/links/${linkId}`, { method: "DELETE" });
}
