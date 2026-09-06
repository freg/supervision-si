import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { isPathSelected, getValueAtPath } from "./JsonTree.jsx";
import { countNodesAndDepth } from "../lib/treeStats.js";

const MAX_DEPTH = 4; // au-delà, on résume en "…" pour garder l'arbre lisible
const HOVER_TABLE_MAX_DEPTH = 2; // profondeur de l'extrait tabulaire au survol

/**
 * Arbre FILTRÉ (vue normale) : ne contient que ce qui est actuellement
 * sélectionné — un nœud décoché, et donc tout son sous-arbre, est
 * simplement absent plutôt que grisé.
 */
function buildFilteredNode(label, value, path, deselectedPaths, depth, sourceName) {
  if (!isPathSelected(path, deselectedPaths)) return null;

  const node = { name: label, path, source: sourceName, partial: false };

  if (value !== null && typeof value === "object") {
    if (depth >= MAX_DEPTH) {
      node.children = [{ name: "…" }];
      return node;
    }

    const entries = Array.isArray(value)
      ? value.map((v, i) => [`[${i}]`, v, `${path}[${i}]`])
      : Object.entries(value).map(([k, v]) => [k, v, `${path}.${k}`]);

    const builtChildren = entries.map(([childLabel, childValue, childPath]) =>
      buildFilteredNode(childLabel, childValue, childPath, deselectedPaths, depth + 1, sourceName)
    );
    const keptChildren = builtChildren.filter(Boolean);

    node.partial = builtChildren.some((c) => c === null) || keptChildren.some((c) => c.partial);
    if (keptChildren.length) node.children = keptChildren;
  }

  return node;
}

function buildFilteredHierarchy(basketEntries, sourceData) {
  const root = { name: "Sélection", children: [] };
  for (const [source, entry] of Object.entries(basketEntries)) {
    const data = sourceData[source];
    if (data === undefined) continue;
    const sourceNode = buildFilteredNode(source, data, "$", entry.deselectedPaths, 0, source);
    if (sourceNode) root.children.push(sourceNode);
  }
  return root;
}

/**
 * Sous-arbre non filtré (branchement complet, plafonné à MAX_DEPTH),
 * utilisé sous le nœud ciblé par l'aperçu — tous les nœuds existent,
 * sélectionnés ou non, avec leur état `selected` propre pour la couleur.
 */
function buildFullSubtreeChildren(value, path, deselectedPaths, depth, sourceName) {
  if (value === null || typeof value !== "object") return undefined;
  if (depth >= MAX_DEPTH) return [{ name: "…" }];

  const entries = Array.isArray(value)
    ? value.map((v, i) => [`[${i}]`, v, `${path}[${i}]`])
    : Object.entries(value).map(([k, v]) => [k, v, `${path}.${k}`]);

  return entries.map(([label, childValue, childPath]) => ({
    name: label,
    path: childPath,
    source: sourceName,
    selected: isPathSelected(childPath, deselectedPaths),
    children: buildFullSubtreeChildren(childValue, childPath, deselectedPaths, depth + 1, sourceName),
  }));
}

/**
 * Arbre de CONTEXTE (aperçu "premier clic") : une chaîne simple depuis
 * la racine jusqu'au nœud ciblé (un segment par niveau, pas de
 * ramification), puis — seulement au nœud ciblé — le sous-arbre complet
 * en aval s'il en a un. Un clic sur une feuille donne donc une simple
 * ligne ; un clic sur un nœud intermédiaire donne la ligne + un petit
 * arbre en bout de chaîne.
 */
function buildFocusChain(source, sourceData, deselectedPaths, targetPath) {
  const rawRoot = sourceData[source];
  if (rawRoot === undefined) return { name: source, path: "$", source, selected: true };

  const tokens = targetPath === "$" ? [] : targetPath.slice(1).match(/\.[^.[\]]+|\[\d+\]/g) || [];
  const chainPaths = ["$"];
  let cumulative = "$";
  for (const token of tokens) {
    cumulative += token;
    chainPaths.push(cumulative);
  }

  let chainNode = null;
  for (let i = chainPaths.length - 1; i >= 0; i--) {
    const p = chainPaths[i];
    const label = i === 0 ? source : tokens[i - 1].startsWith(".") ? tokens[i - 1].slice(1) : tokens[i - 1];
    const selected = isPathSelected(p, deselectedPaths);
    const node = { name: label, path: p, source, selected };

    if (i === chainPaths.length - 1) {
      const value = getValueAtPath(rawRoot, p);
      const children = buildFullSubtreeChildren(value, p, deselectedPaths, 0, source);
      if (children) node.children = children;
    } else {
      node.children = [chainNode];
    }
    chainNode = node;
  }

  return chainNode;
}

/**
 * Extrait tabulaire d'une valeur JSON — jusqu'à HOVER_TABLE_MAX_DEPTH
 * niveaux, aplatis avec indentation. Utilisé par le panneau de survol
 * (remplace la loupe texte SVG, illisible à cette échelle).
 */
function buildTableRows(value, depth = 0, maxDepth = HOVER_TABLE_MAX_DEPTH) {
  if (value === null || typeof value !== "object") return [];

  const entries = Array.isArray(value)
    ? value.map((v, i) => [`[${i}]`, v])
    : Object.entries(value);

  const rows = [];
  for (const [key, val] of entries) {
    const isObj = val !== null && typeof val === "object";
    const summary = isObj
      ? Array.isArray(val)
        ? `[${val.length}]`
        : `{${Object.keys(val).length}}`
      : String(val);
    rows.push({ key, value: summary, depth, expandable: isObj });
    if (isObj && depth + 1 < maxDepth) {
      rows.push(...buildTableRows(val, depth + 1, maxDepth));
    }
  }
  return rows;
}

/**
 * Compte les nœuds et la profondeur maximale d'un arbre {name,
 * children} — voir ../lib/treeStats.js pour la fonction elle-même
 * (extraite pour rester testable sans D3 ni React), rien à
 * redéfinir ici.
 */

// Seuil au-delà duquel le rendu complet est remplacé par un résumé --
// choisi par prudence (un arbre radial D3 reste lisible jusqu'à
// quelques centaines de nœuds, devient franchement confus bien avant
// d'atteindre un problème de performance pur) ; jamais vérifié
// visuellement dans cet environnement de développement, à ajuster
// après un vrai test si ça se révèle trop bas ou trop haut.
const SUMMARY_THRESHOLD_NODES = 300;

export default function RadialTree({ basketEntries, sourceData, onToggleSelection, radius = 200 }) {
  const [hovered, setHovered] = useState(null); // { label, cornerX, cornerY, quadX, quadY, rows }
  const [preview, setPreview] = useState(null); // { source, path } | null
  const [zoomLevel, setZoomLevel] = useState(1);
  const [zoomOrigin, setZoomOrigin] = useState({ x: 50, y: 50 });
  const zoomWrapperRef = useRef(null);
  // Échappatoire explicite au résumé (voir plus bas) -- RÉINITIALISÉE
  // à chaque changement de sélection/prévisualisation : forcer
  // l'affichage complet une fois ne doit jamais rester "collé" sur
  // une AUTRE sélection volumineuse choisie ensuite sans un nouveau
  // choix explicite pour CELLE-LÀ.
  const [forceRenderLarge, setForceRenderLarge] = useState(false);

  const filteredRoot = useMemo(
    () => buildFilteredHierarchy(basketEntries, sourceData),
    [basketEntries, sourceData]
  );
  const coveringRoot = useMemo(() => {
    if (!preview) return null;
    return buildFocusChain(
      preview.source,
      sourceData,
      basketEntries[preview.source]?.deselectedPaths || new Set(),
      preview.path
    );
  }, [preview, basketEntries, sourceData]);

  const isPreviewing = Boolean(preview);
  const displayRoot = isPreviewing ? coveringRoot : filteredRoot;

  useEffect(() => {
    setForceRenderLarge(false);
  }, [basketEntries, preview]);

  if (!isPreviewing && (!filteredRoot.children || filteredRoot.children.length === 0)) {
    return (
      <p className="synthesis-empty">
        L'arbre apparaîtra ici une fois la corbeille non vide.
      </p>
    );
  }

  // Comptage AVANT tout calcul D3 -- un arbre à plusieurs milliers de
  // nœuds rendu en entier n'est pas juste lent, il devient
  // concrètement inutilisable (retour réel rencontré : sélection
  // quasi impossible sur une source à 5000 éléments). Résumé (2
  // chiffres) proposé à la place, avec une échappatoire explicite
  // (bouton) pour la personne qui voudrait quand même voir le rendu
  // complet -- jamais un blocage strict, elle garde la main.
  const { nodeCount, maxDepth } = countNodesAndDepth(displayRoot);
  const tooLargeToRender = nodeCount > SUMMARY_THRESHOLD_NODES;

  if (tooLargeToRender && !forceRenderLarge) {
    return (
      <div className="radial-tree-summary">
        <p className="radial-tree-summary-numbers">
          <strong>{nodeCount}</strong> nœuds · <strong>{maxDepth}</strong> niveaux
        </p>
        <p className="synthesis-empty">
          Trop volumineux pour un rendu lisible — affiné la sélection
          dans la corbeille pour réduire, ou forcez l'affichage complet
          (peut être lent et difficile à naviguer).
        </p>
        <button className="pixel-grid-reset-btn" onClick={() => setForceRenderLarge(true)}>
          Afficher quand même ({nodeCount} nœuds)
        </button>
      </div>
    );
  }

  const hierarchyRoot = d3.hierarchy(displayRoot);
  d3.tree().size([2 * Math.PI, radius])(hierarchyRoot);

  const linkGenerator = d3.linkRadial().angle((d) => d.x).radius((d) => d.y);
  const margin = 60;
  const extent = radius + margin;
  const markerRadius = radius * 0.03;

  function screenPosOf(node) {
    const angle = node.x - Math.PI / 2;
    return { screenX: node.y * Math.cos(angle), screenY: node.y * Math.sin(angle) };
  }

  function handleEnter(node) {
    const { screenX, screenY } = screenPosOf(node);
    const quadX = screenX >= 0 ? 1 : -1;
    const quadY = screenY >= 0 ? 1 : -1;
    const cornerX = quadX * (extent - markerRadius - 6);
    const cornerY = quadY * (extent - markerRadius - 6);

    const rawRoot = sourceData[node.data.source];
    const rawValue = node.data.path ? getValueAtPath(rawRoot, node.data.path) : rawRoot;
    const rows = buildTableRows(rawValue);

    setHovered({ label: node.data.name, cornerX, cornerY, quadX, quadY, rows });
  }

  function handleLeave() {
    setHovered(null);
  }

  function handleClick(node) {
    if (!node.data.path) return;
    if (isPreviewing) {
      onToggleSelection(node.data.source, node.data.path);
      setPreview(null);
    } else {
      setPreview({ source: node.data.source, path: node.data.path });
    }
  }

  // Clic droit = zoom centré sur le point cliqué. Le menu contextuel du
  // navigateur est désactivé sur l'arbre à cet effet.
  function handleContextMenu(e) {
    e.preventDefault();
    if (!zoomWrapperRef.current) return;
    const rect = zoomWrapperRef.current.getBoundingClientRect();
    const originX = ((e.clientX - rect.left) / rect.width) * 100;
    const originY = ((e.clientY - rect.top) / rect.height) * 100;
    setZoomOrigin({ x: originX, y: originY });
    setZoomLevel((z) => Math.min(z + 0.75, 4));
  }

  function handleZoomReset() {
    setZoomLevel(1);
    setZoomOrigin({ x: 50, y: 50 });
  }

  // Position HTML (en %) du panneau de survol, dérivée de la même
  // logique de coin le plus proche que le marqueur SVG.
  const hoverPanelStyle = hovered
    ? {
        left: `${((hovered.cornerX + extent) / (2 * extent)) * 100}%`,
        top: `${((hovered.cornerY + extent) / (2 * extent)) * 100}%`,
        transform: `translate(${hovered.quadX > 0 ? "-100%" : "0%"}, ${hovered.quadY > 0 ? "-100%" : "0%"})`,
      }
    : null;

  return (
    <div className="radial-tree-container-wrapper">
      {isPreviewing && (
        <div className="radial-preview-header">
          <span>Aperçu — {preview.source}</span>
          <button className="calendar-nav-btn" onClick={() => setPreview(null)}>
            ← Retour
          </button>
        </div>
      )}

      {zoomLevel !== 1 && (
        <div className="radial-zoom-control">
          <span>🔍 x{zoomLevel.toFixed(1)}</span>
          <input
            type="range"
            min="1"
            max="4"
            step="0.1"
            value={zoomLevel}
            onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
          />
          <button className="calendar-nav-btn" onClick={handleZoomReset}>
            ↺ Réinitialiser
          </button>
        </div>
      )}

      <div
        ref={zoomWrapperRef}
        className="radial-tree-zoom-wrapper"
        onContextMenu={handleContextMenu}
        title="Clic droit : zoomer sur ce point"
      >
        <svg
          viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`}
          className="radial-tree-svg"
          style={{
            transform: `scale(${zoomLevel})`,
            transformOrigin: `${zoomOrigin.x}% ${zoomOrigin.y}%`,
          }}
        >
          {hierarchyRoot.links().map((link, i) => (
            <path
              key={i}
              d={linkGenerator(link)}
              className={`radial-tree-link ${!isPreviewing && link.target.data.partial ? "radial-tree-link-partial" : ""}`}
            />
          ))}

          {hierarchyRoot.descendants().map((node, i) => {
            const clickable = Boolean(node.data.path);
            const isRoot = node.depth === 0;
            let nodeClass = "radial-tree-node";
            if (!isRoot) {
              if (isPreviewing) {
                nodeClass += node.data.selected ? " radial-tree-node-full" : " radial-tree-node-off";
              } else {
                nodeClass += node.data.partial ? " radial-tree-node-partial" : " radial-tree-node-full";
              }
            }
            if (clickable) nodeClass += " radial-tree-node-clickable";

            return (
              <g
                key={i}
                transform={`rotate(${(node.x * 180) / Math.PI - 90}) translate(${node.y},0)`}
                onClick={clickable ? () => handleClick(node) : undefined}
                onMouseEnter={() => handleEnter(node)}
                onMouseLeave={handleLeave}
                className={clickable ? "radial-tree-node-group" : undefined}
              >
                <circle r={node.depth === 1 ? 5 : 3.5} className={nodeClass}>
                  {clickable && (
                    <title>
                      {isPreviewing
                        ? node.data.selected
                          ? "Cliquer pour désélectionner"
                          : "Cliquer pour ajouter à la sélection"
                        : "Cliquer pour voir le contexte de ce nœud"}
                    </title>
                  )}
                </circle>
                <text
                  dy="0.31em"
                  x={node.x < Math.PI ? 8 : -8}
                  textAnchor={node.x < Math.PI ? "start" : "end"}
                  transform={node.x >= Math.PI ? "rotate(180)" : null}
                  className="radial-tree-label"
                >
                  {node.data.name}
                </text>
              </g>
            );
          })}

          {hovered && (
            <circle cx={hovered.cornerX} cy={hovered.cornerY} r={markerRadius} className="radial-loupe-disk" />
          )}
        </svg>
      </div>

      {hovered && (
        <div className="radial-hover-panel" style={hoverPanelStyle}>
          <div className="radial-hover-title">{hovered.label}</div>
          {hovered.rows.length > 0 ? (
            <table className="radial-hover-table">
              <tbody>
                {hovered.rows.map((r, i) => (
                  <tr key={i}>
                    <th style={{ paddingLeft: `${r.depth * 10}px` }}>{r.key}</th>
                    <td>{r.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="radial-hover-empty">(valeur simple, pas de sous-clés)</p>
          )}
        </div>
      )}
    </div>
  );
}
