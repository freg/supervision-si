import React, { useState, useEffect } from "react";
import { fetchEntityRelations } from "./relationsClient.js";

// Onglet "Relations" de la tuile ENT (livraison #335, backlog item 38
// point 2). PREMIÈRE PASSE -- interroge une entité précise (type +
// id) et affiche ses relations directes (avec le marqueur qui les
// justifie) et indirectes. Voir hub/README.md pour le cadrage complet
// du modèle et les limites connues de cette première passe (un seul
// critère de relation directe -- nom identique -- implémenté pour
// l'instant ; IP/proximité géographique/sémantique pas encore
// construites ; les relations indirectes ne peuvent structurellement
// pas encore se produire tant qu'un seul critère existe, voir
// relations/api/relation_engine.py).

const ENTITY_TYPES = [
  { value: "ticket", label: "Ticket" },
  { value: "calendar_event", label: "Événement calendrier" },
  { value: "document", label: "Document (GED)" },
  { value: "task", label: "Tâche" },
];

export default function RelationsView({ onBack, relationsApiBase, embedded, initialEntityType, initialEntityId }) {
  const [entityType, setEntityType] = useState(initialEntityType || "ticket");
  const [entityId, setEntityId] = useState(initialEntityId || "");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function runSearch(type, id) {
    if (!id?.toString().trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const data = await fetchEntityRelations(relationsApiBase, type, id.toString().trim());
    setLoading(false);
    if (data?.error) {
      setError(data.error);
      return;
    }
    setResult(data);
  }

  // Arrivée depuis un bouton "voir les relations" d'une autre vue
  // (livraison #339, backlog #38 -- "intégration directe depuis les
  // vues existantes" listée en reste à faire) -- lance la recherche
  // automatiquement, jamais besoin de re-saisir manuellement ce que
  // l'autre vue connaît déjà. Dépend de `initialEntityId` (jamais du
  // simple changement d'onglet) pour ne PAS relancer une recherche
  // déjà affichée si la personne navigue ailleurs puis revient sans
  // passer par un nouveau bouton.
  useEffect(() => {
    if (initialEntityType && initialEntityId) {
      runSearch(initialEntityType, initialEntityId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialEntityType, initialEntityId]);

  async function handleSearch(e) {
    e.preventDefault();
    await runSearch(entityType, entityId);
  }

  return (
    <div className={embedded ? "" : "hub-settings hub-settings-wide"}>
      {!embedded && (
        <div className="hub-settings-topbar" style={{ padding: "0 16px" }}>
          <button className="secondary" onClick={onBack}>◀ Retour</button>
          <h1>🔗 Relations</h1>
        </div>
      )}
      <div className="hub-card hub-settings-section">
        <h2 style={{ marginTop: 0 }}>Relations d'une entité</h2>
        <p className="muted" style={{ marginTop: 4 }}>
          Relation DIRECTE = marqueur commun identique (nom/label identique pour l'instant -- IP, proximité
          géographique et sémantique pas encore construites). Relation INDIRECTE = un autre élément du même
          ensemble connecté par des relations directes.
        </p>
        <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
            {ENTITY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Identifiant (ex: 42)"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
          />
          <button type="submit" disabled={loading || !entityId.trim()}>
            {loading ? "Recherche…" : "🔍 Chercher"}
          </button>
        </form>

        {error && <p style={{ color: "var(--danger, #c00)" }}>{error}</p>}

        {result && (
          <div style={{ marginTop: 16 }}>
            <p>
              <strong>{result.entity.label}</strong>{" "}
              <span className="muted">({ENTITY_TYPES.find((t) => t.value === result.entity.type)?.label || result.entity.type} #{result.entity.id})</span>
            </p>

            <h3 style={{ fontSize: 13, textTransform: "uppercase", color: "var(--muted)" }}>
              Relations directes ({result.direct.length})
            </h3>
            {result.direct.length === 0 ? (
              <p className="muted">Aucune.</p>
            ) : (
              <ul>
                {result.direct.map((r) => (
                  <li key={`${r.type}-${r.id}`}>
                    {r.label}{" "}
                    <span className="muted">
                      ({ENTITY_TYPES.find((t) => t.value === r.type)?.label || r.type} #{r.id} -- marqueur : "{r.marker}")
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <h3 style={{ fontSize: 13, textTransform: "uppercase", color: "var(--muted)" }}>
              Relations indirectes ({result.indirect.length})
            </h3>
            {result.indirect.length === 0 ? (
              <p className="muted">
                Aucune -- attendu pour l'instant avec un seul critère de relation directe (voir note ci-dessus).
              </p>
            ) : (
              <ul>
                {result.indirect.map((r) => (
                  <li key={`${r.type}-${r.id}`}>
                    {r.label}{" "}
                    <span className="muted">
                      ({ENTITY_TYPES.find((t) => t.value === r.type)?.label || r.type} #{r.id})
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
