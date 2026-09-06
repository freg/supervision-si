import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import CalendarPanel from "./CalendarPanel.jsx";
import RadialTree from "./RadialTree.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import { isValidGeoJson } from "../lib/geojson.js";

// Piège classique React-Leaflet + empaqueteurs (Vite ici) : l'icône de
// marqueur par défaut référence des chemins d'images relatifs au CSS
// de Leaflet lui-même, qui ne survivent pas à l'empaquetage -- icône
// cassée (image manquante) sans ce correctif explicite. Jamais
// rencontré avant dans ce fichier faute d'avoir utilisé <Marker/>
// jusqu'ici (seulement du GeoJSON).
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const DEFAULT_CENTER = [46.6, 2.4]; // France, vue par défaut avant sélection
const DEFAULT_ZOOM = 5;

/**
 * Réticule de sélection — le signe distinctif de l'interface.
 * Recalcule sa position écran à chaque mouvement/zoom de carte, pour
 * rester collé au point sélectionné plutôt que d'être un simple marqueur.
 */
function SelectionReticle({ selectedLatLng }) {
  const map = useMap();
  const [screenPos, setScreenPos] = useState(null);

  useEffect(() => {
    if (!selectedLatLng) {
      setScreenPos(null);
      return;
    }
    const update = () => setScreenPos(map.latLngToContainerPoint(selectedLatLng));
    update();
    map.on("move zoom", update);
    return () => map.off("move zoom", update);
  }, [map, selectedLatLng]);

  if (!screenPos) return null;

  return (
    <div className="selection-reticle" style={{ left: screenPos.x, top: screenPos.y }}>
      <span /><span /><span /><span />
    </div>
  );
}

/**
 * Outil de coordonnées — survol en continu + capture par Ctrl/clic ou
 * clic droit. Ne rend rien à l'écran lui-même (le pied de page s'en
 * charge) ; se contente d'écouter les événements de la carte.
 */
function CoordinateTool({ onHover, onCapture }) {
  useMapEvents({
    mousemove(e) {
      onHover(e.latlng);
    },
    click(e) {
      if (e.originalEvent.ctrlKey || e.originalEvent.metaKey) {
        onCapture(e.latlng);
      }
    },
    contextmenu(e) {
      e.originalEvent.preventDefault();
      onCapture(e.latlng);
    },
  });
  return null;
}

/**
 * Consomme une demande de recentrage posée par un autre module (voir
 * App.jsx: mapFocusRequest) — appelle map.setView puis prévient
 * l'appelant que c'est fait, pour qu'il vide la demande et éviter de
 * re-déclencher le recentrage à chaque re-rendu sans rapport.
 */
function MapFocusHandler({ focusRequest, onConsumed }) {
  const map = useMap();

  useEffect(() => {
    if (!focusRequest) return;
    const { latitude, longitude, zoom } = focusRequest;
    if (typeof latitude === "number" && typeof longitude === "number") {
      map.setView([latitude, longitude], zoom ?? 14);
    }
    onConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusRequest]);

  return null;
}

/**
 * Ajuste automatiquement la vue pour cadrer TOUS les marqueurs fournis
 * (ex. "voir sur la carte" depuis un autre module — géolocalisations,
 * potentiellement d'autres sources plus tard). Un seul marqueur ->
 * simple centrage (fitBounds sur un point unique zoomerait à l'excès).
 * Se redéclenche uniquement quand la LISTE change (pas à chaque
 * re-rendu sans rapport), même prudence que MapFocusHandler.
 */
function FitToMarkers({ markers }) {
  const map = useMap();

  useEffect(() => {
    if (!markers || markers.length === 0) return;
    if (markers.length === 1) {
      map.setView([markers[0].latitude, markers[0].longitude], 14);
    } else {
      const bounds = markers.map((m) => [m.latitude, m.longitude]);
      map.fitBounds(bounds, { padding: [40, 40] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markers]);

  return null;
}

function formatCoord(latlng, precision = 6) {
  if (!latlng) return null;
  return `${latlng.lat.toFixed(precision)}, ${latlng.lng.toFixed(precision)}`;
}

export default function MapPanel({
  geojsonData,
  onFeatureSelect,
  selectedLatLng,
  showCalendar,
  onOpenCalendar,
  onCloseCalendar,
  calendarProps,
  radialTreeExpanded,
  onCloseRadialTree,
  radialTreeProps,
  focusRequest,
  onFocusConsumed,
  markers,
  collapsed,
  onToggleCollapsed,
}) {
  const geoJsonKeyRef = useRef(0);
  geoJsonKeyRef.current += 1;

  const hasGeojson = Boolean(geojsonData);
  const validGeojson = hasGeojson && isValidGeoJson(geojsonData);
  const invalidGeojson = hasGeojson && !validGeojson;

  const [hoverCoord, setHoverCoord] = useState(null);
  const [capturedCoord, setCapturedCoord] = useState("");
  const [copyFeedback, setCopyFeedback] = useState(false);

  function handleCapture(latlng) {
    setCapturedCoord(formatCoord(latlng));
    setCopyFeedback(false);
  }

  async function handleCopy() {
    if (!capturedCoord) return;
    try {
      await navigator.clipboard.writeText(capturedCoord);
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 1500);
    } catch (err) {
      // Presse-papiers indisponible (contexte non sécurisé, permission
      // refusée...) — le champ reste sélectionnable/copiable à la main.
    }
  }

  return (
    <div className={`col-map ${collapsed ? "col-map-collapsed" : ""}`}>
      {onToggleCollapsed && (
        <button
          className="map-collapse-toggle-btn"
          onClick={onToggleCollapsed}
          title={collapsed ? "Agrandir la carte" : "Réduire la carte"}
        >
          {collapsed ? "⤢ Agrandir" : "⤡ Réduire"}
        </button>
      )}
      <div className="map-area">
        <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {validGeojson && (
            <ErrorBoundary resetKey={geoJsonKeyRef.current} fallback={null}>
              <GeoJSON
                key={geoJsonKeyRef.current}
                data={geojsonData}
                onEachFeature={(feature, layer) => {
                  layer.on("click", () => onFeatureSelect(feature));
                }}
              />
            </ErrorBoundary>
          )}
          <SelectionReticle selectedLatLng={selectedLatLng} />
          <CoordinateTool onHover={setHoverCoord} onCapture={handleCapture} />
          <MapFocusHandler focusRequest={focusRequest} onConsumed={onFocusConsumed} />
          {markers && markers.length > 0 && (
            <>
              <FitToMarkers markers={markers} />
              {markers.map((m, i) => (
                <Marker key={`${m.latitude},${m.longitude},${i}`} position={[m.latitude, m.longitude]}>
                  {m.label && <Popup>{m.label}</Popup>}
                </Marker>
              ))}
            </>
          )}
        </MapContainer>

        {invalidGeojson && (
          <div className="map-geojson-warning">
            ⚠️ Cette source n'est pas un GeoJSON valide — pas d'affichage cartographique possible pour elle.
          </div>
        )}

        {!showCalendar && (
          <button className="calendar-toggle-tab" onClick={onOpenCalendar}>
            📅 Calendrier
          </button>
        )}

        {showCalendar && (
          <div className="calendar-overlay">
            <CalendarPanel {...calendarProps} onClose={onCloseCalendar} />
          </div>
        )}

        {radialTreeExpanded && (
          <div className="radial-tree-overlay">
            <div className="radial-tree-overlay-header">
              <span className="calendar-period-label">Arbre radial — sélection</span>
              <button className="calendar-close-btn" onClick={onCloseRadialTree}>✕ Réduire</button>
            </div>
            <RadialTree {...radialTreeProps} radius={300} />
          </div>
        )}
      </div>

      <div className="map-coord-footer">
        <span className="map-coord-hover">
          {hoverCoord ? `Survol : ${formatCoord(hoverCoord)}` : "Survol : —"}
        </span>
        <span className="map-coord-sep">·</span>
        <span className="map-coord-capture-label">Capturé (Ctrl+clic ou clic droit) :</span>
        <input
          type="text"
          className="map-coord-input"
          value={capturedCoord}
          readOnly
          placeholder="—"
          onFocus={(e) => e.target.select()}
        />
        <button
          className="calendar-nav-btn"
          onClick={handleCopy}
          disabled={!capturedCoord}
          title="Copier dans le presse-papiers"
        >
          {copyFeedback ? "✓ Copié" : "📋 Copier"}
        </button>
      </div>
    </div>
  );
}
