import { useMemo } from "react";
import * as d3 from "d3";
import { truncateLabel, dominantSeverity, severityClass } from "../apps/zenossLib.js";

const MAX_DEPTH = 8; // les classes Zenoss peuvent nicher profondément (ex. /App/Fail/Http/Timeout)

function capDepth(node, depth) {
  if (depth >= MAX_DEPTH && node.children && node.children.length > 0) {
    return { ...node, children: [{ id: `${node.id}-more`, type: "more", name: "…", children: [] }] };
  }
  return { ...node, children: (node.children || []).map((c) => capDepth(c, depth + 1)) };
}

export default function ZenossRadialTree({ tree, selectedId, onSelectNode, relevantIds = null, radius = 220 }) {
  const cappedTree = useMemo(() => (tree ? capDepth(tree, 0) : null), [tree]);

  if (!cappedTree) {
    return <p className="zenoss-empty">Sélectionnez une racine à gauche pour afficher son arbre.</p>;
  }

  const hierarchyRoot = d3.hierarchy(cappedTree);
  d3.tree().size([2 * Math.PI, radius])(hierarchyRoot);

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 70;
  const extent = radius + margin;

  return (
    <div className="zenoss-radial-wrapper">
      <svg viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`} className="zenoss-radial-svg">
        {hierarchyRoot.links().map((link, i) => {
          const dimmed = relevantIds && !(relevantIds.has(link.source.data.id) && relevantIds.has(link.target.data.id));
          return (
            <path
              key={i}
              d={linkGenerator(link)}
              className={`zenoss-radial-link${dimmed ? " zenoss-radial-dim" : ""}`}
            />
          );
        })}

        {hierarchyRoot.descendants().map((node) => {
          const clickable = node.data.type === "class";
          const isSelected = node.data.id === selectedId;
          const dimmed = relevantIds ? !relevantIds.has(node.data.id) : false;
          const sev = node.data.type === "class" ? dominantSeverity(node.data) : null;
          const sClass = sev ? severityClass(sev) : "";

          let nodeClass = "zenoss-radial-node";
          if (node.data.type === "class") nodeClass += ` zenoss-radial-node-class ${sClass}`;
          if (node.data.type === "more") nodeClass += " zenoss-radial-node-more";
          if (isSelected) nodeClass += " zenoss-radial-node-selected";
          if (dimmed) nodeClass += " zenoss-radial-dim";
          if (clickable) nodeClass += " zenoss-radial-node-clickable";

          return (
            <g
              key={node.data.id}
              transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}
              onClick={clickable ? () => onSelectNode(node.data) : undefined}
              className={clickable ? "zenoss-radial-node-group" : undefined}
            >
              <circle r={node.depth === 0 ? 6 : node.depth === 1 ? 5 : 3.5} className={nodeClass}>
                {clickable && <title>{node.data.name}</title>}
              </circle>
              <text
                dy="0.31em"
                x={node.x < Math.PI ? 9 : -9}
                textAnchor={node.x < Math.PI ? "start" : "end"}
                transform={node.x >= Math.PI ? "rotate(180)" : null}
                className={`zenoss-radial-label${dimmed ? " zenoss-radial-dim" : ""}`}
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
