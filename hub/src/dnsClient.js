// Client dns-api (#656) : zones, enregistrements (cache / rafraîchi), modification, journal, retour en arrière, rejeu.
async function fetchJson(url, options) {
  try {
    const res = await fetch(url, options); let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (data === null) return { error: `Réponse invalide (HTTP ${res.status})` };
    if (!res.ok && data.error === undefined && res.status !== 207) return { error: `Erreur HTTP ${res.status}` };
    return data;
  } catch (e) { return { error: `dns-api injoignable : ${e.message}` }; }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const listZones = (b) => fetchJson(`${b}/zones`);
export const createZone = (b, body) => fetchJson(`${b}/zones`, json("POST", body));
export const deleteZone = (b, zone) => fetchJson(`${b}/zones/${encodeURIComponent(zone)}`, { method: "DELETE" });
export const zoneRecords = (b, zone, refresh) => fetchJson(`${b}/zones/${encodeURIComponent(zone)}/records${refresh ? "?refresh=1" : ""}`);
export const setRecord = (b, zone, body) => fetchJson(`${b}/zones/${encodeURIComponent(zone)}/records`, json("PUT", body));
export const deleteRecord = (b, zone, body) => fetchJson(`${b}/zones/${encodeURIComponent(zone)}/records`, json("DELETE", body));
export const zoneChanges = (b, zone) => fetchJson(`${b}/zones/${encodeURIComponent(zone)}/changes`);
export const revertChange = (b, id, byUser) => fetchJson(`${b}/changes/${id}/revert`, json("POST", { by_user: byUser }));
export const replayZone = (b, zone) => fetchJson(`${b}/zones/${encodeURIComponent(zone)}/replay`, { method: "POST" });
