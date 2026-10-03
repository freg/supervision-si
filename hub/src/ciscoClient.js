// Client API vers cisco-api (#508) pour le hub (#660 : routes Cisco dans l'onglet Réseau de la tour de contrôle).
// Même motif que mikrotikClient.js : toujours le corps JSON, même en erreur.
async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (!res.ok) return { error: (data && data.error) || `HTTP ${res.status}` };
    return data || {};
  } catch (e) {
    return { error: e.message };
  }
}
export async function fetchCiscoSwitches(apiBase) { const d = await fetchJson(apiBase, "/switches"); return Array.isArray(d?.switches) ? d.switches : []; }
export const fetchCiscoRoutes = (apiBase, name) => fetchJson(apiBase, `/switches/${encodeURIComponent(name)}/routes`);
