import { useMemo } from "react";
import * as d3 from "d3";
import { buildDeviceHierarchy, makeVolumeWidthScale, prepareWeightedLinks } from "../weightedRadialLayout.js";

// Radial tree augmenté -- backlog item 58, "radial tree augmenté
// avec des liens d'épaisseur proportionnelle au volume échangé"
// (livraison #389). Structure hiérarchique (racine -> segment ->
// appareil) rendue EXACTEMENT comme OptickRadialTree.jsx (même
// bibliothèque d3.hierarchy/d3.tree/d3.linkRadial, motif déjà établi
// et présumé fonctionnel dans ce projet) -- AJOUTE par-dessus des
// liens croisés ENTRE FEUILLES (pas seulement parent-enfant),
// représentant les communications réelles entre appareils, avec une
// épaisseur proportionnelle au volume échangé.
//
// ⚠️ PAS VÉRIFIÉ CONTRE UN VRAI RENDU -- `d3` (le paquet lui-même)
// s'est révélé inaccessible depuis cet environnement de
// développement pour un test direct (voir weightedRadialLayout.js
// pour le détail). La construction hiérarchique et l'échelle de
// largeur SONT testées (fonctions pures, sans d3) ; SEUL l'appel à
// d3.hierarchy/d3.tree/d3.linkRadial lui-même n'a pas pu être
// exécuté ici -- à vérifier en priorité au premier rendu réel.

export default function WeightedRadialTree({ devices, links, segmentLabels = {}, radius = 220 }) {
  const treeData = useMemo(() => buildDeviceHierarchy(devices, segmentLabels), [devices, segmentLabels]);
  const widthScale = useMemo(() => makeVolumeWidthScale(links), [links]);
  const weightedLinks = useMemo(() => prepareWeightedLinks(links, widthScale), [links, widthScale]);

  const hierarchyRoot = useMemo(() => {
    const root = d3.hierarchy(treeData);
    d3.tree().size([2 * Math.PI, radius])(root);
    return root;
  }, [treeData, radius]);

  // Position (x=angle, y=rayon) de CHAQUE nœud, indexée par son id --
  // nécessaire pour les liens croisés (device A -> device B), qui ne
  // suivent PAS les arêtes parent-enfant de l'arbre lui-même.
  const positionById = useMemo(() => {
    const map = new Map();
    for (const node of hierarchyRoot.descendants()) {
      map.set(node.data.id, node);
    }
    return map;
  }, [hierarchyRoot]);

  if (!treeData.children || treeData.children.length === 0) {
    return <p className="muted">Aucun appareil connu pour l'instant.</p>;
  }

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 70;
  const extent = radius + margin;

  return (
    <div className="weighted-radial-wrapper">
      <svg viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`} className="weighted-radial-svg">
        {/* Structure de l'arbre (segment -> appareil) -- traits fins, discrets */}
        {hierarchyRoot.links().map((link, i) => (
          <path key={`struct-${i}`} d={linkGenerator(link)} className="weighted-radial-structure-link" />
        ))}

        {/* Liens de communication réels -- épaisseur proportionnelle au volume */}
        {weightedLinks.map((wl) => {
          const sourceNode = positionById.get(wl.sourceNodeId);
          const destNode = positionById.get(wl.destNodeId);
          if (!sourceNode || !destNode) return null; // appareil référencé absent de CETTE hiérarchie -- omis, jamais une exception
          const path = linkGenerator({ source: sourceNode, target: destNode });
          return (
            <path
              key={`${wl.sourceNodeId}-${wl.destNodeId}`}
              d={path}
              className="weighted-radial-volume-link"
              style={{ strokeWidth: wl.strokeWidth }}
            >
              <title>{`${(wl.bytesTotal / 1024).toFixed(1)} Ko -- ${wl.packetCount ?? "?"} paquet(s)`}</title>
            </path>
          );
        })}

        {hierarchyRoot.descendants().map((node) => {
          const isDevice = node.data.type === "device";
          return (
            <g key={node.data.id} transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}>
              <circle
                r={node.depth === 0 ? 6 : node.depth === 1 ? 5 : 3.5}
                className={`weighted-radial-node${isDevice ? " weighted-radial-node-device" : ""}`}
              >
                <title>{node.data.name}</title>
              </circle>
              <text
                dy="0.31em"
                x={node.x < Math.PI ? 9 : -9}
                textAnchor={node.x < Math.PI ? "start" : "end"}
                transform={node.x >= Math.PI ? "rotate(180)" : null}
                className="weighted-radial-label"
              >
                {node.data.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
