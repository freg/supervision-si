// Client API vers glpi-api pour le résumé d'inventaire (livraison
// #231, backlog item 21). Même motif que les autres clients hub --
// renvoie toujours le corps JSON, même en cas d'erreur.

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

export async function fetchInventorySummary(glpiApiBase) {
  return fetchJson(glpiApiBase, "/inventory-summary");
}

// --- Imports (livraison #269, sélection multiple + clients Nebula) ---

const IMPORT_ROUTES = {
  "nebula-devices": { path: "/import/nebula-devices", selectionKey: "only_macs" },
  "nebula-clients": { path: "/import/nebula-clients", selectionKey: "only_macs" },
  "network-agent-devices": { path: "/import/network-agent-devices", selectionKey: "only_macs" },
  "snmp-targets": { path: "/import/snmp-targets", selectionKey: "only_ids" },
};
export const IMPORT_SOURCES = Object.keys(IMPORT_ROUTES);

export async function previewImport(glpiApiBase, source, segmentId) {
  const route = IMPORT_ROUTES[source];
  if (!route) return { error: `Source inconnue : ${source}` };
  const query = segmentId ? `?dry_run=true&segment_id=${segmentId}` : "?dry_run=true";
  return fetchJson(glpiApiBase, `${route.path}${query}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  });
}
export async function commitImport(glpiApiBase, source, selectedKeys, segmentId) {
  const route = IMPORT_ROUTES[source];
  if (!route) return { error: `Source inconnue : ${source}` };
  const body = selectedKeys ? { [route.selectionKey]: selectedKeys } : {};
  const query = segmentId ? `?dry_run=false&segment_id=${segmentId}` : "?dry_run=false";
  return fetchJson(glpiApiBase, `${route.path}${query}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

// --- Gestion individuelle des actifs déjà créés (annuler/supprimer, livraison #269) ---

export async function fetchItemsOfType(glpiApiBase, itemtype) {
  const data = await fetchJson(glpiApiBase, `/items/${itemtype}`);
  return Array.isArray(data) ? data : [];
}
export async function deleteItem(glpiApiBase, itemtype, itemId, forcePurge) {
  const query = forcePurge ? "?force_purge=true" : "";
  return fetchJson(glpiApiBase, `/items/${itemtype}/${itemId}${query}`, { method: "DELETE" });
}
