import { highlightJsonLines } from "../apps/zenossLib.js";

const TYPE_BADGE_LABELS = {
  class: "Classe",
  location: "Localisation",
  device: "Équipement",
};

export default function ZenossJsonPanel({ node, badgeLabel = null }) {
  if (!node) {
    return <p className="zenoss-empty">Cliquez un nœud de l'arbre pour voir sa fiche brute.</p>;
  }

  const lines = highlightJsonLines(node.raw ?? node);
  const label = badgeLabel || TYPE_BADGE_LABELS[node.type] || "Classe";

  return (
    <div className="zenoss-json-panel">
      <div className="zenoss-json-header">
        <span className="zenoss-json-type-badge">{label}</span>
        <span className="zenoss-json-name">{node.raw?.path || node.name}</span>
      </div>
      <pre className="zenoss-json-body">
        {lines.map((segments, i) => (
          <div key={i} className="zenoss-json-line">
            {segments.map((seg, j) => (
              <span key={j} className={`zenoss-json-tok zenoss-json-tok-${seg.cls}`}>
                {seg.text}
              </span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  );
}
