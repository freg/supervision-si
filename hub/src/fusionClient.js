// Client de la tuile « Fusion IP/MAC » (livraison #431) : listes d'IP des
// bases externes (ipam-api, zenoss-api : /ip_list) et géolocalisation
// (pixel-grid). Jamais d'exception vers le composant ; les écritures
// passent `groups` (droit manage sur pixel-grid-api).
async function call(base, path, init) {
  try {
    const res = await fetch(`${base}${path}`, init);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (!res.ok) return { error: data?.error || `HTTP ${res.status}` };
    return data ?? { error: "réponse vide" };
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export async function fetchIpList(base) {
  if (!base) return { entries: [], error: null, absent: true };
  const d = await call(base, "/ip_list");
  return d?.error ? { entries: [], error: d.error } : { entries: d.entries || [], error: null };
}

export async function fetchGeolocations(base) {
  const d = await call(base, "/geolocations");
  return d?.error ? [] : d.geolocations || [];
}

export async function fetchLocationMatches(base) {
  const d = await call(base, "/geolocations/matches");
  return d?.error ? {} : Object.fromEntries((d.matches || []).map((m) => [m.subject, m]));
}

// IP publiques -> GeoIP côté serveur ; privées -> « en attente ». -> {ok, ...summary} | {ok:false, error}
export async function registerIps(base, ips, groups) {
  const d = await call(base, "/geolocations/register_ips", json("POST", { ips, groups: groups || [] }));
  return d?.error ? { ok: false, error: d.error } : { ok: true, ...(d.summary || d) };
}

export async function fetchCommuneCentroid(base, codePostal) {
  const d = await call(base, `/commune_centroid?code_postal=${encodeURIComponent(codePostal)}`);
  return d?.error ? { commune: null, error: d.error } : { commune: d.commune || d, error: null };
}

export async function upsertGeolocation(base, localisation, latitude, longitude, groups) {
  const d = await call(base, "/geolocations", json("POST", { localisation, latitude, longitude, groups: groups || [] }));
  return !d?.error;
}

export async function resolveByName(base, subjects, persist = true) {
  if (!subjects.length) return {};
  const d = await call(base, "/geolocations/resolve", json("POST", { subjects, persist }));
  return d?.error ? {} : Object.fromEntries((d.matches || []).map((m) => [m.subject, m]));
}
