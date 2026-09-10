// Client dédié à l'API pixel-grid (service indépendant, port séparé).
const API_BASE_URL = import.meta.env.VITE_PIXEL_GRID_API_BASE_URL || "http://localhost:6104";

export async function fetchTypes() {
  try {
    const response = await fetch(`${API_BASE_URL}/types`);
    if (!response.ok) return [];
    const body = await response.json();
    return body.types || [];
  } catch (err) {
    return [];
  }
}

export async function fetchMeta(type) {
  try {
    const response = await fetch(`${API_BASE_URL}/meta?type=${encodeURIComponent(type)}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    return null;
  }
}

/**
 * Liste les événements bruts d'une plage — alimente la colonne de
 * détail quand on clique une cellule de la mosaïque.
 */
export async function fetchGeolocations() {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations`);
    if (!response.ok) return [];
    const body = await response.json();
    return body.geolocations || [];
  } catch (err) {
    return [];
  }
}

export async function upsertGeolocation(localisation, latitude, longitude) {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ localisation, latitude, longitude }),
    });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export async function deleteGeolocation(localisation) {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations?localisation=${encodeURIComponent(localisation)}`, {
      method: "DELETE",
    });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export async function scanGeolocations(type) {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations/scan?type=${encodeURIComponent(type)}`, {
      method: "POST",
    });
    if (!response.ok) return { ok: false };
    const body = await response.json();
    return { ok: true, data: body };
  } catch (err) {
    return { ok: false };
  }
}

/**
 * Enregistre une liste d'IP (venant d'un autre module — Fusion IP/MAC
 * aujourd'hui) dans le système de géolocalisation. IP privée -> "en
 * attente" (à placer à la main) ; IP publique -> tentative de
 * résolution GeoIP externe côté serveur. Ne touche jamais une entrée
 * déjà connue.
 */
export async function registerIpsForGeolocation(ips) {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations/register_ips`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ips }),
    });
    const body = await response.json();
    if (!response.ok) return { ok: false, error: body.error || `Erreur HTTP ${response.status}` };
    return { ok: true, ...body };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

export async function fetchDevices(type) {
  try {
    const response = await fetch(`${API_BASE_URL}/devices?type=${encodeURIComponent(type)}`);
    if (!response.ok) return [];
    const body = await response.json();
    return body.devices || [];
  } catch (err) {
    return [];
  }
}

export async function fetchTimeline(type, nom) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/timeline?type=${encodeURIComponent(type)}&nom=${encodeURIComponent(nom)}`
    );
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    return null;
  }
}

/** Géocodage d'un nom de lieu (bouton "🔍 Chercher" de GeolocationApp)
 * — passe par l'API pixel-grid pour éviter tout CORS et centraliser la
 * config du fournisseur externe (BAN/Géoplateforme par défaut). Ne
 * remplit ni ne sauvegarde jamais rien elle-même : retourne des
 * candidats, le choix et l'enregistrement restent une action humaine
 * explicite côté GeolocationRow. */
export async function geocodeAddress(query, limit = 5) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/geocode?q=${encodeURIComponent(query)}&limit=${limit}`
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { candidates: [], error: body.error || `Erreur HTTP ${response.status}` };
    }
    return { candidates: body.candidates || [], error: body.error || null };
  } catch (err) {
    return { candidates: [], error: String(err) };
  }
}

/** Centroïde de commune pour un code postal (colonne Position de
 * l'onglet Fusion IP/MAC) — voir /commune_centroid côté API. */
export async function fetchCommuneCentroid(codePostal) {
  try {
    const response = await fetch(`${API_BASE_URL}/commune_centroid?code_postal=${encodeURIComponent(codePostal)}`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { commune: null, error: body.error || `Erreur HTTP ${response.status}` };
    }
    return { commune: body.commune || null, error: body.error || null };
  } catch (err) {
    return { commune: null, error: String(err) };
  }
}

export async function fetchEvents(type, startIso, endIso, limit = 200) {
  const params = new URLSearchParams({ type, start: startIso, end: endIso, limit: String(limit) });
  try {
    const response = await fetch(`${API_BASE_URL}/events?${params.toString()}`);
    if (!response.ok) return { events: [], truncated: false };
    return await response.json();
  } catch (err) {
    return { events: [], truncated: false };
  }
}

/**
 * Mosaïque dense sur une plage arbitraire (year/month/day/hour/minute),
 * chaque cellule gardant son contexte complet (voir app.py côté API).
 * Renvoie { ok: true, data } ou { ok: false, error }.
 */
export async function fetchAggregateRange(type, level, startIso, endIso, nom) {
  const params = new URLSearchParams({ type, level, start: startIso, end: endIso });
  if (nom) params.set("nom", nom);
  try {
    const response = await fetch(`${API_BASE_URL}/aggregate_range?${params.toString()}`);
    const body = await response.json();
    if (!response.ok) return { ok: false, error: body.error || `Erreur HTTP ${response.status}` };
    return { ok: true, data: body };
  } catch (err) {
    return { ok: false, error: "Impossible de joindre l'API pixel-grid" };
  }
}

/** Livraison #426 -- résolution par le NOM (pixel-grid /geolocations/resolve) :
 * subjects = [{subject, name, site}], persist = true pour garder les
 * correspondances (statut « auto », corrigeables depuis le hub, cadre
 * « Localisations »). Renvoie {subject -> match}. */
export async function resolveByName(subjects, persist = true) {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subjects, persist }),
    });
    if (!response.ok) return {};
    const body = await response.json();
    return Object.fromEntries((body.matches || []).map((m) => [m.subject, m]));
  } catch (err) {
    return {};
  }
}

export async function fetchLocationMatches() {
  try {
    const response = await fetch(`${API_BASE_URL}/geolocations/matches`);
    if (!response.ok) return [];
    const body = await response.json();
    return body.matches || [];
  } catch (err) {
    return [];
  }
}
