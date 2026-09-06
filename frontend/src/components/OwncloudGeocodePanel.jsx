import { useState } from "react";
import { geocodeAddress, upsertGeolocation } from "../apps/pixelGridApi.js";

/**
 * Géocodage d'un nœud OwnCloud sélectionné — réutilise l'infra déjà
 * construite pour Pixel Grid (même service externe BAN/Géoplateforme,
 * même table `geolocations` partagée) plutôt que d'en dupliquer une
 * copie. Basé UNIQUEMENT sur les métadonnées déjà lues (nom du nœud/
 * de ses dossiers parents) — jamais le contenu du document (voir
 * owncloud/README.md, "Contenu des documents" pour la suite prévue).
 *
 * `query` est une SUGGESTION de départ (voir guessLocationQuery dans
 * owncloudLib.js), toujours éditable avant recherche — jamais géocodé
 * automatiquement à la sélection d'un nœud.
 *
 * Rendu avec `key={selectedNode.id}` par l'appelant : un remount
 * complet à chaque changement de nœud sélectionné réinitialise
 * proprement tout l'état interne (plus simple qu'un useEffect de
 * synchronisation).
 */
export default function OwncloudGeocodePanel({ query: initialQuery }) {
  const [query, setQuery] = useState(initialQuery || "");
  const [searching, setSearching] = useState(false);
  const [candidates, setCandidates] = useState(null);
  const [searchError, setSearchError] = useState(null);
  const [picked, setPicked] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);

  async function handleSearch() {
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    setPicked(null);
    setSaveResult(null);
    const { candidates: found, error } = await geocodeAddress(query);
    setSearching(false);
    setCandidates(found);
    setSearchError(error);
  }

  function handlePick(c) {
    setPicked(c);
    setSaveResult(null);
  }

  async function handleSave() {
    if (!picked) return;
    setSaving(true);
    const ok = await upsertGeolocation(query, picked.latitude, picked.longitude);
    setSaving(false);
    setSaveResult(ok ? "ok" : "error");
  }

  return (
    <div className="owncloud-geocode-panel">
      <h3>Géocodage</h3>
      <p className="owncloud-geocode-hint">
        Basé sur le nom (dossier/fichier), pas sur le contenu du document — modifiez le texte si besoin.
      </p>
      <div className="owncloud-geocode-search-row">
        <input
          className="owncloud-search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Texte à géocoder…"
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <button className="calendar-nav-btn" onClick={handleSearch} disabled={searching || !query.trim()}>
          {searching ? "…" : "🔍"}
        </button>
      </div>

      {searchError && (!candidates || candidates.length === 0) && (
        <p className="geo-candidates-error">⚠️ {searchError}</p>
      )}
      {candidates && candidates.length === 0 && !searchError && (
        <p className="geo-candidates-empty">Aucun résultat pour « {query} ».</p>
      )}
      {candidates && candidates.length > 0 && (
        <ul className="geo-candidates-list">
          {candidates.map((c, i) => (
            <li key={i}>
              <button className="geo-candidate-btn" onClick={() => handlePick(c)}>
                <span className="geo-candidate-label">{c.label || `${c.latitude}, ${c.longitude}`}</span>
                {c.city && <span className="geo-candidate-city">{c.city}</span>}
                <span className="geo-candidate-coords">
                  {c.latitude.toFixed(5)}, {c.longitude.toFixed(5)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {picked && (
        <div className="owncloud-geocode-picked">
          <p>
            {picked.label || `${picked.latitude}, ${picked.longitude}`} —{" "}
            {picked.latitude.toFixed(5)}, {picked.longitude.toFixed(5)}
          </p>
          <button className="calendar-nav-btn" onClick={handleSave} disabled={saving}>
            {saving ? "…" : `💾 Enregistrer pour « ${query} »`}
          </button>
          {saveResult === "ok" && <span className="owncloud-geocode-saved">✓ Enregistré</span>}
          {saveResult === "error" && <span className="geo-candidates-error">Échec de l'enregistrement</span>}
        </div>
      )}
    </div>
  );
}
