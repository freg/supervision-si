import { useState } from "react";

/**
 * <select> classique + bouton "+" qui bascule vers un mini-formulaire
 * de création inline — pour ne jamais bloquer sur "le type/niveau/
 * statut/demandeur que je veux n'existe pas encore".
 *
 * - options : [{id, label}, ...] déjà résolues par le parent (le champ
 *   d'affichage n'est pas forcément "label" côté API — ex: users
 *   utilise "login" — donc le parent mappe avant de passer ici).
 * - onCreate(payload) doit renvoyer le nouvel id (number) ou null en
 *   cas d'échec ; le parent y fait l'appel API ET rafraîchit sa propre
 *   liste de options.
 * - extraFields (optionnel) : champs suffixes requis à la création
 *   (ex: niveaux -> rang), rendus comme petits inputs additionnels.
 */
export default function CreatableSelect({ value, onChange, options, placeholder, onCreate, extraFields = [], defaultLabel = "", suggestion = "" }) {
  const [creating, setCreating] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [extraValues, setExtraValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function startCreating(prefill) {
    setNewLabel(prefill ?? defaultLabel ?? "");
    setCreating(true);
  }

  async function handleSuggestionClick() {
    const existing = options.find((o) => o.label.toLowerCase() === suggestion.toLowerCase());
    if (existing) {
      onChange(String(existing.id));
      return;
    }
    // Pas de correspondance existante -> crée directement en un clic.
    // Ouvrir un formulaire pré-rempli qu'il faut ensuite re-valider
    // séparément est une opération de trop puisqu'on vient déjà
    // d'accepter la suggestion.
    setSaving(true);
    setError(null);
    const newId = await onCreate({ label: suggestion });
    setSaving(false);
    if (newId) {
      onChange(String(newId));
    } else {
      setError("Échec de la création.");
      startCreating(suggestion); // repli : ouvre le formulaire pour réessayer manuellement
    }
  }

  async function handleCreate() {
    if (!newLabel.trim()) return;
    setSaving(true);
    setError(null);
    const newId = await onCreate({ label: newLabel.trim(), ...extraValues });
    setSaving(false);
    if (newId) {
      onChange(String(newId));
      setCreating(false);
      setNewLabel("");
      setExtraValues({});
    } else {
      setError("Échec de la création.");
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleCreate();
    } else if (e.key === "Escape") {
      setCreating(false);
    }
  }

  if (creating) {
    return (
      <span style={{ display: "inline-flex", gap: "0.25rem", alignItems: "center" }}>
        <input
          className="geo-input"
          style={{ width: 110 }}
          placeholder={`nouveau ${placeholder}`}
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        {extraFields.map((f) => (
          <input
            key={f.key}
            className="geo-input"
            style={{ width: 60 }}
            placeholder={f.placeholder}
            value={extraValues[f.key] || ""}
            onChange={(e) => setExtraValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
            onKeyDown={handleKeyDown}
          />
        ))}
        <button className="calendar-nav-btn" onClick={handleCreate} disabled={saving} title="Créer">
          {saving ? "…" : "✓"}
        </button>
        <button className="calendar-nav-btn" onClick={() => setCreating(false)} title="Annuler">✕</button>
        {error && <span className="pixel-grid-error" style={{ fontSize: "0.65rem" }}>{error}</span>}
      </span>
    );
  }

  return (
    <span style={{ display: "inline-flex", gap: "0.2rem", alignItems: "center" }}>
      <select className="geo-input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      <button className="calendar-nav-btn" onClick={() => startCreating()} title={`Nouveau ${placeholder}`}>+</button>
      {suggestion && !value && (
        <button
          className="pixel-grid-level-btn"
          style={{ fontSize: "0.68rem" }}
          onClick={handleSuggestionClick}
          disabled={saving}
          title={`Suggestion basée sur l'événement sélectionné — clique pour ${options.some((o) => o.label.toLowerCase() === suggestion.toLowerCase()) ? "sélectionner" : "créer"} "${suggestion}"`}
        >
          {saving ? "…" : `💡 ${suggestion} ?`}
        </button>
      )}
      {error && !creating && <span className="pixel-grid-error" style={{ fontSize: "0.65rem" }}>{error}</span>}
    </span>
  );
}
