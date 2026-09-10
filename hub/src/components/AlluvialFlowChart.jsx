import { useMemo } from "react";
import * as d3 from "d3";
import { computeAlluvialLayout } from "../alluvialLayout.js";
import ZoomableChart from "./ZoomableChart.jsx";

// Diagramme alluvial simple (flux TCP/IP/UDP entre appareils) --
// livraison #389, backlog item 58. Calcul de layout SÉPARÉ
// (alluvialLayout.js, testable sans navigateur) -- ce composant ne
// fait QUE le rendu SVG à partir du résultat déjà calculé.

// `scale` = {mode, gain} (#413, chartScales) ; `controls` : contrôles
// supplémentaires à afficher dans la barre de l'enveloppe de zoom.
export default function AlluvialFlowChart({ links, deviceLabels, width = 700, height = 500, scale, controls }) {
  const layout = useMemo(
    () => computeAlluvialLayout(links, deviceLabels, { width, height, scale }),
    [links, deviceLabels, width, height, scale]
  );

  if (layout.isEmpty) {
    return <p className="muted">Aucun flux avec du volume échangé pour l'instant.</p>;
  }

  const linkGen = d3.linkHorizontal();

  return (
    <ZoomableChart
      viewBox={`0 0 ${width} ${height}`}
      className="alluvial-svg"
      svgStyle={{ width: "100%", height: "auto" }}
      label="Graphe alluvial"
      controls={controls}
    >
      {layout.linkPaths.map((l) => {
        const path = linkGen({
          source: [layout.nodeWidth, l.sourceY],
          target: [width - layout.nodeWidth, l.destY],
        });
        return (
          <path
            key={l.key}
            d={path}
            className="alluvial-link"
            style={{ strokeWidth: l.strokeWidth }}
          >
            <title>
              {`${(l.bytesTotal / 1024).toFixed(1)} Ko -- ${l.packetCount ?? "?"} paquet(s)`}
            </title>
          </path>
        );
      })}

      {[...layout.sourceNodes, ...layout.destNodes].map((n) => (
        <g key={`${n.x}-${n.id}`}>
          <rect x={n.x} y={n.y0} width={layout.nodeWidth} height={Math.max(1, n.y1 - n.y0)} className="alluvial-node">
            <title>{`${n.label} -- ${(n.total / 1024).toFixed(1)} Ko au total`}</title>
          </rect>
          <text
            x={n.x === 0 ? n.x + layout.nodeWidth + 4 : n.x - 4}
            y={(n.y0 + n.y1) / 2}
            dy="0.31em"
            textAnchor={n.x === 0 ? "start" : "end"}
            className="alluvial-label"
          >
            {n.label}
          </text>
        </g>
      ))}
    </ZoomableChart>
  );
}
