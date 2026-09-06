import { highlightJsonLines } from "../apps/optickLib.js";

// Panneau JSON pour l'onglet Cacti (livraison #362) -- adaptation
// directe d'OptickJsonPanel.jsx (mêmes classes CSS "optick-json-*"
// réutilisées à dessein : styles déjà en place, jamais dupliqués
// pour une simple différence de préfixe) avec les 4 types RÉELS de
// cacti-api (tree/header/host/graph, voir cacti/api/app.py) au lieu
// des types Optick.
export default function CactiJsonPanel({ node }) {
  if (!node) {
    return <p className="optick-empty">Cliquez un nœud de l'arbre pour voir sa fiche brute.</p>;
  }

  const lines = highlightJsonLines(node.raw ?? node);
  const typeLabels = { tree: "Racine", header: "Dossier", host: "Hôte", graph: "Graphe" };

  return (
    <div className="optick-json-panel">
      <div className="optick-json-header">
        <span className={`optick-json-type-badge optick-json-type-${node.type}`}>
          {typeLabels[node.type] || node.type}
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
