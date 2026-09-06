import { useState } from "react";

/** Nœud d'arbre de localisation cliquable -- fonctionne aussi bien
 * enrichi (secretCount/isUnregistered, voir écran de recherche) que
 * brut (sélecteur de l'onglet Collections, voir LocationPicker.jsx) :
 * les champs optionnels sont simplement absents dans ce second cas,
 * jamais une exception. */
export default function LocationTreeNode({ node, selected, onSelect, depth = 0 }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = (node.children || []).length > 0;
  const isSelected = selected === node.localisation;
  const displayName = node.localisation === "__sans_hierarchie__" ? "(sans hiérarchie)" : node.localisation;
  const hasCodes = (node.secretCount || 0) > 0;

  return (
    <div>
      <div
        className={`vault-location-row${isSelected ? " vault-location-selected" : ""}${hasCodes ? " vault-location-has-codes" : ""}`}
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            className="vault-location-expand"
            onClick={() => setExpanded((v) => !v)}
            title={expanded ? "Replier" : "Déplier"}
          >
            {expanded ? "▾" : "▸"}
          </button>
        ) : (
          <span className="vault-location-expand-spacer" />
        )}
        <span className="vault-location-name" onClick={() => onSelect(isSelected ? null : node.localisation)}>
          {node.isVirtualGroup ? "🗂️" : "📍"} {displayName}
          {node.isUnregistered && (
            <span className="vault-location-unregistered" title="Saisie dans un code, pas encore répertoriée dans les géolocalisations">
              (non répertoriée)
            </span>
          )}
        </span>
        {hasCodes && <span className="vault-location-count">{node.secretCount}</span>}
      </div>
      {expanded && (node.children || []).map((child) => (
        <LocationTreeNode key={child.localisation} node={child} selected={selected} onSelect={onSelect} depth={depth + 1} />
      ))}
    </div>
  );
}
