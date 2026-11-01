// Client API vers rights-api (livraison #283, gestion de droits
// centrale + inventaire de fichiers avec visibilité filtrée).

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

export async function fetchFiles(apiBase, groups) {
  const data = await fetchJson(apiBase, "/files", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups }),
  });
  return data;
}
export async function fetchPermissions(apiBase, resourceType) {
  const query = resourceType ? `?resource_type=${encodeURIComponent(resourceType)}` : "";
  const data = await fetchJson(apiBase, `/permissions${query}`);
  return Array.isArray(data?.permissions) ? data.permissions : [];
}
export async function grantPermission(apiBase, groups, { resourceType, resourceId, groupName, action }) {
  return fetchJson(apiBase, "/permissions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ groups, resource_type: resourceType, resource_id: resourceId || null, group_name: groupName, action }),
  });
}
export async function revokePermission(apiBase, groups, permissionId) {
  return fetchJson(apiBase, `/permissions/${permissionId}`, {
    method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups }),
  });
}
export async function fetchResourceTypes(apiBase) {
  const data = await fetchJson(apiBase, "/resource-types");
  return Array.isArray(data?.resource_types) ? data.resource_types : [];
}

// ------------------------------------------------ matrice des droits (#559)
const jsonInit = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export async function fetchVisible(apiBase, groups, user, ids, resourceType = "hub-tile") {
  const data = await fetchJson(apiBase, "/visible", jsonInit("POST", { groups, user, ids, resource_type: resourceType }));
  return data && !data.error ? data : null;  // null = injoignable : le hub reste ouvert (comportement historique)
}
export async function fetchMatrix(apiBase, resourceType = "hub-tile") {
  return fetchJson(apiBase, `/matrix?resource_type=${encodeURIComponent(resourceType)}`);
}
export async function putCatalog(apiBase, groups, user, items, resourceType = "hub-tile") {
  return fetchJson(apiBase, "/catalog", jsonInit("PUT", { groups, user, items, resource_type: resourceType }));
}
export async function putMatrix(apiBase, groups, user, grants) {
  return fetchJson(apiBase, "/matrix", jsonInit("PUT", { groups, user, grants }));
}
export async function putRestriction(apiBase, groups, user, subject, restricted) {
  return fetchJson(apiBase, "/restrictions", jsonInit("PUT", { groups, user, subject, restricted }));
}
