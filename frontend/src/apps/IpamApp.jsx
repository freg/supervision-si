import { useEffect, useMemo, useState } from "react";
import { fetchIpamHealth, fetchIpamRoots, fetchIpamTree } from "./ipamApi.js";
import {
  normalizeText, findPathToNode, computeRelevantIds, computeEditDateRelevantIds,
  editDateBoundsOfLoadedNodes, combineRelevantIds, fmtTimelineDate, pruneToActive,
} from "./ipamLib.js";
import { pruneToRelevant } from "../lib/treeFreeze.js";
import IpamRadialTree from "../components/IpamRadialTree.jsx";
import IpamJsonPanel from "../components/IpamJsonPanel.jsx";
import TimelineRangeSlider from "../components/TimelineRangeSlider.jsx";
import FreezeSnapshotButton from "../components/FreezeSnapshotButton.jsx";

export default function IpamApp() {
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
  const [timelineRange, setTimelineRange] = useState(null); // null = pas de filtre actif
  const [activeOnly, setActiveOnly] = useState(false); // arbre "non rémanent" : actifs seulement
  const [reducedView, setReducedView] = useState(false); // arbre réduit à la sélection temporelle/texte

  useEffect(() => {
    fetchIpamHealth().then(setHealth);
    fetchIpamRoots().then(({ roots, error }) => {
      setRoots(roots);
      setRootsError(error);
      setRootsLoaded(true);
    });
  }, []);

  useEffect(() => {
    if (selectedRootId === null) return;
    setTreeLoading(true);
    setTreeError(null);
    fetchIpamTree(selectedRootId).then(({ tree, error }) => {
      setTree(tree);
      setTreeError(error);
      setSelectedNode(tree || null); // par défaut, la fiche JSON montre la racine elle-même
      setFilterQuery("");
      setTimelineRange(null);
      setReducedView(false);
      setTreeLoading(false);
    });
  }, [selectedRootId]);

  // La réduction n'a de sens que tant qu'une fenêtre temporelle est
  // active — si elle est effacée (bouton "Toute la période" ou racine
  // changée), revenir automatiquement à l'arbre complet plutôt que de
  // laisser un état "réduit" orphelin, sans plus rien pour le justifier.
  useEffect(() => {
    if (!timelineRange) setReducedView(false);
  }, [timelineRange]);

  const displayTree = useMemo(() => (activeOnly && tree ? pruneToActive(tree) : tree), [tree, activeOnly]);

  const editDateBounds = useMemo(() => editDateBoundsOfLoadedNodes(displayTree), [displayTree]);
  const effectiveRange = timelineRange || (editDateBounds && { start: editDateBounds.min, end: editDateBounds.max });

  const relevantIds = useMemo(() => {
    const textRelevant = computeRelevantIds(displayTree, filterQuery);
    const timeRelevant = timelineRange
      ? computeEditDateRelevantIds(displayTree, timelineRange.start, timelineRange.end)
      : null;
    return combineRelevantIds(textRelevant, timeRelevant);
  }, [displayTree, filterQuery, timelineRange]);

  // Photo figée de la vue actuellement affichée (actifs seulement +
  // recherche + fenêtre temporelle confondus) — indépendante de
  // l'affichage à partir de l'instant où elle est prise, contrairement
  // aux filtres qui restent vivants tant qu'on reste sur cet onglet.
  const frozenPreview = useMemo(() => pruneToRelevant(displayTree, relevantIds), [displayTree, relevantIds]);

  const filteredRoots = useMemo(() => {
    const q = normalizeText(rootQuery).trim();
    if (!q) return roots;
    return roots.filter(
      (r) => normalizeText(r.name).includes(q) || normalizeText(r.description || "").includes(q)
    );
  }, [roots, rootQuery]);

  const breadcrumb = useMemo(
    () => (displayTree && selectedNode ? findPathToNode(displayTree, selectedNode.id) : null),
    [displayTree, selectedNode]
  );

  return (
    <div className="ipam-shell">
      {health && health.status !== "ok" && (
        <div className="ipam-health-banner">
          ⚠️ Base IPAM {health.db === "non configuré" ? "non configurée" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir ipam/README.md).
        </div>
      )}

      <div className="ipam-columns">
        <aside className="ipam-col-left">
          <h2>Racines indépendantes</h2>
          <input
            className="ipam-search-input"
            placeholder="Filtrer…"
            value={rootQuery}
            onChange={(e) => setRootQuery(e.target.value)}
          />
          {!rootsLoaded && <p className="ipam-empty">Chargement…</p>}
          {rootsError && <p className="ipam-error">{rootsError}</p>}
          {rootsLoaded && !rootsError && filteredRoots.length === 0 && (
            <p className="ipam-empty">Aucune racine trouvée.</p>
          )}
          <ul className="ipam-root-list">
            {filteredRoots.map((r) => (
              <li key={r.id}>
                <button
                  className={`ipam-root-item${r.id === selectedRootId ? " selected" : ""}`}
                  onClick={() => setSelectedRootId(r.id)}
                >
                  <div className="ipam-root-name">{r.name}</div>
                  {r.description && <div className="ipam-root-desc">{r.description}</div>}
                  <div className="ipam-root-counts">
                    {r.childSectionCount} section{r.childSectionCount > 1 ? "s" : ""} · {r.subnetCount} subnet{r.subnetCount > 1 ? "s" : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="ipam-col-center">
          {selectedRootId !== null && (
            <div className="ipam-center-toolbar">
              <label className="ipam-active-toggle">
                <input
                  type="checkbox"
                  checked={activeOnly}
                  onChange={(e) => setActiveOnly(e.target.checked)}
                />
                Actifs seulement (non rémanent)
              </label>
              <FreezeSnapshotButton prefix="ipam" rootName={tree?.name} frozenData={frozenPreview} />
              <input
                className="ipam-search-input"
                placeholder="🔍 Filtrer l'arbre (nom, description, VLAN…)"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
              />
              {breadcrumb && (
                <div className="ipam-breadcrumb">
                  {breadcrumb.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && <span className="ipam-breadcrumb-sep">›</span>}
                      <span
                        className="ipam-breadcrumb-item"
                        onClick={() => setSelectedNode(n)}
                      >
                        {n.name}
                      </span>
                    </span>
                  ))}
                </div>
              )}
              {editDateBounds && (
                <div className="ipam-timeline-row">
                  <TimelineRangeSlider
                    min={editDateBounds.min}
                    max={editDateBounds.max}
                    start={effectiveRange.start}
                    end={effectiveRange.end}
                    onChange={(start, end) => setTimelineRange({ start, end })}
                    formatValue={fmtTimelineDate}
                  />
                  {timelineRange && (
                    <>
                      <button className="ipam-timeline-reset" onClick={() => setTimelineRange(null)}>
                        ↺ Toute la période
                      </button>
                      <button
                        className={`ipam-timeline-reduce${reducedView ? " active" : ""}`}
                        onClick={() => setReducedView((v) => !v)}
                        title="Affiche uniquement le sous-arbre correspondant à la fenêtre temporelle (et à la recherche texte, si active), au lieu d'estomper le reste."
                      >
                        {reducedView ? "↩ Tout l'arbre" : "⤵ Réduire à la sélection"}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {selectedRootId === null && (
            <p className="ipam-empty">Choisissez une racine indépendante à gauche.</p>
          )}
          {treeLoading && <p className="ipam-empty">Chargement de l'arbre…</p>}
          {treeError && <p className="ipam-error">{treeError}</p>}
          {!treeLoading && !treeError && tree && reducedView && !frozenPreview && (
            <p className="ipam-empty">Aucun nœud ne correspond à la sélection temporelle actuelle.</p>
          )}
          {!treeLoading && !treeError && tree && (!reducedView || frozenPreview) && (
            <IpamRadialTree
              tree={reducedView ? frozenPreview : displayTree}
              selectedId={selectedNode?.id}
              onSelectNode={setSelectedNode}
              relevantIds={relevantIds}
            />
          )}
        </section>

        <aside className="ipam-col-right">
          <h2>Fiche JSON</h2>
          <IpamJsonPanel node={selectedNode} />
        </aside>
      </div>
    </div>
  );
}
