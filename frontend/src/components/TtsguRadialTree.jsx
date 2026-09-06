import { useMemo } from "react";
import * as d3 from "d3";
import { truncateLabel, openRatioPercent, loadClass } from "../apps/ttsguLib.js";

const MAX_DEPTH = 7;

function capDepth(node, depth) {
  if (depth >= MAX_DEPTH && node.children && node.children.length > 0) {
    return { ...node, children: [{ id: `${node.id}-more`, type: "more", name: "…", children: [] }] };
  }
  return { ...node, children: (node.children || []).map((c) => capDepth(c, depth + 1)) };
}

export default function TtsguRadialTree({ tree, selectedId, onSelectNode, relevantIds = null, radius = 220 }) {
  const cappedTree = useMemo(() => (tree ? capDepth(tree, 0) : null), [tree]);

  if (!cappedTree) {
    return <p className="ttsgu-empty">Sélectionnez une racine à gauche pour afficher son arbre.</p>;
  }

  const hierarchyRoot = d3.hierarchy(cappedTree);
  d3.tree().size([2 * Math.PI, radius])(hierarchyRoot);

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 70;
  const extent = radius + margin;

  return (
    <div className="ttsgu-radial-wrapper">
      <svg viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`} className="ttsgu-radial-svg">
        {hierarchyRoot.links().map((link, i) => {
          const dimmed = relevantIds && !(relevantIds.has(link.source.data.id) && relevantIds.has(link.target.data.id));
          return (
            <path
              key={i}
              d={linkGenerator(link)}
              className={`ttsgu-radial-link${dimmed ? " ttsgu-radial-dim" : ""}`}
            />
          );
        })}

        {hierarchyRoot.descendants().map((node) => {
          const clickable = node.data.type === "domain" || node.data.type === "category";
          const isSelected = node.data.id === selectedId;
          const dimmed = relevantIds ? !relevantIds.has(node.data.id) : false;
          const percent = node.data.type === "category" ? openRatioPercent(node.data) : null;
          const lClass = node.data.type === "category" ? loadClass(percent) : "";

          let nodeClass = "ttsgu-radial-node";
          if (node.data.type === "domain") nodeClass += " ttsgu-radial-node-domain";
          if (node.data.type === "category") nodeClass += ` ttsgu-radial-node-category ${lClass}`;
          if (node.data.type === "more") nodeClass += " ttsgu-radial-node-more";
          if (isSelected) nodeClass += " ttsgu-radial-node-selected";
          if (dimmed) nodeClass += " ttsgu-radial-dim";
          if (clickable) nodeClass += " ttsgu-radial-node-clickable";

          return (
            <g
              key={node.data.id}
              transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}
              onClick={clickable ? () => onSelectNode(node.data) : undefined}
              className={clickable ? "ttsgu-radial-node-group" : undefined}
            >
              <circle r={node.depth === 0 ? 6 : node.depth === 1 ? 5 : 3.5} className={nodeClass}>
                {clickable && <title>{node.data.name}</title>}
              </circle>
              <text
                dy="0.31em"
                x={node.x < Math.PI ? 9 : -9}
                textAnchor={node.x < Math.PI ? "start" : "end"}
                transform={node.x >= Math.PI ? "rotate(180)" : null}
                className={`ttsgu-radial-label${dimmed ? " ttsgu-radial-dim" : ""}`}
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
