import { useEffect, useState } from "react";
import { fetchSearchHealth, fetchSearchMapping, runSearch } from "./searchApi.js";
import { OPERATOR_LABELS, isClauseComplete, countCompleteClauses, parseHighlightFragment, firstHighlightFragment } from "./searchLib.js";

const OPERATORS = Object.keys(OPERATOR_LABELS);

function emptyClause() {
  return { field: "", operator: "contains", value: "" };
}

function HighlightSnippet({ fragment }) {
  const segments = parseHighlightFragment(fragment);
  if (segments.length === 0) return null;
  return (
    <p className="search-snippet">
      {segments.map((s, i) => (s.emphasized ? <mark key={i}>{s.text}</mark> : <span key={i}>{s.text}</span>))}
    </p>
  );
}

export default function SearchApp() {
  const [health, setHealth] = useState(null);
  const [fields, setFields] = useState([]);
  const [mappingError, setMappingError] = useState(null);
  const [mappingLoaded, setMappingLoaded] = useState(false);

  const [clauses, setClauses] = useState([emptyClause()]);
  const [combinator, setCombinator] = useState("AND");

  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [searchError, setSearchError] = useState(null);

  useEffect(() => {
    fetchSearchHealth().then(setHealth);
    fetchSearchMapping().then(({ fields, error }) => {
      setFields(fields);
      setMappingError(error);
      setMappingLoaded(true);
    });
  }, []);

  function updateClause(index, patch) {
    setClauses((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  }

  function addClause() {
    setClauses((prev) => [...prev, emptyClause()]);
  }

  function removeClause(index) {
    setClauses((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSearch() {
    const usable = clauses.filter(isClauseComplete);
    setSearching(true);
    setSearchError(null);
    const { total, hits, error } = await runSearch(usable, combinator);
    setSearching(false);
    setResults({ total, hits });
    setSearchError(error);
  }

  const completeCount = countCompleteClauses(clauses);
  const esUnavailable = health && health.status !== "ok";

  return (
    <div className="search-app">
      <header className="search-header">
        <strong>Recherche</strong>
        <span className="search-subtitle">
          — contenu des documents OwnCloud (Elasticsearch / search_elastic)
        </span>
      </header>

      {esUnavailable && (
        <div className="search-health-banner">
          ⚠️ Elasticsearch {health.es === "non configuré" ? "non configuré" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir owncloud/search-api/README.md).
        </div>
      )}

      {mappingLoaded && mappingError && !esUnavailable && (
        <p className="search-error">⚠️ Impossible de lire le mapping : {mappingError}</p>
      )}
      {mappingLoaded && !mappingError && fields.length === 0 && (
        <p className="search-empty">Aucun champ trouvé dans l'index — l'indexation a-t-elle démarré côté ownCloud ?</p>
      )}

      <div className="search-builder">
        {clauses.map((clause, i) => (
          <div key={i} className="search-clause-row">
            <select
              className="search-select"
              value={clause.field}
              onChange={(e) => updateClause(i, { field: e.target.value })}
              disabled={fields.length === 0}
            >
              <option value="">— champ —</option>
              {fields.map((f) => (
                <option key={f.name} value={f.name}>{f.name} ({f.type})</option>
              ))}
            </select>
            <select
              className="search-select"
              value={clause.operator}
              onChange={(e) => updateClause(i, { operator: e.target.value })}
            >
              {OPERATORS.map((op) => (
                <option key={op} value={op}>{OPERATOR_LABELS[op]}</option>
              ))}
            </select>
            {clause.operator !== "exists" && (
              <input
                className="search-value-input"
                value={clause.value}
                onChange={(e) => updateClause(i, { value: e.target.value })}
                placeholder="valeur…"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            )}
            {clauses.length > 1 && (
              <button className="basket-remove-btn" onClick={() => removeClause(i)} title="Retirer cette clause">
                ✕
              </button>
            )}
          </div>
        ))}

        <div className="search-builder-footer">
          <button className="calendar-nav-btn" onClick={addClause}>+ Clause</button>
          <div className="search-combinator">
            <label>
              <input type="radio" checked={combinator === "AND"} onChange={() => setCombinator("AND")} /> ET (toutes)
            </label>
            <label>
              <input type="radio" checked={combinator === "OR"} onChange={() => setCombinator("OR")} /> OU (au moins une)
            </label>
          </div>
          <button className="calendar-nav-btn search-run-btn" onClick={handleSearch} disabled={searching || completeCount === 0}>
            {searching ? "Recherche…" : `🔍 Chercher (${completeCount} clause${completeCount > 1 ? "s" : ""})`}
          </button>
        </div>
      </div>

      {searchError && <p className="search-error">⚠️ {searchError}</p>}

      {results && !searchError && (
        <div className="search-results">
          <p className="search-results-count">{results.total} résultat{results.total > 1 ? "s" : ""}</p>
          {results.hits.length === 0 && <p className="search-empty">Aucun document ne correspond.</p>}
          <ul className="search-results-list">
            {results.hits.map((hit) => (
              <li key={hit.id} className="search-result-item">
                <div className="search-result-header">
                  <span className="search-result-name">
                    {hit.source.name || hit.source.path || hit.id}
                  </span>
                  {hit.score != null && <span className="search-result-score">score {hit.score.toFixed(2)}</span>}
                </div>
                <HighlightSnippet fragment={firstHighlightFragment(hit.highlight)} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
