// Client API vers network-agent-api (livraison #233, backlog item
// 20). Même motif que les autres clients hub -- renvoie toujours le
// corps JSON, même en cas d'erreur.

async function fetchJson(apiBase, path) {
  try {
    const res = await fetch(`${apiBase}${path}`);
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

export async function fetchCaptureStatus(apiBase) {
  return fetchJson(apiBase, "/capture/status");
}
export async function fetchSites(apiBase) {
  const data = await fetchJson(apiBase, "/sites");
  return Array.isArray(data) ? data : [];
}
export async function fetchDevices(apiBase, segmentId, filters = {}) {
  const params = new URLSearchParams({ segment_id: segmentId });
  if (filters.depths && filters.depths.length > 0) {
    for (const d of filters.depths) params.append("depth", d);
  }
  if (filters.building) params.set("building", filters.building);
  if (filters.room) params.set("room", filters.room);
  if (filters.zone) params.set("zone", filters.zone);
  if (filters.minBytesTotal) params.set("min_bytes_total", filters.minBytesTotal);
  const data = await fetchJson(apiBase, `/devices?${params.toString()}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchFilterOptions(apiBase, segmentId) {
  const data = await fetchJson(apiBase, `/filter-options?segment_id=${segmentId}`);
  return data && !data.error ? data : { depths: [], buildings: [], rooms: [], zones: [] };
}
export async function fetchDevicesForPeriod(apiBase, segmentId, startIso, endIso) {
  const params = new URLSearchParams({ segment_id: segmentId, start: startIso, end: endIso });
  const data = await fetchJson(apiBase, `/devices/for-period?${params.toString()}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchDeviceServices(apiBase, deviceId) {
  const data = await fetchJson(apiBase, `/devices/${deviceId}/services`);
  return Array.isArray(data) ? data : [];
}
export async function fetchAllServices(apiBase, segmentId) {
  const data = await fetchJson(apiBase, `/devices/services?segment_id=${segmentId}`);
  return data && typeof data === "object" && !data.error ? data : {};
}
// `period` = { startIso, endIso } (#414) : volumes échangés PENDANT la
// période (différence de relevés côté API) au lieu du cumul actuel.
export async function fetchLinks(apiBase, segmentId, period) {
  const qs = period?.startIso && period?.endIso
    ? `&start=${encodeURIComponent(period.startIso)}&end=${encodeURIComponent(period.endIso)}`
    : "";
  const data = await fetchJson(apiBase, `/links?segment_id=${segmentId}${qs}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchObservedSubnets(apiBase, segmentId, prefixLength) {
  const query = prefixLength ? `&prefix_length=${prefixLength}` : "";
  const data = await fetchJson(apiBase, `/observed-subnets?segment_id=${segmentId}${query}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchPresenceHistory(apiBase, deviceId) {
  const data = await fetchJson(apiBase, `/devices/${deviceId}/presence-history`);
  return Array.isArray(data) ? data : [];
}
// Services utilisés ENTRE deux appareils, les deux sens confondus (route
// existante depuis #251, "services connectés par paire d'ip" -- jamais
// appelée côté hub avant #403).
export async function fetchLinkServices(apiBase, deviceAId, deviceBId) {
  const data = await fetchJson(apiBase, `/links/services?device_a_id=${deviceAId}&device_b_id=${deviceBId}`);
  return Array.isArray(data) ? data : [];
}
export async function fetchLinkHistory(apiBase, deviceAId, deviceBId) {
  const data = await fetchJson(apiBase, `/links/history?device_a_id=${deviceAId}&device_b_id=${deviceBId}`);
  return Array.isArray(data) ? data : [];
}
