// Client dédié à l'API de dépôt/import/fusion de shapefiles.
const API_BASE_URL = import.meta.env.VITE_GEO_IMPORT_API_BASE_URL || "http://localhost:6113";

export async function fetchGeoHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { status: "degraded" };
    return await response.json();
  } catch (err) {
    return { status: "degraded", error: String(err) };
  }
}

export async function fetchGeoLayers() {
  try {
    const response = await fetch(`${API_BASE_URL}/layers`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) return { layers: [], error: body.error || `HTTP ${response.status}` };
    return { layers: body.layers || [], error: null };
  } catch (err) {
    return { layers: [], error: String(err) };
  }
}

/** file: objet File (l'archive .zip du/des shapefile(s)), layerName:
 * nom souhaité (optionnel — ignoré si l'archive contient plusieurs
 * jeux de shapefiles distincts, chacun garde alors son propre nom),
 * mode: "overwrite"|"append". Une archive peut contenir plusieurs
 * couches (ex. copie d'un dossier de travail QGIS complet) : la
 * réponse est toujours une LISTE, même pour un import à une seule
 * couche. */
export async function importShapefile(file, layerName, mode = "overwrite") {
  try {
    const formData = new FormData();
    formData.append("file", file);
    if (layerName) formData.append("layer_name", layerName);
    formData.append("mode", mode);
    const response = await fetch(`${API_BASE_URL}/import`, { method: "POST", body: formData });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { imported: [], skipped: body.details || [], error: body.error || `HTTP ${response.status}` };
    }
    return { imported: body.imported || [], skipped: body.skipped || [], error: null };
  } catch (err) {
    return { imported: [], skipped: [], error: String(err) };
  }
}

export async function fuseLayers(sourceLayers, targetLayer) {
  try {
    const response = await fetch(`${API_BASE_URL}/fusion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_layers: sourceLayers, target_layer: targetLayer }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { layer: null, commonColumns: [], error: body.error || `HTTP ${response.status}` };
    }
    return { layer: body.layer, commonColumns: body.common_columns || [], error: null };
  } catch (err) {
    return { layer: null, commonColumns: [], error: String(err) };
  }
}

export async function fetchLayerColumns(layerName) {
  try {
    const response = await fetch(`${API_BASE_URL}/layers/${encodeURIComponent(layerName)}/columns`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) return { columns: [], error: body.error || `HTTP ${response.status}` };
    return { columns: body.columns || [], error: null };
  } catch (err) {
    return { columns: [], error: String(err) };
  }
}

/** strategy: "semantic"|"geographic"|"temporal", options selon la
 * stratégie (voir geo-import/README.md). */
export async function runCorrelation(layerA, layerB, strategy, options) {
  try {
    const response = await fetch(`${API_BASE_URL}/correlate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layer_a: layerA, layer_b: layerB, strategy, options }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { candidates: [], count: 0, truncated: false, scoreDirection: null, error: body.error || `HTTP ${response.status}` };
    }
    return {
      candidates: body.candidates || [],
      count: body.count || 0,
      truncated: !!body.truncated,
      scoreDirection: body.score_direction,
      error: null,
    };
  } catch (err) {
    return { candidates: [], count: 0, truncated: false, scoreDirection: null, error: String(err) };
  }
}

export async function syncGeolocationsConnector() {
  try {
    const response = await fetch(`${API_BASE_URL}/connectors/geolocations/sync`, { method: "POST" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) return { layer: null, synced: 0, error: body.error || `HTTP ${response.status}` };
    return { layer: body.layer, synced: body.synced || 0, error: null };
  } catch (err) {
    return { layer: null, synced: 0, error: String(err) };
  }
}
