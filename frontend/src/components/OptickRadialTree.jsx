import { useMemo } from "react";
import * as d3 from "d3";
import { truncateLabel, openRatioPercent, loadClass } from "../apps/optickLib.js";

const MAX_DEPTH = 7;

function capDepth(node, depth) {
  if (depth >= MAX_DEPTH && node.children && node.children.length > 0) {
    return { ...node, children: [{ id: `${node.id}-more`, type: "more", name: "…", children: [] }] };
  }
  return { ...node, children: (node.children || []).map((c) => capDepth(c, depth + 1)) };
}

export default function OptickRadialTree({ tree, selectedId, onSelectNode, relevantIds = null, radius = 220 }) {
  const cappedTree = useMemo(() => (tree ? capDepth(tree, 0) : null), [tree]);

  if (!cappedTree) {
    return <p className="optick-empty">Sélectionnez une racine à gauche pour afficher son arbre.</p>;
  }

  const hierarchyRoot = d3.hierarchy(cappedTree);
  d3.tree().size([2 * Math.PI, radius])(hierarchyRoot);

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 70;
  const extent = radius + margin;

  return (
    <div className="optick-radial-wrapper">
      <svg viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`} className="optick-radial-svg">
        {hierarchyRoot.links().map((link, i) => {
          const dimmed = relevantIds && !(relevantIds.has(link.source.data.id) && relevantIds.has(link.target.data.id));
          return (
            <path
              key={i}
              d={linkGenerator(link)}
              className={`optick-radial-link${dimmed ? " optick-radial-dim" : ""}`}
            />
          );
        })}

        {hierarchyRoot.descendants().map((node) => {
          const clickable = node.data.type === "family" || node.data.type === "category";
          const isSelected = node.data.id === selectedId;
          const dimmed = relevantIds ? !relevantIds.has(node.data.id) : false;
          const percent = node.data.type === "category" ? openRatioPercent(node.data) : null;
          const lClass = node.data.type === "category" ? loadClass(percent) : "";

          let nodeClass = "optick-radial-node";
          if (node.data.type === "family") nodeClass += " optick-radial-node-family";
          if (node.data.type === "category") nodeClass += ` optick-radial-node-category ${lClass}`;
          if (node.data.type === "more") nodeClass += " optick-radial-node-more";
          if (isSelected) nodeClass += " optick-radial-node-selected";
          if (dimmed) nodeClass += " optick-radial-dim";
          if (clickable) nodeClass += " optick-radial-node-clickable";

          return (
            <g
              key={node.data.id}
              transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}
              onClick={clickable ? () => onSelectNode(node.data) : undefined}
              className={clickable ? "optick-radial-node-group" : undefined}
            >
              <circle r={node.depth === 0 ? 6 : node.depth === 1 ? 5 : 3.5} className={nodeClass}>
                {clickable && <title>{node.data.name}</title>}
              </circle>
              <text
                dy="0.31em"
                x={node.x < Math.PI ? 9 : -9}
                textAnchor={node.x < Math.PI ? "start" : "end"}
                transform={node.x >= Math.PI ? "rotate(180)" : null}
                className={`optick-radial-label${dimmed ? " optick-radial-dim" : ""}`}
              >
                {truncateLabel(node.data.name)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
