import { highlightJsonLines } from "../apps/optickLib.js";

export default function OptickJsonPanel({ node }) {
  if (!node) {
    return <p className="optick-empty">Cliquez un nœud de l'arbre pour voir sa fiche brute.</p>;
  }

  const lines = highlightJsonLines(node.raw ?? node);

  return (
    <div className="optick-json-panel">
      <div className="optick-json-header">
        <span className={`optick-json-type-badge optick-json-type-${node.type}`}>
          {node.type === "family" ? "Famille" : node.type === "category" ? "Catégorie" : node.type}
        </span>
        <span className="optick-json-name">{node.name}</span>
      </div>
      <pre className="optick-json-body">
        {lines.map((segments, i) => (
          <div key={i} className="optick-json-line">
            {segments.map((seg, j) => (
              <span key={j} className={`optick-json-tok optick-json-tok-${seg.cls}`}>
                {seg.text}
              </span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  );
}
