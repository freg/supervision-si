// Client HTTP du module Portage (hub → portage-api), livraison #650.
// Même contrat que schemaAnalyzerClient.js : TOUJOURS un objet JSON, avec
// {error} précis en cas d'échec HTTP ou réseau -- jamais `undefined`.

async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    if (!res.ok && data.error === undefined) return { error: `Erreur HTTP ${res.status}` };
    return data;
  } catch (e) {
    return { error: `Serveur portage injoignable : ${e.message}` };
  }
}

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const listProjects = (base) => fetchJson(`${base}/projects`);
export const getProject = (base, slug) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}`);
export const createProject = (base, body) => fetchJson(`${base}/projects`, json("POST", body));
export const updateProject = (base, slug, body) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}`, json("PUT", body));
export const deleteProject = (base, slug) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}`, { method: "DELETE" });
export const runSteps = (base, slug, steps) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}/run`, json("POST", { steps }));
export const getReport = (base, slug, name) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}/report/${name}`);
export const getDecisions = (base, slug) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}/decisions`);
export const putDecisions = (base, slug, decisions) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}/decisions`, json("PUT", { decisions }));
export const loadDump = (base, slug) => fetchJson(`${base}/projects/${encodeURIComponent(slug)}/load-dump`, { method: "POST" });
export const archiveUrl = (base, slug) => `${base}/projects/${encodeURIComponent(slug)}/archive`;

// Fichier envoyé BRUT en FormData (convention du projet), jamais lu côté navigateur.
export function uploadFile(base, slug, kind, file) {
  const fd = new FormData();
  fd.append("file", file);
  return fetchJson(`${base}/projects/${encodeURIComponent(slug)}/${kind}`, { method: "POST", body: fd });
}
