import { useEffect, useMemo, useState } from "react";
import { fetchOptickHealth, fetchOptickRoots, fetchOptickTree } from "./optickApi.js";
import { normalizeText, findPathToNode, fmtTimelineDate, computeRelevantIds } from "./optickLib.js";
import { pruneToRelevant } from "../lib/treeFreeze.js";
import OptickRadialTree from "../components/OptickRadialTree.jsx";
import OptickJsonPanel from "../components/OptickJsonPanel.jsx";
import TimelineRangeSlider from "../components/TimelineRangeSlider.jsx";
import FreezeSnapshotButton from "../components/FreezeSnapshotButton.jsx";
import useDebouncedValue from "../hooks/useDebouncedValue.js";

export default function OptickApp() {
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
  const [dateBounds, setDateBounds] = useState(null); // renvoyé par le serveur, pas calculé côté client
  const debouncedRange = useDebouncedValue(timelineRange, 300);

  useEffect(() => {
    fetchOptickHealth().then(setHealth);
    fetchOptickRoots().then(({ roots, error }) => {
      setRoots(roots);
      setRootsError(error);
      setRootsLoaded(true);
    });
  }, []);

  // Changement de racine : fenêtre remise à zéro, arbre rechargé
  // intégralement (pas de fenêtre — comportement historique, mis en
  // cache côté serveur).
  useEffect(() => {
    if (selectedRootId === null) return;
    setTreeLoading(true);
    setTreeError(null);
    setTimelineRange(null);
    fetchOptickTree(selectedRootId).then(({ tree, dateBounds, error }) => {
      setTree(tree);
      setDateBounds(dateBounds);
      setTreeError(error);
      setSelectedNode(tree || null);
      setFilterQuery("");
      setTreeLoading(false);
    });
  }, [selectedRootId]);

  // Fenêtre temporelle modifiée (débattue) : recalcule les comptages
  // côté serveur — PAS un simple filtrage visuel, voir optick/README.md.
  // Conserve la sélection et la recherche texte en cours ; ne fait rien
  // tant qu'aucune racine n'est choisie.
  useEffect(() => {
    if (selectedRootId === null) return;
    fetchOptickTree(selectedRootId, debouncedRange).then(({ tree: newTree, dateBounds: newBounds, error }) => {
      if (error) {
        setTreeError(error);
        return;
      }
      setTree(newTree);
      setDateBounds(newBounds);
      setTreeError(null);
      // Resynchronise la fiche JSON sur le nœud correspondant dans le
      // nouvel arbre (mêmes id, comptages à jour) plutôt que de garder
      // une référence figée aux anciens chiffres.
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
    return roots.filter(
      (r) => normalizeText(r.name).includes(q) || normalizeText(r.description || "").includes(q)
    );
  }, [roots, rootQuery]);

  const breadcrumb = useMemo(
    () => (tree && selectedNode ? findPathToNode(tree, selectedNode.id) : null),
    [tree, selectedNode]
  );

  const effectiveRange = timelineRange || (dateBounds && { start: dateBounds.min, end: dateBounds.max });

  // Recherche texte uniquement ici : la fenêtre temporelle est déjà
  // appliquée côté serveur (tree la reflète déjà) — pas de deuxième
  // dimension à combiner comme pour IPAM/OwnCloud.
  const relevantIds = useMemo(() => computeRelevantIds(tree, filterQuery), [tree, filterQuery]);
  const frozenPreview = useMemo(() => pruneToRelevant(tree, relevantIds), [tree, relevantIds]);

  return (
    <div className="optick-shell">
      {health && health.status !== "ok" && (
        <div className="optick-health-banner">
          ⚠️ Base Optick {health.db === "non configuré" ? "non configurée" : "injoignable"}
          {health.error ? ` — ${health.error}` : ""} (voir optick/README.md).
        </div>
      )}

      <div className="optick-columns">
        <aside className="optick-col-left">
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
          <ul className="optick-root-list">
            {filteredRoots.map((r) => (
              <li key={r.id}>
                <button
                  className={`optick-root-item${r.id === selectedRootId ? " selected" : ""}`}
                  onClick={() => setSelectedRootId(r.id)}
                >
                  <div className="optick-root-name">{r.name}</div>
                  {r.description && <div className="optick-root-desc">{r.description}</div>}
                  <div className="optick-root-counts">
                    {r.childSectionCount} catégorie{r.childSectionCount > 1 ? "s" : ""} · {r.subnetCount} ticket{r.subnetCount > 1 ? "s" : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="optick-col-center">
          {selectedRootId !== null && (
            <div className="optick-center-toolbar">
              <input
                className="optick-search-input"
                placeholder="🔍 Filtrer l'arbre (nom, domaine…)"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
              />
              {breadcrumb && (
                <div className="optick-breadcrumb">
                  {breadcrumb.map((n, i) => (
                    <span key={n.id}>
                      {i > 0 && <span className="optick-breadcrumb-sep">›</span>}
                      <span className="optick-breadcrumb-item" onClick={() => setSelectedNode(n)}>
                        {n.name}
                      </span>
                    </span>
                  ))}
                </div>
              )}
              {dateBounds && (
                <div className="optick-timeline-row">
                  <TimelineRangeSlider
                    min={dateBounds.min}
                    max={dateBounds.max}
                    start={effectiveRange.start}
                    end={effectiveRange.end}
                    onChange={(start, end) => setTimelineRange({ start, end })}
                    formatValue={fmtTimelineDate}
                  />
                  {timelineRange && (
                    <button className="optick-timeline-reset" onClick={() => setTimelineRange(null)}>
                      ↺ Toute la période
                    </button>
                  )}
                </div>
              )}
              <FreezeSnapshotButton prefix="optick" rootName={tree?.name} frozenData={frozenPreview} />
            </div>
          )}

          {selectedRootId === null && (
            <p className="optick-empty">Choisissez une racine indépendante à gauche.</p>
          )}
          {treeLoading && <p className="optick-empty">Chargement de l'arbre…</p>}
          {treeError && <p className="optick-error">{treeError}</p>}
          {!treeLoading && !treeError && tree && (
            <OptickRadialTree
              tree={tree}
              selectedId={selectedNode?.id}
              onSelectNode={setSelectedNode}
              relevantIds={relevantIds}
            />
          )}
        </section>

        <aside className="optick-col-right">
          <h2>Fiche JSON</h2>
          <OptickJsonPanel node={selectedNode} />
        </aside>
      </div>
    </div>
  );
}
