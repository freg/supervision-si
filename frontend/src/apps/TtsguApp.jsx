import { useEffect, useMemo, useState } from "react";
import { fetchTtsguHealth, fetchTtsguRoots, fetchTtsguTree } from "./ttsguApi.js";
import { normalizeText, findPathToNode, fmtTimelineDate, computeRelevantIds } from "./ttsguLib.js";
import { pruneToRelevant } from "../lib/treeFreeze.js";
import TtsguRadialTree from "../components/TtsguRadialTree.jsx";
import TtsguJsonPanel from "../components/TtsguJsonPanel.jsx";
import TimelineRangeSlider from "../components/TimelineRangeSlider.jsx";
import FreezeSnapshotButton from "../components/FreezeSnapshotButton.jsx";
import useDebouncedValue from "../hooks/useDebouncedValue.js";

export default function TtsguApp() {
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
  const [timelineRange, setTimelineRange] = useState(null);
  const [dateBounds, setDateBounds] = useState(null);
  const debouncedRange = useDebouncedValue(timelineRange, 300);

  useEffect(() => {
    fetchTtsguHealth().then(setHealth);
    fetchTtsguRoots().then(({ roots, error }) => {
      setRoots(roots);
      setRootsError(error);
      setRootsLoaded(true);
    });
  }, []);

  useEffect(() => {
    if (selectedRootId === null) return;
    setTreeLoading(true);
    setTreeError(null);
    setTimelineRange(null);
    fetchTtsguTree(selectedRootId).then(({ tree, dateBounds, error }) => {
      setTree(tree);
      setDateBounds(dateBounds);
      setTreeError(error);
      setSelectedNode(tree || null);
      setFilterQuery("");
      setTreeLoading(false);
    });
  }, [selectedRootId]);

  useEffect(() => {
    if (selectedRootId === null) return;
    fetchTtsguTree(selectedRootId, debouncedRange).then(({ tree: newTree, dateBounds: newBounds, error }) => {
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
    <div className="ttsgu-shell">
      {health && health.status !== "ok" && (
        <div className="ttsgu-health-banner">
          ⚠️ Base TTS-GU {health.db === "non configuré" ? "non configurée" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir tts-gu/README.md).
        </div>
      )}

      <div className="ttsgu-columns">
        <aside className="ttsgu-col-left">
          <h2>Racines indépendantes</h2>
          <input
            className="ttsgu-search-input"
            placeholder="Filtrer…"
            value={rootQuery}
            onChange={(e) => setRootQuery(e.target.value)}
          />
          {!rootsLoaded && <p className="ttsgu-empty">Chargement…</p>}
          {rootsError && <p className="ttsgu-error">{rootsError}</p>}
          {rootsLoaded && !rootsError && filteredRoots.length === 0 && (
            <p className="ttsgu-empty">Aucune racine trouvée.</p>
          )}
          <ul className="ttsgu-root-list">
            {filteredRoots.map((r) => (
              <li key={r.id}>
                <button
                  className={`ttsgu-root-item${r.id === selectedRootId ? " selected" : ""}`}
                  onClick={() => setSelectedRootId(r.id)}
                >
                  <div className="ttsgu-root-name">{r.name}</div>
                  <div className="ttsgu-root-counts">
                    {r.childSectionCount} catégorie{r.childSectionCount > 1 ? "s" : ""} · {r.subnetCount} ticket{r.subnetCount > 1 ? "s" : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="ttsgu-col-center">
          {selectedRootId !== null && (
            <div className="ttsgu-center-toolbar">
              <input
                className="ttsgu-search-input"
                placeholder="🔍 Filtrer l'arbre (nom…)"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
              />
              {breadcrumb && (
                <div className="ttsgu-breadcrumb">
                  {breadcrumb.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && <span className="ttsgu-breadcrumb-sep">›</span>}
                      <span className="ttsgu-breadcrumb-item" onClick={() => setSelectedNode(n)}>
                        {n.name}
                      </span>
                    </span>
                  ))}
                </div>
              )}
              {dateBounds && (
                <div className="ttsgu-timeline-row">
                  <TimelineRangeSlider
                    min={dateBounds.min}
                    max={dateBounds.max}
                    start={effectiveRange.start}
                    end={effectiveRange.end}
                    onChange={(start, end) => setTimelineRange({ start, end })}
                    formatValue={fmtTimelineDate}
                  />
                  {timelineRange && (
                    <button className="ttsgu-timeline-reset" onClick={() => setTimelineRange(null)}>
                      ↺ Toute la période
                    </button>
                  )}
                </div>
              )}
              <FreezeSnapshotButton prefix="ttsgu" rootName={tree?.name} frozenData={frozenPreview} />
            </div>
          )}

          {selectedRootId === null && (
            <p className="ttsgu-empty">Choisissez une racine indépendante à gauche.</p>
          )}
          {treeLoading && <p className="ttsgu-empty">Chargement de l'arbre…</p>}
          {treeError && <p className="ttsgu-error">{treeError}</p>}
          {!treeLoading && !treeError && tree && (
            <TtsguRadialTree
              tree={tree}
              selectedId={selectedNode?.id}
              onSelectNode={setSelectedNode}
              relevantIds={relevantIds}
            />
          )}
        </section>

        <aside className="ttsgu-col-right">
          <h2>Fiche JSON</h2>
          <TtsguJsonPanel node={selectedNode} />
        </aside>
      </div>
    </div>
  );
}
