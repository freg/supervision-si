import { highlightJsonLines } from "../apps/owncloudLib.js";

export default function OwncloudJsonPanel({ node }) {
  if (!node) {
    return <p className="owncloud-empty">Cliquez un nœud de l'arbre pour voir sa fiche brute.</p>;
  }

  const lines = highlightJsonLines(node.raw ?? node);

  return (
    <div className="owncloud-json-panel">
      <div className="owncloud-json-header">
        <span className={`owncloud-json-type-badge owncloud-json-type-${node.raw?.isDir ? "folder" : "file"}`}>
          {node.raw?.isDir ? "Dossier" : "Fichier"}
        </span>
        <span className="owncloud-json-name">{node.name || "(racine)"}</span>
      </div>
      <pre className="owncloud-json-body">
        {lines.map((segments, i) => (
          <div key={i} className="owncloud-json-line">
            {segments.map((seg, j) => (
              <span key={j} className={`owncloud-json-tok owncloud-json-tok-${seg.cls}`}>
                {seg.text}
              </span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  );
}
