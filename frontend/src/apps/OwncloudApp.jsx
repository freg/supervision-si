import { useEffect, useMemo, useState } from "react";
import { fetchOwncloudHealth, fetchOwncloudRoots, fetchOwncloudChildren } from "./owncloudApi.js";
import {
  normalizeText, findPathToNode, mergeChildren, buildRenderTree, fmtBytes,
  computeRelevantIdsByTerms, computeMtimeRelevantIds, mtimeBoundsOfLoadedNodes,
  combineRelevantIds, fmtTimelineDate, guessLocationQuery, sortRoots,
  pruneNodesByNames, countDirectoryNamesIn, mergeOccurrenceCounts, splitOccurrencesByThreshold,
  KNOWN_OWNCLOUD_STRUCTURAL_NAMES, buildVersionTimeline,
} from "./owncloudLib.js";
import { pruneToRelevant } from "../lib/treeFreeze.js";
import OwncloudRadialTree from "../components/OwncloudRadialTree.jsx";
import OwncloudClassicTree from "../components/OwncloudClassicTree.jsx";
import OwncloudFilterTerms from "../components/OwncloudFilterTerms.jsx";
import OwncloudRecurringPanel from "../components/OwncloudRecurringPanel.jsx";
import OwncloudVersionTimeline from "../components/OwncloudVersionTimeline.jsx";
import OwncloudJsonPanel from "../components/OwncloudJsonPanel.jsx";
import OwncloudGeocodePanel from "../components/OwncloudGeocodePanel.jsx";
import TimelineRangeSlider from "../components/TimelineRangeSlider.jsx";
import FreezeSnapshotButton from "../components/FreezeSnapshotButton.jsx";

export default function OwncloudApp() {
  const [health, setHealth] = useState(null);

  const [roots, setRoots] = useState([]);
  const [rootsError, setRootsError] = useState(null);
  const [rootsLoaded, setRootsLoaded] = useState(false);
  const [rootQuery, setRootQuery] = useState("");

  const [selectedRoot, setSelectedRoot] = useState(null); // {id (storage), rootFileId, ...}
  // Tri par défaut : nombre d'éléments décroissant (demandé
  // explicitement -- plus pratique pour repérer les gros comptes en
  // un coup d'œil que l'ordre d'arrivée de l'API, qui n'a aucune
  // signification particulière).
  const [rootSortMode, setRootSortMode] = useState("count-desc"); // "count-desc" | "alpha"
  // État plat du dépliage progressif — remis à zéro à chaque nouvelle racine choisie.
  const [nodesById, setNodesById] = useState({});
  const [treeError, setTreeError] = useState(null);
  const [treeLoading, setTreeLoading] = useState(false);

  const [selectedNode, setSelectedNode] = useState(null);
  // Filtre à termes combinables (voir owncloudLib.js,
  // buildCombinedGlobPredicate) -- un seul terme par défaut, "+
  // Critère" en ajoute d'autres. Motif avec '*' = joker (glob simple),
  // sans '*' = sous-chaîne classique (rétrocompatible).
  const [filterTerms, setFilterTerms] = useState([{ pattern: "", mode: "include" }]);
  const [filterCombineMode, setFilterCombineMode] = useState("and");
  // null = aucune fenêtre active (tout est visible) ; {start,end} sinon.
  const [timelineRange, setTimelineRange] = useState(null);
  // Dictionnaire d'occurrences des noms de DOSSIERS -- volontairement
  // JAMAIS remis à zéro en changeant de racine (contrairement à
  // nodesById juste au-dessus) : le but est justement de repérer ce
  // qui REVIENT d'un compte à l'autre au fil de l'exploration,
  // impossible à voir en ne regardant qu'une seule racine à la fois.
  const [nameOccurrences, setNameOccurrences] = useState({});
  // Ensemble des noms EXPLICITEMENT choisis à masquer -- rien de
  // masqué par défaut (même philosophie que l'ancien hideRecurring :
  // rien ne change tant que la personne ne l'active pas).
  const [hiddenNames, setHiddenNames] = useState(() => new Set());
  const [recurringPanelExpanded, setRecurringPanelExpanded] = useState(false);
  const [viewMode, setViewMode] = useState("tree"); // "tree" | "versions"
  // Mise en page de l'arbre -- indépendante de viewMode (qui bascule
  // arbre/timeline versions) : "radial" (par défaut, existant) ou
  // "classic" (liste indentée verticale), demandé pour une lecture
  // plus directe des grandes arborescences.
  const [treeLayout, setTreeLayout] = useState("radial"); // "radial" | "classic"

  useEffect(() => {
    fetchOwncloudHealth().then(setHealth);
    fetchOwncloudRoots().then(({ roots, error }) => {
      setRoots(roots);
      setRootsError(error);
      setRootsLoaded(true);
    });
  }, []);

  const loadNode = async (storage, fileid) => {
    const { node, children, error } = await fetchOwncloudChildren(storage, fileid);
    if (error) {
      setTreeError(error);
      return null;
    }
    setTreeError(null);
    setNodesById((prev) => mergeChildren(prev, node, children));
    // Accumule le dictionnaire d'occurrences (jamais remis à zéro,
    // voir la déclaration du state) -- à CHAQUE chargement reçu,
    // qu'il s'agisse du premier niveau d'une racine ou d'un dossier
    // déplié plus profond.
    setNameOccurrences((prev) => mergeOccurrenceCounts(prev, countDirectoryNamesIn(children)));
    return node;
  };

  const chooseRoot = async (root) => {
    if (root.rootFileId === null || root.rootFileId === undefined) {
      setTreeError("racine sans fileid connu (storage vide ?)");
      return;
    }
    setSelectedRoot(root);
    setNodesById({});
    setTreeLoading(true);
    setTreeError(null);
    setFilterTerms([{ pattern: "", mode: "include" }]);
    setFilterCombineMode("and");
    setTimelineRange(null);
    const node = await loadNode(root.id, root.rootFileId);
    setTreeLoading(false);
    if (node) setSelectedNode({ id: root.rootFileId, type: "folder", name: node.name, raw: node.raw });
  };

  function toggleHiddenName(name) {
    setHiddenNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  const handleSelectNode = async (nodeData) => {
    setSelectedNode(nodeData);
    if (nodeData.hasUnloadedChildren && selectedRoot) {
      await loadNode(selectedRoot.id, nodeData.id);
    }
  };

  const tree = useMemo(
    () => (selectedRoot ? buildRenderTree(nodesById, selectedRoot.rootFileId) : null),
    [nodesById, selectedRoot]
  );

  // Arbre effectivement affiché/filtré/figé — pruning des nœuds
  // récurrents appliqué AVANT tout le reste (recherche, fenêtre
  // temporelle, "figer cette vue") pour que masquer files_trashbin,
  // par exemple, l'exclue cohéremment de ces trois-là aussi.
  const displayTree = useMemo(
    () => pruneNodesByNames(tree, hiddenNames),
    [tree, hiddenNames]
  );

  // Timeline de versions : indépendante du pruning ci-dessus (repose
  // sur l'état plat nodesById, pas sur l'arbre affiché) — masquer
  // files_versions dans l'arbre n'empêche pas de voir son historique
  // dans cette vue dédiée.
  const versionEntries = useMemo(() => buildVersionTimeline(nodesById), [nodesById]);

  function handleSelectVersion(v) {
    const entry = nodesById[v.id];
    if (entry) setSelectedNode({ id: entry.id, type: entry.type, name: entry.name, raw: entry.raw });
  }

  // Bornes des mtime actuellement CHARGÉS — s'élargissent au fil du
  // dépliage ; la fenêtre ne porte jamais sur des données non encore
  // récupérées (voir owncloud/README.md, section Timeline).
  const mtimeBounds = useMemo(() => mtimeBoundsOfLoadedNodes(displayTree), [displayTree]);
  const effectiveRange = timelineRange || (mtimeBounds && { start: mtimeBounds.min, end: mtimeBounds.max });

  const relevantIds = useMemo(() => {
    const textRelevant = computeRelevantIdsByTerms(displayTree, filterTerms, filterCombineMode);
    const mtimeRelevant = timelineRange
      ? computeMtimeRelevantIds(displayTree, timelineRange.start, timelineRange.end)
      : null;
    return combineRelevantIds(textRelevant, mtimeRelevant);
  }, [displayTree, filterTerms, filterCombineMode, timelineRange]);

  // Photo figée de ce qui a été DÉPLIÉ jusqu'ici (+ filtres actifs) —
  // ne peut pas figer ce qui n'a jamais été chargé, cohérent avec le
  // dépliage à la demande de ce module.
  const frozenPreview = useMemo(() => pruneToRelevant(displayTree, relevantIds), [displayTree, relevantIds]);

  const filteredRoots = useMemo(() => {
    const q = normalizeText(rootQuery).trim();
    const base = q
      ? roots.filter(
          (r) => normalizeText(r.name).includes(q) || normalizeText(r.description || "").includes(q)
        )
      : roots;
    return sortRoots(base, rootSortMode);
  }, [roots, rootQuery, rootSortMode]);

  const breadcrumb = useMemo(
    () => (displayTree && selectedNode ? findPathToNode(displayTree, selectedNode.id) : null),
    [displayTree, selectedNode]
  );

  const geocodeQuery = useMemo(
    () => guessLocationQuery(selectedNode, breadcrumb),
    [selectedNode, breadcrumb]
  );

  const { recurring: recurringOccurrences, unique: uniqueOccurrences } = useMemo(
    () => splitOccurrencesByThreshold(nameOccurrences),
    [nameOccurrences]
  );

  return (
    <div className="owncloud-shell">
      {health && health.status !== "ok" && (
        <div className="owncloud-health-banner">
          ⚠️ Base OwnCloud {health.db === "non configuré" ? "non configurée" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir owncloud/README.md).
        </div>
      )}

      <div className="owncloud-columns">
        <aside className="owncloud-col-left">
          <h2>Racines indépendantes</h2>
          <input
            className="owncloud-search-input"
            placeholder="Filtrer…"
            value={rootQuery}
            onChange={(e) => setRootQuery(e.target.value)}
          />
          <div className="owncloud-root-sort">
            <button
              className={`owncloud-root-sort-btn${rootSortMode === "count-desc" ? " active" : ""}`}
              onClick={() => setRootSortMode("count-desc")}
              title="Trier par nombre d'éléments décroissant"
            >
              ↓ Nb éléments
            </button>
            <button
              className={`owncloud-root-sort-btn${rootSortMode === "alpha" ? " active" : ""}`}
              onClick={() => setRootSortMode("alpha")}
              title="Trier par ordre alphabétique"
            >
              A→Z
            </button>
          </div>
          {!rootsLoaded && <p className="owncloud-empty">Chargement…</p>}
          {rootsError && <p className="owncloud-error">{rootsError}</p>}
          {rootsLoaded && !rootsError && filteredRoots.length === 0 && (
            <p className="owncloud-empty">Aucune racine trouvée.</p>
          )}
          <ul className="owncloud-root-list">
            {filteredRoots.map((r) => (
              <li key={r.id}>
                <button
                  className={`owncloud-root-item${selectedRoot?.id === r.id ? " selected" : ""}`}
                  onClick={() => chooseRoot(r)}
                  title={r.storageId && r.storageId !== r.name ? `Identifiant technique : ${r.storageId}` : undefined}
                >
                  <div className="owncloud-root-name">{r.name}</div>
                  {r.description && <div className="owncloud-root-desc">{r.description}</div>}
                  <div className="owncloud-root-counts">
                    {r.itemCount} élément{r.itemCount > 1 ? "s" : ""} · {fmtBytes(r.totalSize)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="owncloud-col-center">
          {selectedRoot && (
            <div className="owncloud-center-toolbar">
              <div className="owncloud-mode-tabs">
                <button
                  className={`owncloud-mode-tab${viewMode === "tree" ? " active" : ""}`}
                  onClick={() => setViewMode("tree")}
                >
                  🌐 Arbre
                </button>
                <button
                  className={`owncloud-mode-tab${viewMode === "versions" ? " active" : ""}`}
                  onClick={() => setViewMode("versions")}
                >
                  🕒 Timeline versions {versionEntries.length > 0 && `(${versionEntries.length})`}
                </button>
                {viewMode === "tree" && (
                  <div className="owncloud-layout-toggle">
                    <button
                      className={`owncloud-layout-btn${treeLayout === "radial" ? " active" : ""}`}
                      onClick={() => setTreeLayout("radial")}
                      title="Vue radiale"
                    >
                      ◎ Radial
                    </button>
                    <button
                      className={`owncloud-layout-btn${treeLayout === "classic" ? " active" : ""}`}
                      onClick={() => setTreeLayout("classic")}
                      title="Vue arbre classique (liste indentée)"
                    >
                      ☰ Classique
                    </button>
                  </div>
                )}
              </div>
              <OwncloudFilterTerms
                terms={filterTerms}
                combineMode={filterCombineMode}
                onChange={setFilterTerms}
                onCombineModeChange={setFilterCombineMode}
              />
              <OwncloudRecurringPanel
                knownStructuralNames={KNOWN_OWNCLOUD_STRUCTURAL_NAMES}
                recurring={recurringOccurrences}
                unique={uniqueOccurrences}
                hiddenNames={hiddenNames}
                onToggle={toggleHiddenName}
                expanded={recurringPanelExpanded}
                onToggleExpanded={() => setRecurringPanelExpanded((v) => !v)}
              />
              {breadcrumb && (
                <div className="owncloud-breadcrumb">
                  {breadcrumb.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && <span className="owncloud-breadcrumb-sep">›</span>}
                      <span className="owncloud-breadcrumb-item" onClick={() => setSelectedNode(n)}>
                        {n.name || "(racine)"}
                      </span>
                    </span>
                  ))}
                </div>
              )}
              {mtimeBounds && viewMode === "tree" && (
                <div className="owncloud-timeline-row">
                  <TimelineRangeSlider
                    min={mtimeBounds.min}
                    max={mtimeBounds.max}
                    start={effectiveRange.start}
                    end={effectiveRange.end}
                    onChange={(start, end) => setTimelineRange({ start, end })}
                    formatValue={fmtTimelineDate}
                  />
                  {timelineRange && (
                    <button className="owncloud-timeline-reset" onClick={() => setTimelineRange(null)}>
                      ↺ Toute la période
                    </button>
                  )}
                </div>
              )}
              <FreezeSnapshotButton prefix="owncloud" rootName={selectedRoot?.name} frozenData={frozenPreview} />
              <p className="owncloud-hint">
                {viewMode === "tree"
                  ? "Un point sur un nœud = dossier non déplié — cliquer pour charger son contenu."
                  : "Un point par version détectée parmi les nœuds déjà chargés — dépliez files_versions pour en voir plus."}
                {viewMode === "tree" && mtimeBounds && " La fenêtre ne porte que sur les nœuds déjà chargés."}
              </p>
            </div>
          )}

          {!selectedRoot && <p className="owncloud-empty">Choisissez une racine indépendante à gauche.</p>}
          {treeLoading && <p className="owncloud-empty">Chargement…</p>}
          {treeError && <p className="owncloud-error">{treeError}</p>}
          {!treeLoading && viewMode === "tree" && displayTree && treeLayout === "radial" && (
            <OwncloudRadialTree
              tree={displayTree}
              selectedId={selectedNode?.id}
              onSelectNode={handleSelectNode}
              relevantIds={relevantIds}
            />
          )}
          {!treeLoading && viewMode === "tree" && displayTree && treeLayout === "classic" && (
            <OwncloudClassicTree
              tree={displayTree}
              selectedId={selectedNode?.id}
              onSelectNode={handleSelectNode}
              relevantIds={relevantIds}
            />
          )}
          {!treeLoading && viewMode === "versions" && (
            <OwncloudVersionTimeline
              entries={versionEntries}
              onSelectVersion={handleSelectVersion}
              selectedId={selectedNode?.id}
            />
          )}
        </section>

        <aside className="owncloud-col-right">
          <h2>Fiche JSON</h2>
          <OwncloudJsonPanel node={selectedNode} />
          {selectedNode && <OwncloudGeocodePanel key={selectedNode.id} query={geocodeQuery} />}
        </aside>
      </div>
    </div>
  );
}
