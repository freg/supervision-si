import { useState } from "react";
import JsonTree, { isPathSelected } from "./JsonTree.jsx";

/**
 * Compte combien de chemins "feuille" restent sélectionnés, pour donner
 * un indicateur rapide sans obliger à déplier l'arbre.
 */
function countSelectedLeaves(value, path, deselectedPaths) {
  if (!isPathSelected(path, deselectedPaths)) return 0;

  if (value !== null && typeof value === "object") {
    const entries = Array.isArray(value)
      ? value.map((v, i) => [`${path}[${i}]`, v])
      : Object.entries(value).map(([k, v]) => [`${path}.${k}`, v]);
    return entries.reduce((sum, [childPath, childValue]) => {
      return sum + countSelectedLeaves(childValue, childPath, deselectedPaths);
    }, 0);
  }

  return 1;
}

function BasketEntry({ source, data, deselectedPaths, onToggleNode, onRemove }) {
  const [expanded, setExpanded] = useState(false);
  const leafCount = data ? countSelectedLeaves(data, "$", deselectedPaths) : 0;

  return (
    <div className="basket-entry">
      <div className="basket-entry-header">
        <button className="basket-expand-btn" onClick={() => setExpanded((e) => !e)}>
          {expanded ? "▾" : "▸"} {source}
        </button>
        <span className="basket-entry-meta">{leafCount} nœud(s) sélectionné(s)</span>
        <button className="basket-remove-btn" onClick={() => onRemove(source)} title="Retirer de la corbeille">
          ✕
        </button>
      </div>

      {expanded && data && (
        <div className="json-tree-container">
          <JsonTree
            data={data}
            deselectedPaths={deselectedPaths}
            onToggle={(path) => onToggleNode(source, path)}
          />
        </div>
      )}
    </div>
  );
}

export default function SelectionBasket({ basketEntries, sourceData, onToggleNode, onRemove }) {
  const sourceNames = Object.keys(basketEntries);

  if (sourceNames.length === 0) {
    return (
      <p className="synthesis-empty">
        Sélectionnez une ou plusieurs dates dans le calendrier pour peupler
        la corbeille avec les sources concernées.
      </p>
    );
  }

  return (
    <div className="basket-list">
      {sourceNames.map((source) => (
        <BasketEntry
          key={source}
          source={source}
          data={sourceData[source]}
          deselectedPaths={basketEntries[source].deselectedPaths}
          onToggleNode={onToggleNode}
          onRemove={onRemove}
        />
      ))}
    </div>
  );
}
