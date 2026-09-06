import { highlightJsonLines } from "../apps/ttsguLib.js";

export default function TtsguJsonPanel({ node }) {
  if (!node) {
    return <p className="ttsgu-empty">Cliquez un nœud de l'arbre pour voir sa fiche brute.</p>;
  }

  const lines = highlightJsonLines(node.raw ?? node);

  return (
    <div className="ttsgu-json-panel">
      <div className="ttsgu-json-header">
        <span className={`ttsgu-json-type-badge ttsgu-json-type-${node.type}`}>
          {node.type === "domain" ? "Domaine" : node.type === "category" ? "Catégorie" : node.type}
        </span>
        <span className="ttsgu-json-name">{node.name}</span>
      </div>
      <pre className="ttsgu-json-body">
        {lines.map((segments, i) => (
          <div key={i} className="ttsgu-json-line">
            {segments.map((seg, j) => (
              <span key={j} className={`ttsgu-json-tok ttsgu-json-tok-${seg.cls}`}>
                {seg.text}
              </span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  );
}
