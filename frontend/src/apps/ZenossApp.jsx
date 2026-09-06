import { useEffect, useMemo, useState } from "react";
import {
  fetchZenossHealth, fetchZenossRoots, fetchZenossTree,
  fetchZenossLocationRoots, fetchZenossLocationTree,
} from "./zenossApi.js";
import { normalizeText, findPathToNode, fmtTimelineDate, computeRelevantIds } from "./zenossLib.js";
import { pruneToRelevant } from "../lib/treeFreeze.js";
import ZenossRadialTree from "../components/ZenossRadialTree.jsx";
import ZenossLocationTree from "../components/ZenossLocationTree.jsx";
import ZenossJsonPanel from "../components/ZenossJsonPanel.jsx";
import TimelineRangeSlider from "../components/TimelineRangeSlider.jsx";
import FreezeSnapshotButton from "../components/FreezeSnapshotButton.jsx";
import useDebouncedValue from "../hooks/useDebouncedValue.js";

// "classification" (existant, /roots + /tree, par eventClass) ou
// "location" (EXCEPTION délibérée et scopée — /location_roots +
// /location_tree, par Location/IP/Systems ; voir zenoss/api/app.py
// et zenoss/README.md, section "Inventaire physique").
const MODES = {
  classification: {
    label: "Classification",
    fetchRoots: fetchZenossRoots,
    fetchTree: (rootId) => fetchZenossTree(rootId),
    fetchTreeWindowed: (rootId, range) => fetchZenossTree(rootId, range),
    TreeComponent: ZenossRadialTree,
    freezePrefix: "zenoss",
    rootCountLabel: (r) => `${r.childSectionCount} classe${r.childSectionCount > 1 ? "s" : ""} · ${r.subnetCount} événement${r.subnetCount > 1 ? "s" : ""} actif${r.subnetCount > 1 ? "s" : ""}`,
  },
  location: {
    label: "Localisation",
    fetchRoots: fetchZenossLocationRoots,
    fetchTree: (rootId) => fetchZenossLocationTree(rootId),
    fetchTreeWindowed: null, // pas de fenêtre temporelle pour ce mode (v1)
    TreeComponent: ZenossLocationTree,
    freezePrefix: "zenoss-location",
    rootCountLabel: (r) => `${r.childSectionCount} noeud${r.childSectionCount > 1 ? "s" : ""} · ${r.subnetCount} équipement${r.subnetCount > 1 ? "s" : ""}`,
  },
};

export default function ZenossApp() {
  const [health, setHealth] = useState(null);
  const [mode, setMode] = useState("classification");
  const modeConfig = MODES[mode];

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
  const [timelineRange, setTimelineRange] = useState(null);
  const [dateBounds, setDateBounds] = useState(null);
  const debouncedRange = useDebouncedValue(timelineRange, 300);

  useEffect(() => {
    fetchZenossHealth().then(setHealth);
  }, []);

  // Rechargement complet des racines à chaque changement de mode (et au
  // montage) — les deux modes n'ont ni le même id de racine ni la même
  // forme d'arbre, donc on repart d'un état propre plutôt que de tenter
  // de faire cohabiter les deux.
  useEffect(() => {
    setRootsLoaded(false);
    setSelectedRootId(null);
    setTree(null);
    setSelectedNode(null);
    setTimelineRange(null);
    setDateBounds(null);
    setFilterQuery("");
    modeConfig.fetchRoots().then(({ roots, error }) => {
      setRoots(roots);
      setRootsError(error);
      setRootsLoaded(true);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    if (selectedRootId === null) return;
    setTreeLoading(true);
    setTreeError(null);
    setTimelineRange(null);
    modeConfig.fetchTree(selectedRootId).then(({ tree, dateBounds, error }) => {
      setTree(tree);
      setDateBounds(dateBounds || null);
      setTreeError(error);
      setSelectedNode(tree || null);
      setFilterQuery("");
      setTreeLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRootId, mode]);

  useEffect(() => {
    if (selectedRootId === null || !modeConfig.fetchTreeWindowed) return;
    modeConfig.fetchTreeWindowed(selectedRootId, debouncedRange).then(({ tree: newTree, dateBounds: newBounds, error }) => {
      if (error) {
        setTreeError(error);
        return;
      }
      setTree(newTree);
      setDateBounds(newBounds);
      setTreeError(null);
      setSelectedNode((prev) => {
        if (!prev) return newTree;
        const path = findPathToNode(newTree, prev.id);
        return path ? path[path.length - 1] : newTree;
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedRange]);

  const filteredRoots = useMemo(() => {
    const q = normalizeText(rootQuery).trim();
    if (!q) return roots;
    return roots.filter((r) => normalizeText(r.name).includes(q));
  }, [roots, rootQuery]);

  const breadcrumb = useMemo(
    () => (tree && selectedNode ? findPathToNode(tree, selectedNode.id) : null),
    [tree, selectedNode]
  );

  const effectiveRange = timelineRange || (dateBounds && { start: dateBounds.min, end: dateBounds.max });

  const relevantIds = useMemo(() => computeRelevantIds(tree, filterQuery), [tree, filterQuery]);
  const frozenPreview = useMemo(() => pruneToRelevant(tree, relevantIds), [tree, relevantIds]);

  return (
    <div className="zenoss-shell">
      {health && health.status !== "ok" && (
        <div className="zenoss-health-banner">
          ⚠️ Base Zenoss {health.db === "non configuré" ? "non configurée" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir zenoss/README.md).
        </div>
      )}

      <div className="zenoss-mode-tabs">
        {Object.entries(MODES).map(([key, cfg]) => (
          <button
            key={key}
            className={`zenoss-mode-tab${mode === key ? " active" : ""}`}
            onClick={() => setMode(key)}
          >
            {cfg.label}
          </button>
        ))}
      </div>

      <div className="zenoss-columns">
        <aside className="zenoss-col-left">
          <h2>Racines indépendantes</h2>
          <input
            className="zenoss-search-input"
            placeholder="Filtrer…"
            value={rootQuery}
            onChange={(e) => setRootQuery(e.target.value)}
          />
          {!rootsLoaded && <p className="zenoss-empty">Chargement…</p>}
          {rootsError && <p className="zenoss-error">{rootsError}</p>}
          {rootsLoaded && !rootsError && filteredRoots.length === 0 && (
            <p className="zenoss-empty">Aucune racine trouvée.</p>
          )}
          <ul className="zenoss-root-list">
            {filteredRoots.map((r) => (
              <li key={r.id}>
                <button
                  className={`zenoss-root-item${r.id === selectedRootId ? " selected" : ""}`}
                  onClick={() => setSelectedRootId(r.id)}
                >
                  <div className="zenoss-root-name">{r.name}</div>
                  <div className="zenoss-root-counts">{modeConfig.rootCountLabel(r)}</div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="zenoss-col-center">
          {selectedRootId !== null && (
            <div className="zenoss-center-toolbar">
              <input
                className="zenoss-search-input"
                placeholder="🔍 Filtrer l'arbre (nom, chemin…)"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
              />
              {breadcrumb && (
                <div className="zenoss-breadcrumb">
                  {breadcrumb.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && <span className="zenoss-breadcrumb-sep">›</span>}
                      <span className="zenoss-breadcrumb-item" onClick={() => setSelectedNode(n)}>
                        {n.name}
                      </span>
                    </span>
                  ))}
                </div>
              )}
              {dateBounds && (
                <div className="zenoss-timeline-row">
                  <TimelineRangeSlider
                    min={dateBounds.min}
                    max={dateBounds.max}
                    start={effectiveRange.start}
                    end={effectiveRange.end}
                    onChange={(start, end) => setTimelineRange({ start, end })}
                    formatValue={fmtTimelineDate}
                  />
                  {timelineRange && (
                    <button className="zenoss-timeline-reset" onClick={() => setTimelineRange(null)}>
                      ↺ Toute la période
                    </button>
                  )}
                </div>
              )}
              <FreezeSnapshotButton prefix={modeConfig.freezePrefix} rootName={tree?.name} frozenData={frozenPreview} />
            </div>
          )}

          {selectedRootId === null && (
            <p className="zenoss-empty">Choisissez une racine indépendante à gauche.</p>
          )}
          {treeLoading && <p className="zenoss-empty">Chargement de l'arbre…</p>}
          {treeError && <p className="zenoss-error">{treeError}</p>}
          {!treeLoading && !treeError && tree && (
            <modeConfig.TreeComponent
              tree={tree}
              selectedId={selectedNode?.id}
              onSelectNode={setSelectedNode}
              relevantIds={relevantIds}
            />
          )}
        </section>

        <aside className="zenoss-col-right">
          <h2>Fiche JSON</h2>
          <ZenossJsonPanel node={selectedNode} />
        </aside>
      </div>
    </div>
  );
}
