import React, { useEffect, useMemo, useRef, useState } from "react";
import { fetchBaseHealth, fetchBaseRoots, fetchBaseTree } from "./externalBasesClient.js";
import {
  availableSources, countNodes, findPath, relevantIds, pruneToIds, pruneToActive, limitDepth, nodeSummary, shortLabel,
  usagePercent, usageTone, sortRoots, rootCounts,
} from "./externalBases.js";
import { radialLayout } from "./supervisedHistory.js";
import ZoomableChart from "./components/ZoomableChart.jsx";

// Tuile « Bases externes » (livraison #425, backlog 64 point 4) -- les
// onglets IPAM / Zenoss / Optick / TTS-GU / Cacti de l'ancienne maquette,
// promus dans le hub en UNE vue générique (même contrat d'API) : racines
// indépendantes à gauche, arbre radial au centre, fiche JSON à droite.
// Filtre texte (ancêtres + descendants du match), « actifs seulement »
// (IPAM), profondeur bornée avec dépliage. Logique pure : externalBases.js.

const TYPE_HUES = ["#4f7cd8", "#2f9e5b", "#d69a2b", "#8e5bd8", "#d64545", "#2aa7a0", "#b56a2a"];

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

export default function ExternalBasesView({ onBack, bases, legacyFrontendUrl }) {
  const sources = useMemo(() => availableSources(bases), [bases]);
  const [sourceId, setSourceId] = useState(() => { try { return localStorage.getItem("hub.bases.source") || ""; } catch { return ""; } });
  const source = sources.find((s) => s.id === sourceId) || sources[0] || null;
  const base = source ? bases[source.id] : null;

  const [health, setHealth] = useState(null);
  const [roots, setRoots] = useState([]);
  const [rootsError, setRootsError] = useState(null);
  const [rootQuery, setRootQuery] = useState("");
  const [rootId, setRootId] = useState(null);
  const [tree, setTree] = useState(null);
  const [treeError, setTreeError] = useState(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);
  const [maxDepth, setMaxDepth] = useState(3);
  const [expanded, setExpanded] = useState(new Set());
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => { try { if (source) localStorage.setItem("hub.bases.source", source.id); } catch { /* ignoré */ } }, [source]);

  // Base dont les racines chargées sont valables : évite, au changement
  // d'onglet, de demander à la nouvelle base l'arbre d'une racine de l'ancienne
  // (les deux effets voient le même rendu ; celui-ci passe en premier).
  const rootsBaseRef = useRef(null);
  useEffect(() => {
    if (!base) return;
    rootsBaseRef.current = null;
    setRoots([]); setRootId(null); setTree(null); setSelectedId(null); setRootsError(null); setHealth(null);
    let cancelled = false;
    fetchBaseHealth(base).then((h) => { if (!cancelled) setHealth(h); });
    fetchBaseRoots(base).then(({ roots: r, error }) => {
      if (cancelled) return;
      rootsBaseRef.current = base;
      setRoots(r); setRootsError(error);
      // première racine (ordre alphabétique) ouverte d'office : la tuile ne s'ouvre jamais vide
      const first = sortRoots(r, "")[0];
      if (first) setRootId(first.id);
    });
    return () => { cancelled = true; };
  }, [base]);

  useEffect(() => {
    if (!base || rootId === null || rootsBaseRef.current !== base) return;
    setTreeLoading(true); setTreeError(null);
    fetchBaseTree(base, rootId).then(({ tree: t, error }) => {
      setTree(t); setTreeError(error); setSelectedId(t?.id ?? null); setQuery(""); setExpanded(new Set()); setTreeLoading(false);
    });
  }, [base, rootId]);

  // --- Dérivés (logique pure) ---
  const shown = useMemo(() => {
    if (!tree) return null;
    let t = activeOnly && source?.activeFilter ? pruneToActive(tree) : tree;
    t = pruneToIds(t, relevantIds(t, query));
    return limitDepth(t, maxDepth, expanded);
  }, [tree, activeOnly, source, query, maxDepth, expanded]);
  const stats = useMemo(() => (tree ? countNodes(tree) : null), [tree]);
  const shownStats = useMemo(() => (shown ? countNodes(shown) : null), [shown]);
  const types = useMemo(() => Object.keys(stats?.byType || {}), [stats]);
  const colorOf = (type) => (type === "more" ? "var(--muted)" : TYPE_HUES[Math.max(0, types.indexOf(type)) % TYPE_HUES.length]);
  const layout = useMemo(() => {
    if (!shown) return null;
    const conv = (n) => ({ name: n.name, kind: n.type, identity: n.id, state: null, node: n, children: (n.children || []).map(conv) });
    return radialLayout(conv(shown), { radius: 210 });
  }, [shown]);
  const selectedNode = useMemo(() => (tree && selectedId != null ? findPath(tree, selectedId).slice(-1)[0] || null : null), [tree, selectedId]);
  const path = useMemo(() => (tree && selectedId != null ? findPath(tree, selectedId) : []), [tree, selectedId]);
  const summary = useMemo(() => nodeSummary(selectedNode), [selectedNode]);
  const filteredRoots = useMemo(() => sortRoots(roots, rootQuery), [roots, rootQuery]);

  const onNodeClick = (n) => {
    if (n.kind === "more") { setExpanded((e) => new Set([...e, n.node.raw.parentId])); return; }
    setSelectedId(n.identity);
  };

  const S = 700;
  return (
    <div className="hub-settings hub-settings-wide ss-root">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🗄 Bases externes</h1>
        <div className="ss-tabs">
          {sources.map((s) => <button key={s.id} className={`secondary na-section-toggle${source?.id === s.id ? " active" : ""}`} onClick={() => setSourceId(s.id)} title={s.description}>{s.label}</button>)}
        </div>
        <span style={{ flex: 1 }} />
        {health && <span className={`np-tone ${health.status === "ok" ? "good" : "warn"}`} style={{ fontSize: 12 }}>{source?.label} : {health.status === "ok" ? "base joignable" : `dégradé (${health.db || health.error || "?"})`}</span>}
        {legacyFrontendUrl && <a className="secondary ss-legacy" href={legacyFrontendUrl} target="_blank" rel="noreferrer" title="ancienne maquette (OwnCloud est dans la tuile GED, la fusion IP/MAC a sa tuile depuis #431)">ancienne maquette ↗</a>}
      </div>
      {sources.length === 0 && <p className="muted">Aucune base externe configurée (VITE_IPAM_API_BASE_URL, VITE_ZENOSS_API_BASE_URL, VITE_OPTICK_API_BASE_URL, VITE_TTSGU_API_BASE_URL, VITE_CACTI_API_BASE_URL).</p>}

      {source && (
        <div className="ss-body eb-body">
          <aside className="ss-left">
            <p className="muted" style={{ margin: "0 0 4px", fontSize: 12 }}>{source.description} · lecture seule</p>
            <input className="ss-search" placeholder="filtrer les racines" value={rootQuery} onChange={(e) => setRootQuery(e.target.value)} />
            {rootsError && <p className="hub-error" style={{ fontSize: 12 }}>{rootsError}</p>}
            <ul className="ss-list">
              {filteredRoots.map((r) => (
                <li key={r.id} className={rootId === r.id ? "active" : ""} onClick={() => setRootId(r.id)}>
                  <span className="ss-name"><strong>{r.name}</strong>{r.description && <span className="muted"> — {r.description}</span>}<br /><span className="muted">{rootCounts(r).join(" · ") || "—"}</span></span>
                </li>
              ))}
              {filteredRoots.length === 0 && !rootsError && <li className="muted">{roots.length ? "Aucune racine pour ce filtre." : "Chargement des racines…"}</li>}
            </ul>
          </aside>

          <main className="eb-center">
            <div className="ss-frame">
              <div className="ss-frame-head">
                <input className="ss-search" style={{ flex: 1 }} placeholder="filtrer l'arbre (nom, description, adresse…)" value={query} onChange={(e) => setQuery(e.target.value)} disabled={!tree} />
                {source.activeFilter && <label className="ups-form-check" style={{ fontSize: 12 }}><input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} /> actifs seulement</label>}
                <label style={{ fontSize: 12 }}>profondeur <select value={maxDepth} onChange={(e) => { setMaxDepth(Number(e.target.value)); setExpanded(new Set()); }}>{[1, 2, 3, 4, 6, 99].map((d) => <option key={d} value={d}>{d === 99 ? "tout" : d}</option>)}</select></label>
                {shownStats && stats && <span className="muted" style={{ fontSize: 12 }}>{shownStats.total}/{stats.total} nœud(s)</span>}
              </div>
              <div className="ss-frame-body ss-tool">
                {!tree && !treeLoading && <p className="muted">{treeError || "Choisir une racine à gauche."}</p>}
                {treeLoading && <p className="muted">Chargement de l'arbre…</p>}
                {layout && (
                  <ZoomableChart viewBox={`0 0 ${S} ${S}`} className="ss-radial-svg" label={`arbre ${source.label}`}>
                    <g transform={`translate(${S / 2}, ${S / 2})`}>
                      {layout.links.map((l, k) => <line key={k} x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="currentColor" opacity="0.25" />)}
                      {layout.nodes.map((n, k) => {
                        const pct = n.kind === "subnet" ? usagePercent(n.node) : null;
                        const isSel = selectedId === n.identity;
                        return (
                          <g key={k} transform={`translate(${n.x}, ${n.y})`} onClick={() => onNodeClick(n)} style={{ cursor: "pointer" }}>
                            <circle r={isSel ? 7 : n.depth === 0 ? 8 : 5} fill={colorOf(n.kind)} stroke={isSel ? "currentColor" : "none"} strokeWidth="2" opacity={n.kind === "more" ? 0.6 : 0.9} />
                            {pct != null && <circle r={9} fill="none" stroke={usageTone(pct) === "bad" ? "#d64545" : usageTone(pct) === "warn" ? "#d69a2b" : "#2f9e5b"} strokeWidth="1.5" strokeDasharray={`${(pct / 100) * 56.5} 56.5`} transform="rotate(-90)" />}
                            <text x={n.depth === 0 ? 0 : n.angle > Math.PI ? -9 : 9} y={n.depth === 0 ? -12 : 4} fontSize={n.depth === 0 ? 12 : 10} fill="currentColor"
                              textAnchor={n.depth === 0 ? "middle" : n.angle > Math.PI ? "end" : "start"}
                              transform={n.depth === 0 ? undefined : `rotate(${(n.angle * 180) / Math.PI - 90 + (n.angle > Math.PI ? 180 : 0)})`}>
                              {shortLabel(n.name, n.depth === 0 ? 40 : 22)}
                            </text>
                            <title>{`${n.name} (${n.kind})${pct != null ? ` — ${pct} % occupé` : ""}${n.leafCount > 1 ? ` · ${n.leafCount} feuilles` : ""}`}</title>
                          </g>
                        );
                      })}
                    </g>
                  </ZoomableChart>
                )}
                {types.length > 0 && (
                  <div className="ss-map-legend" style={{ position: "static", marginTop: 6 }}>
                    {types.map((t) => <span key={t}><i style={{ background: colorOf(t) }} /> {t} ({stats.byType[t]})</span>)}
                    {source.activeFilter && <span><i style={{ background: "transparent", border: "1.5px solid #2f9e5b" }} /> anneau = occupation</span>}
                    <span><i style={{ background: "var(--muted)" }} /> … +N = replié (clic pour déplier)</span>
                  </div>
                )}
              </div>
            </div>
          </main>

          <aside className="ss-left eb-right">
            <h3 style={{ margin: "0 0 4px", fontSize: 13 }}>Fiche</h3>
            {!summary ? <p className="muted" style={{ fontSize: 12 }}>Cliquer un nœud de l'arbre.</p> : (
              <>
                <p style={{ margin: 0, fontSize: 12 }} className="muted">{path.map((n) => n.name).join(" › ")}</p>
                <p style={{ margin: "4px 0" }}><strong>{summary.name}</strong> <span className="muted">({summary.type})</span></p>
                <p className="muted" style={{ margin: "0 0 6px", fontSize: 12 }}>{summary.descendants} descendant(s), profondeur {summary.depth}{Object.keys(summary.byType).length > 1 ? " · " + Object.entries(summary.byType).map(([t, c]) => `${c} ${t}`).join(", ") : ""}{usagePercent(selectedNode) != null ? ` · occupation ${usagePercent(selectedNode)} %` : ""}</p>
                {selectedNode.children?.length > 0 && (
                  <>
                    <h3 style={{ margin: "6px 0 2px", fontSize: 12 }}>Enfants ({selectedNode.children.length})</h3>
                    <ul className="ss-list" style={{ maxHeight: 160, flex: "0 0 auto" }}>
                      {selectedNode.children.slice(0, 200).map((c) => <li key={c.id} onClick={() => setSelectedId(c.id)}><span className="ss-dot" style={{ background: colorOf(c.type) }} /><span className="ss-name">{c.name}<span className="muted"> · {c.type}{c.children?.length ? ` · ${c.children.length} enfant(s)` : ""}</span></span></li>)}
                    </ul>
                  </>
                )}
                <h3 style={{ margin: "6px 0 2px", fontSize: 12 }}>JSON</h3>
                <pre className="eb-json">{JSON.stringify(summary.raw, null, 2)}</pre>
                {selectedNode.raw?.editDate && <p className="muted" style={{ fontSize: 11 }}>modifié : {when(selectedNode.raw.editDate)}</p>}
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
