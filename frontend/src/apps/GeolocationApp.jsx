import { useEffect, useMemo, useState } from "react";
import { fetchTypes, fetchGeolocations, upsertGeolocation, deleteGeolocation, scanGeolocations, geocodeAddress } from "./pixelGridApi.js";
import { buildExternalMapUrl } from "./geolocationLib.js";
import MapPanel from "../components/MapPanel.jsx";

// Service externe pour "ouvrir cette localisation dans..." — Google
// Maps par défaut, entièrement remplaçable via .env (VITE_GEOCODE_
// EXTERNAL_URL_TEMPLATE) pour pointer vers un autre outil (OSM,
// Bing...). {q} est remplacé par le nom de la localisation, encodé.
const EXTERNAL_MAP_URL_TEMPLATE =
  import.meta.env.VITE_GEOCODE_EXTERNAL_URL_TEMPLATE ||
  "https://www.google.com/maps/search/?api=1&query={q}";

function GeolocationRow({ geo, onSaved, onDeleted, onHoverRow }) {
  const [lat, setLat] = useState(geo.latitude ?? "");
  const [lon, setLon] = useState(geo.longitude ?? "");
  const [saving, setSaving] = useState(false);

  const [searching, setSearching] = useState(false);
  const [candidates, setCandidates] = useState(null); // null = pas encore cherché
  const [searchError, setSearchError] = useState(null);

  async function handleSave() {
    setSaving(true);
    const latNum = lat === "" ? null : parseFloat(lat);
    const lonNum = lon === "" ? null : parseFloat(lon);
    const ok = await upsertGeolocation(geo.localisation, latNum, lonNum);
    setSaving(false);
    if (ok) onSaved();
  }

  async function handleDelete() {
    const ok = await deleteGeolocation(geo.localisation);
    if (ok) onDeleted();
  }

  async function handleSearch() {
    setSearching(true);
    setSearchError(null);
    const { candidates: found, error } = await geocodeAddress(geo.localisation);
    setSearching(false);
    setCandidates(found);
    setSearchError(error);
  }

  function handlePickCandidate(candidate) {
    // Remplit les champs SANS enregistrer — l'utilisateur garde la main
    // sur la sauvegarde (bouton 💾 existant), même principe que partout
    // ailleurs dans ce projet : pas d'action automatique silencieuse.
    setLat(String(candidate.latitude));
    setLon(String(candidate.longitude));
    setCandidates(null);
  }

  return (
    <>
      <tr
        className={geo.mapped ? "" : "geo-row-unmapped"}
        onMouseEnter={() => onHoverRow?.(geo)}
        onMouseLeave={() => onHoverRow?.(null)}
      >
        <td className="geo-cell-loc">
          <span className={`status-dot ${geo.mapped ? "ok" : "unavailable"}`} style={{ marginRight: "0.4rem" }} />
          {geo.is_default ? (
            <em>📍 Position par défaut (repli, sources sans localisation connue)</em>
          ) : (
            geo.localisation
          )}
        </td>
        <td>
          <input
            type="text"
            className="geo-input"
            placeholder="latitude"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
        </td>
        <td>
          <input
            type="text"
            className="geo-input"
            placeholder="longitude"
            value={lon}
            onChange={(e) => setLon(e.target.value)}
          />
        </td>
        <td className="geo-cell-actions">
          <button className="calendar-nav-btn" onClick={handleSave} disabled={saving}>
            {saving ? "…" : "💾"}
          </button>
          {!geo.is_default && (
            <>
              <button
                className="calendar-nav-btn"
                onClick={handleSearch}
                disabled={searching}
                title="Chercher des coordonnées (géocodage)"
              >
                {searching ? "…" : "🔍"}
              </button>
              <a
                className="calendar-nav-btn geo-external-link-btn"
                href={buildExternalMapUrl(EXTERNAL_MAP_URL_TEMPLATE, geo.localisation)}
                target="_blank"
                rel="noopener noreferrer"
                title="Ouvrir dans un service cartographique externe"
              >
                🌍
              </a>
              <button className="basket-remove-btn" onClick={handleDelete} title="Supprimer">
                ✕
              </button>
            </>
          )}
        </td>
      </tr>
      {candidates !== null && (
        <tr className="geo-candidates-row">
          <td colSpan={4}>
            {searchError && candidates.length === 0 && (
              <p className="geo-candidates-error">⚠️ {searchError}</p>
            )}
            {candidates.length === 0 && !searchError && (
              <p className="geo-candidates-empty">Aucun résultat pour « {geo.localisation} ».</p>
            )}
            {candidates.length > 0 && (
              <ul className="geo-candidates-list">
                {candidates.map((c, i) => (
                  <li key={i}>
                    <button className="geo-candidate-btn" onClick={() => handlePickCandidate(c)}>
                      <span className="geo-candidate-label">{c.label || `${c.latitude}, ${c.longitude}`}</span>
                      {c.city && <span className="geo-candidate-city">{c.city}</span>}
                      <span className="geo-candidate-coords">{c.latitude.toFixed(5)}, {c.longitude.toFixed(5)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button className="geo-candidates-close" onClick={() => setCandidates(null)}>
              Fermer
            </button>
          </td>
        </tr>
      )}
    </>
  );
}

export default function GeolocationApp({ onShowOnMap }) {
  const [geolocations, setGeolocations] = useState([]);
  const [types, setTypes] = useState([]);
  const [scanType, setScanType] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true);
    const geos = await fetchGeolocations();
    setGeolocations(geos);
    setLoading(false);
  }

  useEffect(() => {
    reload();
    fetchTypes().then((t) => {
      setTypes(t);
      if (t.length > 0) setScanType(t[0].type);
    });
  }, []);

  async function handleScan() {
    if (!scanType) return;
    setScanning(true);
    const result = await scanGeolocations(scanType);
    setScanning(false);
    if (result.ok) {
      setScanResult(result.data);
      reload();
    }
  }

  const unmappedCount = geolocations.filter((g) => !g.mapped).length;
  const mappedCount = geolocations.filter((g) => g.mapped && !g.is_default).length;

  // Carte réduite intégrée -- centrage au survol d'une ligne,
  // activable/désactivable (certaines personnes le trouveront
  // distrayant si non voulu). Marqueurs mémorisés (useMemo) : sans ça,
  // un nouveau tableau à CHAQUE rendu (y compris juste pour un survol)
  // redéclencherait le cadrage automatique sur l'ensemble des points à
  // chaque fois, en concurrence directe avec le centrage au survol.
  const [hoverCenteringEnabled, setHoverCenteringEnabled] = useState(true);
  const [hoveredRow, setHoveredRow] = useState(null);
  const mapMarkers = useMemo(
    () =>
      geolocations
        .filter((g) => g.mapped && !g.is_default)
        .map((g) => ({ latitude: g.latitude, longitude: g.longitude, label: g.localisation })),
    [geolocations]
  );
  const hoverFocusRequest =
    hoverCenteringEnabled && hoveredRow && hoveredRow.mapped && !hoveredRow.is_default
      ? { latitude: hoveredRow.latitude, longitude: hoveredRow.longitude, zoom: 15 }
      : null;

  function handleShowOnMap() {
    onShowOnMap?.(mapMarkers);
  }

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="pixel-grid-controls">
          <span className="pixel-grid-controls-label">Scanner le type :</span>
          {types.map((t) => (
            <button
              key={t.type}
              className={`pixel-grid-level-btn ${scanType === t.type ? "active" : ""}`}
              onClick={() => setScanType(t.type)}
            >
              {t.type}
            </button>
          ))}
          <button className="pixel-grid-reset-btn" onClick={handleScan} disabled={!scanType || scanning}>
            {scanning ? "Scan…" : "🔄 Scanner les localisations"}
          </button>
          <button
            className="pixel-grid-reset-btn"
            onClick={handleShowOnMap}
            disabled={mappedCount === 0}
            title={mappedCount === 0 ? "Aucun lieu avec coordonnées pour l'instant" : `Afficher ${mappedCount} lieu(x) sur la carte`}
          >
            🗺️ Voir sur la carte ({mappedCount})
          </button>
        </div>
      </div>

      {scanResult && (
        <p className="pixel-grid-hover-detail">
          {scanResult.scanned_events} événement(s) scanné(s) — {scanResult.new_count} nouveau(x) lieu(x) détecté(s)
          {scanResult.new_count > 0 && ` : ${scanResult.new_locations.join(", ")}`}
        </p>
      )}

      <p className="synthesis-empty">
        {geolocations.length} lieu(x) connu(s), dont {unmappedCount} en attente de coordonnées (point rouge).
        L'ajout est automatique (scan ci-dessus ou lors du chargement des
        données) ; les coordonnées se saisissent ici à la main.
      </p>

      {mappedCount > 0 && (
        <div className="geo-embedded-map-block">
          <label className="geo-hover-centering-toggle">
            <input
              type="checkbox"
              checked={hoverCenteringEnabled}
              onChange={(e) => setHoverCenteringEnabled(e.target.checked)}
            />
            Centrer la carte au survol d'une ligne
          </label>
          <div className="geo-embedded-map">
            <MapPanel markers={mapMarkers} focusRequest={hoverFocusRequest} />
          </div>
        </div>
      )}

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && geolocations.length > 0 && (
        <table className="geo-table">
          <thead>
            <tr>
              <th>Localisation</th>
              <th>Latitude</th>
              <th>Longitude</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {[...geolocations]
              .sort((a, b) => (b.is_default ? 1 : 0) - (a.is_default ? 1 : 0))
              .map((g) => (
                <GeolocationRow key={g.localisation} geo={g} onSaved={reload} onDeleted={reload} onHoverRow={setHoveredRow} />
              ))}
          </tbody>
        </table>
      )}

      {!loading && geolocations.length === 0 && (
        <p className="synthesis-empty">
          Aucun lieu détecté pour l'instant — lance un scan ci-dessus une
          fois des données chargées.
        </p>
      )}
    </div>
  );
}
