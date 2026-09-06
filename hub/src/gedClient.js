// Client API vers ged-api (livraison #167 -- onglet hub GED). Même
// motif que tickets/portal/src/gedApi.js (#160), étendu ici avec la
// gestion des LIAISONS (créer/supprimer) -- pas nécessaire côté
// tickets (une liaison unique posée à la création suffit là-bas),
// mais utile ici pour une navigation/gestion GÉNÉRALE des documents,
// pas limitée à un seul ticket.
//
// Comme gedApi.js : les fonctions renvoient TOUJOURS le corps JSON
// de la réponse quand une réponse existe -- même en cas d'erreur
// HTTP -- ged-api renvoie systématiquement {"error": "..."} dans ce
// cas, un message PRÉCIS que l'interface doit pouvoir afficher.

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
    if (!res.ok && data.error === undefined) {
      return { error: `Erreur HTTP ${res.status}` };
    }
    return data;
  } catch {
    return { error: "Service documents injoignable" };
  }
}

/** Tous les documents CONNUS de ged-api (au moins une liaison), ou
 * filtrés sur une entité précise si linkedType+linkedId fournis.
 * Toujours un TABLEAU, jamais {error}. */
export async function fetchDocuments(apiBase, linkedType, linkedId) {
  const params = new URLSearchParams();
  if (linkedType && linkedId) {
    params.set("linked_type", linkedType);
    params.set("linked_id", linkedId);
  }
  const qs = params.toString();
  const data = await fetchJson(apiBase, `/documents${qs ? `?${qs}` : ""}`);
  return Array.isArray(data) ? data : [];
}

export async function fetchDocument(apiBase, documentId) {
  return fetchJson(apiBase, `/documents/${documentId}`);
}

/** `file` : objet File. `linkedType`+`linkedId` optionnels, ENSEMBLE
 * -- lie immédiatement le document créé. */
export async function uploadDocument(apiBase, file, name, linkedType, linkedId, actor) {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  if (linkedType && linkedId) {
    formData.append("linked_type", linkedType);
    formData.append("linked_id", String(linkedId));
  }
  if (actor) formData.append("actor", actor);
  return fetchJson(apiBase, "/documents", { method: "POST", body: formData });
}

export async function uploadNewVersion(apiBase, documentId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(apiBase, `/documents/${documentId}/versions`, { method: "POST", body: formData });
}

export async function deleteDocument(apiBase, documentId) {
  return fetchJson(apiBase, `/documents/${documentId}`, { method: "DELETE" });
}

export async function createLink(apiBase, documentId, linkedType, linkedId, actor) {
  return fetchJson(apiBase, `/documents/${documentId}/links`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ linked_type: linkedType, linked_id: String(linkedId), actor }),
  });
}

export async function deleteLink(apiBase, documentId, linkId) {
  return fetchJson(apiBase, `/documents/${documentId}/links/${linkId}`, { method: "DELETE" });
}

/** URL directe de téléchargement (pas un fetch). */
export function documentDownloadUrl(apiBase, documentId, versionSpec = "latest") {
  return `${apiBase}/documents/${documentId}/versions/${versionSpec}/download`;
}
