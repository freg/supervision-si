import React, { useState, useEffect } from "react";
import { fetchSearchMapping, searchOwnCloud } from "./ownCloudClient.js";

// Recherche Elasticsearch OwnCloud (livraison #354, backlog items
// 6/9 -- "greffer l'elasticsearch pour permettre une recherche
// étendue... parcourir les index d'elasticsearch et accéder aux
// données sources"). LECTURE SEULE par construction -- ce composant
// ne construit qu'une spec structurée {field, operator, value},
// jamais de DSL Elasticsearch brut (voir owncloud/search-api/app.py,
// build_search_body -- seule la traduction serveur touche
// réellement Elasticsearch). Champs proposés = mapping RÉEL de
// l'index (jamais une liste supposée en dur, voir README de ce
// service -- le schéma exact n'a jamais pu être inspecté depuis
// l'environnement où ce projet a été développé).

// Miroir de ALLOWED_OPERATORS (owncloud/search-api/app.py) -- jamais
// un opérateur inventé ici qui ne serait pas reconnu côté serveur.
const OPERATORS = [
  { id: "contains", label: "contient" },
  { id: "phrase", label: "contient l'expression exacte" },
  { id: "equals", label: "égal à" },
  { id: "exists", label: "existe (champ renseigné)" },
  { id: "gte", label: "supérieur ou égal à" },
  { id: "lte", label: "inférieur ou égal à" },
];

const EMPTY_CLAUSE = { field: "", operator: "contains", value: "" };

export default function OwnCloudSearchView({ apiBase, frontendUrl }) {
  const [fields, setFields] = useState([]);
  const [loadingMapping, setLoadingMapping] = useState(false);
  const [mappingError, setMappingError] = useState(null);
  const [clauses, setClauses] = useState([{ ...EMPTY_CLAUSE }]);
  const [combinator, setCombinator] = useState("AND");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [expandedHits, setExpandedHits] = useState(() => new Set());

  useEffect(() => {
    setLoadingMapping(true);
    fetchSearchMapping(apiBase).then((f) => {
      setFields(f);
      setLoadingMapping(false);
      if (f.length === 0) {
        setMappingError("Aucun champ disponible -- index Elasticsearch injoignable ou non configuré (voir owncloud/search-api/README.md).");
      }
    });
  }, [apiBase]);

  function updateClause(index, field, value) {
    setClauses((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }

  function addClause() {
    setClauses((prev) => [...prev, { ...EMPTY_CLAUSE }]);
  }

  function removeClause(index) {
    setClauses((prev) => prev.filter((_, i) => i !== index));
  }

  function toggleHit(id) {
    setExpandedHits((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSearch(e) {
    e.preventDefault();
    const validClauses = clauses
      .filter((c) => c.field && (c.operator === "exists" || c.value !== ""))
      .map((c) => ({ field: c.field, operator: c.operator, value: c.operator === "exists" ? true : c.value }));
    if (validClauses.length === 0) {
      setError("Au moins une clause complète (champ + valeur) est requise.");
      return;
    }
    setSearching(true);
    setError(null);
    const result = await searchOwnCloud(apiBase, validClauses, combinator, 20, 0);
    setSearching(false);
    if (result.error) {
      setError(result.error);
      setResults(null);
      return;
    }
    setResults(result);
    setExpandedHits(new Set());
  }

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Recherche en lecture seule sur l'index Elasticsearch alimenté par l'application
        OwnCloud <code>search_elastic</code> (externe à ce projet) -- aucune écriture, aucune
        modification de fichier possible depuis cet écran.
        {frontendUrl && (
          <> Recherche par mots-clés/filtres avancés déjà disponible dans{" "}
          <a href={frontendUrl} target="_blank" rel="noreferrer">Supervision SI</a>.</>
        )}
      </p>
      {loadingMapping && <p className="muted">Chargement des champs disponibles…</p>}
      {mappingError && <p className="hub-error">{mappingError}</p>}

      {fields.length > 0 && (
        <form onSubmit={handleSearch} className="hub-card hub-settings-section">
          <h2>Critères</h2>
          {clauses.map((clause, i) => (
            <div key={i} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 8 }}>
              <div className="hub-settings-row">
                <label>Champ</label>
                <select value={clause.field} onChange={(e) => updateClause(i, "field", e.target.value)}>
                  <option value="">-- choisir --</option>
                  {fields.map((f) => (
                    <option key={f.name} value={f.name}>{f.name} ({f.type})</option>
                  ))}
                </select>
              </div>
              <div className="hub-settings-row">
                <label>Opérateur</label>
                <select value={clause.operator} onChange={(e) => updateClause(i, "operator", e.target.value)}>
                  {OPERATORS.map((op) => (
                    <option key={op.id} value={op.id}>{op.label}</option>
                  ))}
                </select>
              </div>
              {clause.operator !== "exists" && (
                <div className="hub-settings-row">
                  <label>Valeur</label>
                  <input value={clause.value} onChange={(e) => updateClause(i, "value", e.target.value)} />
                </div>
              )}
              {clauses.length > 1 && (
                <button type="button" className="secondary" onClick={() => removeClause(i)}>Retirer</button>
              )}
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
            <button type="button" className="secondary" onClick={addClause}>+ Critère</button>
            <label>
              Combinateur :{" "}
              <select value={combinator} onChange={(e) => setCombinator(e.target.value)}>
                <option value="AND">ET (toutes les clauses)</option>
                <option value="OR">OU (au moins une clause)</option>
              </select>
            </label>
            <button type="submit" disabled={searching}>{searching ? "Recherche…" : "Rechercher"}</button>
          </div>
          {error && <p className="hub-error">{error}</p>}
        </form>
      )}

      {results && (
        <div className="hub-card hub-settings-section">
          <h2>Résultats ({results.total})</h2>
          {results.hits.length === 0 && <p className="muted">Aucun résultat.</p>}
          {results.hits.map((hit) => {
            const isOpen = expandedHits.has(hit.id);
            const sourceEntries = hit.source ? Object.entries(hit.source) : [];
            return (
              <div key={hit.id} style={{ marginBottom: 10, borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
                <button className="secondary" onClick={() => toggleHit(hit.id)}>
                  {isOpen ? "▾" : "▸"} {hit.id} {hit.score != null ? `(score ${hit.score.toFixed(2)})` : ""}
                </button>
                {isOpen && (
                  <div style={{ marginTop: 6, marginLeft: 16 }}>
                    <h4>Données sources (index Elasticsearch)</h4>
                    <table className="hub-table">
                      <tbody>
                        {sourceEntries.map(([key, value]) => (
                          <tr key={key}>
                            <td style={{ fontWeight: 600, verticalAlign: "top" }}>{key}</td>
                            <td style={{ wordBreak: "break-word" }}>
                              {typeof value === "object" ? JSON.stringify(value) : String(value)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
