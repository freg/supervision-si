// Client API vers retro-api (livraison #243, backlog item 30 --
// "Rétro-ingénierie"). Même motif que les autres clients hub --
// renvoie toujours le corps JSON, même en cas d'erreur.

export async function scanPhpArchive(retroApiBase, file) {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch(`${retroApiBase}/scan`, { method: "POST", body: formData });
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

// --- Parcours applicatifs (livraison #441) ---
async function call(base, path, init) {
  try {
    const res = await fetch(`${base}${path}`, init);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

// Même envoi que scanPhpArchive, conservé comme référence de code de l'application `app`.
export async function scanPhpArchiveForApp(retroApiBase, file, app) {
  const formData = new FormData();
  formData.append("file", file);
  if (app) formData.append("app", app);
  return call(retroApiBase, `/scan${app ? `?app=${encodeURIComponent(app)}` : ""}`, { method: "POST", body: formData });
}
export const fetchApps = (base) => call(base, "/apps");
export const upsertApp = (base, body) => call(base, "/apps", json("POST", body));
export const fetchAppMap = (base, label) => call(base, `/apps/${encodeURIComponent(label)}/map`);
export const fetchJourneys = (base, app) => call(base, `/journeys${app ? `?app=${encodeURIComponent(app)}` : ""}`);
export const fetchJourney = (base, id) => call(base, `/journeys/${encodeURIComponent(id)}`);
export const createJourney = (base, body) => call(base, "/journeys", json("POST", body));
export const endJourney = (base, id, notes) => call(base, `/journeys/${encodeURIComponent(id)}/end`, json("POST", { notes }));
export const deleteJourney = (base, id) => call(base, `/journeys/${encodeURIComponent(id)}`, json("DELETE", {}));
export const annotateStep = (base, id, step, text) => call(base, `/journeys/${encodeURIComponent(id)}/annotate`, json("POST", { step, text }));
export const collectQueries = (base, id, body) => call(base, `/journeys/${encodeURIComponent(id)}/queries/collect`, json("POST", body || {}));
