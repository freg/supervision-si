// Client des correspondances nom -> localisation de pixel-grid-api
// (livraison #426) : résolution en lot persistée, décisions humaines
// (validée / rejetée / manuelle), alias. Jamais d'exception vers le composant.
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

// -> {matches: {subject -> match}, error}
export async function resolveSubjects(base, subjects, persist = true) {
  if (!subjects.length) return { matches: {}, error: null };
  const d = await call(base, "/geolocations/resolve", json("POST", { subjects, persist }));
  if (d?.error) return { matches: {}, error: d.error };
  return { matches: Object.fromEntries((d.matches || []).map((m) => [m.subject, m])), error: null };
}

export async function fetchMatches(base) {
  const d = await call(base, "/geolocations/matches");
  return d?.error ? { matches: [], error: d.error } : { matches: d.matches || [], error: null };
}

export function decideMatch(base, subject, { status, localisation, name, site, groups }) {
  return call(base, `/geolocations/matches/${encodeURIComponent(subject)}`, json("PUT", { status, localisation, name, site, groups: groups || [] }));
}

export function resetMatch(base, subject, groups) {
  return call(base, `/geolocations/matches/${encodeURIComponent(subject)}`, json("DELETE", { groups: groups || [] }));
}

export async function fetchAliases(base) {
  const d = await call(base, "/geolocations/aliases");
  return d?.error ? { aliases: [], error: d.error } : { aliases: d.aliases || [], error: null };
}

export function addAlias(base, alias, localisation, groups) {
  return call(base, "/geolocations/aliases", json("POST", { alias, localisation, groups: groups || [] }));
}

export function deleteAlias(base, alias, groups) {
  return call(base, `/geolocations/aliases?alias=${encodeURIComponent(alias)}`, json("DELETE", { groups: groups || [] }));
}
