import { useEffect, useMemo, useState } from "react";
import { fetchCactiHealth, fetchCactiRoots, fetchCactiTree } from "./cactiApi.js";
import { normalizeText, findPathToNode, computeRelevantIds } from "./optickLib.js";
import CactiJsonPanel from "../components/CactiJsonPanel.jsx";

// Onglet Cacti (livraison #362) -- module backend (cacti-api) prêt
// depuis longtemps ("pour alimenter l'onglet Cacti du frontend", voir
// cacti/api/app.py), jamais construit avant cette livraison --
// découvert en vérifiant systématiquement quels services API
// n'avaient AUCUN consommateur frontend évident (même démarche que
// la découverte OwnCloud côté hub, #354).
//
// Arbre SIMPLE (liste imbriquée dépliable), pas de visualisation
// radiale contrairement à OptickApp/OwncloudApp -- cacti-api renvoie
// déjà tout l'arbre en un seul appel (pas de chargement paresseux par
// niveau à orchestrer), et une liste dépliable suffit à naviguer
// dossiers/hôtes/graphes sans le coût de développement d'un rendu
// radial complet. Réutilise les utilitaires GÉNÉRIQUES d'optickLib.js
// (normalizeText/findPathToNode/computeRelevantIds -- travaillent sur
// n'importe quel arbre {id, name, children}, vérifié ne rien
// présumer de spécifique à Optick avant réemploi).

const TYPE_ICONS = { tree: "🌳", header: "📁", host: "🖥️", graph: "📈" };

function TreeNode({ node, depth, selectedId, onSelect, relevantIds }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children && node.children.length > 0;
  const isRelevant = relevantIds === null || relevantIds.has(node.id);

  return (
    <div style={{ marginLeft: depth > 0 ? 16 : 0 }}>
      <div
        className={`cacti-tree-row${node.id === selectedId ? " selected" : ""}`}
        style={{ opacity: isRelevant ? 1 : 0.35, display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}
        onClick={() => onSelect(node)}
      >
        {hasChildren ? (
          <span
            onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
            style={{ cursor: "pointer", width: 14, display: "inline-block" }}
          >
            {expanded ? "▾" : "▸"}
          </span>
        ) : (
          <span style={{ width: 14, display: "inline-block" }} />
        )}
        <span>{TYPE_ICONS[node.type] || "•"}</span>
        <span>{node.name}</span>
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              relevantIds={relevantIds}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function CactiApp() {
  const [health, setHealth] = useState(null);

  const [roots, setRoots] = useState([]);
  const [rootsError, setRootsError] = useState(null);
  const [rootsLoaded, setRootsLoaded] = useState(false);
  const [rootQuery, setRootQuery] = useState("");

  const [selectedRootId, setSelectedRootId] = useState(null);
  const [tree, setTree] = useState(null);
  const [treeError, setTreeError] = useState(null);
  const [treeLoading, setTreeLoading] = useState(false);

  const [selectedNode, setSelectedNode] = useState(null);
  const [filterQuery, setFilterQuery] = useState("");

  useEffect(() => {
    fetchCactiHealth().then(setHealth);
    fetchCactiRoots().then(({ roots, error }) => {
      setRoots(roots);
      setRootsError(error);
      setRootsLoaded(true);
    });
  }, []);

  useEffect(() => {
    if (selectedRootId === null) return;
    setTreeLoading(true);
    setTreeError(null);
    fetchCactiTree(selectedRootId).then(({ tree, error }) => {
      setTree(tree);
      setTreeError(error);
      setSelectedNode(tree || null);
      setFilterQuery("");
      setTreeLoading(false);
    });
  }, [selectedRootId]);

  const filteredRoots = useMemo(() => {
    const q = normalizeText(rootQuery).trim();
    if (!q) return roots;
    return roots.filter((r) => normalizeText(r.name).includes(q));
  }, [roots, rootQuery]);

  const breadcrumb = useMemo(
    () => (tree && selectedNode ? findPathToNode(tree, selectedNode.id) : null),
    [tree, selectedNode]
  );

  const relevantIds = useMemo(() => computeRelevantIds(tree, filterQuery), [tree, filterQuery]);

  return (
    <div className="optick-shell">
      {health && health.status !== "ok" && (
        <div className="optick-health-banner">
          ⚠️ Base Cacti {health.db === "non configuré" ? "non configurée" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir cacti/README.md).
        </div>
      )}

      <div className="optick-columns" style={{ display: "flex", gap: 16 }}>
        <aside className="optick-col-left" style={{ minWidth: 220 }}>
          <h2>Racines indépendantes</h2>
          <input
            className="optick-search-input"
            placeholder="Filtrer…"
            value={rootQuery}
            onChange={(e) => setRootQuery(e.target.value)}
          />
          {!rootsLoaded && <p className="optick-empty">Chargement…</p>}
          {rootsError && <p className="optick-error">{rootsError}</p>}
          {rootsLoaded && !rootsError && filteredRoots.length === 0 && (
            <p className="optick-empty">Aucune racine trouvée.</p>
          )}
          <ul className="optick-root-list" style={{ listStyle: "none", padding: 0 }}>
            {filteredRoots.map((r) => (
              <li key={r.id}>
                <button
                  className={`optick-root-item${r.id === selectedRootId ? " selected" : ""}`}
                  onClick={() => setSelectedRootId(r.id)}
                >
                  <div className="optick-root-name">{r.name}</div>
                  <div className="optick-root-counts">
                    {r.childSectionCount} section{r.childSectionCount > 1 ? "s" : ""} · {r.subnetCount} graphe{r.subnetCount > 1 ? "s" : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="optick-col-center" style={{ flex: 1 }}>
          {selectedRootId !== null && (
            <div className="optick-center-toolbar">
              <input
                className="optick-search-input"
                placeholder="🔍 Filtrer l'arbre (nom…)"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
              />
              {breadcrumb && (
                <div className="optick-breadcrumb">
                  {breadcrumb.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && <span className="optick-breadcrumb-sep">›</span>}
                      <span className="optick-breadcrumb-item" onClick={() => setSelectedNode(n)} style={{ cursor: "pointer" }}>
                        {n.name}
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {selectedRootId === null && (
            <p className="optick-empty">Choisissez une racine indépendante à gauche.</p>
          )}
          {treeLoading && <p className="optick-empty">Chargement de l'arbre…</p>}
          {treeError && <p className="optick-error">{treeError}</p>}
          {!treeLoading && !treeError && tree && (
            <TreeNode
              node={tree}
              depth={0}
              selectedId={selectedNode?.id}
              onSelect={setSelectedNode}
              relevantIds={relevantIds}
            />
          )}
        </section>

        <aside className="optick-col-right" style={{ minWidth: 260 }}>
          <h2>Fiche JSON</h2>
          <CactiJsonPanel node={selectedNode} />
        </aside>
      </div>
    </div>
  );
}
