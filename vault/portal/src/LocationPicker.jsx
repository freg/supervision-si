import { useEffect, useMemo, useState } from "react";
import { buildLocationTree, filterLocationTree } from "./vaultSearchLib.js";
import LocationTreeNode from "./LocationTreeNode.jsx";

// Même source que l'écran de recherche (VaultSearchScreen.jsx) --
// lecture seule, jamais rien de sensible (voir la décision de
// sécurité assumée dans vault/README.md).
const PIXEL_GRID_API_BASE_URL = import.meta.env.VITE_PIXEL_GRID_API_BASE_URL || "";

/**
 * Remplace le champ texte libre "localisation" par un vrai choix dans
 * la hiérarchie connue -- retour explicite : "en collections [...]
 * elles sont visibles et sélectionnables pour le champ localisation",
 * contrairement à l'écran de recherche où les localisations sans code
 * sont masquées par défaut (voir VaultSearchScreen.jsx) : ICI,
 * TOUJOURS la hiérarchie complète, jamais filtrée par usage -- il
 * faut pouvoir choisir un lieu qui n'a encore AUCUN code.
 *
 * `value`/`onChange` : la localisation choisie (chaîne, ou "" si
 * aucune) -- comportement identique au champ texte qu'il remplace,
 * jamais de rupture d'interface pour l'appelant (App.jsx).
 */
export default function LocationPicker({ value, onChange }) {
  const [geolocations, setGeolocations] = useState([]);
  const [geoError, setGeoError] = useState(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!PIXEL_GRID_API_BASE_URL) {
      setGeoError("navigation par arbre indisponible -- saisie libre ci-dessous toujours possible.");
      return;
    }
    fetch(`${PIXEL_GRID_API_BASE_URL}/geolocations`)
      .then((r) => r.json())
      .then((body) => setGeolocations(body.geolocations || []))
      .catch(() => setGeoError("géolocalisations injoignables -- saisie libre ci-dessous toujours possible."));
  }, []);

  const tree = useMemo(() => buildLocationTree(geolocations), [geolocations]);
  const filteredTree = useMemo(() => filterLocationTree(tree, query), [tree, query]);

  function handleSelect(localisation) {
    onChange(localisation || "");
    setOpen(false);
  }

  return (
    <div className="vault-location-picker">
      <div className="vault-form-row">
        <input
          placeholder="📍 localisation (optionnel)"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="vault-location-picker-input"
        />
        <button type="button" className="secondary" onClick={() => setOpen((v) => !v)}>
          {open ? "✕ Fermer" : "🌳 Choisir dans l'arbre"}
        </button>
        {value && (
          <button type="button" className="secondary" onClick={() => onChange("")} title="Retirer la localisation">
            ↺
          </button>
        )}
      </div>
      {open && (
        <div className="vault-location-picker-panel">
          <input
            className="vault-location-search"
            placeholder="🔍 Filtrer les localisations…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {geoError && <p className="vault-muted vault-search-geo-note">{geoError}</p>}
          <div className="vault-location-tree">
            {filteredTree.length === 0 && !geoError && <p className="vault-muted">Aucune localisation.</p>}
            {filteredTree.map((node) => (
              <LocationTreeNode key={node.localisation} node={node} selected={value} onSelect={handleSelect} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
