import * as d3 from "d3";
import { truncateLabel } from "../apps/owncloudLib.js";

// Pas de plafond de profondeur ici : contrairement aux autres modules,
// l'arbre ne grandit QUE par dépliage explicite de l'utilisateur — sa
// taille à l'écran est donc naturellement bornée par ce qu'il a choisi
// d'explorer, pas par une réponse serveur pouvant arriver arbitrairement
// profonde d'un coup.

export default function OwncloudRadialTree({ tree, selectedId, onSelectNode, relevantIds = null, radius = 220 }) {
  if (!tree) {
    return <p className="owncloud-empty">Sélectionnez une racine à gauche pour afficher son arbre.</p>;
  }

  const hierarchyRoot = d3.hierarchy(tree);
  d3.tree().size([2 * Math.PI, radius])(hierarchyRoot);

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 70;
  const extent = radius + margin;

  return (
    <div className="owncloud-radial-wrapper">
      <svg viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`} className="owncloud-radial-svg">
        {hierarchyRoot.links().map((link, i) => {
          const dimmed = relevantIds && !(relevantIds.has(link.source.data.id) && relevantIds.has(link.target.data.id));
          return (
            <path
              key={i}
              d={linkGenerator(link)}
              className={`owncloud-radial-link${dimmed ? " owncloud-radial-dim" : ""}`}
            />
          );
        })}

        {hierarchyRoot.descendants().map((node) => {
          const isSelected = node.data.id === selectedId;
          const dimmed = relevantIds ? !relevantIds.has(node.data.id) : false;
          const isDir = node.data.raw?.isDir;
          const unloaded = node.data.hasUnloadedChildren;

          let nodeClass = "owncloud-radial-node";
          nodeClass += isDir ? " owncloud-radial-node-folder" : " owncloud-radial-node-file";
          if (unloaded) nodeClass += " owncloud-radial-node-unloaded";
          if (isSelected) nodeClass += " owncloud-radial-node-selected";
          if (dimmed) nodeClass += " owncloud-radial-dim";
          nodeClass += " owncloud-radial-node-clickable";

          const nodeRadius = node.depth === 0 ? 6 : node.depth === 1 ? 5 : 3.5;
          const titleText = `${node.data.name || "(racine)"}${unloaded ? " — cliquer pour déplier" : ""}`;

          return (
            <g
              key={node.data.id}
              transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}
              onClick={() => onSelectNode(node.data)}
              className="owncloud-radial-node-group"
            >
              {isDir ? (
                // Losange (carré tourné 45°) pour les dossiers -- distinct
                // des fichiers (cercle) par la FORME, pas seulement la
                // couleur (accessible aussi en daltonisme/niveaux de gris).
                <rect
                  x={-nodeRadius * 0.82}
                  y={-nodeRadius * 0.82}
                  width={nodeRadius * 1.64}
                  height={nodeRadius * 1.64}
                  transform="rotate(45)"
                  className={nodeClass}
                >
                  <title>{titleText}</title>
                </rect>
              ) : (
                <circle r={nodeRadius} className={nodeClass}>
                  <title>{titleText}</title>
                </circle>
              )}
              {unloaded && (
                <circle
                  r={2}
                  cx={0}
                  cy={0}
                  transform={`translate(${node.depth === 0 ? 9 : 8},0)`}
                  className="owncloud-radial-unloaded-marker"
                />
              )}
              <text
                dy="0.31em"
                x={node.x < Math.PI ? 9 : -9}
                textAnchor={node.x < Math.PI ? "start" : "end"}
                transform={node.x >= Math.PI ? "rotate(180)" : null}
                className={`owncloud-radial-label${dimmed ? " owncloud-radial-dim" : ""}`}
              >
                {truncateLabel(node.data.name || "(racine)")}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
