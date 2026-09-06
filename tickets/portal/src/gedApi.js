// Client API vers ged-api (livraison #160 -- "Documents joints" pour
// les tickets). Fichier SÉPARÉ de api.js -- celui-ci cible
// TOUJOURS tickets-api (VITE_TICKETS_API_BASE_URL) et ne gère que du
// JSON, jamais des envois multipart/form-data (fichiers) -- plutôt
// que le complexifier pour un seul usage, un second petit client
// dédié à ged-api, même esprit que schemaAnalyzerClient.js côté hub.
//
// Contrairement à api.js (ok/status/data), les fonctions ICI
// renvoient TOUJOURS le corps JSON de la réponse quand une réponse
// existe -- même en cas d'erreur HTTP -- ged-api renvoie
// systématiquement {"error": "..."} dans ce cas, un message PRÉCIS
// que l'interface doit pouvoir afficher.

const GED_API_BASE_URL = import.meta.env.VITE_GED_API_BASE_URL || "";

async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options);
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

/** Documents liés à un ticket précis -- toujours un TABLEAU, jamais
 * {error} (une erreur devient une liste vide, l'appelant affiche
 * l'erreur au moment d'une ACTION, pas au moment de relire la
 * liste). */
export async function fetchTicketDocuments(ticketId) {
  const data = await fetchJson(`${GED_API_BASE_URL}/documents?linked_type=ticket&linked_id=${ticketId}`);
  return Array.isArray(data) ? data : [];
}

/** Envoie un nouveau document, LIÉ IMMÉDIATEMENT à ce ticket (voir
 * ged-api POST /documents, linked_type/linked_id). `file` : un objet
 * File (natif navigateur, ex. depuis un <input type="file">). */
export async function uploadTicketDocument(ticketId, file, actor) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("linked_type", "ticket");
  formData.append("linked_id", String(ticketId));
  if (actor) formData.append("actor", actor);
  return fetchJson(`${GED_API_BASE_URL}/documents`, { method: "POST", body: formData });
}

/** Ajoute une NOUVELLE VERSION à un document EXISTANT (déjà lié au
 * ticket) -- distinct d'un nouvel envoi, qui créerait un second
 * document séparé. */
export async function uploadNewVersion(documentId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(`${GED_API_BASE_URL}/documents/${documentId}/versions`, { method: "POST", body: formData });
}

export async function deleteTicketDocument(documentId) {
  return fetchJson(`${GED_API_BASE_URL}/documents/${documentId}`, { method: "DELETE" });
}

/** URL directe de téléchargement (pas un fetch) -- ouverte dans un
 * nouvel onglet par le navigateur lui-même, jamais chargée en
 * mémoire ici. */
export function documentDownloadUrl(documentId, versionSpec = "latest") {
  return `${GED_API_BASE_URL}/documents/${documentId}/versions/${versionSpec}/download`;
}
