import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { truncateLabel, usagePercent, usageClass } from "../apps/ipamLib.js";
import { DEFAULT_ZOOM_TRANSFORM, computeZoomTransform } from "../lib/svgZoom.js";

// Au-delà de cette profondeur, un sous-arbre est résumé en "…" pour
// garder l'arbre lisible — un subnetting réel peut nicher beaucoup de
// niveaux (folders successifs), la même logique de plafond existe déjà
// dans components/RadialTree.jsx pour la même raison.
const MAX_DEPTH = 7;

// Molette (haut = avant, bas = arrière) et clic droit (avant ; Ctrl/Cmd
// + clic droit = arrière) — même convention Ctrl/Cmd que CoordinateTool
// dans MapPanel.jsx pour rester cohérent avec le reste du projet.
const ZOOM_STEP = 1.2;
const MIN_SCALE = 0.3;
const MAX_SCALE = 6;

function capDepth(node, depth) {
  if (depth >= MAX_DEPTH && node.children && node.children.length > 0) {
    return { ...node, children: [{ id: `${node.id}-more`, type: "more", name: "…", children: [] }] };
  }
  return { ...node, children: (node.children || []).map((c) => capDepth(c, depth + 1)) };
}

export default function IpamRadialTree({ tree, selectedId, onSelectNode, relevantIds = null, radius = 220 }) {
  const svgRef = useRef(null);
  const [zoomTransform, setZoomTransform] = useState(DEFAULT_ZOOM_TRANSFORM);

  const cappedTree = useMemo(() => (tree ? capDepth(tree, 0) : null), [tree]);

  // Réinitialise le zoom au changement de RACINE (id différent) — pas
  // à chaque nouvelle référence d'arbre : basculer "réduire à la
  // sélection" côté IpamApp.jsx produit un nouvel objet arbre à chaque
  // ajustement du curseur temporel, et réinitialiser le zoom à chaque
  // fois serait agaçant plutôt qu'utile.
  useEffect(() => {
    setZoomTransform(DEFAULT_ZOOM_TRANSFORM);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree?.id]);

  function clientToSvgPoint(clientX, clientY) {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }

  function zoomAt(clientX, clientY, factor) {
    const focal = clientToSvgPoint(clientX, clientY);
    setZoomTransform((prev) => computeZoomTransform(prev, factor, focal, MIN_SCALE, MAX_SCALE));
  }

  // Écouteur natif plutôt que la prop onWheel de React : certaines
  // versions/contextes de React posent leurs écouteurs "wheel" en
  // passif par défaut, ce qui empêche preventDefault() de bloquer le
  // défilement de page pendant qu'on zoome sur l'arbre — {passive:
  // false} explicite ici lève l'ambiguïté.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return undefined;
    function handleWheel(e) {
      e.preventDefault();
      zoomAt(e.clientX, e.clientY, e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP);
    }
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleContextMenu(e) {
    e.preventDefault();
    const zoomOut = e.ctrlKey || e.metaKey;
    zoomAt(e.clientX, e.clientY, zoomOut ? 1 / ZOOM_STEP : ZOOM_STEP);
  }

  function resetZoom() {
    setZoomTransform(DEFAULT_ZOOM_TRANSFORM);
  }

  if (!cappedTree) {
    return <p className="ipam-empty">Sélectionnez une racine à gauche pour afficher son arbre.</p>;
  }

  const hierarchyRoot = d3.hierarchy(cappedTree);
  d3.tree().size([2 * Math.PI, radius])(hierarchyRoot);

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 70;
  const extent = radius + margin;

  return (
    <div className="ipam-radial-wrapper">
      <svg
        ref={svgRef}
        viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`}
        className="ipam-radial-svg"
        onContextMenu={handleContextMenu}
      >
        <g transform={`translate(${zoomTransform.tx},${zoomTransform.ty}) scale(${zoomTransform.scale})`}>
          {hierarchyRoot.links().map((link, i) => {
            const dimmed = relevantIds && !(relevantIds.has(link.source.data.id) && relevantIds.has(link.target.data.id));
            return (
              <path
                key={i}
                d={linkGenerator(link)}
                className={`ipam-radial-link${dimmed ? " ipam-radial-dim" : ""}`}
              />
            );
          })}

          {hierarchyRoot.descendants().map((node) => {
            const clickable = node.data.type === "section" || node.data.type === "subnet";
            const isSelected = node.data.id === selectedId;
            const dimmed = relevantIds ? !relevantIds.has(node.data.id) : false;
            const percent = node.data.type === "subnet" ? usagePercent(node.data) : null;
            const uClass = node.data.type === "subnet" ? usageClass(percent) : "";

            let nodeClass = "ipam-radial-node";
            if (node.data.type === "section") nodeClass += " ipam-radial-node-section";
            if (node.data.type === "subnet") nodeClass += ` ipam-radial-node-subnet ${uClass}`;
            if (node.data.type === "more") nodeClass += " ipam-radial-node-more";
            if (isSelected) nodeClass += " ipam-radial-node-selected";
            if (dimmed) nodeClass += " ipam-radial-dim";
            if (clickable) nodeClass += " ipam-radial-node-clickable";

            return (
              <g
                key={node.data.id}
                transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}
                onClick={clickable ? () => onSelectNode(node.data) : undefined}
                className={clickable ? "ipam-radial-node-group" : undefined}
              >
                <circle r={node.depth === 0 ? 6 : node.depth === 1 ? 5 : 3.5} className={nodeClass}>
                  {clickable && <title>{node.data.name}</title>}
                </circle>
                <text
                  dy="0.31em"
                  x={node.x < Math.PI ? 9 : -9}
                  textAnchor={node.x < Math.PI ? "start" : "end"}
                  transform={node.x >= Math.PI ? "rotate(180)" : null}
                  className={`ipam-radial-label${dimmed ? " ipam-radial-dim" : ""}`}
                >
                  {truncateLabel(node.data.name)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="ipam-radial-zoom-hint">Molette : zoom · Clic droit : zoom avant · Ctrl+clic droit : zoom arrière</div>
      {zoomTransform.scale !== 1 && (
        <button className="ipam-radial-zoom-reset" onClick={resetZoom} title="Réinitialiser le zoom (100%)">
          ⟲ {Math.round(zoomTransform.scale * 100)}%
        </button>
      )}
    </div>
  );
}
