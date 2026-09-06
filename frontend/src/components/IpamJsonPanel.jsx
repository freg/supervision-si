import { highlightJsonLines } from "../apps/ipamLib.js";

export default function IpamJsonPanel({ node }) {
  if (!node) {
    return <p className="ipam-empty">Cliquez un nœud de l'arbre pour voir sa fiche brute.</p>;
  }

  const lines = highlightJsonLines(node.raw ?? node);

  return (
    <div className="ipam-json-panel">
      <div className="ipam-json-header">
        <span className={`ipam-json-type-badge ipam-json-type-${node.type}`}>
          {node.type === "section" ? "Section" : node.type === "subnet" ? "Subnet" : node.type}
        </span>
        <span className="ipam-json-name">{node.name}</span>
      </div>
      <pre className="ipam-json-body">
        {lines.map((segments, i) => (
          <div key={i} className="ipam-json-line">
            {segments.map((seg, j) => (
              <span key={j} className={`ipam-json-tok ipam-json-tok-${seg.cls}`}>
                {seg.text}
              </span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  );
}
