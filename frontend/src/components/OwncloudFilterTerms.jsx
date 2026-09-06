// Constructeur de filtre à plusieurs termes, chacun avec un mode
// inclure/exclure, combinés par ET ou OU -- voir owncloudLib.js
// (nodeMatchesGlob, buildCombinedGlobPredicate) pour la logique pure
// derrière. Le premier terme reste une simple recherche texte pour
// l'usage courant (comme avant) ; "+ Critère" ajoute la puissance du
// multi-terme sans l'imposer à qui n'en a pas besoin.

export default function OwncloudFilterTerms({ terms, combineMode, onChange, onCombineModeChange }) {
  function updateTerm(index, patch) {
    const next = terms.map((t, i) => (i === index ? { ...t, ...patch } : t));
    onChange(next);
  }

  function addTerm() {
    onChange([...terms, { pattern: "", mode: "include" }]);
  }

  function removeTerm(index) {
    onChange(terms.filter((_, i) => i !== index));
  }

  return (
    <div className="owncloud-filter-terms">
      {terms.map((term, i) => (
        <div key={i} className="owncloud-filter-term-row">
          {i > 0 && (
            <button
              type="button"
              className="owncloud-filter-combine-toggle"
              onClick={() => onCombineModeChange(combineMode === "and" ? "or" : "and")}
              title="Bascule la façon dont ce critère se combine avec les précédents"
            >
              {combineMode === "or" ? "OU" : "ET"}
            </button>
          )}
          <button
            type="button"
            className={`owncloud-filter-mode-toggle owncloud-filter-mode-${term.mode}`}
            onClick={() => updateTerm(i, { mode: term.mode === "exclude" ? "include" : "exclude" })}
            title={term.mode === "exclude" ? "Exclut ce motif — cliquer pour inclure à la place" : "Inclut ce motif — cliquer pour exclure à la place"}
          >
            {term.mode === "exclude" ? "− Exclure" : "+ Inclure"}
          </button>
          <input
            className="owncloud-search-input owncloud-filter-term-input"
            placeholder={i === 0 ? "🔍 Filtrer (ex. *.zip, analyse, rapport*)…" : "autre motif…"}
            value={term.pattern}
            onChange={(e) => updateTerm(i, { pattern: e.target.value })}
          />
          {terms.length > 1 && (
            <button
              type="button"
              className="owncloud-filter-term-remove"
              onClick={() => removeTerm(i)}
              title="Retirer ce critère"
            >
              ✕
            </button>
          )}
        </div>
      ))}
      <button type="button" className="owncloud-filter-add-term" onClick={addTerm}>
        + Critère
      </button>
    </div>
  );
}
